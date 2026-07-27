"""Barre de recherche d'une console (Ctrl+F).

Une bande discrete au-dessus de la sortie : champ de saisie, compteur
« 3 / 12 », navigation precedent/suivant, options *casse* et *mot entier*.
Toutes les occurrences sont surlignees, celle en cours l'est plus fortement et
est amenee dans la vue.

La console continue de defiler pendant la recherche : les positions des
occurrences bougent (nouvelles lignes, purge des plus anciennes). Le rescan est
donc **redeclenche a l'arrivee de sortie**, coalesce par un timer pour ne pas
relire le document a chaque paquet, et l'occurrence courante est retrouvee par
sa position dans le document plutot que par son rang.
"""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit)

from taskpilot.qt import overlays, theme

#: Plafond d'occurrences surlignees (5000 lignes de console au maximum).
MAX_MATCHES = 5000
#: Coalescence du rescan quand la console recoit de la sortie (ms).
REFRESH_MS = 200


class _Field(QLineEdit):
    """Champ de saisie : Entree = suivant, Maj+Entree = precedent, Echap = fermer."""

    def __init__(self, bar):
        super().__init__()
        self._bar = bar
        self.setPlaceholderText("Rechercher dans la console…")

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_Escape:
            self._bar.close_bar()
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Down, Qt.Key_Up):
            back = (key == Qt.Key_Up
                    or (key in (Qt.Key_Return, Qt.Key_Enter)
                        and event.modifiers() & Qt.ShiftModifier))
            self._bar.step(-1 if back else 1)
        else:
            super().keyPressEvent(event)


