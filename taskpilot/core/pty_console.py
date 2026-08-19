"""Console adossée à un vrai pseudo-terminal (ConPTY sous Windows, ``pty``
sous Unix — cf. ``pty_backend``).

Contrairement à ``TaskConsole`` (sortie en lecture seule via un tube), le
process tourne ici derrière un PTY : il croit parler à un vrai terminal,
affiche donc ses prompts nativement et accepte des programmes interactifs /
plein écran (``claude``, REPL, etc.). La sortie contient des séquences VT que
la couche UI interprète avec ``pyte`` (cf. ``TerminalPanel``).

L'interface (``queue`` d'évènements, ``is_running``, ``kill``…) est alignée sur
``TaskConsole`` afin que ``TasksTab`` pilote les deux types de console de la
même façon.
"""

import queue
import threading
import time

from taskpilot.core.pty_backend import (
    BACKEND_NAME, HAVE_PTY, MISSING_HINT, PTY_IMPORT_ERROR, PtyHandle)
from taskpilot.core.task_runner import ANSI_RE, EVENT_EXIT, EVENT_OUTPUT

__all__ = ["HAVE_PTY", "PTY_IMPORT_ERROR", "PtyConsole"]


class PtyConsole:
    """Pilote un process derrière un PTY : I/O brute + dimensions."""

    def __init__(self, label, spec, log_path=None, rows=30, cols=100):
        self.label = label
        self.spec = spec
        self.log_path = log_path
        self.interactive = True
        self.pty = True
        self.proc = None              # PtyHandle
        self.queue = queue.Queue()
        self.returncode = None
        self.started = False
        self.rows = rows
        self.cols = cols
        self._reader = None
        self._logfile = None

    # -- Cycle de vie --------------------------------------------------------
    def start(self) -> bool:
        if not HAVE_PTY:
            self.queue.put((EVENT_OUTPUT,
                            f"⚠ {MISSING_HINT} indisponible : terminal "
                            f"impossible ({BACKEND_NAME}).\r\n"))
            self.queue.put((EVENT_EXIT, -1))
            self.returncode = -1
            return False
        try:
            self.proc = PtyHandle.spawn(
                self.spec.argv, cwd=self.spec.cwd or None,
                env=self.spec.env, dimensions=(self.rows, self.cols))
        except Exception as e:  # noqa: BLE001
            self.queue.put((EVENT_OUTPUT, f"⚠ Echec du lancement : {e}\r\n"))
            self.queue.put((EVENT_EXIT, -1))
            self.returncode = -1
            return False
        self.started = True
        self._open_log()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        return True

    def _read_loop(self):
        try:
            while True:
                data = self.proc.read(4096)      # str (déjà décodé)
                if data:
                    self.queue.put((EVENT_OUTPUT, data))
                    self._log(data)
                elif not self.proc.isalive():
                    break
                else:
                    time.sleep(0.01)
        except EOFError:
            pass
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                self.returncode = self.proc.wait()
            except Exception:  # noqa: BLE001
                self.returncode = self.proc.exitstatus
            if self.returncode is None:
                self.returncode = 0
            # Plus aucune lecture en cours : on peut rendre le descripteur du
            # PTY sans risquer de le fermer sous les pieds de ce thread.
            self.proc.close()
            self.queue.put((EVENT_EXIT, self.returncode))
            self._close_log()

    # -- Entrée / dimensions -------------------------------------------------
    def send(self, data: str):
        """Transmet des frappes (texte ou séquences VT) au PTY."""
        if self.proc is None:
            return
        try:
            self.proc.write(data)
        except Exception:  # noqa: BLE001
            pass

    def set_size(self, rows: int, cols: int):
        self.rows, self.cols = rows, cols
        if self.proc is not None:
            try:
                self.proc.setwinsize(rows, cols)
            except Exception:  # noqa: BLE001
                pass

    # -- Journalisation (sortie nettoyée de ses séquences VT) ----------------
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
                self._logfile.write(ANSI_RE.sub("", text))
            except (OSError, ValueError):
                pass

    def _close_log(self):
        if self._logfile is not None:
            try:
                self._logfile.close()
            except OSError:
                pass
            self._logfile = None

    # -- État / arrêt --------------------------------------------------------
    def is_running(self) -> bool:
        return (self.started and self.proc is not None
                and self.proc.isalive())

    def kill(self):
        """Tue le process ET toute sa descendance."""
        if self.proc is not None:
            self.proc.kill()

    def cleanup(self):
        # Le descripteur du PTY est ferme par le thread lecteur, une fois sur
        # de n'avoir plus rien a lire (cf. ``_read_loop``).
        pass
