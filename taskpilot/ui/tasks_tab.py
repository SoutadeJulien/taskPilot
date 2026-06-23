"""Onglet Tasks : selection du projet, lancement et consoles integrees."""

import os
import queue
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from taskpilot.core import logs
from taskpilot.core.pty_console import HAVE_PTY, PTY_IMPORT_ERROR, PtyConsole
from taskpilot.core.task_runner import EVENT_EXIT, EVENT_OUTPUT, TaskConsole
from taskpilot.core.vscode_tasks import (
    CommandSpec, build_task_tree, is_group_task, load_vscode_tasks, task_label,
    tree_leaves)
from taskpilot.ui import theme
from taskpilot.ui.console_panel import ConsolePanel, InteractiveConsolePanel
from taskpilot.ui.menubar import PopupMenu

try:
    # Émulateur de terminal (pyte) : présent dans l'exe, optionnel en dev.
    from taskpilot.ui.terminal_panel import TerminalPanel
    _TERMINAL_OK = HAVE_PTY
    #: Raison du fallback tube quand le vrai terminal est indisponible.
    _TERMINAL_ERROR = None if HAVE_PTY else PTY_IMPORT_ERROR
except Exception as _e:  # noqa: BLE001
    TerminalPanel = None
    _TERMINAL_OK = False
    _TERMINAL_ERROR = repr(_e)
from taskpilot.ui.rounded import RoundedFrame, RoundedNotebook
from taskpilot.ui.task_table import TaskTable
from taskpilot.ui.widgets import add_tooltip, make_button

#: Periode de drainage des sorties de consoles (ms).
POLL_MS = 120
#: Periode de drainage quand un backlog reste a vider : on repasse vite plutot
#: que d'inserer tout d'un coup, pour que l'UI reste reactive.
FAST_POLL_MS = 8
#: Plafond de texte (caracteres) insere par console et par tick. Au-dela, le
#: reste attend le prochain tour : une task tres bavarde (ou en boucle d'erreur)
#: ne peut plus geler l'application en saturant la boucle d'evenements.
MAX_CHARS_PER_TICK = 16 * 1024
#: Periode de surveillance pour l'enchainement sequentiel (ms).
WATCH_MS = 300
#: Longueur max d'un titre d'onglet de console.
MAX_TAB_TITLE = 22

#: Types de console vierge proposes : (libelle, argv interactif du shell).
#: Lancés derrière un vrai pseudo-terminal (ConPTY), d'où une invocation
#: naturelle plutôt que le mode « lecture de stdin ».
SHELL_TYPES = (
    ("PowerShell", ["powershell.exe", "-NoLogo"]),
    ("CMD", ["cmd.exe"]),
    ("Bash", ["bash", "-i"]),
)


