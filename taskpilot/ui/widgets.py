"""Widgets reutilisables : bouton a coins arrondis et fabrique associee."""

import tkinter as tk

from taskpilot.ui import theme


def widget_bg(widget: tk.Misc) -> str:
    """Couleur de fond du parent (pour fondre le canvas du bouton)."""
    try:
        return widget.cget("bg")
    except tk.TclError:
        return theme.BG


def draw_centered_label(canvas, text, font, cx, cy, fg, tag=None):
    """Dessine "<icone> <libelle>" centre, icone et texte alignes verticalement.

    Dans un seul ``create_text``, un emoji (police de secours) et le texte
    latin n'ont pas les memes metriques verticales et se desalignent. On les
    dessine donc separement, chacun ancre par son milieu gauche sur la meme
    ligne mediane ``cy``. ``tag`` (optionnel) est applique aux items crees pour
    pouvoir recolorer le texte ensuite via ``itemconfigure``.
    """
    opts = {"fill": fg, "font": font}
    if tag:
        opts["tags"] = tag
    head, sep, tail = text.partition(" ")
    if not tail:
        canvas.create_text(cx, cy, text=text, **opts)
        return
    gap = font.measure(" ")
    w_head = font.measure(head)
    total = w_head + gap + font.measure(tail)
    x = cx - total / 2
    canvas.create_text(x, cy, text=head, anchor="w", **opts)
    canvas.create_text(x + w_head + gap, cy, text=tail, anchor="w", **opts)


def _round_rect_points(x1, y1, x2, y2, r):
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def _round_bottom_points(x1, y1, x2, y2, r):
    """Points d'un rectangle a coins BAS arrondis, haut carre."""
    return [
        x1, y1, x1, y1, x1, y1,           # coin HG carre
        x2, y1, x2, y1, x2, y1,           # coin HD carre
        x2, y2 - r, x2, y2, x2 - r, y2,   # cote droit + coin BD
        x1 + r, y2, x1, y2, x1, y2 - r,   # bord bas + coin BG
    ]


class RoundedButton(tk.Canvas):
    """Bouton dessine sur un Canvas pour obtenir de vrais coins arrondis."""

    def __init__(self, parent, text, command=None, *, bg, hover, fg,
                 radius=theme.BTN_RADIUS, padx=16, pady=7, font=theme.FONT_UI,
                 stretch=False, corners="all"):
        self._font = theme.get_font(font)
        self._shape = (_round_bottom_points if corners == "bottom"
                       else _round_rect_points)
        # ``_w``/``_h`` sont reserves par Tkinter : on prefixe nos attributs.
        self._bw = self._font.measure(text) + 2 * padx
        self._bh = self._font.metrics("linespace") + 2 * pady
        super().__init__(parent, width=self._bw, height=self._bh,
                         bg=widget_bg(parent), highlightthickness=0,
                         bd=0, cursor="hand2", takefocus=0)
        self._command = command
        self._bg, self._hover, self._fg = bg, hover, fg
        self._radius = radius
        self._text = text
        self._enabled = True
        self._hovered = False
        # En mode etire (``stretch``), le bouton epouse la largeur que lui donne
        # son gestionnaire (pack ``fill="x"``) : on retesselle a chaque resize.
        self._stretch = stretch
        self._draw(bg, fg)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        if stretch:
            self.bind("<Configure>", self._on_resize)

    def _state_colors(self):
        """Couleurs (fond, texte) correspondant a l'etat courant."""
        if not self._enabled:
            return "#2a2a2d", "#5a5a5a"
        if self._hovered:
            return self._hover, self._fg
        return self._bg, self._fg

    def _on_resize(self, event):
        if event.width <= 1 or (event.width == self._bw
                                and event.height == self._bh):
            return
        self._bw, self._bh = event.width, event.height
        self._draw(*self._state_colors())

    def _draw(self, fill, fg):
        # Items crees une seule fois et tagues ; les changements d'etat (survol,
        # activation) ne font que recolorer via ``_set_colors`` plutot que de
        # retesseller le spline a chaque fois.
        self.delete("all")
        # Bouton soude (coins bas) : la forme touche les bords haut/gauche/droit
        # du canvas pour epouser la liste posee juste au-dessus.
        if self._shape is _round_bottom_points:
            box = (0, 0, self._bw, self._bh - 1)
        else:
            box = (2, 2, self._bw - 2, self._bh - 2)
        self.create_polygon(
            self._shape(*box, self._radius),
            smooth=True, splinesteps=24, fill=fill, outline=fill, tags="bg")
        draw_centered_label(self, self._text, self._font,
                            self._bw / 2, self._bh / 2, fg, tag="fg")

    def _set_colors(self, fill, fg):
        self.itemconfigure("bg", fill=fill, outline=fill)
        self.itemconfigure("fg", fill=fg)

    def _on_click(self, _):
        if self._enabled and self._command:
            self._command()

    def _on_enter(self, _):
        self._hovered = True
        if self._enabled:
            self._set_colors(self._hover, self._fg)

    def _on_leave(self, _):
        self._hovered = False
        if self._enabled:
            self._set_colors(self._bg, self._fg)

    def _apply_state(self):
        """Recolore selon l'etat courant (active/desactive, survole ou non)."""
        self._set_colors(*self._state_colors())

    def set_enabled(self, enabled: bool):
        enabled = bool(enabled)
        # Idempotent : appele en boucle par le poll des consoles, il ne doit
        # rien faire si l'etat n'a pas change, sinon il ecraserait la couleur
        # de survol courante (hover qui "clignote").
        if enabled == self._enabled:
            return
        self._enabled = enabled
        self.config(cursor="hand2" if enabled else "arrow")
        self._apply_state()


