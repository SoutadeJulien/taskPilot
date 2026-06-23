"""Lance le POC d'interface PySide6 de TaskPilot.

Utilise le venv dedie :  .venv-qt\\Scripts\\python.exe main_qt.py
(ou voir start_qt.bat). L'UI Tkinter historique reste disponible via main.py.
"""

from taskpilot.qt.app import main

if __name__ == "__main__":
    main()
