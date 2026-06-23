"""Terminal interactif : emulateur VT (``pyte``) rendu dans un QPlainTextEdit.

Equivalent Qt de ``taskpilot.ui.terminal_panel``. Recoit le flux brut d'un
``PtyConsole``, le fait analyser par un ecran ``pyte`` (grille de caracteres +
attributs) et le rend. Les frappes sont retransmises au pseudo-terminal avec
les bonnes sequences VT, ce qui fait tourner les programmes plein ecran
(``claude``, REPL...).
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import (
    QColor, QFont, QFontMetricsF, QKeySequence, QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import (
    QApplication, QFrame, QPlainTextEdit, QVBoxLayout, QWidget)

import pyte

from taskpilot.qt import theme
from taskpilot.qt.header import ConsoleHeader

MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 40

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
        self.setFont(QFont(theme.MONO_FAMILY, owner._base_size))
        self.setFrameStyle(QFrame.NoFrame)
        self.setCursorWidth(0)        # le curseur VT est dessine par pyte

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
        self._owner._resync_size()

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            self._owner.zoom(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
        else:
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
        self.screen = pyte.Screen(console.cols, console.rows)
        self.stream = pyte.Stream(self.screen)
        self._formats = {}
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

    def _on_theme(self):
        """Au changement de theme : recolore tout l'ecran (cache invalide)."""
        self._formats.clear()
        self._render()

    # -- Dimensions ----------------------------------------------------------
    def _resync_size(self):
        fm = QFontMetricsF(self.edit.font())
        cw = max(1.0, fm.horizontalAdvance("M"))
        ch = max(1.0, fm.lineSpacing())
        vp = self.edit.viewport()
        cols = max(20, int(vp.width() / cw))
        rows = max(5, int(vp.height() / ch))
        if (rows, cols) != (self.screen.lines, self.screen.columns):
            self.screen.resize(rows, cols)
            self.console.set_size(rows, cols)
            self._schedule_render()

    # -- Flux / rendu --------------------------------------------------------
    def append(self, data):
        self.stream.feed(data)
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

    def _render(self):
        self._render_pending = False
        screen = self.screen
        sb = self.edit.verticalScrollBar()
        pos = sb.value()
        self.edit.clear()
        cursor = self.edit.textCursor()
        for y in range(screen.lines):
            row = screen.buffer[y]
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
            if y < screen.lines - 1:
                cursor.insertText("\n")
        self._draw_cursor()
        sb.setValue(pos)

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
        self._render()
        self.header.set_running()
        self.focus_input()

    def dispose(self):
        """Coupe les abonnements au thème (à appeler avant destruction)."""
        try:
            theme.notifier.changed.disconnect(self._on_theme)
        except (RuntimeError, TypeError):
            pass
        self.header.dispose()

    # -- Actions -------------------------------------------------------------
    def copy_all_output(self):
        """Copie tout l'écran du terminal, quelle que soit la sélection."""
        QApplication.clipboard().setText(self.edit.toPlainText())

    def copy_output(self):
        """Copie la sélection (séparateurs de paragraphe -> sauts de ligne)."""
        text = self.edit.textCursor().selectedText().replace(" ", "\n")
        QApplication.clipboard().setText(text)

    def clear(self):
        self.screen.reset()
        self._render()

    def zoom(self, delta):
        font = self.edit.font()
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, font.pointSize() + delta))
        font.setPointSize(size)
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
