"""Widgets a coins arrondis dessines sur ``Canvas``.

Tkinter/ttk ne gere pas le ``border-radius`` : on redessine donc nous-memes
un onglet (``_RoundedTab``), un conteneur d'onglets (``RoundedNotebook``) et
une carte/cadre (``RoundedFrame``) sur des ``Canvas``.
"""

import tkinter as tk

from taskpilot.ui import theme
from taskpilot.ui.widgets import (
    _round_bottom_points, _round_rect_points, add_tooltip, draw_centered_label,
    widget_bg)


def _round_top_points(x1, y1, x2, y2, r):
    """Points d'un rectangle a coins HAUT arrondis, bas carre (onglet)."""
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,   # bord haut + coin HD
        x2, y2, x2, y2, x2, y2,                       # coin BD carre
        x1, y2, x1, y2, x1, y2,                       # coin BG carre
        x1, y1 + r, x1, y1,                           # cote gauche + coin HG
    ]


class _RoundedTab(tk.Canvas):
    """Un onglet : pilule (par defaut) ou facon terminal (haut arrondi)."""

    def __init__(self, parent, text, command, *, radius, font,
                 bg_idle, bg_sel, fg_idle, fg_sel, pad_x=14, pad_y=7,
                 top_only=False, accent=None, bg_hover=None):
        self._font = theme.get_font(font)
        self._tw = self._font.measure(text) + 2 * pad_x
        self._th = self._font.metrics("linespace") + 2 * pad_y
        super().__init__(parent, width=self._tw, height=self._th,
                         bg=widget_bg(parent), highlightthickness=0, bd=0,
                         cursor="hand2", takefocus=0)
        self._text = text
        self._radius = radius
        self._bg_idle, self._bg_sel = bg_idle, bg_sel
        self._bg_hover = bg_hover or bg_sel
        self._fg_idle, self._fg_sel = fg_idle, fg_sel
        self._shape = _round_top_points if top_only else _round_rect_points
        self._accent = accent
        self._selected = False
        self._hovered = False
        self._draw()
        self.bind("<Button-1>", lambda _e: command())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _on_enter(self, _e):
        self._hovered = True
        if not self._selected:
            self._draw()

    def _on_leave(self, _e):
        self._hovered = False
        if not self._selected:
            self._draw()

    def _draw(self):
        self.delete("all")
        if self._selected:
            fill = self._bg_sel
        elif self._hovered:
            fill = self._bg_hover
        else:
            fill = self._bg_idle
        fg = self._fg_sel if self._selected else self._fg_idle
        # Un onglet terminal touche le bas du canvas (pas de marge en bas).
        y2 = self._th if self._shape is _round_top_points else self._th - 2
        self.create_polygon(
            self._shape(2, 2, self._tw - 2, y2, self._radius),
            smooth=True, splinesteps=24, fill=fill, outline=fill)
        # Liseré d'accent sur le bord plat du haut (entre les deux coins
        # arrondis), pour ne pas deborder des arrondis de l'onglet.
        if self._selected and self._accent:
            self.create_rectangle(
                2 + self._radius, 2, self._tw - 2 - self._radius, 5,
                fill=self._accent, outline=self._accent)
        draw_centered_label(self, self._text, self._font,
                            self._tw / 2, self._th / 2, fg)

    def set_selected(self, selected: bool):
        self._selected = bool(selected)
        self._draw()


