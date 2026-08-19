"""Ressources embarquees (icone de l'application).

Centralise la resolution du fichier d'icone : le ``.ico`` sert a Windows (et a
l'executable PyInstaller), le ``.png`` aux bureaux Unix, ou les gestionnaires
de fenetres et les serveurs de notification attendent du PNG.
"""

import os

from PySide6.QtGui import QIcon

from taskpilot.core.system import IS_WIN

#: Dossier des ressources embarquees.
ASSETS = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

#: Fichiers d'icone, par ordre de preference selon la plateforme.
_CANDIDATES = ("icon.ico", "icon.png") if IS_WIN else ("icon.png", "icon.ico")


def icon_path():
    """Chemin du meilleur fichier d'icone disponible, ou ``None``."""
    for name in _CANDIDATES:
        path = os.path.join(ASSETS, name)
        if os.path.isfile(path):
            return path
    return None


def app_icon():
    """Icone de l'application (``QIcon`` vide si aucune ressource trouvee)."""
    path = icon_path()
    return QIcon(path) if path else QIcon()
