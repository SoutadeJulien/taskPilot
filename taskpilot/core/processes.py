"""Detection, formatage et destruction des process Node."""

import os
import signal
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional

from taskpilot.core.system import IS_WIN, NO_WINDOW


@dataclass
class NodeProcess:
    """Un process observe a un instant donne.

    ``cpu_time`` est le temps CPU cumule (secondes) ; ``cpu`` est le
    pourcentage instantane calcule par l'appelant a partir des deltas.
    ``ppid`` et ``task`` ne sont remplis que pour les arbres de process des
    tasks (cf. ``find_task_processes``).
    """

    pid: int
    cmd: str
    mem: int                              # octets
    cpu_time: Optional[float]             # secondes cumulees
    ports: List[int] = field(default_factory=list)
    cpu: Optional[float] = None           # % instantane (rempli plus tard)
    ppid: Optional[int] = None            # PID parent (arbres de tasks)
    task: Optional[str] = None            # libelle de la task d'appartenance


def get_listening_ports():
    """Mappe ``pid -> [ports]`` pour les sockets TCP en ecoute."""
    ports = {}
    try:
        if IS_WIN:
            out = subprocess.check_output(
                ["netstat", "-ano", "-p", "TCP"],
                text=True, errors="replace", stderr=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
            )
            for line in out.splitlines():
                parts = line.split()
                if len(parts) < 5 or parts[0].upper() != "TCP":
                    continue
                if parts[3].upper() != "LISTENING":
                    continue
                local, pid = parts[1], parts[-1]
                if not pid.isdigit():
                    continue
                port = local.rsplit(":", 1)[-1]
                if port.isdigit():
                    ports.setdefault(int(pid), set()).add(int(port))
        else:
            out = subprocess.check_output(
                ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"],
                text=True, errors="replace", stderr=subprocess.DEVNULL,
            )
            for line in out.splitlines()[1:]:
                fields = line.split()
                if len(fields) < 9 or not fields[1].isdigit():
                    continue
                pid = int(fields[1])
                port = fields[8].rsplit(":", 1)[-1]
                if port.isdigit():
                    ports.setdefault(pid, set()).add(int(port))
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {}
    return {pid: sorted(s) for pid, s in ports.items()}


def find_task_processes(roots) -> List[NodeProcess]:
    """Liste tous les process des tasks, arbre complet.

    ``roots`` est une liste de couples ``(pid, label)`` : le process racine
    lance par chaque console et le libelle de la task associee. On enumere tous
    les process de la machine, on reconstruit la hierarchie parent -> enfants
    puis on collecte, pour chaque racine, l'integralite de sa descendance.
    Chaque process retourne porte le ``task`` de la racine qui l'a capture en
    premier (pas de doublon entre tasks).
    """
    return _collect_task_trees(roots, _all_processes(), get_listening_ports())


def _collect_task_trees(roots, table, port_map) -> List[NodeProcess]:
    """Collecte les arbres de process de ``roots`` dans une table deja batie."""
    if not roots or not table:
        return []
    children = {}
    for pid, info in table.items():
        children.setdefault(info["ppid"], []).append(pid)

    procs: List[NodeProcess] = []
    seen = set()
    for root_pid, label in roots:
        stack = [root_pid]
        while stack:
            pid = stack.pop()
            if pid in seen:
                continue
            seen.add(pid)
            info = table.get(pid)
            if info is None:
                continue
            procs.append(NodeProcess(
                pid=pid, cmd=info["cmd"] or "?", mem=info["mem"],
                cpu_time=info["cpu_time"], ports=port_map.get(pid, []),
                ppid=info["ppid"], task=label))
            stack.extend(children.get(pid, []))
    return procs


def _is_node(info) -> bool:
    """Vrai si l'entree de table ``_all_processes`` est un process Node."""
    if IS_WIN:
        return info.get("name", "").lower() == "node.exe"
    cmd = (info.get("cmd") or "").lower()
    return "node" in cmd and "taskpilot" not in cmd


def _node_orphans(table, port_map, seen) -> List[NodeProcess]:
    """Process Node de la machine non deja captures sous une task (``seen``)."""
    procs: List[NodeProcess] = []
    for pid, info in table.items():
        if pid in seen or not _is_node(info):
            continue
        procs.append(NodeProcess(
            pid=pid, cmd=info["cmd"] or "node", mem=info["mem"],
            cpu_time=info["cpu_time"], ports=port_map.get(pid, [])))
    return procs


def find_processes(roots) -> List[NodeProcess]:
    """Arbre des process des tasks + process Node orphelins de la machine.

    Les process descendant d'une racine de console sont groupes sous le libelle
    de leur task (``task`` rempli) ; tous les autres process ``node`` visibles
    sont retournes avec ``task=None`` (groupe « hors tasks »). Permet a l'onglet
    Process de fonctionner en permanence, meme sans console lancee.

    Une seule enumeration des process (``_all_processes``) et un seul listing
    des ports (``get_listening_ports``) servent aux deux groupes.
    """
    table = _all_processes()
    port_map = get_listening_ports()
    task_procs = _collect_task_trees(roots, table, port_map)
    seen = {p.pid for p in task_procs}
    return task_procs + _node_orphans(table, port_map, seen)


