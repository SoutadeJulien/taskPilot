"""Onglet Process (Qt) : arbre des process des tasks, surveillance et kill.

Affiche, groupe par task, l'integralite de l'arbre de process lance par chaque
console. Collecte deportee dans un thread (les listings ``wmic`` / ``ps`` sont
lourds) ; le resultat revient sur le thread UI via un signal Qt.
"""

import threading
import time
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QLabel, QMessageBox, QPushButton, QStyle,
    QStyledItemDelegate, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from taskpilot.core.processes import (
    find_processes, format_memory, kill_process)
from taskpilot.core.system import NCPU
from taskpilot.qt import theme

REFRESH_MS = 1500
COLUMNS = ["Task", "Port", "PID", "CPU %", "Mémoire", "Tendance",
           "Ligne de commande"]
#: Index de la colonne sparkline (CPU + memoire) et taille de l'historique.
SPARK_COL = 5
HIST_LEN = 40
#: Libelle du groupe des process Node non rattaches a une task en cours.
ORPHAN_LABEL = "Node (hors tasks)"


class ProcessTab(QWidget):
    """Tableau temps reel des process des tasks, avec tri et kill d'arbre."""

    _collected = Signal(object, object)   # (procs, err) — emis depuis le thread

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._prev_cpu = {}
        self._hist = {}              # pid -> {"cpu": deque, "mem": deque}
        self._sort_col = 3            # CPU %
        self._sort_reverse = True
        self._loading = False
        self._flash = None
        self._activated = False
        self._collapsed = set()       # labels de tasks repliees par l'utilisateur
        self.process_count = None     # dernier total de process (barre de statut)
        self._collected.connect(self._render)
        theme.notifier.changed.connect(self._on_theme)

        self._build()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)

    def _build(self):
        v = QVBoxLayout(self)
        v.setContentsMargins(18, 16, 18, 14)
        v.setSpacing(14)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        refresh = QPushButton("↻  Rafraîchir")
        refresh.clicked.connect(self.refresh)
        bar.addWidget(refresh)
        kill_sel = QPushButton("✕  Tuer la sélection")
        kill_sel.clicked.connect(self.kill_selected)
        bar.addWidget(kill_sel)
        kill_all = QPushButton("⊗  Tuer TOUS")
        kill_all.setProperty("danger", True)
        kill_all.clicked.connect(self.kill_all)
        bar.addWidget(kill_all)
        self._live = QCheckBox("◷  Temps réel")
        self._live.setChecked(True)
        self._live.toggled.connect(self._on_live_toggle)
        bar.addWidget(self._live)
        bar.addStretch(1)
        v.addLayout(bar)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(len(COLUMNS))
        self._tree.setHeaderLabels(COLUMNS)
        self._tree.setSelectionMode(QTreeWidget.ExtendedSelection)
        self._tree.setAlternatingRowColors(self.app.settings.alt_rows)
        self._tree.setColumnWidth(0, 200)
        self._tree.setColumnWidth(SPARK_COL, 110)
        self._tree.setColumnWidth(6, 480)
        for col in range(1, 5):
            self._tree.setColumnWidth(col, 90)
        self._tree.setItemDelegateForColumn(SPARK_COL, SparklineDelegate(self._tree))
        self._tree.headerItem().setToolTip(
            SPARK_COL, "Tendance récente — aire = CPU, ligne = mémoire\n"
                       "(mise à l'échelle sur la fenêtre visible)")
        self._tree.header().setSectionsClickable(True)
        self._tree.header().sectionClicked.connect(self._sort_by)
        self._tree.itemExpanded.connect(self._on_expand)
        self._tree.itemCollapsed.connect(self._on_collapse)
        v.addWidget(self._tree, 1)

        self._status = QLabel("")
        self._style_status()
        v.addWidget(self._status)

    def set_alternating_rows(self, on):
        self._tree.setAlternatingRowColors(bool(on))

    def _style_status(self):
        self._status.setStyleSheet(
            f"background: {theme.SURFACE_2}; border-radius: {theme.radius(9)}px; "
            f"padding: 11px 14px; color: {theme.FG_DIM};")

    def _on_theme(self):
        """Re-style la barre de statut et recolore l'arbre (couleurs de lignes
        posees au rendu) au changement de theme."""
        self._style_status()
        if self._activated and not self._loading:
            self.refresh()

    # -- Activation (lazy) ---------------------------------------------------
    def on_shown(self):
        if self._activated:
            return
        self._activated = True
        self.refresh()
        self._on_live_toggle(self._live.isChecked())

    def _on_live_toggle(self, on):
        if on:
            self._timer.start(REFRESH_MS)
        else:
            self._timer.stop()

    # -- Collecte (thread) ---------------------------------------------------
    def refresh(self):
        if self._loading:
            return
        self._loading = True
        roots = self.app.tasks_tab.running_task_roots()
        threading.Thread(target=self._worker, args=(roots,), daemon=True).start()

    def _worker(self, roots):
        try:
            procs, err = find_processes(roots), None
        except Exception as e:  # noqa: BLE001
            procs, err = None, e
        self._collected.emit(procs, err)

    def _compute_cpu(self, procs):
        now = time.time()
        for p in procs:
            p.cpu = None
            if p.cpu_time is not None:
                prev = self._prev_cpu.get(p.pid)
                if prev:
                    prev_time, prev_ts = prev
                    dt = now - prev_ts
                    if dt > 0:
                        p.cpu = max(0.0,
                                    (p.cpu_time - prev_time) / dt / NCPU * 100.0)
                self._prev_cpu[p.pid] = (p.cpu_time, now)
            hist = self._hist.get(p.pid)
            if hist is None:
                hist = self._hist[p.pid] = {
                    "cpu": deque(maxlen=HIST_LEN), "mem": deque(maxlen=HIST_LEN)}
            hist["cpu"].append(p.cpu if p.cpu is not None else 0.0)
            hist["mem"].append(float(p.mem))
        live = {p.pid for p in procs}
        for pid in list(self._prev_cpu):
            if pid not in live:
                self._prev_cpu.pop(pid, None)
        for pid in list(self._hist):
            if pid not in live:
                self._hist.pop(pid, None)

    def _series_for(self, pid):
        """Couple ``(cpu, mem)`` d'historiques pour la sparkline d'un pid."""
        hist = self._hist.get(pid)
        if not hist or not hist["cpu"]:
            return None
        return (tuple(hist["cpu"]), tuple(hist["mem"]))

    # -- Rendu ---------------------------------------------------------------
    def _render(self, procs, err):
        self._loading = False
        if err is not None:
            if self._live.isChecked():
                self._status.setText(f"⚠ Erreur : {err}")
            else:
                QMessageBox.critical(
                    self, "Erreur", f"Impossible de lister les process :\n{err}")
            return

        self._compute_cpu(procs)
        by_task, order = {}, []
        for p in procs:
            if p.task not in by_task:
                by_task[p.task] = []
                order.append(p.task)
            by_task[p.task].append(p)

        self._tree.blockSignals(True)
        self._tree.clear()
        for label in order:
            display = label if label is not None else ORPHAN_LABEL
            parent = QTreeWidgetItem([display, "", "", "", "", "", ""])
            parent.setData(0, Qt.UserRole, ("task", label))
            pfont = parent.font(0)
            pfont.setBold(True)
            parent.setFont(0, pfont)
            for col in range(len(COLUMNS)):
                parent.setBackground(col, QColor(theme.SURFACE_2))
                parent.setForeground(col, QColor(theme.FG))
            self._tree.addTopLevelItem(parent)
            for p in self._sorted(by_task[label]):
                child = QTreeWidgetItem(self._row_values(p))
                child.setData(0, Qt.UserRole, ("proc", p.pid))
                child.setData(SPARK_COL, Qt.UserRole, self._series_for(p.pid))
                for col in (1, 2, 3, 4):
                    child.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
                parent.addChild(child)
            parent.setExpanded(label not in self._collapsed)
        self._tree.blockSignals(False)
        self._mark_header()
        self._update_status(procs, len(order))
        self.process_count = len(procs)
        refresh = getattr(self.app, "refresh_status_bar", None)
        if refresh is not None:
            refresh()

    def _on_expand(self, item):
        data = item.data(0, Qt.UserRole)
        if data and data[0] == "task":
            self._collapsed.discard(data[1])

    def _on_collapse(self, item):
        data = item.data(0, Qt.UserRole)
        if data and data[0] == "task":
            self._collapsed.add(data[1])

    def _sorted(self, procs):
        col = self._sort_col

        def key(p):
            if col == 1:
                return p.ports[0] if p.ports else -1
            if col == 2:
                return p.pid
            if col == 3:
                return p.cpu or -1
            if col == 4:
                return p.mem or -1
            return str(p.cmd).lower()
        return sorted(procs, key=key, reverse=self._sort_reverse)

    @staticmethod
    def _row_values(p):
        if p.cpu is None:
            cpu = "-"
        elif 0 < p.cpu < 0.01:
            cpu = "<0.01"
        else:
            cpu = f"{p.cpu:.2f}"
        port = ", ".join(str(x) for x in p.ports) if p.ports else "-"
        return ["", port, str(p.pid), cpu, format_memory(p.mem), "", p.cmd]

    def _update_status(self, procs, ntasks):
        if not procs and not self._flash:
            self._status.setText(
                "  Aucun process Node détecté sur la machine.")
            return
        total_mem = sum(p.mem for p in procs)
        total_cpu = sum(p.cpu for p in procs if p.cpu is not None)
        text = (f"  {len(procs)} process   •   {ntasks} groupe(s)"
                f"   •   CPU total ≈ {total_cpu:.1f} %"
                f"   •   Mémoire totale {format_memory(total_mem)}")
        if self._flash:
            text = f"  {self._flash}   —  {text.strip()}"
            self._flash = None
        self._status.setText(text)

    # -- Tri -----------------------------------------------------------------
    def _sort_by(self, col):
        if col in (0, SPARK_COL):
            return
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = col in (3, 4)
        self.refresh()

    def _mark_header(self):
        for col in range(len(COLUMNS)):
            base = COLUMNS[col]
            if col == self._sort_col:
                base += "  ▼" if self._sort_reverse else "  ▲"
            self._tree.headerItem().setText(col, base)

    # -- Kill ----------------------------------------------------------------
    def _selected_pids(self):
        pids = []
        for item in self._tree.selectedItems():
            data = item.data(0, Qt.UserRole)
            if not data:
                continue
            if data[0] == "task":
                for i in range(item.childCount()):
                    cdata = item.child(i).data(0, Qt.UserRole)
                    if cdata and cdata[0] == "proc":
                        pids.append(cdata[1])
            elif data[0] == "proc":
                pids.append(data[1])
        return list(dict.fromkeys(pids))

    def kill_selected(self):
        pids = self._selected_pids()
        if not pids:
            QMessageBox.information(self, "Info", "Aucun process sélectionné.")
            return
        self._kill_pids(pids)

    def kill_all(self):
        pids = []
        for i in range(self._tree.topLevelItemCount()):
            parent = self._tree.topLevelItem(i)
            for j in range(parent.childCount()):
                data = parent.child(j).data(0, Qt.UserRole)
                if data and data[0] == "proc":
                    pids.append(data[1])
        if not pids:
            QMessageBox.information(self, "Info", "Aucun process Node à tuer.")
            return
        if QMessageBox.question(
                self, "Confirmer",
                f"Tuer les {len(pids)} process Node listés ?") != \
                QMessageBox.Yes:
            return
        self._kill_pids(pids)

    def _kill_pids(self, pids):
        ok = sum(kill_process(pid) for pid in pids)
        failed = len(pids) - ok
        msg = f"{ok} process tué(s)."
        if failed:
            msg += f" {failed} échec(s) (droits insuffisants ?)."
        self._flash = msg
        self.refresh()


