"""Point d'entrée du serveur MCP des logs : ``python -m taskpilot.mcp``.

Outils exposés (tous en **lecture seule**) :

* ``list_logs``    : liste les fichiers ``.log`` de la session courante ;
* ``read_log``     : lit un fichier (tronqué si trop gros) ;
* ``tail_log``     : retourne les N dernières lignes d'un fichier ;
* ``search_logs``  : cherche un motif dans tous les logs.

Le dossier des logs est résolu **exactement** comme l'application (cf.
``main_window`` : ``logs.set_log_dir(config.log_dir)``), pour pointer sur le
bon dossier même si l'utilisateur l'a personnalisé.
"""

import os
import re

from mcp.server.fastmcp import FastMCP

from taskpilot.config import Config
from taskpilot.core import logs

mcp = FastMCP("taskpilot-logs")


def _log_dir() -> str:
    """Dossier des logs courant, résolu comme dans l'application."""
    logs.set_log_dir(Config().log_dir)
    return logs.LOG_DIR


def _resolve(name: str) -> str:
    """Chemin absolu sûr d'un log ``name`` à l'intérieur du dossier des logs.

    Empêche toute remontée de chemin (``..``, chemin absolu) : seul un fichier
    ``*.log`` directement contenu dans le dossier des logs est accepté.
    """
    base = _log_dir()
    # On ne garde que le nom de fichier : neutralise les chemins absolus / ``..``.
    candidate = os.path.normpath(os.path.join(base, os.path.basename(name)))
    base_real = os.path.normcase(os.path.realpath(base))
    cand_real = os.path.normcase(os.path.realpath(candidate))
    if os.path.dirname(cand_real) != base_real:
        raise ValueError(f"Fichier hors du dossier des logs : {name!r}")
    if not cand_real.endswith(".log"):
        raise ValueError(f"Seuls les fichiers .log sont autorisés : {name!r}")
    if not os.path.isfile(candidate):
        raise FileNotFoundError(f"Log introuvable : {name!r}")
    return candidate


@mcp.tool()
def list_logs() -> list[dict]:
    """Liste les logs de la session courante (du plus ancien au plus récent).

    Retourne pour chaque fichier : ``name``, ``size`` (octets) et ``modified``
    (timestamp epoch). Le nom (``NNN_label.log``) reflète l'ordre de lancement.
    """
    base = _log_dir()
    out = []
    try:
        names = sorted(n for n in os.listdir(base) if n.endswith(".log"))
    except OSError:
        return out
    for name in names:
        path = os.path.join(base, name)
        try:
            st = os.stat(path)
        except OSError:
            continue
        out.append({"name": name, "size": st.st_size, "modified": st.st_mtime})
    return out


@mcp.tool()
def read_log(name: str, max_bytes: int = 200_000) -> str:
    """Lit le contenu d'un log.

    Si le fichier dépasse ``max_bytes``, seule la **fin** est retournée (les
    logs sont généralement consultés par la fin), précédée d'un marqueur de
    troncature.
    """
    path = _resolve(name)
    size = os.path.getsize(path)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        if size > max_bytes:
            f.seek(size - max_bytes)
            data = f.read()
            skipped = size - max_bytes
            return f"[... {skipped} octets tronqués au début ...]\n{data}"
        return f.read()


@mcp.tool()
def tail_log(name: str, lines: int = 200) -> str:
    """Retourne les ``lines`` dernières lignes d'un log."""
    path = _resolve(name)
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        tail = f.readlines()[-max(1, lines):]
    return "".join(tail)


@mcp.tool()
def search_logs(
    query: str,
    regex: bool = False,
    ignore_case: bool = True,
    max_results: int = 200,
) -> list[dict]:
    """Cherche ``query`` dans tous les logs de la session.

    ``regex`` interprète ``query`` comme une expression régulière, sinon c'est
    une recherche de sous-chaîne littérale. Retourne une liste de
    ``{file, line, text}`` (numéro de ligne à partir de 1, texte sans le saut
    de ligne final), limitée à ``max_results``.
    """
    base = _log_dir()
    flags = re.IGNORECASE if ignore_case else 0
    pattern = re.compile(query if regex else re.escape(query), flags)
    out: list[dict] = []
    try:
        names = sorted(n for n in os.listdir(base) if n.endswith(".log"))
    except OSError:
        return out
    for name in names:
        path = os.path.join(base, name)
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f, 1):
                    if pattern.search(line):
                        out.append({"file": name, "line": i,
                                    "text": line.rstrip("\n")})
                        if len(out) >= max_results:
                            return out
        except OSError:
            continue
    return out


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
