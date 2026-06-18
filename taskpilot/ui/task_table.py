"""Liste des tasks : tableau custom (pastille + nom + type colore) soude a son
bouton d'action principal, pour reproduire fidelement la maquette.

Un ``ttk.Treeview`` ne sait pas colorer une colonne differemment du reste de la
ligne ni se souder sans marge a un bouton aux coins arrondis ; on reconstruit
donc la liste a partir de simples ``Frame``/``Label``, ce qui donne un controle
total sur la couleur de la colonne Type et sur la soudure visuelle.
"""

import tkinter as tk
from tkinter import ttk

from taskpilot.ui import theme
from taskpilot.ui.icons import build_status_dot
from taskpilot.ui.rounded import RoundedFrame
from taskpilot.ui.widgets import RoundedButton

#: Periode de pulsation des pastilles des tasks en cours (ms).
PULSE_MS = 650
#: Largeurs fixes (px) des colonnes pastille et Type.
DOT_COL_W = 26
TYPE_COL_W = 78


class TaskTable(tk.Frame):
    """Liste de tasks (pastille d'etat, nom, type) + bouton « Lancer » soude."""

    def __init__(self, parent, *, on_run, on_select=None):
        super().__init__(parent, bg=theme.BG)
        self._on_run = on_run
        self._on_select = on_select
        self._rows = {}            # label -> dict(widgets, dot, type_label)
        self._order = []           # labels dans l'ordre d'affichage
        self._selected = None
        self._hovered = None
        self._running = set()
        self._pulse_bright = True

        self._dot_run = build_status_dot(self, theme.DOT_RUNNING)
        self._dot_run_dim = build_status_dot(self, theme.DOT_RUNNING_DIM)
        self._dot_idle = build_status_dot(self, theme.DOT_IDLE)

        self._build()
        self._pulse()

    # -- Construction --------------------------------------------------------
    def _build(self):
        # Conteneur liste : coins arrondis EN HAUT seulement (le bas, carre, se
        # soude au bouton place juste dessous). Le fond de la carte reprend la
        # couleur de l'en-tete : la marge haute (= rayon) la prolonge jusqu'au
        # bord arrondi, sans laisser deborder de coin carre. Bas a 0 pour la
        # soudure ; cotes a 1 px pour laisser voir le liseré.
        card = RoundedFrame(self, bg=theme.TASKLIST_HEAD,
                            border=theme.TASKLIST_BORDER, radius=8,
                            corners="top", inset_top=8, inset_bottom=2,
                            inset_left=2, inset_right=2)
        card.pack(fill="both", expand=True)
        wrap = card.inner

        # En-tete Task / Type.
        head = tk.Frame(wrap, bg=theme.TASKLIST_HEAD)
        head.pack(fill="x")
        tk.Frame(head, bg=theme.TASKLIST_HEAD, width=DOT_COL_W).pack(side="left")
        self._type_head = tk.Label(
            head, text="Type", bg=theme.TASKLIST_HEAD, fg=theme.TASKLIST_HEAD_FG,
            font=theme.FONT_UI_BOLD, width=9, anchor="center", pady=6)
        self._type_head.pack(side="right")
        tk.Label(head, text="Task", bg=theme.TASKLIST_HEAD,
                 fg=theme.TASKLIST_HEAD_FG, font=theme.FONT_UI_BOLD,
                 anchor="center", pady=6).pack(side="left", expand=True)
        tk.Frame(wrap, bg=theme.TASKLIST_SEP, height=1).pack(fill="x")

        # Corps defilant : un Canvas contient le Frame des lignes.
        body = tk.Frame(wrap, bg=theme.TASKLIST_BG)
        body.pack(fill="both", expand=True)
        self._canvas = tk.Canvas(body, bg=theme.TASKLIST_BG,
                                 highlightthickness=0, bd=0)
        self._canvas.pack(side="left", fill="both", expand=True)
        self._scroll = ttk.Scrollbar(body, orient="vertical",
                                     command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scroll.set)
        self._rowframe = tk.Frame(self._canvas, bg=theme.TASKLIST_BG)
        self._rowwin = self._canvas.create_window(
            0, 0, window=self._rowframe, anchor="nw")
        self._rowframe.bind("<Configure>", self._on_rows_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_wheel(self._canvas)
        self._bind_wheel(self._rowframe)

        # Bouton principal soude : coins arrondis EN BAS, sans bordure haute.
        self._run_btn = RoundedButton(
            self, "▶ Lancer la task", lambda: self._on_run(),
            bg=theme.RUN_BG, hover=theme.RUN_HOVER, fg=theme.RUN_FG,
            radius=8, corners="bottom", stretch=True, pady=11)
        self._run_btn.pack(fill="x")

    # -- Defilement ----------------------------------------------------------
    def _bind_wheel(self, widget):
        widget.bind("<MouseWheel>", self._on_wheel)

    def _on_wheel(self, event):
        if self._rowframe.winfo_reqheight() > self._canvas.winfo_height():
            self._canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _on_rows_configure(self, _event=None):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))
        self._update_scrollbar()

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(self._rowwin, width=event.width)
        self._update_scrollbar()

    def _update_scrollbar(self):
        need = self._rowframe.winfo_reqheight() > self._canvas.winfo_height()
        mapped = bool(self._scroll.winfo_ismapped())
        if need and not mapped:
            self._scroll.pack(side="right", fill="y")
        elif not need and mapped:
            self._scroll.pack_forget()

    # -- Donnees -------------------------------------------------------------
    def set_tasks(self, items):
        """Reconstruit les lignes. ``items`` : liste de ``(label, type)``."""
        for child in self._rowframe.winfo_children():
            child.destroy()
        self._rows.clear()
        self._order.clear()
        for label, ttype in items:
            self._add_row(label, ttype)
        if self._selected not in self._rows:
            self._selected = None
        self._hovered = None
        for label in self._order:
            self._paint_row(label)

    def _add_row(self, label, ttype):
        bg = theme.TASKLIST_BG
        row = tk.Frame(self._rowframe, bg=bg, cursor="hand2")
        row.pack(fill="x")

        holder = tk.Frame(row, bg=bg, width=DOT_COL_W, height=24)
        holder.pack(side="left")
        holder.pack_propagate(False)
        dot = tk.Label(holder, image=self._dot_idle, bg=bg)
        dot.pack(side="left", padx=(12, 0))

        type_lbl = tk.Label(row, text=ttype, bg=bg, fg=theme.TYPE_FG,
                            font=theme.FONT_UI, width=9, anchor="e", padx=8)
        type_lbl.pack(side="right")
        name_lbl = tk.Label(row, text=label, bg=bg, fg=theme.FG,
                            font=theme.FONT_UI, anchor="w", pady=4)
        name_lbl.pack(side="left", fill="x", expand=True)

        widgets = (row, holder, dot, name_lbl, type_lbl)
        for w in widgets:
            w.bind("<Enter>", lambda _e, lbl=label: self._enter(lbl))
            w.bind("<Leave>", lambda _e, lbl=label: self._leave(lbl))
            w.bind("<Button-1>", lambda _e, lbl=label: self.select(lbl))
            w.bind("<Double-1>", lambda _e: self._on_run())
            self._bind_wheel(w)
        self._rows[label] = {"widgets": widgets, "dot": dot,
                             "type": type_lbl, "name": name_lbl}
        self._order.append(label)

    # -- Etat des lignes -----------------------------------------------------
    def _row_bg(self, label):
        if label == self._selected:
            return theme.TASKLIST_SEL
        if label == self._hovered:
            return theme.TASKLIST_HOVER
        return theme.TASKLIST_BG

    def _paint_row(self, label):
        info = self._rows.get(label)
        if not info:
            return
        bg = self._row_bg(label)
        for w in info["widgets"]:
            try:
                w.config(bg=bg)
            except tk.TclError:
                pass
        info["dot"].config(image=self._dot_for(label))

    def _enter(self, label):
        self._hovered = label
        self._paint_row(label)

    def _leave(self, label):
        if self._hovered == label:
            self._hovered = None
        self._paint_row(label)

    def select(self, label):
        prev = self._selected
        self._selected = label
        if prev and prev != label:
            self._paint_row(prev)
        self._paint_row(label)
        if self._on_select:
            self._on_select(label)

    # -- Pastilles d'etat ----------------------------------------------------
    def _dot_for(self, label):
        if label not in self._running:
            return self._dot_idle
        return self._dot_run if self._pulse_bright else self._dot_run_dim

    def set_running(self, running):
        """Met a jour l'ensemble des labels dont un process tourne."""
        running = set(running)
        if running == self._running:
            return
        self._running = running
        self._repaint_dots()

    def _repaint_dots(self):
        for label, info in self._rows.items():
            info["dot"].config(image=self._dot_for(label))

    def _pulse(self):
        if self._running:
            self._pulse_bright = not self._pulse_bright
            self._repaint_dots()
        self.after(PULSE_MS, self._pulse)

    # -- API facon Treeview (utilisee par TasksTab) --------------------------
    def selection(self):
        return [self._selected] if self._selected else []

    def selection_set(self, label):
        if label in self._rows:
            self.select(label)
