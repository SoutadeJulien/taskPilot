"""Detection, formatage et destruction des process Node.

Chaque OS a son propre backend d'inventaire, choisi par ``_all_processes`` :

* **Windows** — ``wmic``, avec repli PowerShell/CIM (``wmic`` a disparu des
  Windows recents) ;
* **Linux** — lecture directe de ``/proc`` (aucun process externe a lancer, et
  un temps CPU precis au tick pres la ou ``ps`` arrondit a la seconde) ;
* **macOS / BSD** — ``ps``, seul denominateur commun.

Le reste du module est independant de la plateforme : il ne manipule que la
table ``pid -> {ppid, name, cmd, mem, cpu_time}`` produite par ces backends.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

from taskpilot.core.system import (
    IS_LINUX, IS_WIN, kill_pid, kill_tree_win, run_quiet)


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


# ---------------------------------------------------------------------------
# Ports en ecoute
# ---------------------------------------------------------------------------
def get_listening_ports():
    """Mappe ``pid -> [ports]`` pour les sockets TCP en ecoute.

    Sous Unix, seuls les sockets des process de l'utilisateur courant exposent
    leur PID (restriction du noyau, valable pour ``ss`` comme pour ``lsof``) :
    c'est sans consequence ici, ou l'on observe des serveurs de dev lances par
    l'utilisateur.
    """
    ports = _ports_windows() if IS_WIN else _ports_unix()
    return {pid: sorted(s) for pid, s in ports.items()}


def _ports_windows() -> dict:
    ports = {}
    out = run_quiet(["netstat", "-ano", "-p", "TCP"])
    if not out:
        return ports
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
    return ports


#: PID d'un socket dans la colonne « Process » de ``ss`` : ``pid=1234``.
_SS_PID_RE = re.compile(r"pid=(\d+)")


def _ports_unix() -> dict:
    """``ss`` (iproute2, present sur toute distribution) puis repli ``lsof``."""
    return _ports_ss() or _ports_lsof()


def _ports_ss() -> dict:
    ports = {}
    out = run_quiet(["ss", "-lntp"])
    if not out:
        return ports
    for line in out.splitlines():
        pids = _SS_PID_RE.findall(line)
        if not pids:
            continue                      # en-tete, ou socket d'un autre user
        fields = line.split()
        if len(fields) < 4:
            continue
        port = fields[3].rsplit(":", 1)[-1]   # gere « [::]:3000 » et « *:3000 »
        if not port.isdigit():
            continue
        for pid in pids:
            ports.setdefault(int(pid), set()).add(int(port))
    return ports


def _ports_lsof() -> dict:
    ports = {}
    out = run_quiet(["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"])
    if not out:
        return ports
    for line in out.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 9 or not fields[1].isdigit():
            continue
        port = fields[8].rsplit(":", 1)[-1]
        if port.isdigit():
            ports.setdefault(int(fields[1]), set()).add(int(port))
    return ports


# ---------------------------------------------------------------------------
# Arbres de process
# ---------------------------------------------------------------------------
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


def _children_map(table) -> dict:
    """Index ``ppid -> [pids]`` d'une table de process."""
    children = {}
    for pid, info in table.items():
        children.setdefault(info["ppid"], []).append(pid)
    return children


def _collect_task_trees(roots, table, port_map) -> List[NodeProcess]:
    """Collecte les arbres de process de ``roots`` dans une table deja batie."""
    if not roots or not table:
        return []
    children = _children_map(table)

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


#: Noms d'executables consideres comme « Node », par plateforme.
_NODE_NAMES = frozenset(("node.exe",) if IS_WIN else ("node", "nodejs"))


def _is_node(info) -> bool:
    """Vrai si l'entree de table ``_all_processes`` est un process Node.

    On compare le **nom de l'executable**, jamais la ligne de commande : un
    ``grep node`` attraperait ``nodemon``, ``/opt/nodejs/bin/npm`` ou n'importe
    quel chemin contenant « node ».
    """
    return (info.get("name") or "").lower() in _NODE_NAMES


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


# ---------------------------------------------------------------------------
# Inventaire des process : un backend par plateforme
# ---------------------------------------------------------------------------
def _all_processes() -> dict:
    """Table ``pid -> {ppid, name, cmd, mem, cpu_time}`` de tous les process."""
    if IS_WIN:
        return _all_processes_windows()
    if IS_LINUX:
        return _all_processes_proc() or _all_processes_ps()
    return _all_processes_ps()


def _all_processes_windows() -> dict:
    table = {}
    out = run_quiet(
        ["wmic", "process", "get",
         "CommandLine,KernelModeTime,Name,ParentProcessId,ProcessId,"
         "UserModeTime,WorkingSetSize", "/format:csv"])
    if out is None:
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
    out = run_quiet(["powershell", "-NoProfile", "-NonInteractive",
                     "-Command", script])
    if not out:
        return table
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


#: Ticks par seconde et taille de page, pour convertir les champs de ``/proc``.
_CLK_TCK = float(os.sysconf("SC_CLK_TCK")) if hasattr(os, "sysconf") else 100.0
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096