class Tooltip:
    """Infobulle affichee au survol d'un widget (après un court délai)."""

    def __init__(self, widget, text, *, delay=450):
        self.widget = widget
        self._text = text
        self._delay = delay
        self._after_id = None
        self._tip = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<Button-1>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def set_text(self, text):
        """Met a jour le libelle (utile pour un onglet renomme)."""
        self._text = text
        if self._tip is not None:
            self._hide()

    def _schedule(self, _e=None):
        self._cancel()
        if self._text:
            self._after_id = self.widget.after(self._delay, self._show)

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self):
        if self._tip is not None or not self._text:
            return
        try:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except tk.TclError:
            return
        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        # Fin liseré : le Toplevel sert de bordure, le Label de fond.
        self._tip.configure(bg=theme.CONSOLE_BORDER)
        tk.Label(self._tip, text=self._text, bg=theme.BG_ALT, fg=theme.FG,
                 font=theme.get_font(theme.FONT_UI), padx=8, pady=4,
                 justify="left").pack(padx=1, pady=1)
        self._tip.update_idletasks()
        x -= self._tip.winfo_width() // 2
        self._tip.wm_geometry(f"+{max(x, 0)}+{y}")

    def _hide(self, _e=None):
        self._cancel()
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None


def add_tooltip(widget, text, **kwargs) -> Tooltip:
    """Attache une infobulle a ``widget`` et retourne l'objet ``Tooltip``."""
    return Tooltip(widget, text, **kwargs)


def make_button(parent, text, command, *, fg=theme.FG,
                accent=False, danger=False, stretch=False,
                pady=7) -> RoundedButton:
    """Fabrique un ``RoundedButton`` selon la variante demandee."""
    if accent:
        return RoundedButton(parent, text, command, bg=theme.ACCENT,
                             hover=theme.ACCENT_HOVER, fg=theme.ACCENT_FG,
                             stretch=stretch, pady=pady)
    if danger:
        return RoundedButton(parent, text, command, bg=theme.BTN,
                             hover=theme.RED_HOVER, fg=theme.RED,
                             stretch=stretch, pady=pady)
    return RoundedButton(parent, text, command, bg=theme.BTN,
                         hover=theme.BTN_HOVER, fg=fg,
                         stretch=stretch, pady=pady)
