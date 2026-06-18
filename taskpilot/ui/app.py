"""Fenetre principale : Notebook regroupant les onglets Tasks et Process."""

import tkinter as tk

from taskpilot.config import Config
from taskpilot.core import logs
from taskpilot.ui import theme
from taskpilot.ui.icons import build_logo, build_node_icon
from taskpilot.ui.menubar import MenuBar
from taskpilot.ui.process_tab import ProcessTab
from taskpilot.ui.rounded import RoundedNotebook
from taskpilot.ui.tasks_tab import TasksTab


class App(tk.Tk):
    """Application TaskPilot."""

    def __init__(self):
        super().__init__()
        self.title("TaskPilot")
        self.geometry("960x560")
        self.minsize(640, 360)
        self.configure(bg=theme.BG)

        self.settings = Config()
        # Logs : on repart d'un dossier propre a chaque demarrage.
        logs.clean_log_dir()
        self.node_icon = build_node_icon(self, 16)
        self.logo = build_logo(self, 64)
        self.iconphoto(True, self.logo)
        theme.apply_theme(self)

        notebook = RoundedNotebook(self, tab_sel_fg=theme.ACCENT,
                                   tab_accent=theme.ACCENT)
        self.tasks_tab = TasksTab(notebook, self)
        self.process_tab = ProcessTab(notebook, self)

        self._build_menubar()

        notebook.pack(fill="both", expand=True, padx=10, pady=(6, 0))
        notebook.add(self.tasks_tab, text="▶  Tasks",
                     tooltip="Lancer les tasks VS Code du projet et suivre "
                             "leurs consoles")
        notebook.add(self.process_tab, text="☰  Process",
                     tooltip="Suivre et gérer l'arbre des process de chaque "
                             "task en cours")
        # L'onglet Process ne lance sa collecte (sous-process lourds) qu'au
        # premier affichage, pas au demarrage de l'application.
        notebook.on_change(self._on_tab_change)

        self._bind_accelerators()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- Barre de menus ------------------------------------------------------
    def _build_menubar(self):
        bar = MenuBar(self)
        bar.pack(fill="x", side="top")
        tasks = self.tasks_tab

        file_menu = bar.add_menu("Fichier")
        file_menu.add_command("Ouvrir un projet…", tasks.choose_project,
                              accelerator="Ctrl+O")
        file_menu.add_submenu("Projets récents", populate=self._fill_recent)
        file_menu.add_command("Recharger les tasks", tasks.reload_tasks,
                              accelerator="F5")
        file_menu.add_separator()
        file_menu.add_command("Ouvrir le dossier du projet",
                              tasks.open_project_folder)
        file_menu.add_separator()
        file_menu.add_command("Quitter", self._on_close, accelerator="Ctrl+Q")

        run_menu = bar.add_menu("Tasks")
        run_menu.add_command("Lancer la task sélectionnée", tasks.run_selected,
                             accelerator="Ctrl+R")
        run_menu.add_separator()
        run_menu.add_command("Tout fermer", tasks.close_all)
        run_menu.add_command("Tout arrêter", tasks.kill_all)
        run_menu.add_command("Tout redémarrer", tasks.restart_all)

        console_menu = bar.add_menu("Console")
        console_menu.add_command("Zoom avant", lambda: tasks.zoom_current(1),
                                 accelerator="Ctrl++")
        console_menu.add_command("Zoom arrière", lambda: tasks.zoom_current(-1),
                                 accelerator="Ctrl+-")
        console_menu.add_command("Réinitialiser le zoom",
                                 tasks.reset_zoom_current, accelerator="Ctrl+0")
        console_menu.add_separator()
        console_menu.add_command("Copier la sortie", tasks.copy_current_output)
        console_menu.add_command("Vider la console", tasks.clear_current)

        self._confirm_var = tk.BooleanVar(value=self.settings.confirm_bulk)
        self._logs_var = tk.BooleanVar(value=self.settings.save_logs)
        options = bar.add_menu("Options")
        options.add_checkbutton("Confirmer les actions groupées",
                                self._confirm_var, command=self._save_confirm)
        options.add_checkbutton("Enregistrer les logs",
                                self._logs_var, command=self._save_logs_pref)
        options.add_separator()
        options.add_command(logs.LOG_DIR, None)   # rappel du chemin (désactivé)
        options.add_command("Ouvrir le dossier des logs", logs.open_log_dir)

        help_menu = bar.add_menu("Aide")
        help_menu.add_command("Raccourcis clavier", self._show_shortcuts)
        help_menu.add_command("À propos", self._show_about)

    def _fill_recent(self, menu):
        recents = self.settings.recent_projects
        if not recents:
            menu.add_command("(aucun projet récent)", None)
            return
        for path in recents:
            menu.add_command(path, lambda p=path: self.tasks_tab.open_project(p))

    def _save_confirm(self):
        self.settings.confirm_bulk = self._confirm_var.get()

    def _save_logs_pref(self):
        self.settings.save_logs = self._logs_var.get()

    def _bind_accelerators(self):
        tasks = self.tasks_tab
        self.bind_all("<Control-o>", lambda _e: tasks.choose_project())
        self.bind_all("<Control-r>", lambda _e: tasks.run_selected())
        self.bind_all("<F5>", lambda _e: tasks.reload_tasks())
        self.bind_all("<Control-q>", lambda _e: self._on_close())

    # -- Dialogues sombres ---------------------------------------------------
    def _info_dialog(self, title, lines):
        win = tk.Toplevel(self)
        win.title(title)
        win.configure(bg=theme.BG)
        win.resizable(False, False)
        win.transient(self)
        tk.Label(win, text=title, bg=theme.BG, fg=theme.FG,
                 font=theme.FONT_UI_BOLD).pack(anchor="w", padx=16, pady=(14, 6))
        for left, right in lines:
            row = tk.Frame(win, bg=theme.BG)
            row.pack(fill="x", padx=16)
            tk.Label(row, text=left, bg=theme.BG, fg=theme.FG,
                     font=theme.FONT_UI, anchor="w", width=22).pack(side="left")
            tk.Label(row, text=right, bg=theme.BG, fg=theme.CONSOLE_MUTED,
                     font=theme.FONT_UI, anchor="w").pack(side="left")
        tk.Frame(win, bg=theme.BG, height=12).pack()
        win.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() - win.winfo_width()) // 2
        y = self.winfo_rooty() + 80
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def _show_shortcuts(self):
        self._info_dialog("Raccourcis clavier", [
            ("Ctrl + O", "Ouvrir un projet"),
            ("F5", "Recharger les tasks"),
            ("Ctrl + R", "Lancer la task sélectionnée"),
            ("Ctrl + molette", "Zoomer la console"),
            ("Ctrl + + / Ctrl + -", "Zoom avant / arrière"),
            ("Ctrl + 0", "Réinitialiser le zoom"),
            ("Ctrl + Q", "Quitter"),
        ])

    def _show_about(self):
        self._info_dialog("À propos", [
            ("TaskPilot", ""),
            ("Lanceur de tasks VS Code", ""),
            ("et gestionnaire de process.", ""),
        ])

    def _on_tab_change(self, child):
        if child is self.process_tab:
            self.process_tab.on_shown()

    def _on_close(self):
        """Tue tous les process lances par les tasks avant de quitter."""
        try:
            self.tasks_tab.shutdown()
        except Exception:
            pass
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
