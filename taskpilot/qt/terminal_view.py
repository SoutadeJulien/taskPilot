"""Terminal interactif : emulateur VT (``pyte``) rendu dans un QPlainTextEdit.

Recoit le flux brut d'un ``PtyConsole``, le fait analyser par un ecran
``pyte`` (grille de caracteres +
attributs) et le rend. Les frappes sont retransmises au pseudo-terminal avec
les bonnes sequences VT, ce qui fait tourner les programmes plein ecran
(``claude``, REPL...).
"""

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import (
    QColor, QFont, QFontMetricsF, QKeySequence, QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import (
    QApplication, QFrame, QPlainTextEdit, QVBoxLayout, QWidget)

import pyte

from taskpilot.qt import theme
from taskpilot.qt.header import ConsoleHeader

MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 40
#: Delai de coalescence des redimensionnements (ms) avant resynchro grille/PTY.
RESIZE_DEBOUNCE_MS = 40
#: Profondeur du scrollback (lignes conservees au-dessus de la zone visible).
HISTORY_LINES = 5000
#: Nb de lignes defilees par cran de molette.
WHEEL_LINES = 3

#: Qt.Key -> sequence envoyee au PTY pour les touches non imprimables.
KEYMAP = {
    Qt.Key_Return: "\r", Qt.Key_Enter: "\r", Qt.Key_Backspace: "\x7f",
    Qt.Key_Tab: "\t", Qt.Key_Escape: "\x1b", Qt.Key_Up: "\x1b[A",
    Qt.Key_Down: "\x1b[B", Qt.Key_Right: "\x1b[C", Qt.Key_Left: "\x1b[D",
    Qt.Key_Home: "\x1b[H", Qt.Key_End: "\x1b[F", Qt.Key_PageUp: "\x1b[5~",
    Qt.Key_PageDown: "\x1b[6~", Qt.Key_Delete: "\x1b[3~", Qt.Key_Insert: "\x1b[2~",
}


def _hex(color, default):
    if color == "default" or not color:
        return default
    if color in theme.ANSI_COLORS:
        return theme.ANSI_COLORS[color]
    if len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color):
        return f"#{color}"
    return default


class _TermEdit(QPlainTextEdit):
    """Zone de rendu/saisie : capte les frappes, suit la taille en lignes/cols."""

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self.setReadOnly(False)
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setFont(theme.mono_font(owner._base_size))
        self.setFrameStyle(QFrame.NoFrame)
        self.setCursorWidth(0)        # le curseur VT est dessine par pyte
        # La grille pyte fait exactement la taille du viewport (aucun scrollback) :
        # les barres de defilement ne servent a rien et, pire, leur apparition au
        # rendu modifie la taille du viewport, ce qui relance un resync et fait
        # osciller/clignoter l'affichage pendant le redimensionnement.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # La molette est delivree au viewport (et non a wheelEvent) : on la
        # filtre la pour le zoom Ctrl+molette.
        self.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self.viewport() and event.type() == QEvent.Wheel:
            up = event.angleDelta().y() > 0
            if event.modifiers() & Qt.ControlModifier:
                self._owner.zoom(1 if up else -1)
            else:
                # Pas de scrollbar : la molette remonte/descend le scrollback.
                self._owner.scroll_history(WHEEL_LINES if up else -WHEEL_LINES)
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event):
        owner = self._owner
        if not owner.console.is_running():
            return
        if event.matches(QKeySequence.Paste):
            data = QApplication.clipboard().text()
            owner.console.send(data.replace("\r\n", "\r").replace("\n", "\r"))
            return
        seq = KEYMAP.get(event.key())
        if seq is not None:
            owner.console.send(seq)
        elif event.text():
            owner.console.send(event.text())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._owner._resize_timer.start()

    def wheelEvent(self, event):
        # Filet de securite : le zoom Ctrl+molette est gere par l'event filter
        # sur le viewport (cf. __init__) ; ici, defilement normal uniquement.
        super().wheelEvent(event)


