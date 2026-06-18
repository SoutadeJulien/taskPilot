"""Job Object Windows : tuer un process AVEC tout son arbre d'enfants.

Sous Windows, fermer un terminal ne tue pas les process enfants (probleme
classique de VS Code). En assignant chaque process lance a un Job Object
configure avec ``KILL_ON_JOB_CLOSE``, terminer le Job tue tout l'arbre d'un
seul coup.

Hors Windows, ``JobObject`` est un objet inerte ; la terminaison de l'arbre
repose alors sur les groupes de process (voir ``task_runner``).
"""

from taskpilot.core.system import IS_WIN

if IS_WIN:
    import ctypes
    from ctypes import wintypes

    _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
    _JobObjectExtendedLimitInformation = 9

    class _IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", wintypes.LARGE_INTEGER),
            ("PerJobUserTimeLimit", wintypes.LARGE_INTEGER),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", _IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    _k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _k32.CreateJobObjectW.restype = wintypes.HANDLE
    _k32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _k32.SetInformationJobObject.restype = wintypes.BOOL
    _k32.SetInformationJobObject.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    _k32.AssignProcessToJobObject.restype = wintypes.BOOL
    _k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _k32.TerminateJobObject.restype = wintypes.BOOL
    _k32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _k32.CloseHandle.restype = wintypes.BOOL
    _k32.CloseHandle.argtypes = [wintypes.HANDLE]

    class JobObject:
        """Conteneur Windows : tous les process assignes y meurent ensemble."""

        def __init__(self):
            self.handle = _k32.CreateJobObjectW(None, None)
            if not self.handle:
                raise OSError(ctypes.get_last_error(), "CreateJobObjectW")
            info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = \
                _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not _k32.SetInformationJobObject(
                self.handle, _JobObjectExtendedLimitInformation,
                ctypes.byref(info), ctypes.sizeof(info),
            ):
                err = ctypes.get_last_error()
                _k32.CloseHandle(self.handle)
                self.handle = None
                raise OSError(err, "SetInformationJobObject")

        def assign(self, proc_handle):
            """Rattache un process (par son handle Windows) au Job."""
            return bool(_k32.AssignProcessToJobObject(
                self.handle, int(proc_handle)))

        def terminate(self, code=1):
            """Tue tous les process du Job (arbre complet)."""
            if self.handle:
                _k32.TerminateJobObject(self.handle, code)

        def close(self):
            if self.handle:
                _k32.CloseHandle(self.handle)
                self.handle = None

else:
    class JobObject:
        """Implementation inerte hors Windows (repli sur les groupes)."""

        def __init__(self):
            self.handle = None

        def assign(self, proc_handle):
            return False

        def terminate(self, code=1):
            pass

        def close(self):
            pass
