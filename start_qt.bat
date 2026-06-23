@echo off
REM Lance le POC d'interface PySide6 via le venv dedie (.venv-qt).
cd /d "%~dp0"
if not exist ".venv-qt\Scripts\python.exe" (
    echo [setup] Creation du venv .venv-qt ^(Python 3.13^) et installation des deps...
    py -3.13 -m venv .venv-qt
    ".venv-qt\Scripts\python.exe" -m pip install --upgrade pip
    ".venv-qt\Scripts\python.exe" -m pip install -r requirements-qt.txt
)
start "" ".venv-qt\Scripts\pythonw.exe" main_qt.py