class SparklineDelegate(QStyledItemDelegate):
    """Dessine une mini-courbe CPU (aire) + mémoire (ligne) par process.

    Les deux séries sont stockées sur la cellule (``Qt.UserRole``) sous forme
    ``(cpu, mem)`` et mises à l'échelle min-max sur la fenêtre visible : c'est
    la *variation* récente qui est lisible d'un coup d'œil, pas la valeur
    absolue (déjà affichée dans les colonnes CPU % / Mémoire).
    """

    def paint(self, painter, option, index):
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        series = index.data(Qt.UserRole)
        if not series:
            return
        cpu, mem = series
        rect = QRectF(option.rect).adjusted(5, 5, -5, -5)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setClipRect(QRectF(option.rect))
        self._draw_line(painter, rect, mem, QColor(theme.MUTED), width=1.0)
        self._draw_area(painter, rect, cpu, QColor(theme.ACCENT))
        painter.restore()

    @staticmethod
    def _points(rect, values):
        """Projette ``values`` (mise à l'échelle min-max) dans ``rect``."""
        n = len(values)
        if n == 0:
            return []
        lo, hi = min(values), max(values)
        span = hi - lo
        step = rect.width() / (n - 1) if n > 1 else 0.0
        pts = []
        for i, v in enumerate(values):
            frac = 0.5 if span <= 1e-9 else (v - lo) / span
            x = rect.left() + i * step
            y = rect.bottom() - frac * rect.height()
            pts.append(QPointF(x, y))
        return pts

    def _draw_area(self, painter, rect, values, color):
        pts = self._points(rect, values)
        if not pts:
            return
        fill = QColor(color)
        fill.setAlpha(55)
        poly = QPolygonF([QPointF(pts[0].x(), rect.bottom())] + pts
                         + [QPointF(pts[-1].x(), rect.bottom())])
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawPolygon(poly)
        pen = QPen(color)
        pen.setWidthF(1.2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        if len(pts) > 1:
            painter.drawPolyline(QPolygonF(pts))
        else:
            painter.drawPoint(pts[0])

    def _draw_line(self, painter, rect, values, color, width=1.0):
        pts = self._points(rect, values)
        if len(pts) < 2:
            return
        pen = QPen(color)
        pen.setWidthF(width)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawPolyline(QPolygonF(pts))
