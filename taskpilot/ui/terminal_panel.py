"""Panneau terminal : émulateur VT (``pyte``) rendu dans un widget Text.

Reçoit le flux brut d'un ``PtyConsole``, le fait analyser par un écran ``pyte``
(grille de caractères + attributs), puis rend cette grille. Les frappes clavier
sont retransmises telles quelles (avec les bonnes séquences d'échappement) au
pseudo-terminal, ce qui permet aux programmes plein écran (``claude``, REPL…)
de fonctionner comme dans une vraie console.
"""

import tkinter as tk
import tkinter.font as tkfont

import pyte

from taskpilot.ui import theme
from taskpilot.ui.console_panel import (
    MAX_FONT_SIZE, MIN_FONT_SIZE, ConsolePanel)

#: Palette ANSI 16 couleurs (noms pyte -> hex), tons adoucis facon terminal.
ANSI_COLORS = {
    "black": "#1e1e1e", "red": "#d07a7a", "green": "#7cba96",
    "brown": "#d6b36a", "blue": "#6fa8d6", "magenta": "#c98fd0",
    "cyan": "#7bc0c0", "white": "#d4d4d4",
    "brightblack": "#6a6a6a", "brightred": "#e59595", "brightgreen": "#9ed4b0",
    "brightbrown": "#e6c98a", "brightblue": "#8fc0e6", "brightmagenta": "#dba8e0",
    "brightcyan": "#9ad6d6", "brightwhite": "#ffffff",
}

#: keysym Tk -> séquence envoyée au PTY pour les touches non imprimables.
KEYSYM = {
    "Return": "\r", "KP_Enter": "\r", "BackSpace": "\x7f", "Tab": "\t",
    "Escape": "\x1b", "Up": "\x1b[A", "Down": "\x1b[B", "Right": "\x1b[C",
    "Left": "\x1b[D", "Home": "\x1b[H", "End": "\x1b[F", "Prior": "\x1b[5~",
    "Next": "\x1b[6~", "Delete": "\x1b[3~", "Insert": "\x1b[2~",
}


def _hex(color, default):
    """Convertit une couleur pyte (nom, hex ou ``default``) en ``#rrggbb``."""
    if color == "default" or not color:
        return default
    if color in ANSI_COLORS:
        return ANSI_COLORS[color]
    if len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color):
        return f"#{color}"
    return default


