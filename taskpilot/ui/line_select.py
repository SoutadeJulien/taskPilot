"""Selection de lignes a la souris dans un widget Text.

Une poignee discrete apparait au survol, a droite de la ligne pointee. On la
presse puis on glisse (vers le bas ou le haut) pour selectionner une plage de
lignes entieres ; au relachement, elles sont copiees dans le presse-papiers.

Branche-toi sur un ``tk.Text`` existant via :class:`LineSelector`, sans rien
changer a son contenu ni a ses autres usages (selection native incluse).
"""

import tkinter as tk

from taskpilot.ui import theme

#: Nom du tag de surlignage applique aux lignes selectionnees.
TAG = "lineselect"


class LineSelector:
    """Ajoute la selection de lignes par glissement a un ``tk.Text``."""

    def __init__(self, text: tk.Text, parent: tk.Widget):
        self.text = text
        self._hover_line = None      # ligne sous le curseur (numero)
        self._anchor = None          # ligne de depart du glissement
        self._bounds = None          # (lo, hi) lignes selectionnees
        text.tag_configure(TAG, background=theme.SEL)
        self._handle = tk.Label(
            parent, text="⠿", bg=theme.BTN, fg=theme.CONSOLE_MUTED,
            font=theme.FONT_UI_BOLD, cursor="hand2", padx=3, bd=0)
        self._handle.bind("<Enter>",
                          lambda e: self._handle.config(bg=theme.BTN_HOVER))
        self._handle.bind("<Leave>",
                          lambda e: self._handle.config(bg=theme.BTN))
        self._handle.bind("<ButtonPress-1>", self._start)
        self._handle.bind("<B1-Motion>", self._drag)
        self._handle.bind("<ButtonRelease-1>", self._end)
        text.bind("<Motion>", self._on_motion)
        text.bind("<Leave>", self._on_leave)

    def _line_at(self, x, y) -> int:
        return int(self.text.index(f"@{x},{y}").split(".")[0])

    def _on_motion(self, event):
        if self._anchor is not None:
            return  # glissement en cours : on ne deplace pas la poignee
        info = self.text.dlineinfo(f"@{event.x},{event.y}")
        if not info:
            self._handle.place_forget()
            self._hover_line = None
            return
        self._hover_line = self._line_at(event.x, event.y)
        self._handle.place(in_=self.text, relx=1.0, x=-3, y=info[1],
                           anchor="ne")

    def _on_leave(self, event):
        if self._anchor is not None:
            return
        # Ne pas masquer si le pointeur est juste passe sur la poignee.
        hx = self.text.winfo_pointerx() - self._handle.winfo_rootx()
        hy = self.text.winfo_pointery() - self._handle.winfo_rooty()
        if (0 <= hx < self._handle.winfo_width()
                and 0 <= hy < self._handle.winfo_height()):
            return
        self._handle.place_forget()
        self._hover_line = None

    def _start(self, event):
        if self._hover_line is None:
            return
        self._anchor = self._hover_line
        self._highlight(self._anchor, self._anchor)

    def _drag(self, event):
        if self._anchor is None:
            return
        y = self.text.winfo_pointery() - self.text.winfo_rooty()
        height = self.text.winfo_height()
        if y < 0:                       # auto-defilement vers le haut
            self.text.yview_scroll(-1, "units")
            y = 0
        elif y > height:                # auto-defilement vers le bas
            self.text.yview_scroll(1, "units")
            y = height - 1
        self._highlight(self._anchor, self._line_at(0, y))

    def _end(self, event):
        if self._anchor is None:
            return
        if self._bounds:
            lo, hi = self._bounds
            text = self.text.get(f"{lo}.0", f"{hi}.end")
            if text:
                self.text.clipboard_clear()
                self.text.clipboard_append(text)
        self.text.tag_remove(TAG, "1.0", "end")
        self._anchor = None
        self._bounds = None

    def _highlight(self, a, b):
        lo, hi = (a, b) if a <= b else (b, a)
        self._bounds = (lo, hi)
        self.text.tag_remove(TAG, "1.0", "end")
        self.text.tag_add(TAG, f"{lo}.0", f"{hi}.0 lineend")
