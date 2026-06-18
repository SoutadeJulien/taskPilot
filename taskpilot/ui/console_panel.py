"""Panneau d'affichage de la sortie d'une console de task."""

import re
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from taskpilot.ui import theme
from taskpilot.ui.line_select import LineSelector
from taskpilot.ui.rounded import RoundedFrame
from taskpilot.ui.widgets import add_tooltip, make_button

#: Au-dela de ce nombre de lignes, on tronque le debut du buffer.
MAX_LINES = 5000

#: Bornes de la taille de police de la console (zoom Ctrl+molette).
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 40

#: Heuristiques de coloriage par niveau, dans l'ordre de priorite (la premiere
#: qui matche gagne). Mots-cles courants des sorties de build / dev servers.
LEVEL_RULES = (
    ("error", re.compile(
        r"(?<![\w-])(error|err|errored|fail(?:ed|ure)?|fatal|exception|"
        r"npm err!|panic|[ée]chec|✗|✖|❌)(?![\w-])", re.IGNORECASE)),
    ("warn", re.compile(
        r"(?<![\w-])(warn(?:ing)?|deprecated|⚠)(?![\w-])", re.IGNORECASE)),
    ("success", re.compile(
        r"(?<![\w-])(success(?:ful(?:ly)?)?|compiled successfully|ready in|"
        r"built in|done|✓|✔|✅)(?![\w-])", re.IGNORECASE)),
    ("info", re.compile(
        r"(?<![\w-])(info|note|debug|hmr|waiting|listening)(?![\w-])",
        re.IGNORECASE)),
)


