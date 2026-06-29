"""Fenetre principale Qt : onglets Tasks / Process + barre de menus.

Note DPI : Qt gere le High-DPI nativement — il n'y a donc aucun code
d'echelle a la main ici.
"""

import os

from PySide6.QtCore import QTimer
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QIcon, QKeySequence, QPixmap)
from PySide6.QtWidgets import (
    QApplication, QColorDialog, QFileDialog, QLabel, QMainWindow, QMessageBox,
    QTabWidget, QVBoxLayout, QWidget)

from taskpilot import __version__
from taskpilot.core import editors, logs
from taskpilot.qt import theme
from taskpilot.qt.notify import Notifier
from taskpilot.qt.process_tab import ProcessTab
from taskpilot.qt.tasks_tab import TasksTab

ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


def _color_icon(color):
    """Petite pastille de couleur pour une entree de menu."""
    pix = QPixmap(14, 14)
    pix.fill(QColor(color))
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("TaskPilot")
        self.resize(1024, 620)
        self.setMinimumSize(720, 420)
        icon_path = os.path.join(ASSETS, "icon.ico")
        if os.path.isfile(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        logs.set_log_dir(settings.log_dir)
        logs.clean_log_dir()

        self.tabs = QTabWidget()
        self.tasks_tab = TasksTab(self)
        self.process_tab = ProcessTab(self)
        self.tabs.addTab(self.tasks_tab, "▶  Tasks")
        self.tabs.addTab(self.process_tab, "☰  Process")
        self.tabs.currentChanged.connect(self._on_tab_change)
        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(10, 8, 10, 0)
        lay.addWidget(self.tabs)
        self.setCentralWidget(central)

        # Emetteur de toasts (fin/echec de task) — adosse a l'icone deja posee.
        self.notifier = Notifier(self)

        self._build_menus()

        # Barre de statut « vivante » : projet, consoles actives, process Node.
        self._status_label = QLabel()
        self._status_label.setContentsMargins(10, 0, 10, 0)
        self.statusBar().addWidget(self._status_label)
        # Evite que le contenu touche les bords de la fenetre.
        self.statusBar().setContentsMargins(6, 2, 6, 2)
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self.refresh_status_bar)
        self._status_timer.start(1000)
        self.refresh_status_bar()

        # Reglages d'apparence persistes appliques a la fenetre/aux onglets.
        self.setWindowOpacity(settings.opacity)
        self._apply_tab_align(settings.tab_align)
        self._apply_alt_rows(settings.alt_rows)
        self.statusBar().setVisible(settings.show_statusbar)

    # -- Menus ---------------------------------------------------------------
    def _build_menus(self):
        bar = self.menuBar()
        tasks = self.tasks_tab

        file_menu = bar.addMenu("Fichier")
        self._add(file_menu, "Ouvrir un projet…", tasks.choose_project, "Ctrl+O")
        self._recent_menu = file_menu.addMenu("Projets récents")
        self._recent_menu.aboutToShow.connect(self._fill_recent)
        self._add(file_menu, "Recharger les tasks", tasks.reload_tasks, "F5")
        file_menu.addSeparator()
        self._add(file_menu, "Ouvrir le dossier du projet",
                  tasks.open_project_folder)
        file_menu.addSeparator()
        self._add(file_menu, "Quitter", self.close, "Ctrl+Q")

        run_menu = bar.addMenu("Tasks")
        self._add(run_menu, "Lancer la task sélectionnée", tasks.run_selected,
                  "Ctrl+R")
        run_menu.addSeparator()
        self._add(run_menu, "Gérer les profils…", tasks.manage_profiles)
        run_menu.addSeparator()
        self._add(run_menu, "Tout fermer", tasks.close_all)
        self._add(run_menu, "Tout arrêter", tasks.kill_all)
        self._add(run_menu, "Tout redémarrer", tasks.restart_all)

        console_menu = bar.addMenu("Console")
        # Ctrl++ n'est pas fiable selon les claviers : on ajoute Ctrl+= (meme
        # touche sans Maj) comme alias.
        zoom_in = self._add(console_menu, "Zoom avant",
                            lambda: tasks.zoom_current(1), "Ctrl++")
        zoom_in.setShortcuts(
            [QKeySequence("Ctrl++"), QKeySequence("Ctrl+=")])
        self._add(console_menu, "Zoom arrière", lambda: tasks.zoom_current(-1),
                  "Ctrl+-")
        self._add(console_menu, "Réinitialiser le zoom",
                  tasks.reset_zoom_current, "Ctrl+0")
        console_menu.addSeparator()
        self._add(console_menu, "Copier la sortie", tasks.copy_current_output)
        self._add(console_menu, "Vider la console", tasks.clear_current)

        opt = bar.addMenu("Options")

        # — Apparence : thème, couleurs, polices, mise en page —
        appearance = opt.addMenu("Apparence")
        self._build_theme_menu(appearance.addMenu("Thème"))
        self._build_accent_menu(appearance.addMenu("Accent"))
        self._build_radius_menu(appearance.addMenu("Arrondis"))
        self._build_density_menu(appearance.addMenu("Densité"))
        font_menu = appearance.addMenu("Police")
        self._build_font_choice_menu(
            font_menu.addMenu("Interface — police"),
            theme.UI_FONT_CHOICES, self.settings.ui_font_family,
            lambda f: self._set_ui_font(family=f))
        self._build_font_choice_menu(
            font_menu.addMenu("Interface — taille"),
            theme.UI_FONT_SIZES, self.settings.ui_font_size,
            lambda s: self._set_ui_font(size=s))
        self._build_font_choice_menu(
            font_menu.addMenu("Console — police"),
            theme.MONO_FONT_CHOICES, self.settings.mono_font_family,
            lambda f: self._set_mono_font(family=f))
        self._build_font_choice_menu(
            font_menu.addMenu("Console — taille"),
            theme.MONO_FONT_SIZES, self.settings.mono_font_size,
            lambda s: self._set_mono_font(size=s))
        self._build_tabalign_menu(appearance.addMenu("Alignement des onglets"))
        self._build_opacity_menu(appearance.addMenu("Opacité de la fenêtre"))
        appearance.addSeparator()
        self._alt_rows_act = self._add_check(
            appearance, "Lignes alternées", self.settings.alt_rows,
            self._set_alt_rows)
        self._statusbar_act = self._add_check(
            appearance, "Barre de statut", self.settings.show_statusbar,
            self._set_statusbar)

        # — Comportement : éditeur, confirmations —
        behavior = opt.addMenu("Comportement")
        self._build_editor_menu(behavior.addMenu("Éditeur de code"))
        behavior.addSeparator()
        self._confirm_act = self._add_check(
            behavior, "Confirmer les actions groupées",
            self.settings.confirm_bulk, self._save_confirm)
        behavior.addSeparator()
        self._notify_act = self._add_check(
            behavior, "Notifier la fin des tasks",
            self.settings.notify_on_exit, self._set_notify_on_exit)
        self._notify_bg_act = self._add_check(
            behavior, "Notifier seulement en arrière-plan",
            self.settings.notify_only_background, self._set_notify_bg)
        self._notify_bg_act.setEnabled(self.settings.notify_on_exit)

        # — Logs : enregistrement et dossier —
        logs_menu = opt.addMenu("Logs")
        self._logs_act = self._add_check(
            logs_menu, "Enregistrer les logs", self.settings.save_logs,
            self._save_logs_pref)
        logs_menu.addSeparator()
        self._add(logs_menu, "Choisir le dossier des logs…",
                  self._choose_log_dir)
        self._log_path_act = self._add(logs_menu, logs.LOG_DIR, None)
        self._log_path_act.setEnabled(False)
        self._add(logs_menu, "Ouvrir le dossier des logs", logs.open_log_dir)
        self._add(logs_menu, "Vider les logs", logs.clean_log_dir)

        help_menu = bar.addMenu("Aide")
        self._add(help_menu, "Raccourcis clavier", self._show_shortcuts)
        self._add(help_menu, "À propos", self._show_about)

    def _build_theme_menu(self, menu):
        group = QActionGroup(self)
        group.setExclusive(True)
        active = self.settings.theme
        for name in theme.THEMES:
            act = QAction(name, self, checkable=True)
            act.setChecked(name == active)
            act.triggered.connect(lambda _=False, n=name: self._set_theme(n))
            group.addAction(act)
            menu.addAction(act)

    def _set_theme(self, name):
        self.settings.theme = name
        theme.apply_theme(QApplication.instance(), name)

    def _build_radius_menu(self, menu):
        group = QActionGroup(self)
        group.setExclusive(True)
        active = self.settings.radius
        for label, scale in theme.RADIUS_PRESETS.items():
            act = QAction(label, self, checkable=True)
            act.setChecked(abs(scale - active) < 1e-6)
            act.triggered.connect(lambda _=False, s=scale: self._set_radius(s))
            group.addAction(act)
            menu.addAction(act)

    def _set_radius(self, scale):
        self.settings.radius = scale
        theme.apply_radius(QApplication.instance(), scale)

    # -- Densité -------------------------------------------------------------
    def _build_density_menu(self, menu):
        group = QActionGroup(self)
        group.setExclusive(True)
        active = self.settings.density
        for label, scale in theme.DENSITY_PRESETS.items():
            act = QAction(label, self, checkable=True)
            act.setChecked(abs(scale - active) < 1e-6)
            act.triggered.connect(lambda _=False, s=scale: self._set_density(s))
            group.addAction(act)
            menu.addAction(act)

    def _set_density(self, scale):
        self.settings.density = scale
        theme.apply_density(QApplication.instance(), scale)

    # -- Accent --------------------------------------------------------------
    def _build_accent_menu(self, menu):
        active = self.settings.accent_override
        follow = QAction("Suivre le thème", self, checkable=True)
        follow.setChecked(not active)
        follow.triggered.connect(lambda: self._set_accent(""))
        menu.addAction(follow)
        menu.addSeparator()
        for color in theme.ACCENT_CHOICES:
            act = QAction(("✓ " if color.lower() == active.lower() else "    ")
                          + color, self)
            act.setIcon(_color_icon(color))
            act.triggered.connect(lambda _=False, c=color: self._set_accent(c))
            menu.addAction(act)
        menu.addSeparator()
        self._add(menu, "Couleur personnalisée…", self._pick_accent)

    def _pick_accent(self):
        start = self.settings.accent_override or theme.ACCENT
        col = QColorDialog.getColor(QColor(start), self, "Couleur d'accent")
        if col.isValid():
            self._set_accent(col.name())

    def _set_accent(self, hexstr):
        self.settings.accent_override = hexstr
        theme.apply_accent_override(QApplication.instance(), hexstr)

    # -- Polices -------------------------------------------------------------
    def _build_font_choice_menu(self, menu, choices, active, slot):
        group = QActionGroup(self)
        group.setExclusive(True)
        for value in choices:
            label = str(value)
            act = QAction(label, self, checkable=True)
            act.setChecked(str(active) == label)
            act.triggered.connect(lambda _=False, v=value: slot(v))
            group.addAction(act)
            menu.addAction(act)

    def _set_ui_font(self, family=None, size=None):
        if family is not None:
            self.settings.ui_font_family = family
        if size is not None:
            self.settings.ui_font_size = size
        theme.apply_ui_font(QApplication.instance(),
                            self.settings.ui_font_family,
                            self.settings.ui_font_size)

    def _set_mono_font(self, family=None, size=None):
        if family is not None:
            self.settings.mono_font_family = family
        if size is not None:
            self.settings.mono_font_size = size
        theme.set_mono_font(self.settings.mono_font_family,
                            self.settings.mono_font_size)

    # -- Position des onglets ------------------------------------------------
    def _build_tabalign_menu(self, menu):
        group = QActionGroup(self)
        group.setExclusive(True)
        active = self.settings.tab_align
        for label, align in (("À gauche", "left"), ("Au milieu", "center"),
                             ("À droite", "right")):
            act = QAction(label, self, checkable=True)
            act.setChecked(align == active)
            act.triggered.connect(lambda _=False, a=align: self._set_tab_align(a))
            group.addAction(act)
            menu.addAction(act)

    def _apply_tab_align(self, align):
        # L'alignement de la barre d'onglets se pilote en QSS (left/center/right) ;
        # la regle fusionne avec le QSS global de l'application.
        self.tabs.setStyleSheet(
            f"QTabWidget::tab-bar {{ alignment: {align}; }}")

    def _set_tab_align(self, align):
        self.settings.tab_align = align
        self._apply_tab_align(align)

    # -- Opacité -------------------------------------------------------------
    def _build_opacity_menu(self, menu):
        group = QActionGroup(self)
        group.setExclusive(True)
        active = self.settings.opacity
        for pct in (100, 95, 90, 85, 80, 70):
            value = pct / 100.0
            act = QAction(f"{pct} %", self, checkable=True)
            act.setChecked(abs(value - active) < 1e-6)
            act.triggered.connect(lambda _=False, v=value: self._set_opacity(v))
            group.addAction(act)
            menu.addAction(act)

    def _set_opacity(self, value):
        self.settings.opacity = value
        self.setWindowOpacity(value)

    # -- Editeur de code (Ctrl+clic sur un chemin) ---------------------------
    def _build_editor_menu(self, menu):
        menu.setToolTipsVisible(True)
        info = menu.addAction("Ctrl+clic sur un chemin dans une console")
        info.setEnabled(False)
        menu.addSeparator()
        group = QActionGroup(self)
        group.setExclusive(True)
        active = editors.valid_key(self.settings.editor)
        for key, spec in editors.EDITORS.items():
            act = QAction(spec["name"], self, checkable=True)
            act.setChecked(key == active)
            act.triggered.connect(lambda _=False, k=key: self._set_editor(k))
            group.addAction(act)
            menu.addAction(act)

    def _set_editor(self, key):
        self.settings.editor = key

    # -- Lignes alternées / barre de statut ----------------------------------
    def _apply_alt_rows(self, on):
        for tab in (self.tasks_tab, self.process_tab):
            tab.set_alternating_rows(on)

    def _set_alt_rows(self, on):
        self.settings.alt_rows = on
        self._apply_alt_rows(on)

    def _set_statusbar(self, on):
        self.settings.show_statusbar = on
        self.statusBar().setVisible(on)

    def refresh_status_bar(self):
        """Compose la ligne de statut a partir de l'etat courant de l'app.

        Rafraichie chaque seconde (consoles / running) et poussee par l'onglet
        Process des qu'il recompte les process Node."""
        if not self.settings.show_statusbar:
            return
        proj = self.tasks_tab.project
        proj_name = os.path.basename(os.path.normpath(proj)) if proj else None
        segs = [f"TaskPilot {__version__}",
                "Projet : " + (proj_name or "aucun")]
        panels = self.tasks_tab.panels
        running = sum(1 for p in panels if p.console.is_running())
        segs.append(f"▶ {running}/{len(panels)} console(s) active(s)"
                    if panels else "▶ aucune console")
        count = getattr(self.process_tab, "process_count", None)
        if count is not None:
            segs.append(f"☰ {count} process Node")
        self._status_label.setText("      •      ".join(segs))

    def _add(self, menu, text, slot, shortcut=None):
        act = QAction(text, self)
        if slot is not None:
            act.triggered.connect(lambda _=False: slot())
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        menu.addAction(act)
        return act

    def _add_check(self, menu, text, checked, slot):
        act = QAction(text, self, checkable=True)
        act.setChecked(checked)
        act.toggled.connect(slot)
        menu.addAction(act)
        return act

    def _fill_recent(self):
        self._recent_menu.clear()
        recents = self.settings.recent_projects
        if not recents:
            act = self._recent_menu.addAction("(aucun projet récent)")
            act.setEnabled(False)
            return
        for path in recents:
            act = self._recent_menu.addAction(path)
            act.triggered.connect(
                lambda _=False, p=path: self.tasks_tab.open_project(p))

    def _save_confirm(self, on):
        self.settings.confirm_bulk = on

    def _set_notify_on_exit(self, on):
        self.settings.notify_on_exit = on
        self._notify_bg_act.setEnabled(on)

    def _set_notify_bg(self, on):
        self.settings.notify_only_background = on

    def _save_logs_pref(self, on):
        self.settings.save_logs = on

    def _choose_log_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Dossier des logs", logs.LOG_DIR)
        if not path:
            return
        self.settings.log_dir = path
        logs.set_log_dir(path)
        logs.ensure_log_dir()
        self._log_path_act.setText(logs.LOG_DIR)

    # -- Dialogues -----------------------------------------------------------
    def _show_shortcuts(self):
        QMessageBox.information(self, "Raccourcis clavier", (
            "Ctrl + O\t\tOuvrir un projet\n"
            "F5\t\tRecharger les tasks\n"
            "Ctrl + R\t\tLancer la task sélectionnée\n"
            "Ctrl + molette\tZoomer la console\n"
            "Ctrl + + / Ctrl + -\tZoom avant / arrière\n"
            "Ctrl + 0\t\tRéinitialiser le zoom\n"
            "Ctrl + clic\tOuvrir le fichier pointé dans l'éditeur\n"
            "Ctrl + Q\t\tQuitter"))

    def _show_about(self):
        QMessageBox.about(self, "À propos", (
            f"<b>TaskPilot</b> — version {__version__}<br><br>"
            "Lanceur de tasks VS Code et gestionnaire de process."))

    def _on_tab_change(self, index):
        if self.tabs.widget(index) is self.process_tab:
            self.process_tab.on_shown()

    # -- Notifications -------------------------------------------------------
    def notify_task_exit(self, label, returncode, interactive=False):
        """Emet un toast a la fin d'une task (succes ou echec).

        Ignore les consoles interactives (shells) et respecte les preferences :
        notifications globales activees, et — hors echec — seulement en
        arriere-plan si l'utilisateur l'a demande.
        """
        if interactive or not self.settings.notify_on_exit:
            return
        failed = returncode != 0
        if (self.settings.notify_only_background and not failed
                and self.isActiveWindow()):
            return
        if failed:
            self.notifier.notify(
                "Task en échec",
                f"« {label} » s'est arrêtée (code {returncode}).",
                success=False)
        else:
            self.notifier.notify(
                "Task terminée",
                f"« {label} » s'est terminée avec succès.", success=True)

    def closeEvent(self, event):
        try:
            self.tasks_tab.shutdown()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.notifier.dispose()
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)
