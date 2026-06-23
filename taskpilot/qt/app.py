"""Point d'entree du POC Qt : cree la QApplication et la fenetre principale."""

import sys

from PySide6.QtWidgets import QApplication

from taskpilot.config import Config
from taskpilot.qt import theme
from taskpilot.qt.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("TaskPilot")
    app.setStyle("Fusion")
    config = Config()
    theme.apply_theme(app, config.theme)
    window = MainWindow(config)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