class TerminalView(QWidget):
    """Affiche et pilote un ``PtyConsole`` comme un vrai terminal."""

    def __init__(self, console, on_restart=None, parent=None):
        super().__init__(parent)
        self.console = console
        self.on_restart = on_restart
        self.project = None
        self.group_color = None
        self._base_size = theme.MONO_SIZE
        self._render_pending = False
        # ``HistoryScreen`` (et non ``Screen``) : conserve les lignes sorties par
        # le haut dans un scrollback, sinon elles sont perdues definitivement —
        # notamment au retrecissement vertical, ou pyte jette les lignes du haut.
        self.screen = pyte.HistoryScreen(console.cols, console.rows,
                                         history=HISTORY_LINES, ratio=0.5)
        self.stream = pyte.Stream(self.screen)
        #: Nb de lignes remontees dans l'historique (0 = colle a la sortie vive).
        self._scroll_offset = 0
        self._formats = {}
        # Le redimensionnement est deboucle : pendant un glissement de bordure,
        # ``resizeEvent`` arrive a chaque pixel ; on coalesce pour ne resynchroniser
        # la grille et le PTY (= repaint complet de ConPTY) qu'une fois la taille
        # stabilisee, sinon la fenetre sature et parait figee.
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(RESIZE_DEBOUNCE_MS)
        self._resize_timer.timeout.connect(self._resync_size)
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)
        self.header = ConsoleHeader(self._restart)
        layout.addWidget(self.header)
        self.edit = _TermEdit(self)
        layout.addWidget(self.edit, 1)
        theme.notifier.changed.connect(self._on_theme)
        theme.notifier.fonts_changed.connect(self._on_fonts)

    def _on_theme(self):
        """Au changement de theme : recolore tout l'ecran (cache invalide)."""
        self._formats.clear()
        self._render()

    def _on_fonts(self):
        """Police monospace modifiee : reapplique (remet le zoom a zero)."""
        self._base_size = theme.MONO_SIZE
        self.edit.setFont(theme.mono_font(self._base_size))
        self._resync_size()
        self._formats.clear()
        self._render()

    # -- Dimensions ----------------------------------------------------------
    def _resync_size(self):
        fm = QFontMetricsF(self.edit.font())
        cw = max(1.0, fm.horizontalAdvance("M"))
        ch = max(1.0, fm.lineSpacing())
        vp = self.edit.viewport()
        # La marge du document borde le texte sur les quatre cotes : la
        # retrancher, sinon la grille deborde de quelques pixels et la vue
        # defile pour garder le bas visible (le haut est rogne, sans scrollbar
        # pour remonter puisqu'elles sont desactivees).
        margin = 2 * self.edit.document().documentMargin()
        cols = max(20, int((vp.width() - margin) / cw))
        rows = max(5, int((vp.height() - margin) / ch))
        if (rows, cols) != (self.screen.lines, self.screen.columns):
            self._resize_screen(rows, cols)
            self.console.set_size(rows, cols)
            self._clamp_offset()
            self._schedule_render()

    def _resize_screen(self, rows, cols):
        """Redimensionne la grille pyte en **ancrant le contenu en haut**, comme
        le fait ConPTY.

        ``pyte.Screen.resize`` retire toujours les lignes du *haut* au
        retrecissement ; ConPTY, lui, garde le contenu en place et supprime les
        lignes vides du *bas*, ne faisant defiler que si le curseur deborderait.
        Comme ConPTY n'emet qu'un repaint differentiel au resize (il ne reecrit
        pas la banniere ni le prompt), cette divergence efface le contenu utile.
        On reproduit donc l'ancrage haut de ConPTY (les lignes reellement
        sorties par le haut partent dans le scrollback)."""
        screen = self.screen
        old_rows = screen.lines
        if rows < old_rows:
            scroll = max(0, screen.cursor.y - (rows - 1))
            buf = screen.buffer
            if scroll:
                for y in range(scroll):
                    screen.history.top.append(buf[y])
                for y in range(old_rows - scroll):
                    buf[y] = buf[y + scroll]
                for y in range(old_rows - scroll, old_rows):
                    buf.pop(y, None)
                screen.cursor.y = max(0, screen.cursor.y - scroll)
            for y in range(rows, old_rows):      # tronque les lignes du bas
                buf.pop(y, None)
            screen.lines = rows                  # evite le retrait-haut de pyte
        screen.resize(rows, cols)                # croissance / colonnes : pyte ok

    def _clamp_offset(self):
        self._scroll_offset = max(0, min(self._scroll_offset,
                                         len(self.screen.history.top)))

    def scroll_history(self, lines):
        """Defile le scrollback de ``lines`` (>0 vers le haut/passe)."""
        before = self._scroll_offset
        self._scroll_offset += lines
        self._clamp_offset()
        if self._scroll_offset != before:
            self._schedule_render()

    # -- Flux / rendu --------------------------------------------------------
    def append(self, data):
        self.stream.feed(data)
        # Toute nouvelle sortie recolle a la zone vive : le prompt reste visible.
        self._scroll_offset = 0
        self._schedule_render()

    def _schedule_render(self):
        if not self._render_pending:
            self._render_pending = True
            QTimer.singleShot(0, self._render)

    def _fmt(self, key):
        fmt = self._formats.get(key)
        if fmt is None:
            fg, bg, bold, reverse = key
            f = _hex(fg, theme.FG)
            b = _hex(bg, theme.CONSOLE_BG)
            if reverse:
                f, b = b, f
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(f))
            if b != theme.CONSOLE_BG:
                fmt.setBackground(QColor(b))
            if bold:
                fmt.setFontWeight(QFont.Bold)
            self._formats[key] = fmt
        return fmt

    def _visible_rows(self):
        """Les ``screen.lines`` lignes a afficher : la sortie vive, ou une
        fenetre remontee dans le scrollback selon ``_scroll_offset``."""
        screen = self.screen
        n = screen.lines
        live = [screen.buffer[y] for y in range(n)]
        if self._scroll_offset <= 0:
            return live
        top = list(screen.history.top)
        start = max(0, len(top) - self._scroll_offset)
        return (top + live)[start:start + n]

    def _render(self):
        self._render_pending = False
        screen = self.screen
        self.edit.clear()
        cursor = self.edit.textCursor()
        rows = self._visible_rows()
        for y, row in enumerate(rows):
            run_key = None
            run = []
            for x in range(screen.columns):
                ch = row[x]
                key = (ch.fg, ch.bg, ch.bold, ch.reverse)
                if key != run_key:
                    if run:
                        cursor.insertText("".join(run), self._fmt(run_key))
                    run_key = key
                    run = [ch.data or " "]
                else:
                    run.append(ch.data or " ")
            if run:
                cursor.insertText("".join(run), self._fmt(run_key))
            if y < len(rows) - 1:
                cursor.insertText("\n")
        # Le curseur VT n'a de sens que sur la sortie vive (offset 0).
        if self._scroll_offset <= 0:
            self._draw_cursor()

    def _draw_cursor(self):
        screen = self.screen
        if screen.cursor.hidden or not self.console.is_running():
            return
        block = self.edit.document().findBlockByNumber(screen.cursor.y)
        if not block.isValid():
            return
        cur = QTextCursor(block)
        cur.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor,
                         screen.cursor.x)
        cur.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, 1)
        fmt = QTextCharFormat()
        fmt.setBackground(QColor(theme.ACCENT))
        fmt.setForeground(QColor(theme.CONSOLE_BG))
        cur.mergeCharFormat(fmt)

    # -- Etat / couleur ------------------------------------------------------
    def set_project_color(self, color):
        self.project_color = color or None
        self.header.set_dot(color)

    def set_exited(self, code):
        self.header.set_exited(code)

    def attach_console(self, console):
        self.console = console
        self.screen.reset()
        self._scroll_offset = 0
        self._render()
        self.header.set_running()
        self.focus_input()

    def dispose(self):
        """Coupe les abonnements au thème (à appeler avant destruction)."""
        self._resize_timer.stop()
        try:
            theme.notifier.changed.disconnect(self._on_theme)
            theme.notifier.fonts_changed.disconnect(self._on_fonts)
        except (RuntimeError, TypeError):
            pass
        self.header.dispose()

    # -- Actions -------------------------------------------------------------
    def copy_all_output(self):
        """Copie tout l'écran du terminal, quelle que soit la sélection."""
        QApplication.clipboard().setText(self.edit.toPlainText())

    def clear(self):
        self.screen.reset()
        self._scroll_offset = 0
        self._render()

    def zoom(self, delta):
        font = self.edit.font()
        cur = font.pointSize()
        if cur <= 0:               # police posee en pixels : repart de la base
            cur = self._base_size
        font.setPointSize(max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, cur + delta)))
        self.edit.setFont(font)
        self._resync_size()

    def reset_zoom(self):
        font = self.edit.font()
        font.setPointSize(self._base_size)
        self.edit.setFont(font)
        self._resync_size()

    def focus_input(self):
        self.edit.setFocus()

    def _restart(self):
        if self.on_restart:
            self.on_restart(self)
