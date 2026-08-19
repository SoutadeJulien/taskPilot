"""Backend pseudo-terminal, uniforme entre Windows (ConPTY) et Unix.

Deux implementations natives coexistent :

* **Windows** — ``pywinpty`` (ConPTY) ;
* **Unix** — ``ptyprocess`` (``openpty`` + ``setsid`` + ``TIOCSWINSZ``).

Leurs API se ressemblent beaucoup mais divergent sur trois points qui comptent
pour nous : le type lu (bytes / str), la variable ``TERM`` (indispensable sous
Unix pour que le programme emette des sequences VT que ``pyte`` sait rendre —
ConPTY, lui, en emet toujours) et la portee de l'arret (``terminate`` ne tue
que le process direct sous Unix, alors qu'il faut tuer toute la session).

``PtyHandle`` gomme ces differences ; ``pty_console.py`` ne connait donc plus
aucune plateforme.
"""

import os

from taskpilot.core.system import IS_WIN, kill_session

#: Raison de l'indisponibilite du PTY (affichee en repli, pour diagnostic).
PTY_IMPORT_ERROR = None
#: Nom du backend actif, pour les messages d'erreur.
BACKEND_NAME = "ConPTY (pywinpty)" if IS_WIN else "pty (ptyprocess)"

try:
    if IS_WIN:
        from winpty import PtyProcess as _Native
    else:
        from ptyprocess import PtyProcessUnicode as _Native
    HAVE_PTY = True
except Exception as _e:  # noqa: BLE001  (dep absente, ABI incompatible...)
    _Native = None
    HAVE_PTY = False
    PTY_IMPORT_ERROR = repr(_e)

#: Paquet a installer quand le backend manque (message d'aide).
MISSING_HINT = ("pywinpty" if IS_WIN else "ptyprocess")


def _pty_env(env):
    """Environnement du process fils, complete pour Unix.

    Sans ``TERM``, un programme Unix se croit sur un terminal muet et
    n'emet ni couleurs ni sequences de positionnement : le rendu ``pyte``
    serait du texte brut. ConPTY n'a pas ce probleme, on ne touche donc a rien
    sous Windows.
    """
    if IS_WIN:
        return env
    out = dict(env if env is not None else os.environ)
    out.setdefault("TERM", "xterm-256color")
    out.setdefault("COLORTERM", "truecolor")
    return out


class PtyHandle:
    """Process derriere un pseudo-terminal, vu de facon identique sur tout OS.

    Sous Unix, ``ptyprocess`` cree une nouvelle session (``setsid``) : le fils
    en est le chef et ``kill`` peut emporter toute sa descendance, exactement
    comme le fait le Job Object sous Windows.
    """

    def __init__(self, proc):
        self._proc = proc
        self.pid = proc.pid

    @classmethod
    def spawn(cls, argv, cwd=None, env=None, dimensions=(30, 100)):
        """Lance ``argv`` derriere un PTY. Leve si le backend est absent."""
        if not HAVE_PTY:
            raise RuntimeError(
                f"{MISSING_HINT} indisponible : {PTY_IMPORT_ERROR}")
        return cls(_Native.spawn(list(argv), cwd=cwd or None,
                                 env=_pty_env(env), dimensions=dimensions))

    # -- I/O -----------------------------------------------------------------
    def read(self, size=4096) -> str:
        """Lit au plus ``size`` caracteres. Leve ``EOFError`` en fin de flux."""
        return self._proc.read(size)

    def write(self, data: str):
        self._proc.write(data)

    def setwinsize(self, rows: int, cols: int):
        self._proc.setwinsize(rows, cols)

    # -- Etat / arret --------------------------------------------------------
    def isalive(self) -> bool:
        return bool(self._proc.isalive())

    def wait(self):
        return self._proc.wait()

    @property
    def exitstatus(self):
        return getattr(self._proc, "exitstatus", None)

    def kill(self):
        """Tue le process et toute sa descendance.

        Sous Unix, ``terminate`` de ``ptyprocess`` ne vise que le fils direct :
        un ``npm run dev`` laisserait son serveur Node orphelin. On tue donc
        toute la session (``ptyprocess`` en a ouvert une neuve via ``setsid``),
        avec ``terminate`` en filet de securite.
        """
        if not IS_WIN:
            kill_session(self.pid)
        try:
            self._proc.terminate(force=True)
        except Exception:  # noqa: BLE001
            pass

    def close(self):
        """Libere le descripteur du PTY (a n'appeler qu'apres la fin des lectures)."""
        try:
            self._proc.close(force=True)
        except Exception:  # noqa: BLE001
            pass
