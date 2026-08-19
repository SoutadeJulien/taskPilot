#!/usr/bin/env bash
# Installe TaskPilot dans le menu du bureau (Linux), pour l'utilisateur courant.
#
#   ./packaging/install-desktop.sh [chemin/vers/TaskPilot]
#
# Sans argument, pointe sur dist/TaskPilot s'il existe (build.sh), sinon sur
# start.sh (lancement depuis les sources). Desinstallation :
#
#   rm ~/.local/share/applications/taskpilot.desktop
#   rm ~/.local/share/icons/hicolor/256x256/apps/taskpilot.png
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)

TARGET=${1:-}
if [ -z "$TARGET" ]; then
    if [ -x "$ROOT/dist/TaskPilot" ]; then
        TARGET="$ROOT/dist/TaskPilot"
    else
        TARGET="$ROOT/start.sh"
    fi
fi
TARGET=$(cd "$(dirname "$TARGET")" && pwd)/$(basename "$TARGET")

if [ ! -x "$TARGET" ]; then
    echo "Cible introuvable ou non executable : $TARGET" >&2
    exit 1
fi

APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/256x256/apps"
mkdir -p "$APPS" "$ICONS"

install -m 644 "$ROOT/taskpilot/assets/icon.png" "$ICONS/taskpilot.png"
sed "s|@EXEC@|$TARGET|" "$ROOT/packaging/taskpilot.desktop" \
    > "$APPS/taskpilot.desktop"
chmod 644 "$APPS/taskpilot.desktop"

# Rafraichit les caches ; absents sur les bureaux minimalistes, sans gravite.
command -v update-desktop-database >/dev/null && \
    update-desktop-database "$APPS" || true
command -v gtk-update-icon-cache >/dev/null && \
    gtk-update-icon-cache -f -t "${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor" 2>/dev/null || true

echo "Installe : $APPS/taskpilot.desktop"
echo "Cible    : $TARGET"