class TerminalPanel(ConsolePanel):
    """Affiche et pilote un ``PtyConsole`` comme un vrai terminal."""

    def __init__(self, parent, console, on_close, on_restart=None):
        self._tags = set()
        self._render_scheduled = False
        super().__init__(parent, console, on_close, on_restart)

    # -- Construction --------------------------------------------------------
    def _build_text(self):
        from taskpilot.ui.rounded import RoundedFrame
        from tkinter import ttk

        card = RoundedFrame(self, bg=theme.CONSOLE_BG,
                            border=theme.CONSOLE_BORDER, inset=8)
        card.pack(fill="both", expand=True)
        wrap = card.inner

        self._base_size = theme.FONT_MONO[1]
        self._font = tkfont.Font(family=theme.FONT_MONO[0], size=self._base_size)
        self._font_bold = tkfont.Font(
            family=theme.FONT_MONO_BOLD[0], size=self._base_size, weight="bold")

        self.screen = pyte.Screen(self.console.cols, self.console.rows)
        self.stream = pyte.Stream(self.screen)

        self.text = tk.Text(
            wrap, bg=theme.CONSOLE_BG, fg=theme.FG, insertbackground=theme.FG,
            relief="flat", wrap="none", font=self._font, padx=4, pady=2,
            highlightthickness=0, bd=0, takefocus=1, cursor="xterm")
        self.text.tag_configure("cursor", background=theme.ACCENT,
                                foreground=theme.CONSOLE_BG)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.bind("<Key>", self._on_key)
        self.text.bind("<Control-v>", self._paste)
        self.text.bind("<Button-1>", lambda _e: self.text.focus_set())
        self.text.bind("<Configure>", self._on_configure)
        self.text.bind("<Control-MouseWheel>", self._on_zoom_wheel)
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.text.bind(seq, lambda _e: self.zoom(1) or "break")
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.text.bind(seq, lambda _e: self.zoom(-1) or "break")
        self.text.bind("<Control-Key-0>", lambda _e: self.reset_zoom() or "break")

    def focus_input(self):
        try:
            self.text.focus_set()
        except tk.TclError:
            pass

    # -- Clavier -------------------------------------------------------------
    def _on_key(self, event):
        if not self.console.is_running():
            return "break"
        if event.keysym in KEYSYM:
            self.console.send(KEYSYM[event.keysym])
        elif event.char:
            # ``event.char`` porte déjà les caractères de contrôle (Ctrl+C…).
            self.console.send(event.char)
        return "break"

    def _paste(self, _e=None):
        try:
            data = self.clipboard_get()
        except tk.TclError:
            return "break"
        self.console.send(data.replace("\r\n", "\r").replace("\n", "\r"))
        return "break"

    # -- Dimensions / zoom ---------------------------------------------------
    def _on_configure(self, event):
        cw = max(1, self._font.measure("M"))
        ch = max(1, self._font.metrics("linespace"))
        cols = max(20, (event.width - 8) // cw)
        rows = max(5, (event.height - 4) // ch)
        if (rows, cols) != (self.screen.lines, self.screen.columns):
            self.screen.resize(rows, cols)
            self.console.set_size(rows, cols)
            self._render_screen()

    def _set_font_size(self, size):
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
        self._font.configure(size=size)
        self._font_bold.configure(size=size)
        # Les tags référencent les objets Font (mis à jour en place), mais la
        # taille de grille change : on laisse <Configure> recalculer.
        self.text.event_generate("<Configure>",
                                 width=self.text.winfo_width(),
                                 height=self.text.winfo_height())

    # -- Rendu ---------------------------------------------------------------
    def append(self, data):
        self.stream.feed(data)
        if not self._render_scheduled:
            self._render_scheduled = True
            self.after_idle(self._flush)

    def _flush(self):
        self._render_scheduled = False
        try:
            self._render_screen()
        except tk.TclError:
            pass

    def _style_tag(self, fg, bg, bold, reverse):
        name = f"s_{fg}_{bg}_{int(bold)}_{int(reverse)}"
        if name not in self._tags:
            f = _hex(fg, theme.FG)
            b = _hex(bg, theme.CONSOLE_BG)
            if reverse:
                f, b = b, f
            self.text.tag_configure(
                name, foreground=f, background=b,
                font=self._font_bold if bold else self._font)
            self._tags.add(name)
        return name

    def _render_screen(self):
        screen = self.screen
        view = self.text.yview()
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        for y in range(screen.lines):
            row = screen.buffer[y]
            run_style = None
            run_text = []
            for x in range(screen.columns):
                ch = row[x]
                style = (ch.fg, ch.bg, ch.bold, ch.reverse)
                if style != run_style:
                    if run_text:
                        self.text.insert(
                            "end", "".join(run_text), self._style_tag(*run_style))
                    run_style = style
                    run_text = [ch.data or " "]
                else:
                    run_text.append(ch.data or " ")
            if run_text:
                self.text.insert(
                    "end", "".join(run_text), self._style_tag(*run_style))
            if y < screen.lines - 1:
                self.text.insert("end", "\n")
        if not screen.cursor.hidden and self.console.is_running():
            cy, cx = screen.cursor.y, screen.cursor.x
            self.text.tag_add("cursor", f"{cy + 1}.{cx}", f"{cy + 1}.{cx + 1}")
            # Les tags de style sont créés après le tag "cursor" et ont donc une
            # priorité supérieure : sans cela leur fond masquerait le curseur.
            self.text.tag_raise("cursor")
        self.text.config(state="disabled")
        self.text.yview_moveto(view[0])

    # -- Cycle de vie --------------------------------------------------------
    def clear(self):
        self.screen.reset()
        self._render_screen()

    def attach_console(self, console):
        self.console = console
        self.screen.reset()
        self._render_screen()
        self.status.config(text="●  en cours", fg=theme.ACCENT)
        self.focus_input()