class FindBar(QFrame):
    """Recherche incrementale dans un ``QPlainTextEdit`` de console."""

    def __init__(self, edit, parent=None):
        super().__init__(parent)
        self.edit = edit
        self._matches = []      # [(debut, fin)] en positions document
        self._index = -1        # rang de l'occurrence courante
        self._anchor = -1       # position de l'occurrence courante (rescan)
        self._build()
        self.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(REFRESH_MS)
        self._timer.timeout.connect(self._rescan)
        theme.notifier.changed.connect(self._restyle)

    # -- Construction --------------------------------------------------------
    def _build(self):
        h = QHBoxLayout(self)
        h.setContentsMargins(10, 4, 6, 4)
        h.setSpacing(6)
        self._field = _Field(self)
        self._field.textChanged.connect(self._on_text)
        h.addWidget(self._field, 1)
        self._count = QLabel()
        self._count.setMinimumWidth(70)
        self._count.setAlignment(Qt.AlignCenter)
        h.addWidget(self._count)
        self._case = self._toggle(h, "Aa", "Respecter la casse")
        self._word = self._toggle(h, "|ab|", "Mots entiers")
        self._button(h, "▲", "Occurrence précédente (Maj+Entrée)",
                     lambda: self.step(-1))
        self._button(h, "▼", "Occurrence suivante (Entrée)",
                     lambda: self.step(1))
        self._button(h, "✕", "Fermer (Échap)", self.close_bar)
        self._restyle()

    def _button(self, layout, text, tip, slot):
        btn = QPushButton(text)
        btn.setToolTip(tip)
        btn.setFixedWidth(30)
        btn.setFocusPolicy(Qt.NoFocus)
        btn.clicked.connect(lambda: slot())
        layout.addWidget(btn)
        return btn

    def _toggle(self, layout, text, tip):
        btn = self._button(layout, text, tip, lambda: None)
        btn.setCheckable(True)
        btn.setFixedWidth(38)
        btn.toggled.connect(lambda _on: self._rescan(jump=True))
        return btn

    def _restyle(self):
        self.setStyleSheet(
            f"FindBar {{ background: {theme.SURFACE_2}; "
            f"border-radius: {theme.radius(10)}px; }}")
        self._count.setStyleSheet(
            f"color: {theme.MUTED}; background: transparent;")
        if self.isVisible():
            self._paint()

    # -- Cycle de vie --------------------------------------------------------
    def activate(self, seed=""):
        """Ouvre la barre (Ctrl+F) : amorcee par ``seed``, champ selectionne."""
        # Une selection multi-lignes ne fait pas une requete utile (Qt separe
        # les paragraphes par U+2029 dans ``selectedText``).
        if seed and "\n" not in seed and "\u2029" not in seed:
            self._field.setText(seed)
        self.show()
        self._field.setFocus()
        self._field.selectAll()
        self._rescan(jump=True)

    def close_bar(self):
        """Ferme la barre, retire les surlignages et rend le focus a la sortie."""
        self.hide()
        self._matches, self._index, self._anchor = [], -1, -1
        overlays.clear_layer(self.edit, "find")
        overlays.clear_layer(self.edit, "find-current")
        self.edit.setFocus()

    def dispose(self):
        """Coupe l'abonnement au theme (a appeler avant destruction)."""
        self._timer.stop()
        try:
            theme.notifier.changed.disconnect(self._restyle)
        except (RuntimeError, TypeError):
            pass

    def on_output(self):
        """Sortie recue : les positions ont bouge, on replanifie un rescan."""
        if self.isVisible() and self._field.text():
            self._timer.start()

    # -- Recherche -----------------------------------------------------------
    def _on_text(self):
        self._anchor = -1       # nouvelle requete : on repart du haut de la vue
        self._rescan(jump=True)

    def _flags(self):
        flags = QTextDocument.FindFlags()
        if self._case.isChecked():
            flags |= QTextDocument.FindCaseSensitively
        if self._word.isChecked():
            flags |= QTextDocument.FindWholeWords
        return flags

    def _rescan(self, jump=False):
        """Relit le document et recompose les surlignages.

        ``jump`` amene l'occurrence courante dans la vue (frappe, navigation) ;
        un rescan declenche par l'arrivee de sortie ne bouge pas la vue.
        """
        query = self._field.text()
        self._matches = []
        if query:
            doc = self.edit.document()
            flags = self._flags()
            cursor = doc.find(query, 0, flags)
            while not cursor.isNull():
                self._matches.append(
                    (cursor.selectionStart(), cursor.selectionEnd()))
                if len(self._matches) >= MAX_MATCHES:
                    break
                cursor = doc.find(query, cursor.selectionEnd(), flags)
        self._index = self._locate()
        self._paint(jump)

    def _locate(self):
        """Rang de l'occurrence courante apres un rescan.

        On reprend celle qui etait active (par sa position, robuste au defilement
        et a la purge des vieilles lignes) ; a defaut, la premiere visible.
        """
        if not self._matches:
            return -1
        target = self._anchor if self._anchor >= 0 else self._first_visible()
        for i, (start, _end) in enumerate(self._matches):
            if start >= target:
                return i
        return len(self._matches) - 1

    def _first_visible(self):
        """Position du document en haut de la zone visible."""
        return self.edit.cursorForPosition(self.edit.viewport().rect().topLeft()
                                           ).position()

    def step(self, delta):
        """Passe a l'occurrence suivante (``+1``) ou precedente (``-1``)."""
        if not self._matches:
            return
        self._index = (self._index + delta) % len(self._matches)
        self._paint(jump=True)

    # -- Rendu ---------------------------------------------------------------
    def _paint(self, jump=False):
        total = len(self._matches)
        if not self._field.text():
            self._count.setText("")
        elif not total:
            self._count.setText("aucun")
        else:
            self._count.setText(f"{self._index + 1} / {total}"
                                + (" +" if total >= MAX_MATCHES else ""))
        self._field.setStyleSheet(
            "" if total or not self._field.text()
            else f"QLineEdit {{ color: {theme.RED}; }}")
        others, current = [], []
        for i, (start, end) in enumerate(self._matches):
            sel = QTextEdit.ExtraSelection()
            sel.cursor = self._cursor(start, end)
            if i == self._index:
                sel.format.setBackground(QColor(theme.ACCENT))
                sel.format.setForeground(QColor(theme.ACCENT_FG))
                current.append(sel)
            else:
                sel.format.setBackground(QColor(theme.SURFACE_3))
                others.append(sel)
        overlays.set_layer(self.edit, "find", others)
        overlays.set_layer(self.edit, "find-current", current)
        if jump and current:
            self._anchor = self._matches[self._index][0]
            self._reveal(current[0].cursor)

    def _cursor(self, start, end):
        cursor = QTextCursor(self.edit.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        return cursor

    def _reveal(self, cursor):
        """Amene ``cursor`` dans la vue sans voler la selection au champ."""
        self.edit.setTextCursor(cursor)
        self.edit.ensureCursorVisible()