class RoundedNotebook(tk.Frame):
    """Notebook minimaliste : barre d'onglets en pilules + pages empilees.

    Expose une API compatible avec l'usage qu'en fait l'app :
    ``add(child, text=...)``, ``select(child)``, ``forget(child)``.
    Les pages sont creees avec ce widget comme parent puis placees en grille
    (toutes dans la meme cellule, on releve la page active avec ``tkraise``).
    """

    def __init__(self, parent, *, bg=theme.BG, tab_bg=theme.HEAD,
                 tab_sel=theme.BG_ALT, tab_fg=theme.FG,
                 tab_sel_fg=theme.ACCENT, radius=theme.TAB_RADIUS,
                 font=theme.FONT_UI_BOLD, tab_gap=4, top_only=False,
                 tab_accent=None):
        super().__init__(parent, bg=bg)
        self._tab_opts = dict(radius=radius, font=font, bg_idle=tab_bg,
                              bg_sel=tab_sel, fg_idle=tab_fg, fg_sel=tab_sel_fg,
                              top_only=top_only, accent=tab_accent)
        self._gap = tab_gap
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        # Bandeau d'onglets defilant horizontalement : un Canvas (fenetre
        # visible) contenant le Frame des onglets (potentiellement plus large).
        self._tabcanvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0,
                                    takefocus=0, xscrollincrement=12)
        self._tabcanvas.grid(row=0, column=0, sticky="ew",
                            pady=(0, 0 if top_only else 6))
        self._tabbar = tk.Frame(self._tabcanvas, bg=bg)
        self._tabwin = self._tabcanvas.create_window(
            0, 0, window=self._tabbar, anchor="nw")
        self._tabbar.bind("<Configure>", self._on_tabbar_configure)
        self._tabcanvas.bind("<MouseWheel>", self._on_tab_wheel)
        self._tabbar.bind("<MouseWheel>", self._on_tab_wheel)
        self._pages = []          # liste de dict(child, tab)
        self._current = None
        self._on_change = None

    # -- API ----------------------------------------------------------------
    def add(self, child, text="", tooltip=None):
        tab = _RoundedTab(self._tabbar, text, lambda c=child: self.select(c),
                          **self._tab_opts)
        tab.pack(side="left", padx=(0, self._gap))
        tab.bind("<MouseWheel>", self._on_tab_wheel)
        if tooltip:
            add_tooltip(tab, tooltip)
        child.grid(row=1, column=0, sticky="nsew")
        self._pages.append({"child": child, "tab": tab})
        if self._current is None:
            self.select(child)
        else:
            self._raise_current()

    def select(self, child):
        self._current = child
        selected_tab = None
        for page in self._pages:
            selected = page["child"] is child
            page["tab"].set_selected(selected)
            if selected:
                selected_tab = page["tab"]
                page["child"].tkraise()
        if selected_tab is not None:
            self._scroll_into_view(selected_tab)
        if self._on_change:
            self._on_change(child)

    def forget(self, child):
        idx = next((i for i, p in enumerate(self._pages)
                    if p["child"] is child), None)
        if idx is None:
            return
        page = self._pages.pop(idx)
        page["tab"].destroy()
        page["child"].grid_forget()
        if self._current is child:
            self._current = None
            if self._pages:
                fallback = self._pages[min(idx, len(self._pages) - 1)]["child"]
                self.select(fallback)

    def tabs(self):
        return [p["child"] for p in self._pages]

    def current(self):
        """Page actuellement sélectionnée (ou ``None``)."""
        return self._current

    def on_change(self, callback):
        self._on_change = callback

    # -- Interne ------------------------------------------------------------
    def _raise_current(self):
        for page in self._pages:
            if page["child"] is self._current:
                page["child"].tkraise()

    def _on_tabbar_configure(self, _event=None):
        # La zone defilable et la hauteur du canvas suivent le contenu.
        w = self._tabbar.winfo_reqwidth()
        h = self._tabbar.winfo_reqheight()
        self._tabcanvas.configure(scrollregion=(0, 0, w, h), height=h)

    def _overflowing(self) -> bool:
        return self._tabbar.winfo_reqwidth() > self._tabcanvas.winfo_width()

    def _on_tab_wheel(self, event):
        # Molette -> selection de la console precedente / suivante.
        self._select_relative(-1 if event.delta > 0 else 1)
        return "break"

    def _select_relative(self, step):
        """Selectionne la console decalee de ``step`` (cyclique)."""
        if not self._pages:
            return
        idx = next((i for i, p in enumerate(self._pages)
                    if p["child"] is self._current), 0)
        idx = (idx + step) % len(self._pages)
        self.select(self._pages[idx]["child"])

    def _scroll_into_view(self, tab):
        """Fait defiler le bandeau pour que l'onglet ``tab`` soit visible."""
        self.update_idletasks()
        total = self._tabbar.winfo_reqwidth()
        canvas_w = self._tabcanvas.winfo_width()
        if total <= canvas_w or canvas_w <= 1:
            return
        x1 = tab.winfo_x()
        x2 = x1 + tab.winfo_width()
        view_left = self._tabcanvas.canvasx(0)
        view_right = view_left + canvas_w
        if x1 < view_left:
            self._tabcanvas.xview_moveto(x1 / total)
        elif x2 > view_right:
            self._tabcanvas.xview_moveto((x2 - canvas_w) / total)


