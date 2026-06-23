"""En-tete partage des panneaux console / terminal.

Une « pilule » elevee (en relief sur le fond profond de la console) portant la
pastille de couleur du projet, l'etat du process et le bouton Redemarrer.
Se re-style a chaud lors d'un changement de theme (``theme.notifier``).
"""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from taskpilot.qt import effects, theme


class ConsoleHeader(QFrame):
    """Barre d'en-tete d'une console : pastille + etat + bouton Redemarrer."""

    def __init__(self, on_restart, on_copy=None, parent=None):
        super().__init__(parent)
        self._status = ("running", None)
        self._dot_color = None

        h = QHBoxLayout(self)
        h.setContentsMargins(12, 4, 6, 4)
        h.setSpacing(8)
        self._dot = QLabel()
        self._dot.setFixedSize(9, 9)
        self._dot.hide()
        h.addWidget(self._dot)
        self.status = QLabel()
        h.addWidget(self.status)
        h.addStretch(1)
        if on_copy is not None:
            self._copy = QPushButton("⧉ Copier")
            self._copy.setToolTip(
                "Copier la sélection (ou toute la sortie si rien n'est "
                "sélectionné)")
            self._copy.clicked.connect(lambda: on_copy())
            h.addWidget(self._copy)
        self._restart = QPushButton("↻ Redémarrer")
        self._restart.setToolTip("Relancer la commande dans cette console")
        self._restart.clicked.connect(lambda: on_restart())
        h.addWidget(self._restart)

        effects.add_shadow(self, blur=20, dy=3, alpha=90)
        self._restyle()
        theme.notifier.changed.connect(self._restyle)

    def dispose(self):
        """Coupe l'abonnement au thème (à appeler avant destruction)."""
        try:
            theme.notifier.changed.disconnect(self._restyle)
        except (RuntimeError, TypeError):
            pass

    # -- Etat ----------------------------------------------------------------
    def set_running(self):
        self._status = ("running", None)
        self._apply_status()

    def set_exited(self, code):
        self._status = ("exited", code)
        self._apply_status()

    def set_dot(self, color):
        self._dot_color = color or None
        self._apply_dot()

    # -- Application du style -------------------------------------------------
    def _apply_status(self):
        kind, code = self._status
        if kind == "running":
            self.status.setText("●  en cours")
            color = theme.ACCENT
        elif code == 0:
            self.status.setText("●  terminé (0)")
            color = theme.MUTED
        else:
            self.status.setText(f"●  arrêté (code {code})")
            color = theme.RED
        self.status.setStyleSheet(
            f"color: {color}; font-weight: 600; background: transparent;")

    def _apply_dot(self):
        if self._dot_color:
            self._dot.setStyleSheet(
                f"background: {self._dot_color}; border-radius: 4px;")
            self._dot.show()
        else:
            self._dot.hide()

    def _restyle(self):
        self.setStyleSheet(
            f"ConsoleHeader {{ background: {theme.SURFACE_2}; "
            f"border-radius: 10px; }}")
        self._apply_status()
        self._apply_dot()
