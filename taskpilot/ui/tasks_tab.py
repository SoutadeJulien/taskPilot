"""Onglet Tasks : selection du projet, lancement et consoles integrees."""

import os
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from taskpilot.core import logs
from taskpilot.core.task_runner import EVENT_EXIT, EVENT_OUTPUT, TaskConsole
from taskpilot.core.vscode_tasks import (
    flatten_tasks, is_group_task, load_vscode_tasks, task_label)
from taskpilot.ui import theme
from taskpilot.ui.console_panel import ConsolePanel
from taskpilot.ui.rounded import RoundedFrame, RoundedNotebook
from taskpilot.ui.task_table import TaskTable
from taskpilot.ui.widgets import add_tooltip, make_button

#: Periode de drainage des sorties de consoles (ms).
POLL_MS = 120
#: Periode de surveillance pour l'enchainement sequentiel (ms).
WATCH_MS = 300
#: Longueur max d'un titre d'onglet de console.
MAX_TAB_TITLE = 22


class TasksTab(ttk.Frame):
    """Charge les tasks d'un projet et pilote leurs consoles."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.settings = app.settings
        self.tasks = []
        self.tasks_by_label = {}
        self.panels = []
        self._group_colors = {}    # id de groupe -> couleur (cyclee)

        self.project = tk.StringVar(value=self.settings.project)

        self._build_top()
        self._build_body()

        if self.project.get():
            self.reload_tasks(silent=True)
        self._poll()

    # -- Construction de l'UI ------------------------------------------------
    def _build_top(self):
        top = tk.Frame(self, bg=theme.BG)
        top.pack(fill="x", padx=10, pady=(10, 6))
        tk.Label(top, text="Projet :", bg=theme.BG, fg=theme.FG,
                 font=theme.FONT_UI).pack(side="left")
        combo_card = RoundedFrame(
            top, bg=theme.BG_ALT, border=theme.CONSOLE_BORDER,
            radius=theme.BTN_RADIUS, inset=4)
        combo_card.pack(side="left", fill="x", expand=True, padx=8)
        # Lecture seule : pas de saisie clavier. En mode ``readonly``, un clic
        # n'importe où sur le champ déplie nativement la liste ; le choix d'un
        # nouveau dossier passe sinon par « Choisir… ».
        self.project_combo = ttk.Combobox(
            combo_card.inner, textvariable=self.project, font=theme.FONT_UI,
            values=self.settings.recent_projects, style="Flat.TCombobox",
            state="readonly")
        self.project_combo.pack(fill="x", expand=True)
        self.project_combo.bind(
            "<<ComboboxSelected>>", lambda e: self.reload_tasks())
        make_button(top, "⌂ Choisir…", self.choose_project).pack(
            side="left")
        make_button(top, "↻ Recharger", self.reload_tasks).pack(
            side="left", padx=6)

    def _build_body(self):
        paned = tk.PanedWindow(self, orient="horizontal", bg=theme.BG,
                               sashwidth=6, sashrelief="flat", bd=0)
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        paned.add(self._build_task_list(paned), minsize=200, width=320)
        paned.add(self._build_consoles(paned), minsize=300)

    def _build_task_list(self, parent):
        left = tk.Frame(parent, bg=theme.BG)
        # Liste custom (pastille + nom + type colore) soudee a son bouton
        # « Lancer la task » : voir TaskTable.
        self.task_list = TaskTable(
            left, on_run=self.run_selected,
            on_toggle_favorite=self._toggle_favorite,
            on_section_toggle=self._set_section_collapsed,
            fav_collapsed=self.settings.fav_collapsed,
            all_collapsed=self.settings.all_collapsed)
        self.task_list.pack(fill="both", expand=True)
        return left

    def _toggle_favorite(self, label):
        project = self.project.get().strip()
        if not project:
            return
        self.settings.toggle_favorite(project, label)
        self._render_tasks()

    def _set_section_collapsed(self, key, collapsed):
        if key == "fav":
            self.settings.fav_collapsed = collapsed
        elif key == "all":
            self.settings.all_collapsed = collapsed

    def _build_consoles(self, parent):
        right = tk.Frame(parent, bg=theme.BG)

        # En-tete « Consoles » : barre a coins arrondis EN HAUT (titre a gauche,
        # actions groupees a droite), soudee au corps des consoles dessous.
        header = RoundedFrame(right, bg=theme.CONSOLE_BAR,
                              border=theme.TASKLIST_BORDER, radius=8,
                              corners="top", inset_top=8, inset_bottom=2,
                              inset_left=10, inset_right=8)
        header.pack(fill="x")
        hb = header.inner
        tk.Label(hb, text="Consoles", bg=theme.CONSOLE_BAR, fg=theme.FG,
                 font=theme.FONT_UI_BOLD).pack(side="left", pady=4)
        # Ordre visuel : « Tout fermer », « Tout arrêter », « Tout redémarrer ».
        self._restart_all_btn = make_button(
            hb, "↻ Tout redémarrer", self.restart_all)
        self._restart_all_btn.pack(side="right")
        self._restart_all_btn.set_enabled(False)
        add_tooltip(self._restart_all_btn,
                    "Relancer toutes les consoles (nouveau process)")
        self._kill_all_btn = make_button(
            hb, "■ Tout arrêter", self.kill_all, danger=True)
        self._kill_all_btn.pack(side="right", padx=6)
        self._kill_all_btn.set_enabled(False)
        add_tooltip(self._kill_all_btn,
                    "Arrêter tous les process en cours (garde les onglets)")
        self._close_all_btn = make_button(hb, "✕ Tout fermer", self.close_all)
        self._close_all_btn.pack(side="right")
        self._close_all_btn.set_enabled(False)
        add_tooltip(self._close_all_btn,
                    "Fermer toutes les consoles (arrête les process en cours)")

        # Corps : carte a coins arrondis EN BAS, sans bordure haute (soudee a
        # l'en-tete), contenant les onglets de consoles et leur sortie.
        body = RoundedFrame(right, bg=theme.CONSOLE_BG,
                            border=theme.TASKLIST_BORDER, radius=8,
                            corners="bottom", inset_top=0, inset_bottom=2,
                            inset_left=2, inset_right=2)
        body.pack(fill="both", expand=True)
        cwrap = body.inner
        self.consoles = RoundedNotebook(
            cwrap, bg=theme.CONSOLE_BG, top_only=True, tab_gap=2,
            tab_accent=theme.ACCENT, tab_bg=theme.CONSOLE_TAB_IDLE,
            tab_sel=theme.CONSOLE_TAB_SEL, tab_fg=theme.CONSOLE_MUTED,
            tab_sel_fg=theme.ACCENT)
        self.consoles.pack(fill="both", expand=True)
        self._empty = tk.Label(
            cwrap, text="Aucune console.\nLance une task pour voir sa sortie ici.",
            bg=theme.CONSOLE_BG, fg="#777", font=("Segoe UI", 10),
            justify="center")
        self._empty.place(relx=0.5, rely=0.55, anchor="center")
        return right

    # -- Selection / chargement du projet ------------------------------------
    def choose_project(self):
        initial = self.project.get() or os.path.expanduser("~")
        path = filedialog.askdirectory(
            title="Choisir un projet (contenant .vscode/tasks.json)",
            initialdir=initial)
        if path:
            self.project.set(path)
            self.reload_tasks()

    def reload_tasks(self, silent=False):
        project = self.project.get().strip()
        if not project:
            if not silent:
                messagebox.showinfo("Info", "Choisis d'abord un dossier de projet.")
            return
        try:
            self.tasks = load_vscode_tasks(project)
        except FileNotFoundError:
            self.tasks = []
            if not silent:
                messagebox.showwarning(
                    "tasks.json introuvable",
                    f"Aucun fichier .vscode/tasks.json dans :\n{project}")
        except Exception as e:  # noqa: BLE001
            self.tasks = []
            if not silent:
                messagebox.showerror("Erreur de lecture",
                                     f"tasks.json illisible :\n{e}")

        self.tasks_by_label = {task_label(t): t for t in self.tasks}
        self.settings.project = project
        self.project_combo["values"] = self.settings.recent_projects
        self._render_tasks()

    def _render_tasks(self):
        items = []
        for t in self.tasks:
            ttype = "groupe" if is_group_task(t) else t.get("type", "process")
            items.append((task_label(t), ttype))
        favorites = self.settings.get_favorites(self.project.get().strip())
        self.task_list.set_tasks(items, favorites)

    def _refresh_task_status(self):
        """Reactualise les pastilles selon les tasks dont un process tourne."""
        running = {p.console.label for p in self.panels
                   if p.console.is_running()}
        self.task_list.set_running(running)

    # -- Lancement -----------------------------------------------------------
    def run_selected(self):
        sel = self.task_list.selection()
        if not sel:
            messagebox.showinfo("Info", "Aucune task sélectionnée.")
            return
        self.launch_task(sel[0])

    def launch_task(self, label):
        leaves, sequential = flatten_tasks(
            label, self.tasks_by_label, self.project.get().strip())
        if not leaves:
            messagebox.showwarning(
                "Rien à lancer",
                f"La task « {label} » n'a pas de commande exécutable.")
            return
        # Une task composite (plusieurs commandes) forme un groupe : ses
        # consoles partagent une couleur et restent cote a cote.
        group = label if len(leaves) > 1 else None
        color = self._group_color(group) if group else None
        if sequential and len(leaves) > 1:
            self._launch_sequential(leaves, group, color)
        else:
            for leaf in leaves:
                self._launch_leaf(leaf, group, color)

    def _group_color(self, group):
        """Couleur stable pour un groupe (cyclee dans la palette)."""
        if group not in self._group_colors:
            palette = theme.GROUP_COLORS
            self._group_colors[group] = palette[
                len(self._group_colors) % len(palette)]
        return self._group_colors[group]

    def _make_console(self, label, spec):
        """Crée une console, avec journalisation fichier si l'option est active."""
        log_path = logs.new_log_path(label) if self.settings.save_logs else None
        return TaskConsole(label, spec, log_path=log_path)

    def _launch_leaf(self, leaf, group=None, group_color=None):
        console = self._make_console(leaf.label, leaf.spec)
        panel = ConsolePanel(self.consoles, console, self._close_panel,
                             self._restart_panel)
        title = (leaf.label if len(leaf.label) <= MAX_TAB_TITLE
                 else leaf.label[:MAX_TAB_TITLE - 1] + "…")
        self.consoles.add(panel, text=title, tooltip=leaf.label,
                          group=group, group_color=group_color)
        self.consoles.select(panel)
        self.panels.append(panel)
        self._empty.place_forget()
        console.start()
        self._refresh_kill_all()
        return panel

    def _launch_sequential(self, leaves, group=None, group_color=None):
        """Enchaine les commandes (dependsOrder: sequence)."""
        def run_next(index):
            if index >= len(leaves):
                return
            panel = self._launch_leaf(leaves[index], group, group_color)

            def watch():
                console = panel.console
                if console.is_running() or console.returncode is None:
                    self.after(WATCH_MS, watch)
                    return
                if console.returncode == 0:
                    run_next(index + 1)

            self.after(WATCH_MS, watch)

        run_next(0)

    # -- Arret / fermeture ---------------------------------------------------
    def _restart_panel(self, panel):
        """Relance la commande dans le même onglet (nouveau process)."""
        old = panel.console
        if old.is_running():
            old.kill()
        old.cleanup()
        console = self._make_console(old.label, old.spec)
        panel.attach_console(console)
        self.consoles.set_tab_status(panel, crashed=False)
        console.start()

    def _close_panel(self, panel):
        if panel.console.is_running():
            panel.console.kill()
        panel.console.cleanup()
        try:
            self.consoles.forget(panel)
        except tk.TclError:
            pass
        if panel in self.panels:
            self.panels.remove(panel)
        panel.destroy()
        if not self.panels:
            self._empty.place(relx=0.5, rely=0.55, anchor="center")
        self._refresh_kill_all()

    def _confirm(self, question):
        """Demande confirmation, sauf si l'option est désactivée."""
        if not self.settings.confirm_bulk:
            return True
        return messagebox.askyesno("Confirmer", question)

    def kill_all(self):
        running = [p for p in self.panels if p.console.is_running()]
        if not running:
            return
        if not self._confirm(f"Arrêter {len(running)} console(s) en cours ?"):
            return
        for p in running:
            p.console.kill()
        self._refresh_kill_all()

    def close_all(self):
        if not self.panels:
            return
        if not self._confirm(f"Fermer {len(self.panels)} console(s) ?"):
            return
        for p in list(self.panels):
            self._close_panel(p)

    def restart_all(self):
        if not self.panels:
            return
        if not self._confirm(f"Redémarrer {len(self.panels)} console(s) ?"):
            return
        for p in list(self.panels):
            self._restart_panel(p)
        self._refresh_kill_all()

    # -- Actions exposées au menu --------------------------------------------
    def open_project(self, path):
        """Sélectionne un projet (depuis l'historique) et recharge ses tasks."""
        self.project.set(path)
        self.reload_tasks()

    def open_project_folder(self):
        """Ouvre le dossier du projet courant dans l'explorateur."""
        path = self.project.get().strip()
        if path and os.path.isdir(path):
            try:
                os.startfile(path)  # noqa: S606 (Windows)
            except OSError:
                pass

    def _current_console(self):
        panel = self.consoles.current()
        return panel if isinstance(panel, ConsolePanel) else None

    def zoom_current(self, delta):
        panel = self._current_console()
        if panel:
            panel.zoom(delta)

    def reset_zoom_current(self):
        panel = self._current_console()
        if panel:
            panel.reset_zoom()

    def copy_current_output(self):
        panel = self._current_console()
        if panel:
            panel.copy_output()

    def clear_current(self):
        panel = self._current_console()
        if panel:
            panel.clear()

    def shutdown(self):
        """Tue tous les process au moment de fermer l'application."""
        for panel in self.panels:
            if panel.console.is_running():
                panel.console.kill()
            panel.console.cleanup()

    # -- Boucle de drainage des sorties --------------------------------------
    def _poll(self):
        for panel in list(self.panels):
            for kind, payload in self._drain(panel.console.queue):
                if kind == EVENT_OUTPUT:
                    panel.append(payload)
                elif kind == EVENT_EXIT:
                    panel.set_exited(payload)
                    panel.console.cleanup()
                    self.consoles.set_tab_status(panel, crashed=payload != 0)
        self._refresh_kill_all()
        self.after(POLL_MS, self._poll)

    def _refresh_kill_all(self):
        has_running = any(p.console.is_running() for p in self.panels)
        self._kill_all_btn.set_enabled(has_running)
        self._close_all_btn.set_enabled(bool(self.panels))
        self._restart_all_btn.set_enabled(bool(self.panels))
        self._refresh_task_status()

    @staticmethod
    def _drain(q):
        items = []
        try:
            while True:
                items.append(q.get_nowait())
        except queue.Empty:
            pass
        return items
