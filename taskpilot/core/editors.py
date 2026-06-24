"""Ouverture d'un fichier (ligne/colonne) dans l'editeur configure.

Sert au clic sur une reference de fichier reperee dans la sortie d'une console
(ex. ``src/app.ts:42:13`` d'une erreur de build). L'editeur est choisi par
l'utilisateur (VS Code, Cursor, Zed) ; sa commande shell est resolue dans le
PATH.
"""

import os
import re
import shutil
import subprocess

from taskpilot.core.system import IS_WIN, NO_WINDOW

#: Editeurs supportes : cle -> (nom affiche, commande shell, drapeau ``-g``).
#: ``goto`` indique d'utiliser ``-g`` (VS Code / Cursor) ; Zed accepte la cible
#: ``chemin:ligne:colonne`` sans drapeau.
EDITORS = {
    "vscode": {"name": "VS Code", "cmd": "code", "goto": True},
    "cursor": {"name": "Cursor", "cmd": "cursor", "goto": True},
    "zed": {"name": "Zed", "cmd": "zed", "goto": False},
}
DEFAULT_EDITOR = "vscode"

#: Reference de fichier dans une ligne de console : un chemin (avec un segment
#: de repertoire, ou un simple ``nom.ext``) suivi d'un ``:ligne[:colonne]``
#: optionnel. L'extension obligatoire limite fortement les faux positifs.
PATH_RE = re.compile(
    r"(?P<path>"
    r"(?:[A-Za-z]:[\\/])?(?:[\w.+\-]+[\\/])+[\w.+\-]+\.[A-Za-z][\w]*"
    r"|[\w.+\-]+\.[A-Za-z][\w]*)"
    r"(?::(?P<line>\d+)(?::(?P<col>\d+))?)?")


def valid_key(key):
    """Normalise une cle d'editeur (retombe sur le defaut si inconnue)."""
    return key if key in EDITORS else DEFAULT_EDITOR


def editor_name(key):
    return EDITORS[valid_key(key)]["name"]


def find_link_at(line, col):
    """Reference de fichier sous la colonne ``col`` de ``line``, ou ``None``.

    Retourne ``(start, end, path, line_no, col_no)`` (bornes dans ``line``).
    Ignore les portions d'URL (``http://…``) qui ne sont pas des fichiers
    locaux.
    """
    for m in PATH_RE.finditer(line):
        if m.start() <= col <= m.end():
            # Ecarte les URL : si le token qui contient le match comporte
            # « :// », ce n'est pas un fichier local ouvrable.
            ws = line.rfind(" ", 0, m.start()) + 1
            if "://" in line[ws:m.end()]:
                return None
            ln = int(m.group("line")) if m.group("line") else None
            cn = int(m.group("col")) if m.group("col") else None
            return (m.start(), m.end(), m.group("path"), ln, cn)
    return None


def resolve_path(path, cwd):
    """Resout un chemin relatif contre ``cwd`` s'il existe sur disque."""
    if not os.path.isabs(path) and cwd:
        candidate = os.path.normpath(os.path.join(cwd, path))
        if os.path.exists(candidate):
            return candidate
    return path


def _target(path, line, col):
    target = path
    if line:
        target += f":{line}"
        if col:
            target += f":{col}"
    return target


def open_in_editor(key, path, line=None, col=None, cwd=None):
    """Ouvre ``path`` (eventuellement ligne/colonne) dans l'editeur ``key``.

    Retourne ``(ok, message)`` : ``message`` decrit l'echec si ``ok`` est faux.
    """
    spec = EDITORS[valid_key(key)]
    exe = shutil.which(spec["cmd"])
    if not exe:
        return False, (
            f"La commande « {spec['cmd']} » de {spec['name']} est introuvable "
            "dans le PATH.\nInstalle sa commande shell (VS Code/Cursor : "
            "« Shell Command: Install 'code'/'cursor' command » depuis la "
            "palette).")
    target = _target(resolve_path(path, cwd), line, col)
    args = ["-g", target] if spec["goto"] else [target]
    try:
        if IS_WIN and exe.lower().endswith((".cmd", ".bat")):
            # Les shims .cmd ne sont pas executables par CreateProcess : on
            # passe par cmd.exe (la forme liste gere le quoting des espaces).
            subprocess.Popen(["cmd", "/c", exe, *args], creationflags=NO_WINDOW)
        else:
            subprocess.Popen([exe, *args], creationflags=NO_WINDOW)
    except OSError as e:
        return False, f"Impossible de lancer {spec['name']} : {e}"
    return True, ""