class TasksTab(ttk.Frame):
    """Charge les tasks d'un projet et pilote leurs consoles."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.settings = app.settings
        self.tasks = []
        self.tasks_by_label = {}
        self.panels = []
        # id de groupe -> couleur (cyclee), restaurees depuis la config pour
        # garder la meme couleur d'une session a l'autre.
        self._group_colors = dict(self.settings.get_group_colors())

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
        # Pastille de couleur du projet : un clic ouvre le choix de couleur.
        # Elle identifie les consoles du projet (distinguer deux worktrees).
        self._color_swatch = tk.Frame(
            top, width=24, height=24, cursor="hand2", highlightthickness=1,
            highlightbackground=theme.CONSOLE_BORDER)
        self._color_swatch.pack_propagate(False)
        self._color_swatch.pack(side="left", padx=(0, 8))
        self._color_swatch.bind("<Button-1>", lambda _e: self._open_color_menu())
        add_tooltip(self._color_swatch,
                    "Couleur du projet : repère ses consoles\n"
                    "(utile pour distinguer deux worktrees)")
        self._color_menu = PopupMenu(self)
        self._update_color_swatch()
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

    # -- Couleur du projet (reperage des consoles) ---------------------------
    def _project_color(self):
        """Couleur choisie pour le projet courant (chaine vide si aucune)."""
        project = self.project.get().strip()
        return self.settings.get_project_color(project) if project else ""

    def _update_color_swatch(self):
        color = self._project_color()
        self._color_swatch.config(bg=color or theme.BTN)

    def _open_color_menu(self):
        # Bascule (referme si deja ouvert), comme le menu « + Console ».
        if self._color_menu.is_open():
            self._color_menu.hide()
            return
        project = self.project.get().strip()
        if not project:
            messagebox.showinfo("Info", "Choisis d'abord un projet.")
            return
        current = self.settings.get_project_color(project)
        self._color_menu.clear()
        self._color_menu.add_color(
            "", lambda: self._set_project_color(""),
            label="Aucune couleur", selected=not current)
        for c in theme.PROJECT_PALETTE:
            self._color_menu.add_color(
                c, lambda col=c: self._set_project_color(col),
                label=c, selected=(c == current))
        w = self._color_swatch
        self._color_menu.show(w.winfo_rootx(),
                              w.winfo_rooty() + w.winfo_height(), anchor=w)

    def _set_project_color(self, color):
        """Persiste la couleur et la repercute sur les consoles deja ouvertes."""
        project = self.project.get().strip()
        if not project:
            return
        self.settings.set_project_color(project, color)
        self._update_color_swatch()
        new = color or None
        for panel in self.panels:
            if getattr(panel, "project", None) != project:
                continue
            panel.set_project_color(new)
            # La barre d'onglet privilegie la couleur du projet (repli groupe).
            bar = new or getattr(panel, "group_color", None)
            self.consoles.set_tab_bar_color(panel, bar)

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
        # Bouton « + Console » : ouvre un menu de choix du type de shell.
        self._new_btn = make_button(
            hb, "＋ Console", self._popup_new_menu, accent=True)
        self._new_btn.pack(side="left", padx=(12, 0))
        add_tooltip(self._new_btn,
                    "Ouvrir une console interactive vierge (PowerShell, CMD, Bash)")
        self._new_menu = PopupMenu(self)
        for display, argv in SHELL_TYPES:
            self._new_menu.add_command(
                display, lambda d=display, a=argv: self.new_console(d, a))
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
        # Un peu d'air au-dessus de la barre d'onglets des consoles.
        self.consoles.pack(fill="both", expand=True, pady=(8, 0))
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
        self._update_color_swatch()
        # Recalcule tout de suite les pastilles « en cours » avec le filtre par
        # projet : sinon une task d'un worktree precedent (meme label) resterait
        # marquee active jusqu'au prochain tour de boucle.
        self._refresh_task_status()

    def _render_tasks(self):
        items = []
        for t in self.tasks:
            ttype = "groupe" if is_group_task(t) else t.get("type", "process")
            items.append((task_label(t), ttype))
        favorites = self.settings.get_favorites(self.project.get().strip())
        self.task_list.set_tasks(items, favorites)

    def _refresh_task_status(self):
        """Reactualise les pastilles des tasks dont un process tourne.

        On ne compte que les consoles lancees depuis le projet AFFICHE : deux
        worktrees exposent les memes labels, donc filtrer par projet evite
        qu'une task active dans l'un n'apparaisse active dans l'autre.
        """
        project = self.project.get().strip()
        running = {p.console.label for p in self.panels
                   if p.console.is_running()
                   and getattr(p, "project", None) == project}
        self.task_list.set_running(running)

    # -- Lancement -----------------------------------------------------------
    def run_selected(self):
        sel = self.task_list.selection()
        if not sel:
            messagebox.showinfo("Info", "Aucune task sélectionnée.")
            return
        self.launch_task(sel[0])

    def launch_task(self, label):
        project = self.project.get().strip()
        tree = build_task_tree(label, self.tasks_by_label, project)
        leaves = tree_leaves(tree)
        if not leaves:
            messagebox.showwarning(
                "Rien à lancer",
                f"La task « {label} » n'a pas de commande exécutable.")
            return
        # Le projet et sa couleur sont fixes au lancement (les lancements
        # sequentiels et leur surveillance s'etalant dans le temps, l'utilisateur
        # peut entre-temps changer le projet affiche).
        project_color = self.settings.get_project_color(project) or None
        # Une task composite (plusieurs commandes) forme un groupe : ses
        # consoles partagent une couleur et restent cote a cote.
        group = label if len(leaves) > 1 else None
        color = self._group_color(group) if group else None
        # Execute l'arbre en respectant l'ordre propre a chaque groupe :
        # une *sequence* attend la fin de chaque etape, un groupe *parallel*
        # lance tous ses enfants simultanement.
        self._run_node(tree, (project, group, color, project_color),
                       lambda ok: None)

    def _group_color(self, group):
        """Couleur stable pour un groupe (cyclee dans la palette)."""
        if group not in self._group_colors:
            palette = theme.GROUP_COLORS
            color = palette[len(self._group_colors) % len(palette)]
            self._group_colors[group] = color
            self.settings.set_group_color(group, color)
        return self._group_colors[group]

    def _make_console(self, label, spec):
        """Crée une console, avec journalisation fichier si l'option est active."""
        log_path = logs.new_log_path(label) if self.settings.save_logs else None
        return TaskConsole(label, spec, log_path=log_path)

    def _launch_leaf(self, leaf, project, group=None, group_color=None,
                     project_color=None):
        console = self._make_console(leaf.label, leaf.spec)
        panel = ConsolePanel(self.consoles, console, self._close_panel,
                             self._restart_panel)
        self._tag_panel(panel, project, group_color, project_color)
        title = (leaf.label if len(leaf.label) <= MAX_TAB_TITLE
                 else leaf.label[:MAX_TAB_TITLE - 1] + "…")
        # Barre d'onglet : couleur du projet en priorite (repere du worktree) ;
        # la couleur de groupe ne sert que de repli quand le projet n'en a pas.
        self.consoles.add(panel, text=title, tooltip=leaf.label,
                          group=group, group_color=project_color or group_color,
                          on_close=lambda p=panel: self._close_panel(p))
        self.consoles.select(panel)
        self.panels.append(panel)
        self._empty.place_forget()
        console.start()
        self._refresh_kill_all()
        return panel

    def _tag_panel(self, panel, project, group_color, project_color):
        """Rattache un panneau a son projet et applique son repere couleur."""
        panel.project = project
        panel.group_color = group_color
        panel.set_project_color(project_color)

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
                self.after(WATCH_MS, watch)
                return
            on_done(console.returncode == 0)
        self.after(WATCH_MS, watch)

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

    # -- Console interactive vierge ------------------------------------------
    def _popup_new_menu(self):
        # Clic sur le bouton : bascule (ferme si déjà ouvert, sinon ouvre).
        if self._new_menu.is_open():
            self._new_menu.hide()
            return
        b = self._new_btn
        self._new_menu.show(b.winfo_rootx(), b.winfo_rooty() + b.winfo_height(),
                            anchor=b)

    def new_console(self, display, argv):
        """Ouvre une console interactive vierge pour le shell choisi.

        Privilégie un vrai terminal (ConPTY + ``pyte``) ; à défaut (pywinpty
        absent), retombe sur une console ligne-à-ligne via tube.
        """
        project = self.project.get().strip()
        cwd = project or os.path.expanduser("~")
        project_color = self.settings.get_project_color(project) or None
        log_path = logs.new_log_path(display) if self.settings.save_logs else None
        if _TERMINAL_OK:
            spec = CommandSpec(argv=list(argv), shell=False, cwd=cwd, env=None,
                               display=display)
            console = PtyConsole(display, spec, log_path=log_path)
            panel = TerminalPanel(self.consoles, console, self._close_panel,
                                  self._restart_panel)
        else:
            spec = CommandSpec(argv=self._fallback_argv(argv), shell=False,
                               cwd=cwd, env=None, display=display)
            console = TaskConsole(display, spec, log_path=log_path,
                                  interactive=True)
            panel = InteractiveConsolePanel(self.consoles, console,
                                            self._close_panel, self._restart_panel)
        # Console vierge : pas de groupe, mais elle porte la couleur du projet.
        self._tag_panel(panel, project, None, project_color)
        self.consoles.add(panel, text=display, tooltip=f"Console {display}",
                          group_color=project_color,
                          on_close=lambda p=panel: self._close_panel(p))
        self.consoles.select(panel)
        self.panels.append(panel)
        self._empty.place_forget()
        console.start()
        if not _TERMINAL_OK:
            # Mode tube (stdin n'est pas un vrai TTY) : les programmes
            # interactifs/plein écran (claude, REPL…) basculent en mode
            # non-interactif et peuvent échouer. On l'indique explicitement.
            console.queue.put((EVENT_OUTPUT,
                               "⚠ Terminal PTY indisponible — mode tube : les "
                               "programmes interactifs (claude…) peuvent "
                               f"échouer.\n   Raison : {_TERMINAL_ERROR}\n"))
        panel.focus_input()
        self._refresh_kill_all()
        return panel

    @staticmethod
    def _fallback_argv(argv):
        """Adapte l'argv au mode tube (sans PTY) : PowerShell lit stdin."""
        if argv and "powershell" in argv[0].lower():
            return ["powershell.exe", "-NoLogo", "-NoProfile", "-Command", "-"]
        if argv and argv[0].lower().startswith("bash"):
            return ["bash"]
        return list(argv)

    def running_task_roots(self):
        """Couples ``(pid, label)`` des process racines encore en cours.

        Consommé par l'onglet Process pour reconstruire l'arbre des process de
        chaque task (et de chaque console interactive).
        """
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
        """Relance la commande dans le même onglet (nouveau process)."""
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
        backlog = False
        for panel in list(self.panels):
            chunk, more = self._drain(panel.console.queue, MAX_CHARS_PER_TICK)
            backlog = backlog or more
            # On regroupe les sorties contigues en UN seul append : insérer le
            # texte d'un bloc est bien moins couteux que des dizaines d'appels
            # (chacun forçant un recalcul de géométrie du widget).
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
                    self.consoles.set_tab_status(panel, crashed=payload != 0)
            if out:
                panel.append("".join(out))
        self._refresh_kill_all()
        # S'il reste de la sortie en file (task tres bavarde), on revient vite
        # au lieu d'inserer tout d'un bloc : la boucle d'evenements respire,
        # l'UI repond (on peut notamment fermer l'onglet, ce qui tue le process).
        self.after(FAST_POLL_MS if backlog else POLL_MS, self._poll)

    def _refresh_kill_all(self):
        has_running = any(p.console.is_running() for p in self.panels)
        self._kill_all_btn.set_enabled(has_running)
        self._close_all_btn.set_enabled(bool(self.panels))
        self._restart_all_btn.set_enabled(bool(self.panels))
        self._refresh_task_status()

    @staticmethod
    def _drain(q, max_chars):
        """Retire jusqu'a ``max_chars`` caracteres de sortie de la file.

        Retourne ``(items, backlog)`` ou ``backlog`` indique qu'il reste des
        elements non draines (plafond atteint). Les evenements hors sortie
        (ex. fin de process) ne comptent pas dans le plafond et passent toujours.
        """
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
