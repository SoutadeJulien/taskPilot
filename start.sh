#!/usr/bin/env bash
# Lance TaskPilot (interface PySide6) via le venv dedie (.venv).
# Equivalent Unix de start.bat.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}

if [ ! -x ".venv/bin/python" ]; then
    echo "[setup] Creation du venv .venv et installation des dependances..."
    "$PY" -m venv .venv
    .venv/bin/python -m pip install --upgrade pip
    .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python main.py "$@"
