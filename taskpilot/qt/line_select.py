"""Sélection de lignes à la souris dans une console (poignée de glissement).

Reproduit l'outil de l'UI Tkinter (``taskpilot.ui.line_select``) : une poignée
discrète « ⠿ » apparaît au survol, à droite de la ligne pointée. On la presse
puis on glisse (haut/bas) pour sélectionner une plage de lignes entières
(surlignées) ; au relâchement, elles sont copiées dans le presse-papiers.
Auto-défilement quand on glisse au-delà du bord. La sélection native du texte
reste disponible en parallèle.
"""

from PySide6.QtCore import QEvent, QObject, QPoint, Qt
from PySide6.QtGui import QColor, QTextCursor, QTextFormat
from PySide6.QtWidgets import QApplication, QLabel, QTextEdit

from taskpilot.qt import theme


class _Handle(QLabel):
    """Poignée de glissement (capte presse / glisse / relâche)."""

    def __init__(self, selector):
        super().__init__("⠿", selector.viewport)
        self._sel = selector
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setToolTip("Glisser pour sélectionner des lignes "
                        "(copiées au relâcher)")
        self.restyle()
        self.hide()

    def restyle(self, hover=False):
        bg = theme.SURFACE_3 if hover else theme.SURFACE_2
        fg = theme.FG if hover else theme.MUTED
        self.setStyleSheet(
            f"QLabel {{ background: {bg}; color: {fg}; border-radius: 5px;"
            f" padding: 0 4px; font-weight: bold; }}")

    def enterEvent(self, _e):
        self.restyle(hover=True)

    def leaveEvent(self, _e):
        self.restyle()
        self._sel._maybe_hide()

    def mousePressEvent(self, _e):
        self._sel._start()

    def mouseMoveEvent(self, e):
        vy = self._sel.viewport.mapFromGlobal(
            e.globalPosition().toPoint()).y()
        self._sel._drag(vy)

    def mouseReleaseEvent(self, _e):
        self._sel._end()


class LineSelector(QObject):
    """Ajoute la sélection de lignes par glissement à un ``QPlainTextEdit``."""

    def __init__(self, edit):
        super().__init__(edit)
        self.edit = edit
        self.viewport = edit.viewport()
        self._anchor = None        # ligne de départ (numéro de bloc)
        self._hover_block = None
        self._bounds = None
        self.viewport.setMouseTracking(True)
        self.viewport.installEventFilter(self)
        self.handle = _Handle(self)
        theme.notifier.changed.connect(self._on_theme)

    def _on_theme(self):
        self.handle.restyle()

    def dispose(self):
        """Coupe l'abonnement au thème (à appeler avant destruction)."""
        try:
            theme.notifier.changed.disconnect(self._on_theme)
        except (RuntimeError, TypeError):
            pass

    # -- Survol : positionnement de la poignée -------------------------------
    def eventFilter(self, obj, ev):
        if obj is self.viewport and self._anchor is None:
            t = ev.type()
            if t == QEvent.MouseMove:
                self._hover(ev.position().toPoint())
            elif t == QEvent.Leave:
                self._maybe_hide()
        return False

    def _hover(self, pos):
        cursor = self.edit.cursorForPosition(pos)
        rect = self.edit.cursorRect(cursor)
        last = cursor.blockNumber() == self.edit.document().blockCount() - 1
        if last and pos.y() > rect.bottom():
            self.handle.hide()
            self._hover_block = None
            return
        self._hover_block = cursor.blockNumber()
        h = self.handle
        h.adjustSize()
        x = self.viewport.width() - h.width() - 4
        y = rect.top() + (rect.height() - h.height()) // 2
        h.move(max(0, x), max(0, y))
        h.show()
        h.raise_()

    def _maybe_hide(self):
        if not self.handle.underMouse():
            self.handle.hide()
            self._hover_block = None

    # -- Glissement ----------------------------------------------------------
    def _start(self):
        if self._hover_block is None:
            return
        self._anchor = self._hover_block
        self._highlight(self._anchor, self._anchor)

    def _drag(self, vy):
        if self._anchor is None:
            return
        sb = self.edit.verticalScrollBar()
        if vy < 0:
            sb.setValue(sb.value() - 1)
            vy = 0
        elif vy > self.viewport.height():
            sb.setValue(sb.value() + 1)
            vy = self.viewport.height() - 1
        vy = max(0, min(self.viewport.height() - 1, vy))
        block = self.edit.cursorForPosition(QPoint(2, vy)).blockNumber()
        self._highlight(self._anchor, block)

    def _end(self):
        if self._anchor is None:
            return
        if self._bounds:
            lo, hi = self._bounds
            doc = self.edit.document()
            lines = [doc.findBlockByNumber(b).text()
                     for b in range(lo, hi + 1)]
            text = "\n".join(lines)
            if text:
                QApplication.clipboard().setText(text)
        self.edit.setExtraSelections([])
        self._anchor = None
        self._bounds = None
        self.handle.hide()

    def _highlight(self, a, b):
        lo, hi = (a, b) if a <= b else (b, a)
        self._bounds = (lo, hi)
        doc = self.edit.document()
        start = doc.findBlockByNumber(lo)
        end = doc.findBlockByNumber(hi)
        cursor = QTextCursor(start)
        cursor.setPosition(end.position() + end.length() - 1,
                           QTextCursor.KeepAnchor)
        sel = QTextEdit.ExtraSelection()
        sel.cursor = cursor
        sel.format.setBackground(QColor(theme.SELECTION))
        sel.format.setProperty(QTextFormat.FullWidthSelection, True)
        self.edit.setExtraSelections([sel])
