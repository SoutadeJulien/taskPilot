"""Lecture et interpretation des tasks VS Code (``.vscode/tasks.json``).

Gere le format JSONC (commentaires + virgules finales), la substitution des
variables ``${...}`` courantes, les types ``shell`` / ``process`` / ``npm`` et
la resolution recursive des tasks composees (``dependsOn``).
"""

import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from taskpilot.core.system import IS_WIN

#: Une task VS Code est conservee telle quelle sous forme de dict JSON.
Task = Dict[str, object]


@dataclass
class CommandSpec:
    """Tout ce qu'il faut pour lancer une commande de task."""

    argv: List[str]
    shell: bool
    cwd: str
    env: Optional[Dict[str, str]]
    display: str


@dataclass
class TaskLeaf:
    """Une commande concrete a executer, issue de la resolution d'une task."""

    label: str
    spec: CommandSpec


# ---------------------------------------------------------------------------
# Parsing JSONC
# ---------------------------------------------------------------------------
def parse_jsonc(text: str):
    """Parse du JSON tolerant aux commentaires et virgules finales."""
    out = []
    i, n = 0, len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            i += 2
            while i < n and text[i] not in "\r\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(c)
        i += 1
    s = "".join(out)
    s = re.sub(r",(\s*[}\]])", r"\1", s)        # virgules finales
    return json.loads(s)


def load_vscode_tasks(project_dir: str) -> List[Task]:
    """Retourne la liste des tasks d'un projet (``.vscode/tasks.json``)."""
    path = os.path.join(project_dir, ".vscode", "tasks.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "r", encoding="utf-8-sig") as f:
        data = parse_jsonc(f.read())
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    return [t for t in tasks if isinstance(t, dict)]


def task_label(task: Task) -> str:
    return (task.get("label") or task.get("script")
            or task.get("command") or "(task)")


def is_group_task(task: Task) -> bool:
    """Vrai si la task n'est qu'un assemblage (``dependsOn``)."""
    return bool(task.get("dependsOn"))


# ---------------------------------------------------------------------------
# Construction des commandes
# ---------------------------------------------------------------------------
def _subst_vars(value, workspace: str):
    """Substitue les variables VS Code courantes dans une chaine."""
    if not isinstance(value, str):
        return value
    base = os.path.basename(workspace.rstrip("\\/"))
    value = value.replace("${workspaceFolder}", workspace)
    value = value.replace("${workspaceRoot}", workspace)
    value = value.replace("${workspaceFolderBasename}", base)
    value = value.replace("${cwd}", workspace)
    value = value.replace("${userHome}", os.path.expanduser("~"))
    value = value.replace("${pathSeparator}", os.sep)
    value = re.sub(r"\$\{env:([^}]+)\}",
                   lambda m: os.environ.get(m.group(1), ""), value)
    return value


def _quote(arg: str) -> str:
    if any(ch in arg for ch in ' "\t&|<>^'):
        return '"' + arg.replace('"', '\\"') + '"'
    return arg


def _shell_argv(cmdline: str) -> List[str]:
    """Encapsule une ligne de commande dans le shell de la plateforme."""
    if IS_WIN:
        return ["cmd", "/d", "/s", "/c", cmdline]
    return ["/bin/sh", "-c", cmdline]


def build_command(task: Task, workspace: str) -> Optional[CommandSpec]:
    """Construit la ``CommandSpec`` d'une task, ou ``None`` si task composee."""
    options = task.get("options") or {}
    cwd = _subst_vars(options.get("cwd") or workspace, workspace)
    env = None
    if isinstance(options.get("env"), dict):
        env = dict(os.environ)
        for k, v in options["env"].items():
            env[str(k)] = _subst_vars(str(v), workspace)

    ttype = task.get("type", "process")

    if ttype == "npm":
        script = task.get("script", "")
        cmdline = f"npm run {script}".strip() if script else "npm"
        return CommandSpec(_shell_argv(cmdline), True, cwd, env, cmdline)

    command = _subst_vars(task.get("command", ""), workspace)
    raw_args = task.get("args", []) or []
    args = []
    for a in raw_args:
        if isinstance(a, dict):
            a = a.get("value", "")
        args.append(_subst_vars(str(a), workspace))

    if not command:
        return None  # task composee (dependsOn) sans commande propre

    if ttype == "shell":
        cmdline = (" ".join([command] + [_quote(a) for a in args])
                   if args else command)
        return CommandSpec(_shell_argv(cmdline), True, cwd, env, cmdline)

    # type "process" (ou autre) : execution directe sans shell
    argv = [command] + args
    return CommandSpec(argv, False, cwd, env, " ".join(argv))


def flatten_tasks(label: str, tasks_by_label: Dict[str, Task],
                  workspace: str, seen=None) -> Tuple[List[TaskLeaf], bool]:
    """Resout ``dependsOn`` recursivement en une liste ordonnee de commandes.

    Renvoie ``(leaves, sequential)`` ou ``sequential`` indique qu'un
    ``dependsOrder: sequence`` a ete rencontre.
    """
    if seen is None:
        seen = set()
    task = tasks_by_label.get(label)
    if task is None or label in seen:
        return [], False
    seen.add(label)

    sequential = task.get("dependsOrder") == "sequence"
    leaves: List[TaskLeaf] = []

    depends = task.get("dependsOn")
    if depends:
        dep_labels = [depends] if isinstance(depends, str) else list(depends)
        for dep in dep_labels:
            sub_leaves, sub_seq = flatten_tasks(
                dep, tasks_by_label, workspace, seen)
            leaves.extend(sub_leaves)
            sequential = sequential or sub_seq

    spec = build_command(task, workspace)
    if spec is not None:
        leaves.append(TaskLeaf(label=task_label(task), spec=spec))

    return leaves, sequential
