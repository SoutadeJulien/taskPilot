"""Execution d'une commande de task : process, capture de sortie, kill d'arbre.

``TaskConsole`` n'a aucune dependance a Tkinter : il pousse ses evenements
dans une ``queue.Queue`` que la couche UI draine a son rythme.
"""

import os
import queue
import re
import signal
import subprocess
import threading

from taskpilot.core.jobobject import JobObject
from taskpilot.core.system import IS_WIN, NO_WINDOW
from taskpilot.core.vscode_tasks import CommandSpec

#: Sequences d'echappement ANSI a retirer de la sortie affichee.
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

#: Types d'evenements pousses dans la file (kind, payload).
EVENT_OUTPUT = "out"
EVENT_EXIT = "exit"


class TaskConsole:
    """Gere un process unique : capture sa sortie et le tue avec son arbre."""

    def __init__(self, label: str, spec: CommandSpec, log_path: str = None,
                 interactive: bool = False):
        self.label = label
        self.spec = spec
        self.log_path = log_path
        #: Si vrai, le process garde un stdin ouvert : on peut lui envoyer des
        #: commandes via ``send`` (consoles interactives type shell).
        self.interactive = interactive
        self.proc = None
        self.job = None
        self.queue = queue.Queue()
        self.returncode = None
        self.started = False
        self._reader = None
        self._logfile = None

    # -- Cycle de vie --------------------------------------------------------
    def start(self) -> bool:
        """Lance le process et demarre la lecture de sa sortie."""
        preexec = None if IS_WIN else os.setsid  # groupe de process (Unix)
        try:
            self.proc = subprocess.Popen(
                self.spec.argv,
                cwd=self.spec.cwd or None,
                env=self.spec.env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE if self.interactive else subprocess.DEVNULL,
                creationflags=NO_WINDOW,
                preexec_fn=preexec,
                bufsize=0,
            )
        except Exception as e:  # noqa: BLE001
            self.queue.put((EVENT_OUTPUT, f"⚠ Echec du lancement : {e}\n"))
            self.queue.put((EVENT_EXIT, -1))
            self.returncode = -1
            return False

        self.started = True
        self._attach_job()
        self._open_log()
        header = f"$ {self.spec.display}\n"
        self.queue.put((EVENT_OUTPUT, header))
        self._log(header)
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        return True

    # -- Journalisation (fichier) --------------------------------------------
    def _open_log(self):
        if not self.log_path:
            return
        try:
            self._logfile = open(self.log_path, "w", encoding="utf-8",
                                 buffering=1)
        except OSError:
            self._logfile = None

    def _log(self, text):
        if self._logfile is not None:
            try:
                self._logfile.write(text)
            except (OSError, ValueError):
                pass

    def _close_log(self):
        if self._logfile is not None:
            try:
                self._logfile.close()
            except OSError:
                pass
            self._logfile = None

    def _attach_job(self):
        """Rattache le process a un Job Object pour le kill d'arbre (Windows)."""
        if not IS_WIN:
            return
        try:
            self.job = JobObject()
            if not self.job.assign(self.proc._handle):
                self.job.close()
                self.job = None
        except OSError:
            self.job = None

    def _read_loop(self):
        try:
            for chunk in iter(lambda: self.proc.stdout.read(4096), b""):
                if not chunk:
                    break
                text = ANSI_RE.sub("", chunk.decode("utf-8", errors="replace"))
                self.queue.put((EVENT_OUTPUT, text))
                self._log(text)
        except Exception:
            pass
        finally:
            try:
                self.proc.stdout.close()
            except Exception:
                pass
            self.returncode = self.proc.wait()
            self.queue.put((EVENT_EXIT, self.returncode))
            self._log(f"\n[exit code {self.returncode}]\n")
            self._close_log()

    # -- Entree interactive --------------------------------------------------
    def send(self, text: str):
        """Ecrit du texte brut dans le stdin du process (frappes clavier).

        Aucun écho ici : la couche UI affiche déjà ce que l'utilisateur tape
        directement dans la console.
        """
        if not (self.proc and self.proc.stdin):
            return
        self._log(text)
        try:
            self.proc.stdin.write(text.encode("utf-8"))
            self.proc.stdin.flush()
        except (OSError, ValueError):
            pass

    # -- Etat / arret --------------------------------------------------------
    def is_running(self) -> bool:
        return (self.started and self.proc is not None
                and self.proc.poll() is None)

    def kill(self):
        """Tue le process ET tout son arbre d'enfants."""
        if not self.proc:
            return
        if IS_WIN:
            if self.job:
                self.job.terminate(1)      # tue tout le Job (arbre complet)
            self._taskkill_tree()          # filet de securite
        else:
            self._killpg()

    def _taskkill_tree(self):
        try:
            subprocess.call(
                ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=NO_WINDOW,
            )
        except Exception:
            pass

    def _killpg(self):
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass

    def cleanup(self):
        """Libere le handle du Job Object."""
        if self.job:
            self.job.close()
            self.job = None
