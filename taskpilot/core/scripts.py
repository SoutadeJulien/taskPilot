"""Scripts utilitaires : resolution d'interpreteur et materialisation sur disque.

Un « script » est un bout de code Python ou Node nomme, ecrit dans un fichier
temporaire puis lance dans une console classique (``TaskConsole``). Ce module
ne connait rien de Qt : il ne fait que fabriquer une ``CommandSpec`` prete a
lancer.
"""

import os
import shutil
import sys
import tempfile

from taskpilot.core.vscode_tasks import CommandSpec

#: Metadonnees par langage : extension du fichier temporaire et libelle.
LANGUAGES = {
    "python": {"label": "Python", "ext": ".py"},
    "node": {"label": "JavaScript (Node)", "ext": ".js"},
}

#: Dossier ou sont materialises les scripts avant execution.
SCRIPTS_DIR = os.path.join(tempfile.gettempdir(), "taskpilot-scripts")


class InterpreterMissing(Exception):
    """Aucun interpreteur trouve pour le langage demande."""


def python_exe():
    """Chemin de l'interpreteur Python a utiliser.

    En mode « gele » (exe PyInstaller), ``sys.executable`` pointe sur
    TaskPilot.exe et non sur un Python : on retombe alors sur un ``python`` du
    PATH. En mode normal, on reutilise l'interpreteur courant.
    """
    if getattr(sys, "frozen", False):
        return shutil.which("python") or shutil.which("python3")
    return sys.executable


def node_exe():
    """Chemin de l'executable Node du PATH (``None`` s'il est absent)."""
    return shutil.which("node")


def interpreter_for(language):
    """Interpreteur pour ``language`` ou ``InterpreterMissing`` si introuvable."""
    if language == "node":
        exe = node_exe()
        if not exe:
            raise InterpreterMissing(
                "Node est introuvable dans le PATH. Installe Node.js pour "
                "lancer des scripts JavaScript.")
        return exe
    exe = python_exe()
    if not exe:
        raise InterpreterMissing(
            "Aucun interpreteur Python trouve dans le PATH.")
    return exe


def _safe_name(name):
    """Nom de fichier sur, derive du nom de script (jamais vide)."""
    keep = [c if c.isalnum() or c in "-_." else "_" for c in name.strip()]
    return ("".join(keep) or "script")[:60]


def build_spec(script, project=""):
    """Materialise ``script`` sur disque et renvoie sa ``CommandSpec``.

    ``script`` est un dict ``{name, language, code, cwd}``. Le repertoire de
    travail est celui du script s'il est renseigne, sinon le ``project`` fourni,
    sinon le dossier personnel. Le projet courant est aussi expose via la
    variable d'environnement ``TASKPILOT_PROJECT``.
    """
    language = script.get("language", "python")
    meta = LANGUAGES.get(language, LANGUAGES["python"])
    interpreter = interpreter_for(language)

    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    path = os.path.join(SCRIPTS_DIR, _safe_name(script.get("name", "")) + meta["ext"])
    with open(path, "w", encoding="utf-8") as f:
        f.write(script.get("code", ""))

    cwd = (script.get("cwd") or "").strip() or project or os.path.expanduser("~")
    env = dict(os.environ)
    if project:
        env["TASKPILOT_PROJECT"] = project

    argv = [interpreter, path]
    display = f"{meta['label']} · {script.get('name', '')}"
    return CommandSpec(argv=argv, shell=False, cwd=cwd, env=env, display=display)
