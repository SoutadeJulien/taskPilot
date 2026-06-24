"""Onglet Tasks (Qt) : selection du projet, lancement, consoles integrees.

QSplitter + QTreeWidget (liste des tasks) + QTabWidget (consoles fermables).
Le drainage des files de sortie se fait par un unique ``QTimer``, avec
accelaration quand il reste du backlog.
"""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QMenu, QMessageBox,
    QPushButton, QSplitter, QStackedWidget, QTabBar, QTabWidget, QToolButton,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from taskpilot.core import logs
from taskpilot.core.pty_console import HAVE_PTY, PtyConsole
from taskpilot.core.task_runner import EVENT_EXIT, EVENT_OUTPUT, TaskConsole
from taskpilot.core.vscode_tasks import (
    CommandSpec, build_task_tree, is_group_task, load_vscode_tasks, task_label,
    tree_leaves)
from taskpilot.qt import theme
from taskpilot.qt.console_view import ConsoleView
from taskpilot.qt.terminal_view import TerminalView

#: Role de donnee portant la cle de section ("fav"/"all") sur les en-tetes.
SECTION_ROLE = Qt.UserRole + 1

POLL_MS = 120
FAST_POLL_MS = 8
MAX_CHARS_PER_TICK = 16 * 1024
WATCH_MS = 300
MAX_TAB_TITLE = 22

SHELL_TYPES = (
    ("PowerShell", ["powershell.exe", "-NoLogo"]),
    ("CMD", ["cmd.exe"]),
    ("Bash", ["bash", "-i"]),
)


