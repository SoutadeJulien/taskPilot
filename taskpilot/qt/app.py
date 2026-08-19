"""Point d'entree Qt : cree la QApplication et la fenetre principale."""

import sys

from PySide6.QtWidgets import QApplication

from taskpilot.config import Config
from taskpilot.core.system import DESKTOP_FILE_NAME
from taskpilot.qt import theme
from taskpilot.qt.assets import app_icon
from taskpilot.qt.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TaskPilot")
    # Sans nom de fichier .desktop, GNOME/Wayland n'associe pas la fenetre a
    # son icone et l'affiche comme une application inconnue. Sans effet
    # ailleurs.
    app.setDesktopFileName(DESKTOP_FILE_NAME)
    app.setWindowIcon(app_icon())
    # « Fusion » est le seul style Qt disponible sur toutes les plateformes :
    # il garantit que le QSS des themes rende partout a l'identique.
    app.setStyle("Fusion")
    config = Config()
    theme.set_radius(config.radius)
    theme.set_density(config.density)
    theme.set_ui_font(config.ui_font_family, config.ui_font_size)
    theme.set_mono_font(config.mono_font_family, config.mono_font_size)
    theme.set_accent_override(config.accent_override)
    theme.apply_theme(app, config.theme)
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
