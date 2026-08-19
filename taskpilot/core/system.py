"""Couche d'adaptation a la plateforme : le seul module qui sait sur quel OS
tourne TaskPilot.

Tout le reste du code (``task_runner``, ``processes``, ``editors``, la couche
Qt...) passe par les helpers d'ici plutot que de tester l'OS lui-meme. Ajouter
le support d'une plateforme se fait donc en etendant ce module, sans toucher a
la logique metier.

Les seules exceptions volontaires sont l'inventaire des process
(``processes.py``) et le pseudo-terminal (``pty_backend.py``) : chaque OS y a
un backend entier, trop gros pour vivre ici.
"""

import os
import shlex
import shutil
import signal
import subprocess
import sys

#: Vrai sous Windows.
IS_WIN = os.name == "nt"
#: Vrai sous macOS.
IS_MAC = sys.platform == "darwin"
#: Vrai sous Linux (et assimiles : *BSD).
IS_LINUX = not IS_WIN and not IS_MAC
#: Vrai partout sauf Windows (Linux + macOS).
IS_POSIX = not IS_WIN

#: Nombre de coeurs logiques (au moins 1), utilise pour le calcul du CPU%.
NCPU = os.cpu_count() or 1

#: Drapeau de creation de process empechant l'ouverture d'une console
#: (Windows uniquement ; 0 ailleurs).
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if IS_WIN else 0


# ---------------------------------------------------------------------------
# Lancement de process
# ---------------------------------------------------------------------------
def spawn_kwargs(new_group: bool = False) -> dict:
    """Arguments ``subprocess`` specifiques a la plateforme.

    ``new_group`` isole le process dans sa propre session, ce qui rend possible
    le kill de tout son arbre (cf. ``kill_session``). Sous Windows le kill
    d'arbre passe par un Job Object (cf. ``jobobject.py``) : le drapeau y est
    sans effet.

    On utilise ``start_new_session`` et **jamais** ``preexec_fn=os.setsid`` :
    ``preexec_fn`` est documente comme non sur dans une application
    multi-thread — ce qui est exactement notre cas (un thread lecteur par
    console).
    """
    if IS_WIN:
        return {"creationflags": NO_WINDOW}
    return {"start_new_session": True} if new_group else {}


def run_quiet(argv, **kwargs):
    """Sortie texte d'une commande, sans fenetre console ni bruit sur stderr.

    Retourne ``None`` si la commande est absente ou echoue : tous les appelants
    ont un repli.
    """
    try:
        return subprocess.check_output(
            argv, text=True, errors="replace", stderr=subprocess.DEVNULL,
            **spawn_kwargs(), **kwargs)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError,
            UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# Shell
# ---------------------------------------------------------------------------
def shell_argv(cmdline: str):
    """Encapsule une ligne de commande dans le shell de la plateforme."""
    if IS_WIN:
        return ["cmd", "/d", "/s", "/c", cmdline]
    return ["/bin/sh", "-c", cmdline]


def quote_arg(arg: str) -> str:
    """Protege un argument pour le shell de la plateforme.

    Comme VS Code, on applique un *strong quoting* : l'argument arrive au
    programme tel quel, sans expansion (``$VAR``, glob...).
    """
    if IS_WIN:
        if any(ch in arg for ch in ' "\t&|<>^'):
            return '"' + arg.replace('"', '\\"') + '"'
        return arg
    return shlex.quote(arg)


#: Shells interactifs proposes dans le menu « nouvelle console », par
#: plateforme : ``(libelle, argv, commande cherchee dans le PATH)``.
_WIN_SHELLS = (
    ("PowerShell", ["powershell.exe", "-NoLogo"], "powershell"),
    ("CMD", ["cmd.exe"], "cmd"),
    ("Bash", ["bash", "-i"], "bash"),
)
_POSIX_SHELLS = (
    ("Bash", ["bash", "-i"], "bash"),
    ("Zsh", ["zsh", "-i"], "zsh"),
    ("Fish", ["fish", "-i"], "fish"),
    ("sh", ["sh", "-i"], "sh"),
)


def default_shells():
    """Shells interactifs disponibles : ``((libelle, argv), ...)``.

    Les shells absents du PATH sont filtres pour ne pas proposer une entree qui
    echouerait au lancement. Sous Unix, le shell de l'utilisateur (``$SHELL``)
    passe en tete. Si rien n'est detectable (PATH exotique), on renvoie la
    liste brute plutot qu'un menu vide.
    """
    table = _WIN_SHELLS if IS_WIN else _POSIX_SHELLS
    found = [(label, argv) for label, argv, probe in table if shutil.which(probe)]
    if not IS_WIN:
        user_shell = (os.environ.get("SHELL") or "").strip()
        name = os.path.basename(user_shell)
        if user_shell and os.path.isfile(user_shell):
            # ``bash`` -> ``Bash``, pour rester homogene avec les libelles
            # ecrits en dur dans les tables ci-dessus.
            label = name.capitalize() if name else "Shell"
            found = [(label, [user_shell, "-i"])] + [
                f for f in found if os.path.basename(f[1][0]) != name]
    if not found:
        found = [(label, argv) for label, argv, _ in table]
    return tuple(found)


