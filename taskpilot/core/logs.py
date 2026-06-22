"""Sauvegarde optionnelle des sorties de consoles dans un dossier temporaire.

Chaque console peut écrire sa sortie dans un fichier ``.log`` sous un dossier
dédié du répertoire temporaire de l'OS. Le dossier est vidé au démarrage de
l'application pour ne garder que les logs de la session courante.
"""

import os
import re
import shutil
import tempfile

#: Dossier des logs par défaut, sous le répertoire temporaire de l'OS.
DEFAULT_LOG_DIR = os.path.join(tempfile.gettempdir(), "taskpilot-logs")

#: Dossier des logs courant (modifiable via ``set_log_dir``).
LOG_DIR = DEFAULT_LOG_DIR

#: Compteur global : garantit des noms de fichiers uniques et ordonnés.
_counter = 0
#: Caractères non sûrs dans un nom de fichier (remplacés par ``-``).
_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def set_log_dir(path):
    """Définit le dossier des logs. Vide / ``None`` => revient au défaut."""
    global LOG_DIR
    path = (path or "").strip()
    LOG_DIR = path or DEFAULT_LOG_DIR
    return LOG_DIR


def clean_log_dir():
    """Vide (puis recrée) le dossier des logs. Sans effet en cas d'erreur."""
    try:
        shutil.rmtree(LOG_DIR, ignore_errors=True)
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError:
        pass


def ensure_log_dir() -> bool:
    """Crée le dossier des logs au besoin. Retourne ``True`` s'il existe."""
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        return True
    except OSError:
        return False


def new_log_path(label: str):
    """Chemin de fichier unique pour la sortie d'une console ``label``.

    Retourne ``None`` si le dossier ne peut pas être créé.
    """
    global _counter
    if not ensure_log_dir():
        return None
    _counter += 1
    safe = _SAFE_RE.sub("-", label).strip("-")[:60] or "task"
    return os.path.join(LOG_DIR, f"{_counter:03d}_{safe}.log")


def open_log_dir():
    """Ouvre le dossier des logs dans l'explorateur de fichiers (Windows)."""
    ensure_log_dir()
    try:
        os.startfile(LOG_DIR)  # noqa: S606 (Windows uniquement)
    except (OSError, AttributeError):
        pass
