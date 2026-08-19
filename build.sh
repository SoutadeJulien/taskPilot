#!/usr/bin/env bash
# Genere dist/TaskPilot (binaire autonome). Equivalent Unix de build.bat.
# Pour l'AppImage (avec entree de menu et icone) : ./packaging/build-appimage.sh
set -euo pipefail
cd "$(dirname "$0")"

PY=${PYTHON:-python3}

echo "[1/4] Verification de PyInstaller..."
"$PY" -c "import PyInstaller" 2>/dev/null || "$PY" -m pip install "pyinstaller>=6.11"

# Qt charge ses bibliotheques xcb depuis le systeme : PyInstaller ne peut les
# embarquer que si elles sont installees ICI. Sans elles, le binaire se
# construit sans erreur puis refuse de demarrer sur tout bureau X11.
echo "[2/4] Verification des bibliotheques Qt du systeme..."
if [ "$(uname -s)" = "Linux" ] && ! ldconfig -p | grep -q libxcb-cursor; then
    echo "  ATTENTION : libxcb-cursor est absente."
    echo "  Le binaire produit ne demarrera pas sur un bureau X11."
    echo "  Installe d'abord les paquets de packaging/linux-deps.txt, par ex. :"
    echo "    sudo apt-get install \$(grep -v '^#' packaging/linux-deps.txt)"
    echo
fi

echo "[3/4] Dependances runtime (ptyprocess, pyte, PySide6) embarquees..."
"$PY" -m pip install -r requirements.txt

echo "[4/4] Build..."
"$PY" -m PyInstaller --noconfirm taskpilot.spec

echo
echo "Termine. Executable : dist/TaskPilot"
echo "Installation dans le menu du bureau : ./packaging/install-desktop.sh"