def _all_processes_proc() -> dict:
    """Backend Linux : lecture de ``/proc``.

    Prefere a ``ps`` pour deux raisons : aucun process externe a lancer a
    chaque rafraichissement, et un temps CPU au tick pres (``ps`` n'affiche que
    des secondes entieres, ce qui rendrait la courbe de CPU% en escalier).

    Un process peut disparaitre entre le listing et la lecture de ses fichiers :
    chaque entree est donc lue de facon defensive et simplement ignoree si elle
    s'evapore.
    """
    table = {}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return table
    for entry in entries:
        if not entry.isdigit():
            continue
        pid = int(entry)
        info = _read_proc_entry(pid)
        if info is not None:
            table[pid] = info
    return table


def _read_proc_entry(pid: int):
    """Entree de table pour ``/proc/<pid>``, ou ``None`` si illisible."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            stat = f.read().decode("utf-8", "replace")
    except (OSError, ValueError):
        return None
    # Le champ ``comm`` est entre parentheses et peut contenir espaces et
    # parenthesing : on decoupe apres la DERNIERE parenthese fermante.
    close = stat.rfind(")")
    open_ = stat.find("(")
    if close < 0 or open_ < 0:
        return None
    name = stat[open_ + 1:close]
    fields = stat[close + 2:].split()
    # Indices relatifs (champ N de proc(5) -> fields[N - 3]) : ppid=4,
    # utime=14, stime=15, rss=24 (en pages).
    if len(fields) < 22:
        return None
    if fields[0] == "Z":
        # Process zombie : deja mort, il n'attend que d'etre recolte par son
        # pere. Il n'a plus ni ligne de commande ni memoire, on ne peut pas le
        # tuer — l'afficher dans l'onglet Process n'aurait aucun sens.
        return None
    try:
        ppid = int(fields[1])
        cpu_time = (int(fields[11]) + int(fields[12])) / _CLK_TCK
        mem = int(fields[21]) * _PAGE_SIZE
    except (ValueError, IndexError):
        return None
    return {"ppid": ppid or None, "name": name, "cmd": _read_cmdline(pid) or name,
            "mem": mem, "cpu_time": cpu_time}


def _read_cmdline(pid: int) -> str:
    """Ligne de commande de ``/proc/<pid>/cmdline`` (arguments separes par NUL).

    Vide pour les threads noyau, qui n'ont pas de ligne de commande.
    """
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            raw = f.read()
    except OSError:
        return ""
    return " ".join(raw.decode("utf-8", "replace").split("\x00")).strip()


def _all_processes_ps() -> dict:
    """Backend macOS / BSD (et repli Linux) : ``ps``.

    Le nom de l'executable est derive du premier mot de ``args`` : demander
    ``comm`` en colonne separee serait plus direct, mais ``comm`` vaut le chemin
    complet sous macOS et un chemin contenant une espace decalerait toutes les
    colonnes suivantes.
    """
    table = {}
    out = run_quiet(["ps", "-eo", "pid,ppid,rss,time,args"])
    if not out:
        return table
    for line in out.splitlines()[1:]:
        fields = line.split(None, 4)
        if len(fields) < 5 or not fields[0].isdigit():
            continue
        pid, ppid, rss, cputime, args = fields
        args = args.strip()
        exe = args.split(" ", 1)[0]
        table[int(pid)] = {
            "ppid": int(ppid) if ppid.isdigit() else None,
            "name": os.path.basename(exe),
            "cmd": args,
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


# ---------------------------------------------------------------------------
# Arret
# ---------------------------------------------------------------------------
def kill_process(pid) -> bool:
    """Tue un process **et toute sa descendance** par son PID.

    Hors Windows, on ne peut pas tuer le groupe : rien ne garantit qu'un PID
    arbitraire (un serveur Node repere dans l'onglet Process, lance depuis un
    terminal quelconque) soit seul dans le sien — on emporterait des process
    etrangers. On reconstruit donc l'arbre et on tue chaque descendant, le pere
    d'abord pour qu'il cesse d'en engendrer de nouveaux.
    """
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if IS_WIN:
        return kill_tree_win(pid)

    children = _children_map(_all_processes())
    order, stack = [], [pid]
    while stack:
        current = stack.pop(0)
        if current in order:
            continue                      # cycle impossible en theorie, sur en pratique
        order.append(current)
        stack.extend(children.get(current, []))
    # ``kill_pid`` echoue sur les process deja morts (course avec l'inventaire) :
    # seul le sort de la racine fait foi.
    killed = kill_pid(pid)
    for child in order[1:]:
        kill_pid(child)
    return killed


def format_memory(num_bytes) -> str:
    """Formate des octets en Ko/Mo/Go lisible."""
    if num_bytes <= 0:
        return "-"
    value = float(num_bytes)
    for unit in ("o", "Ko", "Mo", "Go"):
        if value < 1024 or unit == "Go":
            return f"{value:.0f} {unit}" if unit == "o" else f"{value:.1f} {unit}"
        value /= 1024
