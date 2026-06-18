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
        # Le pied est construit AVANT la zone de texte : pose en ``side=bottom``,
        # il reserve sa hauteur avant que la zone de texte (expand) ne prenne le
        # reste. Sans cela, la zone extensible avalerait tout l'espace.
        self._build_footer()
        self._build_text()

    def _build_footer(self):
        """Pied de panneau (vide par defaut ; cf. ``InteractiveConsolePanel``)."""

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
        # La fermeture (et l'arrêt du process) se fait via la croix de l'onglet.
        self.btn_restart = make_button(
            header, "↻ Redémarrer", self._restart)
        self.btn_restart.pack(side="right", padx=4, pady=2)
        add_tooltip(self.btn_restart,
                    "Relancer la commande dans cette console (nouveau process)")

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
    def _apply_cr(line: str):
        """Applique la sémantique du retour chariot (``\\r``) sur UNE ligne.

        Un ``\\r`` ramène le curseur en début de ligne : ce qui suit écrase le
        début. Sans ce traitement, les barres de progression (npm, webpack,
        pip, spinners… qui réécrivent la ligne via ``\\r`` sans ``\\n``)
        s'empileraient en une ligne géante grandissant sans fin — chaque
        rafraîchissement la ré-insérant entièrement, d'où un gel de l'UI.
        """
        if "\r" not in line:
            return line
        out = ""
        for seg in line.split("\r"):
            out = seg + out[len(seg):]   # écrase depuis la colonne 0
        return out

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
        self._pending = self._apply_cr(lines.pop())
        for line in lines:
            line = self._apply_cr(line)
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

    def attach_console(self, console):
        """Rattache un nouveau process (relance) et réinitialise l'affichage."""
        self.console = console
        self._pending = ""
        self._has_pending = False
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")
        self.status.config(text="●  en cours", fg=theme.ACCENT)

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
    def _restart(self):
        if self.on_restart:
            self.on_restart(self)


class InteractiveConsolePanel(ConsolePanel):
    """Console interactive « ligne-à-ligne » : on tape directement dedans.

    Repli quand le vrai terminal (ConPTY) est indisponible. On écrit au clavier
    en bas de la console comme dans un terminal : les caractères s'affichent en
    place, la sortie du shell s'insère au-dessus de la ligne en cours, et chaque
    ligne validée par ``Entrée`` est transmise au stdin du process. La zone déjà
    affichée (sortie + commandes envoyées) ne peut pas être éditée.

    Le repère ``inpstart`` marque le début de la ligne en cours de saisie ;
    ``self._input`` en est la source de vérité (le shell, lu via un tube,
    n'écho pas la frappe).
    """

    def __init__(self, parent, console, on_close, on_restart=None):
        self._history = []
        self._hist_idx = None
        self._input = ""
        super().__init__(parent, console, on_close, on_restart)

    def _build_text(self):
        super()._build_text()
        # Le widget devient éditable, mais toutes les frappes passent par nos
        # gestionnaires (qui renvoient « break ») : la zone amont reste figée.
        self.text.config(state="normal", insertbackground=theme.FG)
        self.text.mark_set("inpstart", "end-1c")
        self.text.mark_gravity("inpstart", "left")
        self.text.bind("<Key>", self._on_key)
        self.text.bind("<Return>", self._on_return)
        self.text.bind("<KP_Enter>", self._on_return)
        self.text.bind("<BackSpace>", self._on_backspace)
        self.text.bind("<Up>", self._history_prev)
        self.text.bind("<Down>", self._history_next)
        self.text.bind("<Control-v>", self._paste)

    def focus_input(self):
        try:
            self.text.focus_set()
            self.text.mark_set("insert", "end")
        except tk.TclError:
            pass

    # -- Affichage de la saisie ----------------------------------------------
    def _echo(self, text):
        """Affiche du texte saisi en fin de console."""
        self.text.insert("end-1c", text)
        self.text.mark_set("insert", "end")
        self.text.see("end")

    def _redraw_input(self, text):
        """Remplace la ligne en cours affichée par ``text`` (historique)."""
        self.text.delete("inpstart", "end-1c")
        self._input = text
        self.text.insert("inpstart", text)
        self.text.mark_set("insert", "end")
        self.text.see("end")

    # -- Sortie (insérée au-dessus de la ligne en cours) ---------------------
    def append(self, text):
        at_bottom = self.text.yview()[1] >= 0.999
        saved = self._input
        if saved:                       # retire la saisie le temps d'insérer
            self.text.delete("inpstart", "end-1c")
        for line in text.splitlines(keepends=True):
            body = line[:-1] if line.endswith("\n") else line
            tag = self._line_tag(body)
            self.text.insert("end-1c", line, tag or ())
        self.text.mark_set("inpstart", "end-1c")
        if saved:                       # ré-affiche la saisie en cours
            self.text.insert("end-1c", saved)
        self.text.mark_set("insert", "end")
        if at_bottom:
            self.text.see("end")

    # -- Clavier -------------------------------------------------------------
    def _on_key(self, event):
        if not self.console.is_running():
            return "break"
        ch = event.char
        if ch and ch >= " ":            # imprimable (exclut Ctrl/Échap/etc.)
            self._input += ch
            self._echo(ch)
        return "break"

    def _on_backspace(self, _e=None):
        if self._input:
            self._input = self._input[:-1]
            self.text.delete("end-2c", "end-1c")
            self.text.see("end")
        return "break"

    def _on_return(self, _e=None):
        if not self.console.is_running():
            return "break"
        line = self._input
        self._input = ""
        if line.strip():
            self._history.append(line)
        self._hist_idx = None
        self.text.insert("end-1c", "\n")
        self.text.mark_set("inpstart", "end-1c")
        self.text.mark_set("insert", "end")
        self.text.see("end")
        self.console.send(line + "\n")
        return "break"

    def _paste(self, _e=None):
        try:
            data = self.clipboard_get()
        except tk.TclError:
            return "break"
        parts = data.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        for i, part in enumerate(parts):
            self._input += part
            self._echo(part)
            if i < len(parts) - 1:
                self._on_return()
        return "break"

    def _history_prev(self, _e=None):
        if not self._history:
            return "break"
        if self._hist_idx is None:
            self._hist_idx = len(self._history)
        self._hist_idx = max(0, self._hist_idx - 1)
        self._redraw_input(self._history[self._hist_idx])
        return "break"

    def _history_next(self, _e=None):
        if self._hist_idx is None:
            return "break"
        self._hist_idx += 1
        if self._hist_idx >= len(self._history):
            self._hist_idx = None
            self._redraw_input("")
        else:
            self._redraw_input(self._history[self._hist_idx])
        return "break"

    # -- Cycle de vie --------------------------------------------------------
    def clear(self):
        super().clear()
        self._input = ""
        self.text.config(state="normal")
        self.text.mark_set("inpstart", "end-1c")
        self.text.mark_gravity("inpstart", "left")

    def attach_console(self, console):
        super().attach_console(console)
        self._input = ""
        self._hist_idx = None
        self.text.config(state="normal")
        self.text.mark_set("inpstart", "end-1c")
        self.text.mark_gravity("inpstart", "left")
        self.focus_input()
