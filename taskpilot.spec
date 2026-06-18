# -*- mode: python ; coding: utf-8 -*-
"""Spec PyInstaller pour TaskPilot : un seul .exe autonome, sans console.

Build :  pyinstaller taskpilot.spec   (ou lancer build.bat)
Sortie :  dist/TaskPilot.exe
"""

from PyInstaller.utils.hooks import collect_all

block_cipher = None

# pywinpty embarque des binaires natifs (OpenConsole.exe / winpty-agent.exe +
# DLL) et pyte ses modules : on collecte tout pour que le terminal fonctionne
# dans l'exe autonome. ATTENTION : collect_all renvoie (datas, binaries,
# hiddenimports) DANS CET ORDRE — toute inversion casse le bundling du PTY.
_pty_d, _pty_b, _pty_h = collect_all("winpty")
_pyte_d, _pyte_b, _pyte_h = collect_all("pyte")

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=_pty_b + _pyte_b,
    datas=_pty_d + _pyte_d,
    hiddenimports=_pty_h + _pyte_h,
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
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
    icon="taskpilot/assets/icon.ico",
)
