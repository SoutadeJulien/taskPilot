#!/usr/bin/env bash
# Genere dist/TaskPilotMcp : le serveur MCP des logs seul, autonome.
# L'app Qt se construit avec build.sh — les deux binaires sont independants.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}

echo "[1/4] Verification de PyInstaller..."
"$PY" -c "import PyInstaller" 2>/dev/null || "$PY" -m pip install "pyinstaller>=6.11"

echo "[2/4] SDK MCP (non embarque dans le binaire Qt)..."
"$PY" -m pip install -r requirements-mcp.txt

echo "[3/4] Build..."
"$PY" -m PyInstaller --noconfirm taskpilot-mcp.spec

# Le transport MCP est stdio : un binaire qui demarre mais ne repond pas au
# handshake passerait le build sans que rien ne le signale.
echo "[4/4] Verification du dialogue stdio..."
if ! "$PY" tools/smoke_mcp.py dist/TaskPilotMcp; then
    echo
    echo "ECHEC : l'executable ne repond pas au protocole MCP."
    exit 1
fi

echo
echo "Termine. Executable : dist/TaskPilotMcp"
