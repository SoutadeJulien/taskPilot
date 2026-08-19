#!/usr/bin/env bash
# Genere dist/TaskPilot (binaire autonome). Equivalent Unix de build.bat.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}

echo "[1/3] Verification de PyInstaller..."
"$PY" -c "import PyInstaller" 2>/dev/null || "$PY" -m pip install "pyinstaller>=6.11"

echo "[2/3] Dependances runtime (ptyprocess, pyte, PySide6) embarquees..."
"$PY" -m pip install -r requirements.txt

echo "[3/3] Build..."
"$PY" -m PyInstaller --noconfirm taskpilot.spec

echo
echo "Termine. Executable : dist/TaskPilot"
echo "Installation dans le menu du bureau : ./packaging/install-desktop.sh"
