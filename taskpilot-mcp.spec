# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller pour le serveur MCP des logs : un .exe autonome, console.

Volontairement disjoint de ``taskpilot.spec`` : l'exe GUI exclut le SDK ``mcp``,
celui-ci exclut Qt et le PTY. Aucun des deux ne porte les dependances de
l'autre — c'est toute la raison d'etre de ce second artefact.

Build :  pyinstaller taskpilot-mcp.spec   (ou lancer build-mcp.bat / .sh)
Sortie :  dist/TaskPilotMcp.exe (Windows) ou dist/TaskPilotMcp (Linux, macOS)
"""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

IS_WIN = os.name == 'nt'

# Le SDK `mcp` (FastMCP) charge des sous-modules par introspection : on les
# collecte explicitement. `mcp.cli` est ecarte — c'est l'outillage en ligne de
# commande du SDK, il importe `typer` (un extra non installe) et le collecter
# ferait echouer l'analyse ; le serveur stdio ne s'en sert pas.
_mcp_h = collect_submodules("mcp", filter=lambda n: not n.startswith("mcp.cli"))
_mcp_d = collect_data_files("mcp")

a = Analysis(
    ["mcp_main.py"],
    pathex=[],
    binaries=[],
    datas=_mcp_d,
    # pydantic v2 (dependance de FastMCP) resout une partie de ses modules
    # dynamiquement ; PyInstaller ne les voit pas par analyse statique seule.
    hiddenimports=_mcp_h + ["taskpilot.config", "taskpilot.core.logs"],
    hookspath=[],
    runtime_hooks=[],
    # Le serveur n'a aucune interface : tout le stack graphique et le PTY sont
    # du poids mort ici (~150 Mo de PySide6 en moins).
    excludes=[
        "PySide6", "shiboken6", "taskpilot.qt",
        "winpty", "ptyprocess", "pyte", "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="TaskPilotMcp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    # OBLIGATOIRE : le transport MCP est stdio. Sans console, PyInstaller prive
    # le process de stdin/stdout et le serveur ne repond a rien.
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Idem taskpilot.spec : une icone .ico ne concerne qu un binaire PE.
    icon="taskpilot/assets/icon.ico" if IS_WIN else None,
)
