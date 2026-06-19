"""Barre de menus custom au thème sombre.

``tk.Menu`` natif s'affiche avec le thème clair de l'OS sous Windows, ce qui
jure avec le reste de l'interface. On redessine donc une barre (``MenuBar``),
ses menus déroulants (``_Popup``) et leurs entrées sur des widgets Tk simples,
en réutilisant la palette de ``theme``.
"""

import tkinter as tk

from taskpilot.ui import theme

#: Fond des menus déroulants et couleur de survol d'une entrée.
_POPUP_BG = theme.BG_ALT
_HOVER_BG = theme.SEL
_DISABLED_FG = "#5a5a5a"


class _MenuBuilder:
    """Collecte les entrées d'un menu / sous-menu (API façon ``tk.Menu``)."""

    def __init__(self):
        self.items = []

    def add_command(self, label, command, *, accelerator=None):
        """Ajoute une commande. ``command`` à ``None`` => entrée désactivée."""
        self.items.append({"type": "command", "label": label,
                           "command": command, "accel": accelerator})

    def add_separator(self):
        self.items.append({"type": "separator"})

    def add_checkbutton(self, label, variable, command=None):
        self.items.append({"type": "check", "label": label,
                           "variable": variable, "command": command})

    def add_color(self, color, command, *, label=None, selected=False):
        """Ajoute une entree affichant un echantillon de couleur (selecteur).

        ``color`` vide => pastille « aucune couleur ». ``selected`` coche
        l'entree correspondant a la couleur courante.
        """
        self.items.append({"type": "color", "color": color, "command": command,
                           "label": label if label is not None else color,
                           "selected": selected})

    def add_submenu(self, label, populate=None):
        """Sous-menu. ``populate(builder)`` (optionnel) le remplit à l'ouverture
        (contenu dynamique, ex. projets récents)."""
        sub = _MenuBuilder()
        self.items.append({"type": "submenu", "label": label,
                           "builder": sub, "populate": populate})
        return sub


class MenuBar(tk.Frame):
    """Barre de menus horizontale au thème sombre."""

    def __init__(self, parent, *, bg=theme.HEAD):
        super().__init__(parent, bg=bg)
        self._bg = bg
        self._menus = []          # dict(label, builder, header)
        self._active = None       # index du menu ouvert, ou None
        self._popups = []         # _Popup actuellement affichés
        # Referme les menus si on clique n'importe où ailleurs.
        self.bind_all("<Button-1>", self._on_global_click, add="+")

    # -- Construction --------------------------------------------------------
    def add_menu(self, label) -> _MenuBuilder:
        builder = _MenuBuilder()
        header = tk.Label(self, text=label, bg=self._bg, fg=theme.FG,
                          font=theme.get_font(theme.FONT_UI),
                          padx=10, pady=4, cursor="hand2")
        header.pack(side="left")
        idx = len(self._menus)
        header.bind("<Button-1>", lambda _e, i=idx: self._toggle(i))
        header.bind("<Enter>", lambda _e, i=idx: self._on_header_enter(i))
        header.bind("<Leave>", lambda _e, i=idx: self._on_header_leave(i))
        self._menus.append({"label": label, "builder": builder,
                            "header": header})
        return builder

    # -- Ouverture / fermeture ----------------------------------------------
    def _toggle(self, i):
        if self._active == i:
            self._close_all()
        else:
            self._open(i)
        return "break"

    def _open(self, i):
        self._close_all()
        self._active = i
        menu = self._menus[i]
        header = menu["header"]
        header.config(bg=_HOVER_BG)
        x = header.winfo_rootx()
        y = header.winfo_rooty() + header.winfo_height()
        self._popups.append(_Popup(self, menu["builder"].items, x, y))

    def _close_all(self):
        for popup in self._popups:
            try:
                popup.destroy()
            except tk.TclError:
                pass
        self._popups = []
        if self._active is not None:
            self._menus[self._active]["header"].config(bg=self._bg)
            self._active = None

    # -- Survol des en-têtes -------------------------------------------------
    def _on_header_enter(self, i):
        if self._active is None:
            self._menus[i]["header"].config(bg=_HOVER_BG)
        elif self._active != i:
            self._open(i)            # navigation entre menus, comme un vrai menu

    def _on_header_leave(self, i):
        if self._active != i:
            self._menus[i]["header"].config(bg=self._bg)

    # -- Clic en dehors ------------------------------------------------------
    def _on_global_click(self, event):
        if self._active is None and not self._popups:
            return
        node = event.widget
        while node is not None:
            if node is self or node in self._popups:
                return               # clic dans la barre ou un menu : on garde
            node = getattr(node, "master", None)
        self._close_all()


