"""Detection, formatage et destruction des process Node."""

import os
import signal
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional

from taskpilot.core.system import IS_WIN, NO_WINDOW


@dataclass
class NodeProcess:
    """Un process Node observe a un instant donne.

    ``cpu_time`` est le temps CPU cumule (secondes) ; ``cpu`` est le
    pourcentage instantane calcule par l'appelant a partir des deltas.
    """

    pid: int
    cmd: str
    mem: int                              # octets
    cpu_time: Optional[float]             # secondes cumulees
    ports: List[int] = field(default_factory=list)
    cpu: Optional[float] = None           # % instantane (rempli plus tard)


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


def find_node_processes() -> List[NodeProcess]:
    """Liste les process Node visibles sur la machine."""
    procs: List[NodeProcess] = []
    port_map = get_listening_ports()

    if IS_WIN:
        procs = _find_windows(port_map)
    else:
        procs = _find_unix(port_map)
    return procs


def _find_windows(port_map) -> List[NodeProcess]:
    procs: List[NodeProcess] = []
    try:
        out = subprocess.check_output(
            ["wmic", "process", "where", "name='node.exe'",
             "get", "CommandLine,KernelModeTime,ProcessId,UserModeTime,WorkingSetSize",
             "/format:csv"],
            text=True, errors="replace", stderr=subprocess.DEVNULL,
            creationflags=NO_WINDOW,
        )
        for line in out.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("node,"):
                continue
            parts = line.split(",")
            if len(parts) < 6:
                continue
            working_set = parts[-1].strip()
            user_time = parts[-2].strip()
            pid = parts[-3].strip()
            kernel_time = parts[-4].strip()
            cmd = ",".join(parts[1:-4]).strip()
            if not pid.isdigit():
                continue
            mem = int(working_set) if working_set.isdigit() else 0
            if kernel_time.isdigit() and user_time.isdigit():
                cpu_time = (int(kernel_time) + int(user_time)) / 1e7
            else:
                cpu_time = None
            procs.append(NodeProcess(
                pid=int(pid), cmd=cmd or "node.exe", mem=mem,
                cpu_time=cpu_time, ports=port_map.get(int(pid), [])))
        return procs
    except (subprocess.CalledProcessError, FileNotFoundError):
        return _find_windows_tasklist(port_map)


def _find_windows_tasklist(port_map) -> List[NodeProcess]:
    """Repli si wmic est absent : tasklist (memoire seule, pas de CPU)."""
    procs: List[NodeProcess] = []
    out = subprocess.check_output(
        ["tasklist", "/FI", "IMAGENAME eq node.exe", "/FO", "CSV", "/NH"],
        text=True, errors="replace", stderr=subprocess.DEVNULL,
        creationflags=NO_WINDOW,
    )
    for line in out.splitlines():
        cols = [c.strip('"') for c in line.split('","')]
        if len(cols) >= 5 and cols[1].isdigit():
            mem_kb = cols[4].replace(" ", "").replace(" ", "") \
                .replace("Ko", "").replace("K", "").replace(".", "") \
                .replace(",", "")
            mem = int(mem_kb) * 1024 if mem_kb.isdigit() else 0
            procs.append(NodeProcess(
                pid=int(cols[1]), cmd=cols[0], mem=mem, cpu_time=None,
                ports=port_map.get(int(cols[1]), [])))
    return procs


def _find_unix(port_map) -> List[NodeProcess]:
    procs: List[NodeProcess] = []
    out = subprocess.check_output(
        ["ps", "-eo", "pid,rss,time,args"], text=True, errors="replace")
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        fields = line.split(None, 3)
        if len(fields) < 4 or not fields[0].isdigit():
            continue
        pid, rss, cputime, args = fields
        name = args.lower()
        if "node" not in name or "taskpilot" in name:
            continue
        procs.append(NodeProcess(
            pid=int(pid), cmd=args.strip(),
            mem=int(rss) * 1024 if rss.isdigit() else 0,
            cpu_time=parse_ps_time(cputime),
            ports=port_map.get(int(pid), [])))
    return procs


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