def _all_processes() -> dict:
    """Table ``pid -> {ppid, cmd, mem, cpu_time}`` de tous les process."""
    if IS_WIN:
        return _all_processes_windows()
    return _all_processes_unix()


def _all_processes_windows() -> dict:
    table = {}
    try:
        out = subprocess.check_output(
            ["wmic", "process", "get",
             "CommandLine,KernelModeTime,Name,ParentProcessId,ProcessId,"
             "UserModeTime,WorkingSetSize", "/format:csv"],
            text=True, errors="replace", stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _all_processes_powershell()
    for line in out.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("node,"):
            continue
        parts = line.split(",")
        if len(parts) < 8:
            continue
        # Colonnes (ordre alphabetique wmic, prefixees du nom de machine) :
        # Node,CommandLine,KernelModeTime,Name,ParentProcessId,ProcessId,
        # UserModeTime,WorkingSetSize. On lit par la fin (champs numeriques),
        # la CommandLine pouvant contenir des virgules.
        working, user, pid = parts[-1].strip(), parts[-2].strip(), parts[-3].strip()
        ppid, name, kernel = parts[-4].strip(), parts[-5].strip(), parts[-6].strip()
        cmd = ",".join(parts[1:-6]).strip()
        if not pid.isdigit():
            continue
        if kernel.isdigit() and user.isdigit():
            cpu_time = (int(kernel) + int(user)) / 1e7
        else:
            cpu_time = None
        table[int(pid)] = {
            "ppid": int(ppid) if ppid.isdigit() else None,
            "cmd": cmd, "name": name,
            "mem": int(working) if working.isdigit() else 0,
            "cpu_time": cpu_time}
    return table


def _all_processes_powershell() -> dict:
    """Repli si wmic est absent (Windows recent) : Get-CimInstance."""
    table = {}
    script = (
        "Get-CimInstance Win32_Process | ForEach-Object { "
        "'{0}`t{1}`t{2}`t{3}`t{4}`t{5}' -f $_.ProcessId,$_.ParentProcessId,"
        "$_.WorkingSetSize,($_.KernelModeTime+$_.UserModeTime),$_.Name,"
        "$_.CommandLine }"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            text=True, errors="replace", stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {}
    for line in out.splitlines():
        f = line.split("\t", 5)
        if len(f) < 5 or not f[0].isdigit():
            continue
        ticks = int(f[3]) if f[3].isdigit() else None
        table[int(f[0])] = {
            "ppid": int(f[1]) if f[1].isdigit() else None,
            "name": f[4], "cmd": f[5] if len(f) > 5 else "",
            "mem": int(f[2]) if f[2].isdigit() else 0,
            "cpu_time": ticks / 1e7 if ticks is not None else None}
    return table


def _all_processes_unix() -> dict:
    table = {}
    try:
        out = subprocess.check_output(
            ["ps", "-eo", "pid,ppid,rss,time,args"], text=True, errors="replace")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return {}
    for line in out.splitlines()[1:]:
        fields = line.split(None, 4)
        if len(fields) < 5 or not fields[0].isdigit():
            continue
        pid, ppid, rss, cputime, args = fields
        table[int(pid)] = {
            "ppid": int(ppid) if ppid.isdigit() else None,
            "cmd": args.strip(),
            "mem": int(rss) * 1024 if rss.isdigit() else 0,
            "cpu_time": parse_ps_time(cputime)}
    return table


def parse_ps_time(s) -> Optional[float]:
    """Convertit le format TIME de ``ps`` (``[[DD-]HH:]MM:SS``) en secondes."""
    try:
        days = 0
        if "-" in s:
            d, s = s.split("-", 1)
            days = int(d)
        parts = [int(x) for x in s.split(":")]
        while len(parts) < 3:
            parts.insert(0, 0)
        h, m, sec = parts
        return days * 86400 + h * 3600 + m * 60 + sec
    except Exception:
        return None


def kill_process(pid) -> bool:
    """Tue un process (et son arbre sous Windows) par son PID."""
    try:
        if IS_WIN:
            subprocess.check_call(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
            )
        else:
            os.kill(pid, signal.SIGKILL)
        return True
    except Exception:
        return False


def format_memory(num_bytes) -> str:
    """Formate des octets en Ko/Mo/Go lisible."""
    if num_bytes <= 0:
        return "-"
    value = float(num_bytes)
    for unit in ("o", "Ko", "Mo", "Go"):
        if value < 1024 or unit == "Go":
            return f"{value:.0f} {unit}" if unit == "o" else f"{value:.1f} {unit}"
        value /= 1024
