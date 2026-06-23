"""Onglet Process (Qt) : arbre des process des tasks, surveillance et kill.

Affiche, groupe par task, l'integralite de l'arbre de process lance par chaque
console. Collecte deportee dans un thread (les listings ``wmic`` / ``ps`` sont
lourds) ; le resultat revient sur le thread UI via un signal Qt.
"""

import threading
import time

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QHBoxLayout, QMessageBox, QPushButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget)

from taskpilot.core.processes import (
    find_task_processes, format_memory, kill_process)
from taskpilot.core.system import NCPU
from taskpilot.qt import theme

REFRESH_MS = 1500
COLUMNS = ["Task", "Port", "PID", "CPU %", "Mémoire", "Ligne de commande"]


class ProcessTab(QWidget):
    """Tableau temps reel des process des tasks, avec tri et kill d'arbre."""

    _collected = Signal(object, object)   # (procs, err) — emis depuis le thread

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._prev_cpu = {}
        self._sort_col = 3            # CPU %
        self._sort_reverse = True
        self._loading = False
        self._flash = None
        self._activated = False
        self._collapsed = set()       # labels de tasks repliees par l'utilisateur
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
        self._tree.setAlternatingRowColors(True)
        self._tree.setColumnWidth(0, 200)
        self._tree.setColumnWidth(5, 480)
        for col in range(1, 5):
            self._tree.setColumnWidth(col, 90)
        self._tree.header().setSectionsClickable(True)
        self._tree.header().sectionClicked.connect(self._sort_by)
        self._tree.itemExpanded.connect(self._on_expand)
        self._tree.itemCollapsed.connect(self._on_collapse)
        v.addWidget(self._tree, 1)

        from PySide6.QtWidgets import QLabel
        from taskpilot.qt import effects
        self._status = QLabel("")
        self._style_status()
        effects.add_shadow(self._status, blur=18, dy=3, alpha=80)
        v.addWidget(self._status)

    def _style_status(self):
        self._status.setStyleSheet(
            f"background: {theme.SURFACE_2}; border-radius: 9px; "
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
            procs, err = find_task_processes(roots), None
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
        live = {p.pid for p in procs}
        for pid in list(self._prev_cpu):
            if pid not in live:
                self._prev_cpu.pop(pid, None)

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
            parent = QTreeWidgetItem([label, "", "", "", "", ""])
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
                for col in (1, 2, 3, 4):
                    child.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
                parent.addChild(child)
            parent.setExpanded(label not in self._collapsed)
        self._tree.blockSignals(False)
        self._mark_header()
        self._update_status(procs, len(order))

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
        return ["", port, str(p.pid), cpu, format_memory(p.mem), p.cmd]

    def _update_status(self, procs, ntasks):
        if not procs and not self._flash:
            self._status.setText(
                "  Aucune task en cours. Lance une task (ou ouvre une console) "
                "dans l'onglet Tasks.")
            return
        total_mem = sum(p.mem for p in procs)
        total_cpu = sum(p.cpu for p in procs if p.cpu is not None)
        text = (f"  {len(procs)} process   •   {ntasks} task(s)"
                f"   •   CPU total ≈ {total_cpu:.1f} %"
                f"   •   Mémoire totale {format_memory(total_mem)}")
        if self._flash:
            text = f"  {self._flash}   —  {text.strip()}"
            self._flash = None
        self._status.setText(text)

    # -- Tri -----------------------------------------------------------------
    def _sort_by(self, col):
        if col == 0:
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
            QMessageBox.information(self, "Info", "Aucun process de task à tuer.")
            return
        if QMessageBox.question(
                self, "Confirmer",
                f"Tuer les {len(pids)} process des tasks en cours ?") != \
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
