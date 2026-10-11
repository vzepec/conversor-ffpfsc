"""Ata el proceso de MkPFS a la vida de la app: si la app termina, MkPFS también.

Sin esto, cerrar la app a la fuerza (o un cuelgue) deja a MkPFS comprimiendo en
segundo plano: ocupa la CPU y sigue escribiendo el ``.ffpfsc``.

- Windows: un *Job Object* con ``KILL_ON_JOB_CLOSE``; al cerrarse el proceso de la
  app, Windows cierra el Job y termina a MkPFS y a sus procesos de compresión.
- Linux: ``PR_SET_PDEATHSIG``; el núcleo envía ``SIGTERM`` a MkPFS si la app muere.
"""
from __future__ import annotations

import ctypes
import signal
import subprocess
import sys
from collections.abc import Callable

_PR_SET_PDEATHSIG = 1
_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000


class _BasicLimits(ctypes.Structure):
    """``JOBOBJECT_BASIC_LIMIT_INFORMATION`` de la API de Windows."""

    _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", ctypes.c_uint32),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", ctypes.c_uint32),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", ctypes.c_uint32),
                ("SchedulingClass", ctypes.c_uint32)]


class _ExtendedLimits(ctypes.Structure):
    """``JOBOBJECT_EXTENDED_LIMIT_INFORMATION`` de la API de Windows."""

    _fields_ = [("BasicLimitInformation", _BasicLimits),
                ("IoInfo", ctypes.c_uint64 * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t)]


_job_handle: int | None = None


def child_setup(platform: str = sys.platform) -> Callable[[], None] | None:
    """Prepara la función que el proceso hijo ejecuta antes de arrancar (solo Linux).

    La biblioteca de C se carga aquí, en la app, para que el hijo solo haga una
    llamada al sistema entre ``fork`` y ``exec``.

    Args:
        platform (str): Valor de ``sys.platform``.

    Returns:
        Callable[[], None] | None: Función para ``preexec_fn``, o ``None`` si el
        sistema no la necesita o no la admite.
    """
    if not platform.startswith("linux"):
        return None
    try:
        prctl = ctypes.CDLL(None, use_errno=True).prctl
    except (OSError, AttributeError):
        return None

    def die_with_parent() -> None:
        """Pide al núcleo que termine este proceso si la app muere."""
        prctl(_PR_SET_PDEATHSIG, signal.SIGTERM)

    return die_with_parent


def bind_to_app(process: subprocess.Popen[bytes], platform: str = sys.platform) -> bool:
    """Mete el proceso en el *Job Object* de la app (solo Windows, *best effort*).

    Args:
        process (subprocess.Popen[bytes]): Proceso recién lanzado.
        platform (str): Valor de ``sys.platform``.

    Returns:
        bool: ``True`` si el proceso quedó atado a la app.
    """
    if platform != "win32":
        return False
    try:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        kernel32.AssignProcessToJobObject.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
        return bool(kernel32.AssignProcessToJobObject(_app_job(kernel32),
                                                      int(process._handle)))  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False


def _app_job(kernel32: ctypes.CDLL) -> int:
    """Crea (una vez) el *Job Object* que termina a sus procesos al cerrarse la app.

    Args:
        kernel32 (ctypes.CDLL): Biblioteca ``kernel32`` de Windows.

    Returns:
        int: Identificador del Job.

    Raises:
        OSError: Si Windows no pudo crear o configurar el Job.
    """
    global _job_handle
    if _job_handle is None:
        kernel32.CreateJobObjectW.restype = ctypes.c_void_p
        handle = kernel32.CreateJobObjectW(None, None)
        limits = _ExtendedLimits()
        limits.BasicLimitInformation.LimitFlags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        kernel32.SetInformationJobObject.argtypes = (ctypes.c_void_p, ctypes.c_int,
                                                     ctypes.c_void_p, ctypes.c_uint32)
        if not handle or not kernel32.SetInformationJobObject(
                handle, _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits),
                ctypes.sizeof(limits)):
            raise OSError("no se pudo crear el Job Object")
        _job_handle = handle
    return _job_handle
