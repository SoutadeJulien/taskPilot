"""Fenetre principale Qt : onglets Tasks / Process + barre de menus.

Note DPI : contrairement a l'UI Tkinter (``_enable_dpi_awareness`` + facteur
``_sc()`` applique a la main partout), Qt gere le High-DPI nativement — il n'y
a donc aucun code d'echelle ici.
"""

import os

from PySide6.QtGui import QAction, QActionGroup, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QMainWindow, QMessageBox, QTabWidget,
    QVBoxLayout, QWidget)

from taskpilot import __version__
from taskpilot.core import logs
from taskpilot.qt import theme
from taskpilot.qt.process_tab import ProcessTab
from taskpilot.qt.tasks_tab import TasksTab

ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


class MainWindow(QMainWindow):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.setWindowTitle("TaskPilot — POC Qt")
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

        self._build_menus()
        self.statusBar().showMessage(f"TaskPilot {__version__} — POC PySide6")

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
        self._add(run_menu, "Tout fermer", tasks.close_all)
        self._add(run_menu, "Tout arrêter", tasks.kill_all)
        self._add(run_menu, "Tout redémarrer", tasks.restart_all)

        console_menu = bar.addMenu("Console")
        self._add(console_menu, "Zoom avant", lambda: tasks.zoom_current(1),
                  "Ctrl++")
        self._add(console_menu, "Zoom arrière", lambda: tasks.zoom_current(-1),
                  "Ctrl+-")
        self._add(console_menu, "Réinitialiser le zoom",
                  tasks.reset_zoom_current, "Ctrl+0")
        console_menu.addSeparator()
        self._add(console_menu, "Copier la sortie", tasks.copy_current_output)
        self._add(console_menu, "Vider la console", tasks.clear_current)

        opt = bar.addMenu("Options")
        self._build_theme_menu(opt.addMenu("Thème"))
        opt.addSeparator()
        self._confirm_act = self._add_check(
            opt, "Confirmer les actions groupées", self.settings.confirm_bulk,
            self._save_confirm)
        self._logs_act = self._add_check(
            opt, "Enregistrer les logs", self.settings.save_logs,
            self._save_logs_pref)
        opt.addSeparator()
        self._add(opt, "Choisir le dossier des logs…", self._choose_log_dir)
        self._log_path_act = self._add(opt, logs.LOG_DIR, None)
        self._log_path_act.setEnabled(False)
        self._add(opt, "Ouvrir le dossier des logs", logs.open_log_dir)
        self._add(opt, "Vider les logs", logs.clean_log_dir)

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
            "Ctrl + Q\t\tQuitter"))

    def _show_about(self):
        QMessageBox.about(self, "À propos", (
            f"<b>TaskPilot</b> — version {__version__} (POC PySide6)<br><br>"
            "Lanceur de tasks VS Code et gestionnaire de process."))

    def _on_tab_change(self, index):
        if self.tabs.widget(index) is self.process_tab:
            self.process_tab.on_shown()

    def closeEvent(self, event):
        try:
            self.tasks_tab.shutdown()
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)