class ConsolePanel(tk.Frame):
    """Affiche (en lecture seule) la sortie d'un ``TaskConsole``."""

    def __init__(self, parent, console, on_close, on_restart=None):
        super().__init__(parent, bg=theme.BG)
        self.console = console
        self.on_close = on_close
        self.on_restart = on_restart
        self._pending = ""        # texte de la ligne partielle affichee
        self._has_pending = False  # une ligne partielle est-elle affichee ?
        self._build_header()
        self._build_text()

    def _build_header(self):
        # Barre de titre arrondie, detachee de la carte de sortie.
        bar = RoundedFrame(self, bg=theme.CONSOLE_HEAD, radius=theme.TAB_RADIUS,
                           inset=6)
        bar.pack(fill="x", pady=(0, 6))
        header = bar.inner
        # Pastille d'etat + libelle, regroupes pour un rendu plus lisible.
        self.status = tk.Label(
            header, text="●  en cours", bg=theme.CONSOLE_HEAD, fg=theme.ACCENT,
            font=theme.FONT_UI_BOLD, anchor="w", padx=6, pady=2)
        self.status.pack(side="left")
        self.btn_close = make_button(header, "✕ Fermer", self._close)
        self.btn_close.pack(side="right", padx=(0, 4), pady=2)
        add_tooltip(self.btn_close,
                    "Fermer cette console (disponible une fois le process arrêté)")
        self.btn_kill = make_button(header, "■ Arrêter", self._kill, danger=True)
        self.btn_kill.pack(side="right", padx=4, pady=2)
        add_tooltip(self.btn_kill, "Arrêter le process de cette console")
        self.btn_restart = make_button(
            header, "↻ Redémarrer", self._restart)
        self.btn_restart.pack(side="right", padx=4, pady=2)
        add_tooltip(self.btn_restart,
                    "Relancer la commande dans cette console (nouveau process)")
        self.btn_close.set_enabled(False)

    def _build_text(self):
        card = RoundedFrame(self, bg=theme.CONSOLE_BG,
                            border=theme.CONSOLE_BORDER, inset=8)
        card.pack(fill="both", expand=True)
        wrap = card.inner
        # Polices propres au panneau (copies) : le zoom Ctrl+molette est ainsi
        # independant pour chaque console et ne touche pas la police partagee.
        self._base_size = theme.FONT_MONO[1]
        self._font = tkfont.Font(family=theme.FONT_MONO[0], size=self._base_size)
        self._font_bold = tkfont.Font(
            family=theme.FONT_MONO_BOLD[0], size=self._base_size, weight="bold")
        self.text = tk.Text(
            wrap, bg=theme.CONSOLE_BG, fg=theme.FG, insertbackground=theme.FG,
            relief="flat", wrap="char", font=self._font,
            state="disabled", padx=4, pady=2, spacing1=1,
            highlightthickness=0, bd=0)
        # Tags de coloriage par type de ligne.
        self.text.tag_configure("prompt", foreground=theme.CONSOLE_PROMPT,
                                font=self._font_bold)
        self.text.tag_configure("error", foreground=theme.CONSOLE_ERROR)
        self.text.tag_configure("warn", foreground=theme.CONSOLE_WARN)
        self.text.tag_configure("info", foreground=theme.CONSOLE_INFO)
        self.text.tag_configure("success", foreground=theme.CONSOLE_SUCCESS)
        scroll = ttk.Scrollbar(wrap, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        # Selection de lignes par glissement -> copie dans le presse-papiers.
        self._line_selector = LineSelector(self.text, wrap)
        # Zoom : Ctrl+molette, Ctrl++/Ctrl+- pour ajuster, Ctrl+0 pour reset.
        self.text.bind("<Control-MouseWheel>", self._on_zoom_wheel)
        for seq in ("<Control-plus>", "<Control-equal>", "<Control-KP_Add>"):
            self.text.bind(seq, lambda _e: self.zoom(1) or "break")
        for seq in ("<Control-minus>", "<Control-KP_Subtract>"):
            self.text.bind(seq, lambda _e: self.zoom(-1) or "break")
        self.text.bind("<Control-Key-0>", lambda _e: self.reset_zoom() or "break")

    # -- Zoom ----------------------------------------------------------------
    def _on_zoom_wheel(self, event):
        self.zoom(1 if event.delta > 0 else -1)
        return "break"

    def zoom(self, delta):
        """Augmente (delta>0) ou diminue la taille de police de la console."""
        self._set_font_size(self._font["size"] + delta)

    def reset_zoom(self):
        """Revient à la taille de police par défaut."""
        self._set_font_size(self._base_size)

    def _set_font_size(self, size):
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, size))
        at_bottom = self.text.yview()[1] >= 0.999
        self._font.configure(size=size)
        self._font_bold.configure(size=size)
        if at_bottom:
            self.text.see("end")

    @staticmethod
    def _line_tag(line: str):
        """Choisit un tag de coloriage : ligne de commande, sinon niveau de log."""
        if line.startswith("$ "):
            return "prompt"
        for tag, pattern in LEVEL_RULES:
            if pattern.search(line):
                return tag
        return None

    # -- Mise a jour ---------------------------------------------------------
    def append(self, text: str):
        self.text.config(state="normal")
        at_bottom = self.text.yview()[1] >= 0.999
        # Coloriage ligne par ligne. Le flux arrive par bouts : une ligne peut
        # etre affichee incomplete puis completee. On retire l'affichage de la
        # ligne partielle precedente avant de reinserer la ligne reconstituee,
        # pour la taguer correctement sans la dupliquer.
        if self._has_pending:
            self.text.delete("pending", "end-1c")
        buf = self._pending + text
        lines = buf.split("\n")
        self._pending = lines.pop()
        for line in lines:
            tag = self._line_tag(line)
            self.text.insert("end", line + "\n", tag or ())
        if self._pending:
            # Marque a gravite gauche : elle reste au debut de la ligne
            # partielle quand on y inserera la suite.
            self.text.mark_set("pending", "end-1c")
            self.text.mark_gravity("pending", "left")
            self.text.insert(
                "end", self._pending, self._line_tag(self._pending) or ())
            self._has_pending = True
        else:
            self._has_pending = False
        if int(self.text.index("end-1c").split(".")[0]) > MAX_LINES:
            self.text.delete("1.0", "1000.end")
        self.text.config(state="disabled")
        if at_bottom:
            self.text.see("end")

    def set_exited(self, code: int):
        if code == 0:
            self.status.config(text="●  terminé (0)", fg=theme.CONSOLE_MUTED)
        else:
            self.status.config(text=f"●  arrêté (code {code})", fg=theme.RED)
        self.btn_kill.set_enabled(False)
        self.btn_close.set_enabled(True)

    def attach_console(self, console):
        """Rattache un nouveau process (relance) et réinitialise l'affichage."""
        self.console = console
        self._pending = ""
        self._has_pending = False
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")
        self.status.config(text="●  en cours", fg=theme.ACCENT)
        self.btn_kill.set_enabled(True)
        self.btn_close.set_enabled(False)

    def copy_output(self):
        """Copie tout le contenu de la console dans le presse-papiers."""
        content = self.text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(content)

    def clear(self):
        """Vide l'affichage de la console (sans toucher au process)."""
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")
        self._pending = ""
        self._has_pending = False

    # -- Actions -------------------------------------------------------------
    def _kill(self):
        self.console.kill()

    def _restart(self):
        if self.on_restart:
            self.on_restart(self)

    def _close(self):
        self.on_close(self)