# ---------------------------------------------------------------------------
# Arret de process
# ---------------------------------------------------------------------------
def kill_pid(pid: int) -> bool:
    """Tue un process **seul**, sans sa descendance."""
    try:
        if IS_WIN:
            return subprocess.call(
                ["taskkill", "/F", "/PID", str(pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                **spawn_kwargs()) == 0
        os.kill(pid, signal.SIGKILL)
        return True
    except (OSError, ValueError):
        return False


def kill_tree_win(pid: int) -> bool:
    """``taskkill /T`` : tue le process et toute sa descendance (Windows)."""
    try:
        return subprocess.call(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **spawn_kwargs()) == 0
    except (OSError, ValueError):
        return False


def _all_pids():
    """Liste brute des PID vivants (juste les numeros, sans leurs details).

    Volontairement minimal : l'inventaire complet — lignes de commande,
    memoire, temps CPU — est le travail de ``processes.py``. On ne veut ici
    qu'un balayage rapide pour un arret.
    """
    if IS_LINUX and os.path.isdir("/proc"):
        try:
            return [int(e) for e in os.listdir("/proc") if e.isdigit()]
        except OSError:
            return []
    out = run_quiet(["ps", "-eo", "pid="])
    return [int(t) for t in out.split() if t.isdigit()] if out else []


def kill_session(pid: int) -> bool:
    """Tue toute la session du process ``pid`` : l'analogue Unix du Job Object.

    A n'utiliser que sur un process **qu'on a lance nous-memes** dans une
    session neuve (``spawn_kwargs(new_group=True)``, ou un PTY qui appelle
    ``setsid``) : toute sa descendance y reste, et rien d'etranger n'y entre.
    Pour un PID arbitraire, voir ``processes.kill_process``, qui parcourt
    l'arbre.

    Tuer le seul *groupe* ne suffit pas : un shell interactif active le
    controle de tache et place chaque job d'arriere-plan (``npm run dev &``)
    dans un groupe distinct. Ces jobs restent en revanche dans la **session**
    du shell — c'est donc la bonne unite, et celle qui correspond a ce que fait
    le Job Object sous Windows.
    """
    if IS_WIN:
        return kill_tree_win(pid)
    try:
        sid = os.getsid(pid)
    except (OSError, ValueError):
        return kill_pid(pid)
    # Garde-fou : si le process partage notre session (le ``setsid`` a echoue,
    # ou l'appelant s'est trompe de PID), la tuer emporterait l'application.
    # On se rabat sur le groupe — et seulement s'il n'est pas le notre non
    # plus, sinon le repli serait tout aussi fatal.
    if sid == os.getsid(0):
        try:
            pgid = os.getpgid(pid)
            if pgid != os.getpgid(0):
                os.killpg(pgid, signal.SIGKILL)
                return True
        except (OSError, ValueError):
            pass
        return kill_pid(pid)

    killed = kill_pid(pid)                 # le chef d'abord : il cesse d'engendrer
    for other in _all_pids():
        if other == pid:
            continue
        try:
            if os.getsid(other) == sid:
                kill_pid(other)
        except (OSError, ValueError):
            continue                       # process disparu entre-temps
    return killed


# ---------------------------------------------------------------------------
# Integration bureau
# ---------------------------------------------------------------------------
def open_in_file_manager(path: str) -> bool:
    """Ouvre ``path`` dans l'explorateur de fichiers du bureau."""
    if not path:
        return False
    try:
        if IS_WIN:
            os.startfile(path)  # noqa: S606 (Windows uniquement)
            return True
        opener = "open" if IS_MAC else "xdg-open"
        if not shutil.which(opener):
            return False
        subprocess.Popen([opener, path], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return True
    except (OSError, AttributeError):
        return False


#: Identifiant du fichier ``.desktop`` (Linux) : sans lui, GNOME/Wayland
#: n'associe pas la fenetre a son icone et l'affiche comme « Unknown ».
DESKTOP_FILE_NAME = "taskpilot"


# ---------------------------------------------------------------------------
# Polices par defaut
# ---------------------------------------------------------------------------
#: Polices par defaut, par plateforme. Ce sont des listes de familles separees
#: par des virgules, resolues a l'execution contre les polices reellement
#: installees (cf. ``taskpilot.qt.theme.resolve_families``) : « Segoe UI »
#: n'existe pas sous Linux, « DejaVu Sans » pas sous Windows.
if IS_WIN:
    DEFAULT_UI_FONT = "Segoe UI"
    DEFAULT_MONO_FONT = "Cascadia Mono, Consolas"
    UI_FONT_CHOICES = ("Segoe UI", "Inter", "Roboto", "Calibri", "Verdana",
                       "Tahoma")
    MONO_FONT_CHOICES = ("Cascadia Mono, Consolas", "Cascadia Code", "Consolas",
                         "JetBrains Mono", "Fira Code", "Courier New")
elif IS_MAC:
    DEFAULT_UI_FONT = "SF Pro Text, Helvetica Neue, Lucida Grande"
    DEFAULT_MONO_FONT = "SF Mono, Menlo, Monaco"
    UI_FONT_CHOICES = ("SF Pro Text, Helvetica Neue, Lucida Grande", "Inter",
                       "Roboto", "Helvetica Neue", "Verdana")
    MONO_FONT_CHOICES = ("SF Mono, Menlo, Monaco", "Menlo", "Monaco",
                         "JetBrains Mono", "Fira Code", "Courier New")
else:
    DEFAULT_UI_FONT = "Cantarell, Noto Sans, DejaVu Sans, Liberation Sans"
    DEFAULT_MONO_FONT = ("JetBrains Mono, Noto Sans Mono, DejaVu Sans Mono, "
                         "Liberation Mono")
    UI_FONT_CHOICES = ("Cantarell, Noto Sans, DejaVu Sans, Liberation Sans",
                       "Inter", "Roboto", "Noto Sans", "DejaVu Sans",
                       "Liberation Sans", "Ubuntu")
    MONO_FONT_CHOICES = ("JetBrains Mono, Noto Sans Mono, DejaVu Sans Mono, "
                         "Liberation Mono", "JetBrains Mono", "Fira Code",
                         "Source Code Pro", "DejaVu Sans Mono",
                         "Liberation Mono", "Ubuntu Mono")
