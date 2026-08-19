# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller pour TaskPilot : un seul executable autonome, sans console.

Build :  pyinstaller taskpilot.spec   (ou lancer build.bat / build.sh)
Sortie :  dist/TaskPilot.exe (Windows) ou dist/TaskPilot (Linux, macOS)
"""

import os

from PyInstaller.utils.hooks import collect_all

block_cipher = None

IS_WIN = os.name == "nt"

# Mode « un dossier » au lieu de l'executable unique, active par
# TASKPILOT_ONEDIR=1. Sert a construire l'AppImage (cf.
# packaging/build-appimage.sh) : un binaire onefile dans une AppImage se
# ferait extraire deux fois a chaque lancement — plusieurs secondes de
# demarrage pour ~80 Mo — alors qu'un AppDir monte les fichiers directement.
ONEDIR = os.environ.get("TASKPILOT_ONEDIR") == "1"

# Le backend PTY est different selon la plateforme et embarque des ressources
# que PyInstaller ne trouve pas seul : pywinpty a des binaires natifs
# (OpenConsole.exe / winpty-agent.exe + DLL), ptyprocess un module pur mais
# importe dynamiquement. On ne collecte QUE celui de la plateforme courante :
# collecter l'autre echouerait, il n'y est pas installe (cf. requirements.txt).
# ATTENTION : collect_all renvoie (datas, binaries, hiddenimports) DANS CET
# ORDRE — toute inversion casse le bundling du PTY.
_pty_d, _pty_b, _pty_h = collect_all("winpty" if IS_WIN else "ptyprocess")
_pyte_d, _pyte_b, _pyte_h = collect_all("pyte")

# PySide6 (interface Qt) est embarque par le hook PyInstaller du module, tire
# automatiquement par l'import dans main.py.
a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=_pty_b + _pyte_b,
    datas=_pty_d + _pyte_d + [("taskpilot/assets", "taskpilot/assets")],
    hiddenimports=_pty_h + _pyte_h,
    hookspath=[],
    runtime_hooks=[],
    # Le serveur MCP des logs (taskpilot/mcp) est lance a part par le client
    # (Zed, Claude Code...), jamais par l'app : on l'exclut, ainsi que son SDK
    # `mcp`, pour ne pas alourdir l'exe avec des dependances inutilisees en GUI.
    excludes=["taskpilot.mcp", "mcp"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    *([] if ONEDIR else [a.binaries, a.zipfiles, a.datas]),
    [],
    exclude_binaries=ONEDIR,
    name="TaskPilot",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # app GUI : pas de fenetre console
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # L'icone .ico n'a de sens que pour un binaire PE : hors Windows, l'icone
    # vient du fichier .desktop (packaging/taskpilot.desktop).
    icon="taskpilot/assets/icon.ico" if IS_WIN else None,
)

if ONEDIR:
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="TaskPilot",
    )
