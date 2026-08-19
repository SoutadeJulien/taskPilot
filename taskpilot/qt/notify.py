"""Notifications systeme, avec deux transports selon ce que le bureau expose.

1. **Zone de notification** (``QSystemTrayIcon.showMessage``) : route vers le
   centre de notifications natif sous Windows 10/11, KDE, XFCE, Cinnamon… et
   donne en prime une icone cliquable qui ramene la fenetre au premier plan.
2. **``notify-send``** : repli Linux. GNOME (et les sessions Wayland en
   general) n'expose plus de zone de notification : ``isSystemTrayAvailable``
   y est faux et le transport 1 ne notifierait jamais. ``notify-send``
   (libnotify) parle directement au serveur de notifications du bureau et est
   present sur toutes les installations de bureau courantes.

Si aucun des deux n'est disponible, ``notify`` devient un no-op silencieux :
une notification manquante ne doit jamais empecher une task de tourner.
"""

import shutil
import subprocess

from PySide6.QtWidgets import QSystemTrayIcon

from taskpilot.core.system import IS_LINUX
from taskpilot.qt.assets import app_icon, icon_path


class Notifier:
    """Emetteur de notifications ; choisit son transport au demarrage."""

    #: Duree d'affichage des bulles (ms).
    TIMEOUT_MS = 6000

    def __init__(self, window):
        self._window = window
        self._tray = None
        self._notify_send = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._setup_tray()
        elif IS_LINUX:
            self._notify_send = shutil.which("notify-send")

    def _setup_tray(self):
        icon = self._window.windowIcon()
        if icon.isNull():
            icon = app_icon()
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
        if self._tray is not None:
            icon = (QSystemTrayIcon.Information if success
                    else QSystemTrayIcon.Warning)
            self._tray.showMessage(title, message, icon, self.TIMEOUT_MS)
        elif self._notify_send:
            self._notify_send_notify(title, message, success)

    def _notify_send_notify(self, title, message, success):
        argv = [self._notify_send, "--app-name=TaskPilot",
                f"--expire-time={self.TIMEOUT_MS}",
                "--urgency=" + ("normal" if success else "critical")]
        path = icon_path()
        if path:
            argv.append(f"--icon={path}")
        # ``--`` protege un titre ou un message commencant par « - ».
        argv += ["--", title, message]
        try:
            subprocess.Popen(argv, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        except OSError:
            self._notify_send = None      # inutile de reessayer a chaque task

    def dispose(self):
        if self._tray is not None:
            self._tray.hide()
            self._tray = None
