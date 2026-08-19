#!/usr/bin/env bash
# Construit dist/TaskPilot-x86_64.AppImage a partir du build « un dossier ».
#
#   ./packaging/build-appimage.sh
#
# Prerequis : les dependances de packaging/linux-deps.txt installees (sinon le
# binaire ne demarrera pas sur X11), PyInstaller et requirements.txt.
#
# Pourquoi une AppImage en plus du binaire brut : elle porte son entree de
# menu et son icone, les bureaux savent l'integrer sans script d'installation,
# et c'est le format qu'un utilisateur Linux s'attend a telecharger pour une
# application graphique. Elle ne resout PAS la question de la glibc — c'est la
# version de la distribution de BUILD qui fixe le plancher, d'ou le runner
# ubuntu-22.04 en CI.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)

PY=${PYTHON:-python3}
APPDIR=$ROOT/build/AppDir
OUT=$ROOT/dist/TaskPilot-x86_64.AppImage

echo "[1/4] Build PyInstaller (mode un dossier)..."
TASKPILOT_ONEDIR=1 "$PY" -m PyInstaller --noconfirm --distpath "$ROOT/dist/onedir" \
    taskpilot.spec

echo "[2/4] Construction de l'AppDir..."
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"
cp -a "$ROOT/dist/onedir/TaskPilot/." "$APPDIR/usr/bin/"

# L'entree .desktop d'une AppImage ne porte pas de chemin absolu : c'est AppRun
# qui localise le binaire, Exec ne contient donc que son nom.
sed 's|Exec="@EXEC@"|Exec=TaskPilot|' "$ROOT/packaging/taskpilot.desktop" \
    > "$APPDIR/usr/share/applications/taskpilot.desktop"
cp "$ROOT/taskpilot/assets/icon.png" \
   "$APPDIR/usr/share/icons/hicolor/256x256/apps/taskpilot.png"

# appimagetool exige le .desktop et l'icone a la RACINE de l'AppDir, en plus
# de leur emplacement normal sous usr/share.
cp "$APPDIR/usr/share/applications/taskpilot.desktop" "$APPDIR/taskpilot.desktop"
cp "$ROOT/taskpilot/assets/icon.png" "$APPDIR/taskpilot.png"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
# Point d'entree de l'AppImage. $APPDIR est renseigne par le runtime.
HERE=$(dirname "$(readlink -f "$0")")
exec "$HERE/usr/bin/TaskPilot" "$@"
APPRUN
chmod +x "$APPDIR/AppRun"

echo "[3/4] Recuperation d'appimagetool..."
TOOL=$ROOT/build/appimagetool-x86_64.AppImage
if [ ! -x "$TOOL" ]; then
    curl -fsSL -o "$TOOL" \
        https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x "$TOOL"
fi

echo "[4/4] Assemblage..."
mkdir -p "$ROOT/dist"
# --appimage-extract-and-run : appimagetool est lui-meme une AppImage et FUSE
# n'existe ni dans un conteneur CI ni dans beaucoup de VM.
ARCH=x86_64 "$TOOL" --appimage-extract-and-run "$APPDIR" "$OUT"

echo
echo "Termine : $OUT"
