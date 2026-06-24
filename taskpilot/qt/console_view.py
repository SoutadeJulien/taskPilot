"""Panneau d'affichage (lecture seule) de la sortie d'un ``TaskConsole``.

En-tete (etat + couleur de projet + redemarrer) au-dessus d'un
``QPlainTextEdit``. Le coloriage par niveau de log, la semantique du retour
chariot ``\\r`` et le zoom y sont geres. Le rendu de gros buffers, la selection
et le scroll sont natifs.
"""

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QFrame, QMessageBox, QPlainTextEdit, QTextEdit, QVBoxLayout, QWidget)

from taskpilot.core import editors
from taskpilot.qt import theme
from taskpilot.qt.header import ConsoleHeader
from taskpilot.qt.line_select import LineSelector

MAX_LINES = 5000
MIN_FONT_SIZE = 6
MAX_FONT_SIZE = 40

#: Heuristiques de coloriage par niveau (premiere regle qui matche gagne).
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

def _level_color(level):
    """Couleur d'un niveau, lue dynamiquement (suit le theme actif)."""
    return {
        "error": theme.LV_ERROR, "warn": theme.LV_WARN,
        "info": theme.LV_INFO, "success": theme.LV_SUCCESS,
        "prompt": theme.CONSOLE_PROMPT,
    }.get(level)


class ConsoleView(QWidget):
    """Affiche la sortie d'un ``TaskConsole`` (tube, lecture seule)."""

    def __init__(self, console, on_restart=None, settings=None, parent=None):
        super().__init__(parent)
        self.console = console
        self.on_restart = on_restart
        self.settings = settings
        self.project = None
        self.group_color = None
        self._pending = ""
        self._base_size = theme.MONO_SIZE
        self._formats = {}
        self._build()
        theme.notifier.changed.connect(self._on_theme)
        theme.notifier.fonts_changed.connect(self._on_fonts)

    # -- Construction --------------------------------------------------------
    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(10)
        layout.addWidget(self._build_header())
        self.edit = self._build_edit()
        layout.addWidget(self.edit, 1)
        self._line_selector = LineSelector(self.edit)

    def _build_header(self):
        self.header = ConsoleHeader(self._restart)
        return self.header

    def _build_edit(self):
        edit = _ConsoleEdit(self)
        edit.setReadOnly(True)
        edit.setMaximumBlockCount(0)
        edit.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        edit.setFont(QFont(theme.MONO_FAMILY, self._base_size))
        edit.setFrameStyle(QFrame.NoFrame)
        return edit

    # -- Liens vers l'editeur (Ctrl+clic) ------------------------------------
    def _link_at(self, pos):
        """Reference de fichier sous le point ``pos`` (viewport), ou ``None``."""
        cursor = self.edit.cursorForPosition(pos)
        return editors.find_link_at(cursor.block().text(),
                                    cursor.positionInBlock())

    def open_link(self, info):
        """Ouvre la reference ``info`` (cf. ``editors.find_link_at``)."""
        _start, _end, path, line, col = info
        key = self.settings.editor if self.settings else editors.DEFAULT_EDITOR
        cwd = getattr(self.console.spec, "cwd", None)
        ok, msg = editors.open_in_editor(key, path, line, col, cwd)
        if not ok:
            QMessageBox.warning(self, "Éditeur", msg)

    # -- Formats de coloriage ------------------------------------------------
    def _fmt(self, level):
        fmt = self._formats.get(level)
        if fmt is None:
            fmt = QTextCharFormat()
            color = _level_color(level)
            if color:
                fmt.setForeground(QColor(color))
            if level == "prompt":
                fmt.setFontWeight(QFont.Bold)
            self._formats[level] = fmt
        return fmt

    def _on_theme(self):
        """Au changement de theme : les nouvelles lignes prennent les nouvelles
        couleurs (le cache de formats est invalide)."""
        self._formats.clear()

    def _on_fonts(self):
        """Police monospace modifiee : on la reapplique (remet le zoom a zero)."""
        self._base_size = theme.MONO_SIZE
        self.edit.setFont(QFont(theme.MONO_FAMILY, self._base_size))

    @staticmethod
    def _apply_cr(line):
        """Applique la semantique du retour chariot ``\\r`` sur une ligne."""
        if "\r" not in line:
            return line
        out = ""
        for seg in line.split("\r"):
            out = seg + out[len(seg):]
        return out

    @staticmethod
    def _level(line):
        if line.startswith("$ "):
            return "prompt"
        for tag, pattern in LEVEL_RULES:
            if pattern.search(line):
                return tag
        return None

    # -- Mise a jour ---------------------------------------------------------
    def append(self, text):
        sb = self.edit.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 4
        cursor = self.edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        # Retire la ligne partielle precedente avant de la reconstituer.
        if self._pending:
            cursor.movePosition(QTextCursor.StartOfBlock, QTextCursor.KeepAnchor)
            cursor.removeSelectedText()
        buf = self._pending + text
        lines = buf.split("\n")
        self._pending = self._apply_cr(lines.pop())
        for line in lines:
            line = self._apply_cr(line)
            cursor.insertText(line + "\n", self._fmt(self._level(line)))
        if self._pending:
            cursor.insertText(self._pending, self._fmt(self._level(self._pending)))
        self._trim()
        if at_bottom:
            sb.setValue(sb.maximum())

    def _trim(self):
        extra = self.edit.blockCount() - MAX_LINES
        if extra <= 0:
            return
        cursor = self.edit.textCursor()
        cursor.movePosition(QTextCursor.Start)
        cursor.movePosition(QTextCursor.NextBlock, QTextCursor.KeepAnchor, extra)
        cursor.removeSelectedText()

    # -- Etat / couleur ------------------------------------------------------
    def set_project_color(self, color):
        self.project_color = color or None
        self.header.set_dot(color)

    def set_exited(self, code):
        self.header.set_exited(code)

    def attach_console(self, console):
        self.console = console
        self._pending = ""
        self.edit.clear()
        self.header.set_running()

    def dispose(self):
        """Coupe les abonnements au thème (à appeler avant destruction)."""
        try:
            theme.notifier.changed.disconnect(self._on_theme)
            theme.notifier.fonts_changed.disconnect(self._on_fonts)
        except (RuntimeError, TypeError):
            pass
        self.header.dispose()
        self._line_selector.dispose()

    # -- Actions -------------------------------------------------------------
    def copy_all_output(self):
        """Copie toute la sortie (logs), quelle que soit la sélection."""
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self.edit.toPlainText())

    def copy_output(self):
        """Copie la sélection si elle existe, sinon toute la sortie."""
        from PySide6.QtWidgets import QApplication
        cursor = self.edit.textCursor()
        text = cursor.selectedText().replace(" ", "\n") \
            if cursor.hasSelection() else self.edit.toPlainText()
        QApplication.clipboard().setText(text)

    def clear(self):
        self.edit.clear()
        self._pending = ""

    def zoom(self, delta):
        font = self.edit.font()
        size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, font.pointSize() + delta))
        font.setPointSize(size)
        self.edit.setFont(font)

    def reset_zoom(self):
        font = self.edit.font()
        font.setPointSize(self._base_size)
        self.edit.setFont(font)

    def focus_input(self):
        self.edit.setFocus()

    def _restart(self):
        if self.on_restart:
            self.on_restart(self)

    # -- Zoom a la molette (Ctrl) --------------------------------------------
    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            self.zoom(1 if event.angleDelta().y() > 0 else -1)
            event.accept()
        else:
            super().wheelEvent(event)