class RoundedFrame(tk.Canvas):
    """Carte a fond arrondi (optionnellement bordee).

    Le contenu doit etre cree avec ``card.inner`` comme parent ; il est
    encastre via une fenetre Canvas redimensionnee a chaque ``<Configure>``.
    """

    def __init__(self, parent, *, bg, radius=theme.CARD_RADIUS, border=None,
                 border_width=1, inset=None, corners="all",
                 inset_top=None, inset_bottom=None,
                 inset_left=None, inset_right=None):
        super().__init__(parent, bg=widget_bg(parent), highlightthickness=0,
                         bd=0)
        self._bg = bg
        self._radius = radius
        self._border = border
        self._bw = border_width if border else 0
        self._shape = {"top": _round_top_points,
                       "bottom": _round_bottom_points}.get(
                           corners, _round_rect_points)
        # Marges internes : par defaut le rayon (pour que les coins arrondis
        # restent visibles autour du contenu rectangulaire), surchargeables
        # cote par cote. Un cote a 0 colle le contenu au bord : utile pour
        # souder une carte a coins arrondis d'un seul cote a un voisin.
        base = radius if inset is None else inset
        self._inset_t = base if inset_top is None else inset_top
        self._inset_b = base if inset_bottom is None else inset_bottom
        self._inset_l = base if inset_left is None else inset_left
        self._inset_r = base if inset_right is None else inset_right
        self.inner = tk.Frame(self, bg=bg)
        self._win = self.create_window(0, 0, window=self.inner, anchor="nw")
        self._last_size = (0, 0)     # derniere taille pour laquelle on a dessine
        self._redraw_id = None       # redessin du cadre coalisce (debounce)
        self.bind("<Configure>", self._on_configure)
        # Un Canvas ne se dimensionne pas sur son contenu : on demande nous-meme
        # la taille du contenu (+ marges). Un pack ``expand=True`` etirera la
        # carte au-dela ; un simple ``fill="x"`` la fera epouser sa hauteur.
        self.inner.bind("<Configure>", self._sync_request)

    def _sync_request(self, _event=None):
        self.configure(
            width=self.inner.winfo_reqwidth() + self._inset_l + self._inset_r,
            height=self.inner.winfo_reqheight() + self._inset_t + self._inset_b)

    def _on_configure(self, event):
        w, h = event.width, event.height
        # Repositionner le contenu est peu couteux : toujours immediat.
        self.coords(self._win, self._inset_l, self._inset_t)
        self.itemconfigure(
            self._win, width=max(w - self._inset_l - self._inset_r, 1),
            height=max(h - self._inset_t - self._inset_b, 1))
        # Le cadre arrondi (spline) est couteux : on coalisce les rafales
        # d'evenements <Configure> d'un redimensionnement en un seul redessin.
        if (w, h) == self._last_size:
            return
        self._last_size = (w, h)
        if self._redraw_id is not None:
            self.after_cancel(self._redraw_id)
        self._redraw_id = self.after(16, self._redraw_border)

    def _redraw_border(self):
        self._redraw_id = None
        w, h = self._last_size
        self.delete("rect")
        pad = max(self._bw, 1)
        self.create_polygon(
            self._shape(pad, pad, w - pad, h - pad, self._radius),
            smooth=True, splinesteps=24, fill=self._bg,
            outline=self._border or self._bg, width=self._bw, tags="rect")
        self.tag_lower("rect")
