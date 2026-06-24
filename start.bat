@echo off
REM Lance TaskPilot (interface PySide6) via le venv dedie (.venv).
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [setup] Creation du venv .venv ^(Python 3.13^) et installation des deps...
    py -3.13 -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)
start "" ".venv\Scripts\pythonw.exe" main.py