class _ConsoleEdit(QPlainTextEdit):
    """Zone de sortie avec liens vers l'editeur.

    Au survol d'une reference de fichier, on la souligne et on affiche une
    info-bulle « Ctrl+clic » (decouvrabilite, a la maniere de VS Code) ; le
    curseur prend la forme d'une main quand Ctrl est tenu. ``Ctrl+clic`` ouvre
    le fichier sans perturber la selection de texte (clic simple inchange).
    """

    def __init__(self, owner):
        super().__init__()
        self._owner = owner
        self._hover_range = None      # (start, end) en positions document
        self.setMouseTracking(True)

    def mouseMoveEvent(self, event):
        cursor = self.cursorForPosition(event.pos())
        block = cursor.block()
        link = self._owner._link_at(event.pos())
        if link:
            start = block.position() + link[0]
            self._set_hover(start, block.position() + link[1])
            self.viewport().setCursor(
                Qt.PointingHandCursor if event.modifiers() & Qt.ControlModifier
                else Qt.IBeamCursor)
        else:
            self._clear_hover()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self._clear_hover()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if (event.button() == Qt.LeftButton
                and event.modifiers() & Qt.ControlModifier):
            link = self._owner._link_at(event.pos())
            if link:
                self._owner.open_link(link)
                event.accept()
                return
        super().mousePressEvent(event)

    # -- Surlignage du lien survole ------------------------------------------
    def _set_hover(self, start, end):
        if self._hover_range == (start, end):
            return
        self._hover_range = (start, end)
        cursor = self.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        sel = QTextEdit.ExtraSelection()
        sel.cursor = cursor
        sel.format.setForeground(QColor(theme.ACCENT))
        sel.format.setFontUnderline(True)
        sel.format.setUnderlineColor(QColor(theme.ACCENT))
        self.setExtraSelections([sel])
        self.setToolTip("Ctrl+clic pour ouvrir dans l'éditeur")

    def _clear_hover(self):
        if self._hover_range is None:
            return
        self._hover_range = None
        self.setExtraSelections([])
        self.viewport().setCursor(Qt.IBeamCursor)
        self.setToolTip("")
