"""Notifications systeme (toasts Windows) via QSystemTrayIcon.

Aucune dependance externe : ``QSystemTrayIcon.showMessage`` route vers le
centre de notifications natif sous Windows 10/11. L'icone de la zone de
notification est creee une seule fois et reste discrete ; elle ne sert qu'a
emettre les bulles (un clic dessus ramene la fenetre au premier plan).
"""

import os

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon

ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")


class Notifier:
    """Emetteur de toasts adosse a une icone de zone de notification.

    Degrade proprement : si le systeme n'expose pas de zone de notification
    (``isSystemTrayAvailable`` faux), ``notify`` devient un no-op silencieux.
    """

    #: Duree d'affichage des bulles (ms).
    TIMEOUT_MS = 6000

    def __init__(self, window):
        self._window = window
        self._tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self._window.windowIcon()
        if icon.isNull():
            icon_path = os.path.join(ASSETS, "icon.ico")
            if os.path.isfile(icon_path):
                icon = QIcon(icon_path)
        self._tray = QSystemTrayIcon(icon, self._window)
        self._tray.setToolTip("TaskPilot")
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _on_activated(self, reason):
        # Un clic (ou double-clic) sur l'icone ramene la fenetre au premier plan.
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self._window.showNormal()
            self._window.raise_()
            self._window.activateWindow()

    def notify(self, title, message, success=True):
        """Affiche une bulle. ``success`` choisit l'icone info/avertissement."""
        if self._tray is None:
            return
        icon = (QSystemTrayIcon.Information if success
                else QSystemTrayIcon.Warning)
        self._tray.showMessage(title, message, icon, self.TIMEOUT_MS)

    def dispose(self):
        if self._tray is not None:
            self._tray.hide()
            self._tray = None