class PopupMenu(tk.Frame):
    """Menu déroulant autonome (hors barre de menus) au même style sombre.

    Sert pour un bouton qui ouvre une liste de choix (ex. « + Console »). Le
    widget lui-même n'est jamais affiché : il sert d'hôte (master du Toplevel)
    et expose l'API (``_popups`` / ``_close_all``) attendue par ``_Popup``.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self._builder = _MenuBuilder()
        self._popups = []
        self._bound = False
        self._anchor = None

    def add_command(self, label, command, *, accelerator=None):
        self._builder.add_command(label, command, accelerator=accelerator)

    def add_separator(self):
        self._builder.add_separator()

    def add_color(self, color, command, *, label=None, selected=False):
        self._builder.add_color(color, command, label=label, selected=selected)

    def clear(self):
        """Vide les entrees (utile pour reconstruire le menu a chaque ouverture)."""
        self._builder.items = []

    def is_open(self):
        return bool(self._popups)

    def hide(self):
        self._close_all()

    def show(self, x, y, anchor=None):
        """Affiche le menu, coin haut-gauche en (x, y) écran.

        ``anchor`` est le widget déclencheur (ex. le bouton « + Console ») : un
        clic dessus est ignoré par le handler global, sinon il rouvrirait puis
        refermerait aussitôt le menu (le binding bouton précède le binding
        toplevel dans l'ordre de propagation Tk).
        """
        self._close_all()
        self._anchor = anchor
        self._popups.append(_Popup(self, self._builder.items, x, y))
        if not self._bound:
            self.winfo_toplevel().bind("<Button-1>", self._on_global_click,
                                       add="+")
            self._bound = True

    def _close_all(self):
        for popup in self._popups:
            try:
                popup.destroy()
            except tk.TclError:
                pass
        self._popups = []

    def _on_global_click(self, event):
        if not self._popups:
            return
        node = event.widget
        while node is not None:
            if node in self._popups or node is self._anchor:
                return
            node = getattr(node, "master", None)
        self._close_all()


class _Popup(tk.Toplevel):
    """Un menu déroulant : liste d'entrées dans une fenêtre sans décoration."""

    def __init__(self, menubar, items, x, y):
        super().__init__(menubar)
        self.menubar = menubar
        self._child = None           # sous-menu ouvert, le cas échéant
        self.wm_overrideredirect(True)
        # Le Toplevel sert de fin liseré ; le Frame interne porte le fond.
        self.configure(bg=theme.CONSOLE_BORDER)
        self.inner = tk.Frame(self, bg=_POPUP_BG)
        self.inner.pack(padx=1, pady=1)
        for spec in items:
            self._add_row(spec)
        self.update_idletasks()
        # Recentre vers la gauche si le menu déborde de l'écran.
        if x + self.winfo_width() > self.winfo_screenwidth():
            x = max(0, self.winfo_screenwidth() - self.winfo_width())
        self.wm_geometry(f"+{x}+{y}")
        self.lift()

    # -- Entrées -------------------------------------------------------------
    def _add_row(self, spec):
        if spec["type"] == "separator":
            tk.Frame(self.inner, bg=theme.CONSOLE_BORDER, height=1).pack(
                fill="x", padx=6, pady=3)
            return

        disabled = spec["type"] == "command" and not spec.get("command")
        fg = _DISABLED_FG if disabled else theme.FG
        row = tk.Frame(self.inner, bg=_POPUP_BG,
                       cursor="arrow" if disabled else "hand2")
        row.pack(fill="x")

        widgets = [row]
        if spec["type"] == "color":
            # Echantillon de couleur a gauche ; un damier neutre figure « aucune ».
            swatch = tk.Frame(row, width=14, height=14,
                              bg=spec["color"] or theme.BTN,
                              highlightthickness=1,
                              highlightbackground=theme.CONSOLE_BORDER)
            swatch.pack_propagate(False)
            swatch.pack(side="left", padx=(12, 0), pady=4)
            swatch._is_swatch = True   # exclu du survol (garde sa couleur)
            widgets.append(swatch)

        prefix = ""
        if spec["type"] == "check":
            prefix = "✓  " if spec["variable"].get() else "      "
        pad_l = 8 if spec["type"] == "color" else 12
        left = tk.Label(row, text=prefix + spec["label"], bg=_POPUP_BG, fg=fg,
                        font=theme.get_font(theme.FONT_UI), anchor="w",
                        padx=pad_l, pady=4)
        left.pack(side="left", fill="x", expand=True)

        if spec["type"] == "color":
            right_text = "✓" if spec.get("selected") else ""
        else:
            right_text = ("▸" if spec["type"] == "submenu"
                          else (spec.get("accel") or ""))
        widgets.append(left)
        if right_text:
            right = tk.Label(row, text=right_text, bg=_POPUP_BG,
                             fg=theme.CONSOLE_MUTED,
                             font=theme.get_font(theme.FONT_UI), anchor="e",
                             padx=12, pady=4)
            right.pack(side="right")
            widgets.append(right)

        self._bind_row(widgets, spec, row, disabled, label=left)

    def _bind_row(self, widgets, spec, row, disabled, label=None):
        label = label or widgets[1]
        # L'echantillon de couleur garde sa propre couleur de fond au survol
        # (sinon le hover l'effacerait) : on ne recolore que les autres widgets.
        tinted = [w for w in widgets if not getattr(w, "_is_swatch", False)]

        def on_enter(_e=None):
            self._close_child()
            if not disabled:
                for w in tinted:
                    w.config(bg=_HOVER_BG)
                label.config(fg="#ffffff")
            if spec["type"] == "submenu":
                self._open_child(row, spec)

        def on_leave(_e=None):
            x, y = row.winfo_pointerxy()
            if row.winfo_containing(x, y) in widgets:
                return               # toujours sur la même entrée : pas de bascule
            for w in tinted:
                w.config(bg=_POPUP_BG)
            label.config(fg=_DISABLED_FG if disabled else theme.FG)

        for w in widgets:
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            if spec["type"] in ("command", "check", "color") and not disabled:
                w.bind("<Button-1>", lambda _e, s=spec: self._activate(s))

    # -- Actions -------------------------------------------------------------
    def _activate(self, spec):
        if spec["type"] == "check":
            spec["variable"].set(not spec["variable"].get())
            self.menubar._close_all()
            if spec.get("command"):
                spec["command"]()
        else:
            command = spec.get("command")
            self.menubar._close_all()
            if command:
                command()

    def _open_child(self, row, spec):
        builder = spec["builder"]
        if spec.get("populate") is not None:
            builder.items = []
            spec["populate"](builder)
        x = self.winfo_rootx() + self.winfo_width()
        y = row.winfo_rooty()
        self._child = _Popup(self.menubar, builder.items, x, y)
        self.menubar._popups.append(self._child)

    def _close_child(self):
        if self._child is not None:
            try:
                self.menubar._popups.remove(self._child)
            except ValueError:
                pass
            try:
                self._child.destroy()
            except tk.TclError:
                pass
            self._child = None