class TasksTab(QWidget):
    """Charge les tasks d'un projet et pilote leurs consoles."""

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.settings = app.settings
        self.tasks = []
        self.tasks_by_label = {}
        self.panels = []
        self._group_colors = dict(self.settings.get_group_colors())
        self._task_items = []          # (QTreeWidgetItem, label)

        self._build()
        self._apply_label_styles()
        if self.settings.project:
            self._select_project(self.settings.project)
            self.reload_tasks(silent=True)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(POLL_MS)
        theme.notifier.changed.connect(self._restyle)

    # -- Construction --------------------------------------------------------
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 14)
        root.setSpacing(16)
        root.addLayout(self._build_top())
        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_task_list())
        splitter.addWidget(self._build_consoles())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 700])
        root.addWidget(splitter, 1)

    def _build_top(self):
        top = QHBoxLayout()
        top.setSpacing(10)
        self._projet_label = QLabel("PROJET")
        top.addWidget(self._projet_label)
        self._project_combo = QComboBox()
        self._project_combo.setEditable(False)
        self._project_combo.addItems(self.settings.recent_projects)
        self._project_combo.setMinimumWidth(280)
        self._project_combo.activated.connect(lambda _i: self.reload_tasks())
        top.addWidget(self._project_combo, 1)

        self._swatch = QPushButton()
        self._swatch.setFixedSize(24, 24)
        self._swatch.setToolTip("Couleur du projet : repère ses consoles\n"
                                "(utile pour distinguer deux worktrees)")
        self._swatch.clicked.connect(self._open_color_menu)
        top.addWidget(self._swatch)

        choose = QPushButton("⌂ Choisir…")
        choose.clicked.connect(self.choose_project)
        top.addWidget(choose)
        reload_btn = QPushButton("↻ Recharger")
        reload_btn.clicked.connect(lambda: self.reload_tasks())
        top.addWidget(reload_btn)
        self._update_swatch()
        return top

    def _build_task_list(self):
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        self._tree = QTreeWidget()
        self._tree.setColumnCount(3)
        self._tree.setHeaderLabels(["Task", "Type", ""])
        self._tree.setRootIsDecorated(True)
        self._tree.setAlternatingRowColors(self.settings.alt_rows)
        header = self._tree.header()
        header.setStretchLastSection(False)
        from PySide6.QtWidgets import QHeaderView
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        self._tree.setColumnWidth(2, 30)
        self._tree.itemDoubleClicked.connect(
            lambda *_: self.run_selected())
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.itemExpanded.connect(self._on_section_toggle)
        self._tree.itemCollapsed.connect(self._on_section_toggle)
        self._tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self._tree.customContextMenuRequested.connect(self._task_menu)
        # L'arbre est enveloppe dans une carte arrondie : la carte porte le
        # rayon (le QTreeWidget reste a angles francs, mais en leger retrait, ses
        # coins sont masques par ceux — arrondis — de la carte).
        card = QFrame()
        card.setObjectName("taskCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(7, 7, 7, 7)
        cl.addWidget(self._tree)
        v.addWidget(card, 1)
        run = QPushButton("▶  Lancer la task")
        run.setProperty("accent", True)
        run.clicked.connect(self.run_selected)
        v.addWidget(run)
        # Detache un peu la carte Task de la zone Consoles (marge a droite, la
        # poignee du splitter ajoutant deja un espace).
        wrap.setContentsMargins(0, 0, 4, 0)
        return wrap

    def set_alternating_rows(self, on):
        self._tree.setAlternatingRowColors(bool(on))

    def _build_consoles(self):
        wrap = QWidget()
        v = QVBoxLayout(wrap)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._consoles_title = QLabel("Consoles")
        header.addWidget(self._consoles_title)
        header.addSpacing(4)
        new_btn = QPushButton("＋ Console")
        new_btn.setProperty("accent", True)
        new_btn.setToolTip("Ouvrir une console interactive (PowerShell, CMD, Bash)")
        new_btn.clicked.connect(lambda: self._new_menu(new_btn))
        header.addWidget(new_btn)
        header.addStretch(1)
        self._close_all_btn = QPushButton("✕ Tout fermer")
        self._close_all_btn.clicked.connect(self.close_all)
        header.addWidget(self._close_all_btn)
        self._kill_all_btn = QPushButton("■ Tout arrêter")
        self._kill_all_btn.setProperty("danger", True)
        self._kill_all_btn.clicked.connect(self.kill_all)
        header.addWidget(self._kill_all_btn)
        self._restart_all_btn = QPushButton("↻ Tout redémarrer")
        self._restart_all_btn.clicked.connect(self.restart_all)
        header.addWidget(self._restart_all_btn)
        v.addLayout(header)

        self._stack = QStackedWidget()
        self._empty_label = QLabel(
            "Aucune console.\nLance une task pour voir sa sortie ici.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._stack.addWidget(self._empty_label)
        self._tabs = QTabWidget()
        self._tabs.setObjectName("consoleTabs")
        self._tabs.setTabBar(ColorTabBar())
        # Croix de fermeture maison (cf. _make_close_button) plutot que la croix
        # native : on maitrise totalement son rendu (aucun fond, jamais).
        self._tabs.setTabsClosable(False)
        self._tabs.setMovable(True)
        self._tabs.setElideMode(Qt.ElideNone)
        self._tabs.setUsesScrollButtons(True)
        self._stack.addWidget(self._tabs)
        v.addWidget(self._stack, 1)
        self._refresh_actions()
        return wrap

    # -- Projet --------------------------------------------------------------
    @property
    def project(self):
        return self._project_combo.currentText().strip()

    def _select_project(self, path):
        """Selectionne un chemin dans le combo (non-editable), en l'inserant
        en tete s'il n'y figure pas encore."""
        self._project_combo.blockSignals(True)
        index = self._project_combo.findText(path)
        if index < 0:
            self._project_combo.insertItem(0, path)
            index = 0
        self._project_combo.setCurrentIndex(index)
        self._project_combo.blockSignals(False)

    def choose_project(self):
        initial = self.project or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(
            self, "Choisir un projet (contenant .vscode/tasks.json)", initial)
        if path:
            path = path.replace("/", os.sep)
            self._select_project(path)
            self.reload_tasks()

    def open_project(self, path):
        self._select_project(path)
        self.reload_tasks()

    def reload_tasks(self, silent=False):
        project = self.project
        if not project:
            if not silent:
                QMessageBox.information(self, "Info", "Choisis d'abord un projet.")
            return
        try:
            self.tasks = load_vscode_tasks(project)
        except FileNotFoundError:
            self.tasks = []
            if not silent:
                QMessageBox.warning(
                    self, "tasks.json introuvable",
                    f"Aucun fichier .vscode/tasks.json dans :\n{project}")
        except Exception as e:  # noqa: BLE001
            self.tasks = []
            if not silent:
                QMessageBox.critical(self, "Erreur de lecture",
                                     f"tasks.json illisible :\n{e}")
        self.tasks_by_label = {task_label(t): t for t in self.tasks}
        self.settings.project = project
        self._refresh_recent_combo()
        self._render_tasks()
        self._update_swatch()
        self._refresh_task_status()

    def _refresh_recent_combo(self):
        current = self.project
        self._project_combo.blockSignals(True)
        self._project_combo.clear()
        items = list(self.settings.recent_projects)
        if current and current not in items:
            items.insert(0, current)
        self._project_combo.addItems(items)
        self._project_combo.setCurrentIndex(max(0, self._project_combo.findText(current)))
        self._project_combo.blockSignals(False)

    def _render_tasks(self):
        self._tree.clear()
        self._task_items = []
        favorites = set(self.settings.get_favorites(self.project))
        fav_root = QTreeWidgetItem(["★  FAVORIS", "", ""])
        all_root = QTreeWidgetItem(["TOUTES LES TASKS", "", ""])
        fav_root.setData(0, SECTION_ROLE, "fav")
        all_root.setData(0, SECTION_ROLE, "all")
        for item in (fav_root, all_root):
            item.setFirstColumnSpanned(True)
            item.setFlags(Qt.ItemIsEnabled)
            self._tree.addTopLevelItem(item)
            self._style_section(item)
        for t in self.tasks:
            label = task_label(t)
            ttype = "groupe" if is_group_task(t) else t.get("type", "process")
            is_fav = label in favorites
            parent = fav_root if is_fav else all_root
            child = QTreeWidgetItem([label, ttype, ""])
            child.setData(0, Qt.UserRole, label)
            child.setForeground(1, QColor(theme.LV_SUCCESS))
            self._set_star(child, is_fav)
            parent.addChild(child)
            self._task_items.append((child, label))
        fav_root.setHidden(fav_root.childCount() == 0)
        # Restaure l'etat replie/deplie memorise (sans declencher la sauvegarde).
        self._tree.blockSignals(True)
        fav_root.setExpanded(not self.settings.fav_collapsed)
        all_root.setExpanded(not self.settings.all_collapsed)
        self._tree.blockSignals(False)

    @staticmethod
    def _style_section(item):
        """Donne aux lignes de section un aspect d'en-tete de groupe."""
        font = QFont()
        font.setBold(True)
        font.setPointSizeF(8.5)
        font.setLetterSpacing(QFont.PercentageSpacing, 108)
        item.setFont(0, font)
        item.setForeground(0, QColor(theme.MUTED))
        item.setBackground(0, QColor(theme.SURFACE_2))

    @staticmethod
    def _set_star(item, is_fav):
        item.setText(2, "★" if is_fav else "☆")
        item.setForeground(2, QColor("#f0b400" if is_fav else theme.MUTED))
        item.setTextAlignment(2, Qt.AlignCenter)
        item.setToolTip(2, "Retirer des favoris" if is_fav
                        else "Ajouter aux favoris")

    def _on_section_toggle(self, item):
        """Memorise l'etat replie/deplie d'une section (FAVORIS / TOUTES)."""
        key = item.data(0, SECTION_ROLE)
        if key is None:
            return
        collapsed = not item.isExpanded()
        if key == "fav":
            self.settings.fav_collapsed = collapsed
        elif key == "all":
            self.settings.all_collapsed = collapsed

    def _on_item_clicked(self, item, column):
        """Un clic sur la colonne étoile bascule le favori."""
        if column != 2:
            return
        label = item.data(0, Qt.UserRole)
        if label:
            self._toggle_favorite(label)

    def _selected_label(self):
        items = self._tree.selectedItems()
        for it in items:
            label = it.data(0, Qt.UserRole)
            if label:
                return label
        return None

    def _refresh_task_status(self):
        project = self.project
        running = {p.console.label for p in self.panels
                   if p.console.is_running() and getattr(p, "project", None) == project}
        for item, label in self._task_items:
            on = label in running
            item.setText(0, ("●  " + label) if on else label)
            item.setForeground(
                0, QColor(theme.DOT_RUNNING if on else theme.FG))

    # -- Couleur du projet ---------------------------------------------------
    def _project_color(self):
        return self.settings.get_project_color(self.project) if self.project else ""

    def _update_swatch(self):
        color = self._project_color() or theme.SURFACE_2
        self._swatch.setStyleSheet(
            f"QPushButton {{ background: {color}; border: 1px solid "
            f"{theme.BORDER}; border-radius: {theme.radius(6)}px; }}")

    def _apply_label_styles(self):
        """(Re)applique les styles inline des libelles (suit le theme actif)."""
        self._projet_label.setStyleSheet(
            f"color: {theme.MUTED}; font-weight: 600; font-size: 11px;")
        self._consoles_title.setStyleSheet(
            f"font-size: 14px; font-weight: 700; color: {theme.FG};")
        self._empty_label.setStyleSheet(f"color: {theme.MUTED};")

    def _restyle(self):
        """Rafraichit a chaud tout ce qui n'est pas couvert par le QSS global."""
        self._apply_label_styles()
        self._update_swatch()
        if self.tasks:
            self._render_tasks()
            self._refresh_task_status()
        for panel in self.panels:
            btn = getattr(panel, "_close_btn", None)
            if btn is not None:
                self._style_close_button(btn)
        self._tabs.tabBar().update()

    def _open_color_menu(self):
        if not self.project:
            QMessageBox.information(self, "Info", "Choisis d'abord un projet.")
            return
        current = self.settings.get_project_color(self.project)
        menu = QMenu(self)
        none_act = menu.addAction("Aucune couleur")
        none_act.triggered.connect(lambda: self._set_project_color(""))
        for c in theme.PROJECT_PALETTE:
            act = menu.addAction(("✓ " if c == current else "    ") + c)
            pix = _swatch_icon(c)
            act.setIcon(pix)
            act.triggered.connect(lambda _=False, col=c: self._set_project_color(col))
        menu.exec(self._swatch.mapToGlobal(self._swatch.rect().bottomLeft()))

    def _set_project_color(self, color):
        if not self.project:
            return
        self.settings.set_project_color(self.project, color)
        self._update_swatch()
        new = color or None
        for panel in self.panels:
            if getattr(panel, "project", None) != self.project:
                continue
            panel.set_project_color(new)
            self._color_tab(panel, new or getattr(panel, "group_color", None))

    # -- Lancement -----------------------------------------------------------
    def run_selected(self):
        label = self._selected_label()
        if not label:
            QMessageBox.information(self, "Info", "Aucune task sélectionnée.")
            return
        self.launch_task(label)

    def launch_task(self, label):
        project = self.project
        tree = build_task_tree(label, self.tasks_by_label, project)
        leaves = tree_leaves(tree)
        if not leaves:
            QMessageBox.warning(
                self, "Rien à lancer",
                f"La task « {label} » n'a pas de commande exécutable.")
            return
        project_color = self.settings.get_project_color(project) or None
        group = label if len(leaves) > 1 else None
        color = self._group_color(group) if group else None
        # Execute l'arbre en respectant l'ordre propre a chaque groupe :
        # une *sequence* attend la fin de chaque etape, un groupe *parallel*
        # lance tous ses enfants simultanement.
        self._run_node(tree, (project, group, color, project_color),
                       lambda ok: None)

    def _group_color(self, group):
        if group not in self._group_colors:
            palette = theme.GROUP_COLORS
            self._group_colors[group] = palette[len(self._group_colors) % len(palette)]
            self.settings.set_group_color(group, self._group_colors[group])
        return self._group_colors[group]

    def _launch_leaf(self, leaf, project, group=None, group_color=None,
                     project_color=None):
        log_path = logs.new_log_path(leaf.label) if self.settings.save_logs else None
        console = TaskConsole(leaf.label, leaf.spec, log_path=log_path)
        panel = ConsoleView(console, on_restart=self._restart_panel,
                            settings=self.settings)
        self._tag_panel(panel, project, group_color, project_color)
        title = (leaf.label if len(leaf.label) <= MAX_TAB_TITLE
                 else leaf.label[:MAX_TAB_TITLE - 1] + "…")
        self._add_panel(panel, title, leaf.label, project_color or group_color)
        console.start()
        self._refresh_actions()
        return panel

    # -- Execution de l'arbre de dependances --------------------------------
    def _run_node(self, node, ctx, on_done):
        """Lance le sous-arbre ``node``. ``on_done(ok)`` est appele quand tout
        le sous-arbre s'est termine (``ok`` = aucun process en echec). Une
        feuille qui ne se termine jamais (serveur de dev) n'appelle jamais son
        ``on_done`` — c'est attendu pour la derniere etape d'une sequence."""
        if node is None:
            on_done(True)
        elif node.is_leaf:
            panel = self._launch_leaf(node, *ctx)
            self._watch_exit(panel, on_done)
        elif node.order == "sequence":
            self._run_sequence(node.children, 0, ctx, on_done)
        else:
            self._run_parallel(node.children, ctx, on_done)

    def _watch_exit(self, panel, on_done):
        def watch():
            console = panel.console
            if console.is_running() or console.returncode is None:
                QTimer.singleShot(WATCH_MS, watch)
                return
            on_done(console.returncode == 0)
        QTimer.singleShot(WATCH_MS, watch)

    def _run_sequence(self, children, index, ctx, on_done):
        if index >= len(children):
            on_done(True)
            return

        def step(ok):
            if not ok:
                on_done(False)        # une etape echoue -> sequence interrompue
                return
            self._run_sequence(children, index + 1, ctx, on_done)
        self._run_node(children[index], ctx, step)

    def _run_parallel(self, children, ctx, on_done):
        if not children:
            on_done(True)
            return
        state = {"pending": len(children), "ok": True}

        def child_done(ok):
            state["ok"] = state["ok"] and ok
            state["pending"] -= 1
            if state["pending"] == 0:
                on_done(state["ok"])
        for child in children:
            self._run_node(child, ctx, child_done)

    def _tag_panel(self, panel, project, group_color, project_color):
        panel.project = project
        panel.group_color = group_color
        panel.set_project_color(project_color)

    def _add_panel(self, panel, title, tooltip, tab_color):
        index = self._tabs.addTab(panel, title)
        self._tabs.setTabToolTip(index, tooltip)
        panel._close_btn = self._make_close_button(panel)
        self._tabs.tabBar().setTabButton(
            index, QTabBar.RightSide, panel._close_btn)
        self._tabs.setCurrentWidget(panel)
        self.panels.append(panel)
        if tab_color:
            self._color_tab(panel, tab_color)
        self._stack.setCurrentIndex(1)

    def _make_close_button(self, panel):
        """Croix de fermeture plate : aucun fond, seule l'icone change de
        couleur au survol (jamais de carre colore derriere le ``×``)."""
        btn = QToolButton()
        btn.setText("✕")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip("Fermer la console")
        self._style_close_button(btn)
        btn.clicked.connect(lambda: self._close_panel(panel))
        return btn

    @staticmethod
    def _style_close_button(btn):
        btn.setStyleSheet(
            "QToolButton { background: transparent; border: none; "
            f"color: {theme.MUTED}; font-size: 13px; padding: 0 1px; }} "
            f"QToolButton:hover {{ color: {theme.RED}; background: transparent; }}"
        )

    def _color_tab(self, panel, color):
        """Teinte le fond de l'onglet avec la couleur (projet/groupe) — peinte
        par ``ColorTabBar`` a partir de la donnee d'onglet."""
        panel._tab_color = color or None
        self._apply_tab_color(panel, color)

    def _apply_tab_color(self, panel, color):
        index = self._tabs.indexOf(panel)
        if index < 0:
            return
        bar = self._tabs.tabBar()
        bar.setTabData(index, color or None)
        bar.update()

    # -- Console vierge ------------------------------------------------------
    def _new_menu(self, button):
        menu = QMenu(self)
        for display, argv in SHELL_TYPES:
            act = menu.addAction(display)
            act.triggered.connect(
                lambda _=False, d=display, a=argv: self.new_console(d, a))
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def new_console(self, display, argv):
        project = self.project
        cwd = project or os.path.expanduser("~")
        project_color = self.settings.get_project_color(project) or None
        log_path = logs.new_log_path(display) if self.settings.save_logs else None
        if HAVE_PTY:
            spec = CommandSpec(argv=list(argv), shell=False, cwd=cwd, env=None,
                               display=display)
            console = PtyConsole(display, spec, log_path=log_path)
            panel = TerminalView(console, on_restart=self._restart_panel)
        else:
            spec = CommandSpec(argv=list(argv), shell=False, cwd=cwd, env=None,
                               display=display)
            console = TaskConsole(display, spec, log_path=log_path,
                                  interactive=True)
            panel = ConsoleView(console, on_restart=self._restart_panel,
                                settings=self.settings)
        self._tag_panel(panel, project, None, project_color)
        self._add_panel(panel, display, f"Console {display}", project_color)
        console.start()
        panel.focus_input()
        self._refresh_actions()
        return panel

    # -- Process tab ---------------------------------------------------------
    def running_task_roots(self):
        roots = []
        for p in self.panels:
            c = p.console
            if c.is_running() and c.proc is not None:
                try:
                    roots.append((c.proc.pid, c.label))
                except Exception:  # noqa: BLE001
                    pass
        return roots

    # -- Arret / fermeture ---------------------------------------------------
    def _restart_panel(self, panel):
        old = panel.console
        if old.is_running():
            old.kill()
        old.cleanup()
        log_path = logs.new_log_path(old.label) if self.settings.save_logs else None
        if getattr(old, "pty", False):
            console = PtyConsole(old.label, old.spec, log_path=log_path)
        else:
            console = TaskConsole(old.label, old.spec, log_path=log_path,
                                  interactive=old.interactive)
        panel.attach_console(console)
        self._apply_tab_color(panel, getattr(panel, "_tab_color", None))
        console.start()

    def _close_panel(self, panel):
        if panel.console.is_running():
            panel.console.kill()
        panel.console.cleanup()
        index = self._tabs.indexOf(panel)
        if index >= 0:
            self._tabs.removeTab(index)
        if panel in self.panels:
            self.panels.remove(panel)
        if hasattr(panel, "dispose"):
            panel.dispose()
        panel.deleteLater()
        if not self.panels:
            self._stack.setCurrentIndex(0)
        self._refresh_actions()

    def _confirm(self, question):
        if not self.settings.confirm_bulk:
            return True
        return QMessageBox.question(self, "Confirmer", question) == \
            QMessageBox.Yes

    def kill_all(self):
        running = [p for p in self.panels if p.console.is_running()]
        if not running or not self._confirm(
                f"Arrêter {len(running)} console(s) en cours ?"):
            return
        for p in running:
            p.console.kill()
        self._refresh_actions()

    def close_all(self):
        if not self.panels or not self._confirm(
                f"Fermer {len(self.panels)} console(s) ?"):
            return
        for p in list(self.panels):
            self._close_panel(p)

    def restart_all(self):
        if not self.panels or not self._confirm(
                f"Redémarrer {len(self.panels)} console(s) ?"):
            return
        for p in list(self.panels):
            self._restart_panel(p)
        self._refresh_actions()

    def open_project_folder(self):
        path = self.project
        if path and os.path.isdir(path):
            try:
                os.startfile(path)  # noqa: S606
            except OSError:
                pass

    # -- Console courante (menu) ---------------------------------------------
    def _current_panel(self):
        w = self._tabs.currentWidget()
        return w if w in self.panels else None

    def zoom_current(self, delta):
        p = self._current_panel()
        if p:
            p.zoom(delta)

    def reset_zoom_current(self):
        p = self._current_panel()
        if p:
            p.reset_zoom()

    def copy_current_output(self):
        """Action du menu : copie TOUTE la sortie de la console courante."""
        p = self._current_panel()
        if p:
            p.copy_all_output()

    def clear_current(self):
        p = self._current_panel()
        if p:
            p.clear()

    def shutdown(self):
        for panel in self.panels:
            if panel.console.is_running():
                panel.console.kill()
            panel.console.cleanup()

    # -- Drainage des sorties ------------------------------------------------
    def _poll(self):
        backlog = False
        for panel in list(self.panels):
            chunk, more = self._drain(panel.console.queue, MAX_CHARS_PER_TICK)
            backlog = backlog or more
            out = []
            for kind, payload in chunk:
                if kind == EVENT_OUTPUT:
                    out.append(payload)
                    continue
                if out:
                    panel.append("".join(out))
                    out = []
                if kind == EVENT_EXIT:
                    panel.set_exited(payload)
                    panel.console.cleanup()
                    self._mark_tab_crashed(panel, payload != 0)
            if out:
                panel.append("".join(out))
        self._refresh_actions()
        self._timer.start(FAST_POLL_MS if backlog else POLL_MS)

    def _mark_tab_crashed(self, panel, crashed):
        if crashed:
            self._apply_tab_color(panel, theme.RED)
        else:
            self._apply_tab_color(panel, getattr(panel, "_tab_color", None))

    def _refresh_actions(self):
        has_running = any(p.console.is_running() for p in self.panels)
        self._kill_all_btn.setEnabled(has_running)
        self._close_all_btn.setEnabled(bool(self.panels))
        self._restart_all_btn.setEnabled(bool(self.panels))
        self._refresh_task_status()

    @staticmethod
    def _drain(q, max_chars):
        import queue
        items, chars = [], 0
        try:
            while chars < max_chars:
                kind, payload = q.get_nowait()
                items.append((kind, payload))
                if kind == EVENT_OUTPUT:
                    chars += len(payload)
        except queue.Empty:
            return items, False
        return items, True

    # -- Menu contextuel de la liste -----------------------------------------
    def _task_menu(self, pos):
        item = self._tree.itemAt(pos)
        if item is None:
            return
        label = item.data(0, Qt.UserRole)
        if not label:
            return
        menu = QMenu(self)
        run = menu.addAction("▶  Lancer")
        run.triggered.connect(lambda: self.launch_task(label))
        favorites = set(self.settings.get_favorites(self.project))
        fav_label = ("★  Retirer des favoris" if label in favorites
                     else "☆  Ajouter aux favoris")
        fav = menu.addAction(fav_label)
        fav.triggered.connect(lambda: self._toggle_favorite(label))
        if is_group_task(self.tasks_by_label.get(label, {})):
            menu.addSeparator()
            self._fill_group_color_menu(menu.addMenu("Couleur du groupe"), label)
        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _fill_group_color_menu(self, menu, group):
        current = self._group_colors.get(group)
        auto = menu.addAction("Auto (par défaut)")
        auto.triggered.connect(lambda: self._set_group_color_manual(group, ""))
        menu.addSeparator()
        for c in theme.GROUP_COLORS:
            act = menu.addAction(("✓ " if c == current else "    ") + c)
            act.setIcon(_swatch_icon(c))
            act.triggered.connect(
                lambda _=False, col=c: self._set_group_color_manual(group, col))

    def _set_group_color_manual(self, group, color):
        """Force (ou remet en auto) la couleur d'un groupe et recolore ses
        consoles ouvertes."""
        old = self._group_colors.get(group)
        if color:
            self._group_colors[group] = color
        else:
            self._group_colors.pop(group, None)
            color = self._group_color(group)  # reattribue une couleur auto
        self.settings.set_group_color(group, color)
        for panel in self.panels:
            if getattr(panel, "group_color", None) != old:
                continue
            panel.group_color = color
            pcol = self.settings.get_project_color(
                getattr(panel, "project", "")) or None
            self._color_tab(panel, pcol or color)

    def _toggle_favorite(self, label):
        if not self.project:
            return
        self.settings.toggle_favorite(self.project, label)
        self._render_tasks()
        self._refresh_task_status()


def _swatch_icon(color):
    """Petite pastille de couleur (carree) pour les entrees de menu."""
    pix = QPixmap(14, 14)
    pix.fill(QColor(color))
    return QIcon(pix)


class ColorTabBar(QTabBar):
    """Barre d'onglets dont le fond peut etre teinte a une couleur par onglet.

    La couleur (projet / groupe / rouge si crash) est stockee comme donnee
    d'onglet (``setTabData``) — robuste aux deplacements/fermetures — et peinte
    par-dessus le rendu QSS : un voile colore translucide + un liseré bas plus
    franc, lisible sans ecraser le texte. Repere bien plus visible qu'une
    pastille, surtout pour distinguer deux worktrees.
    """

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        for i in range(self.count()):
            color = self.tabData(i)
            if not color:
                continue
            rect = self.tabRect(i).adjusted(0, 0, 0, -1)
            selected = i == self.currentIndex()
            veil = QColor(color)
            veil.setAlpha(70 if selected else 42)
            painter.fillRect(rect, veil)
            painter.fillRect(rect.left(), rect.bottom() - 2,
                             rect.width(), 3, QColor(color))
        painter.end()
