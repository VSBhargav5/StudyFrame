"""GUI entry point and explicit frozen-worker dispatch; never spawn another GUI."""
import io
import os
import sys
from pathlib import Path

_install_mutex = None


def hold_install_mutex():
    """Let the installer refuse updates/uninstall while a GUI session is running."""
    global _install_mutex
    if sys.platform != 'win32' or _install_mutex is not None:
        return
    import ctypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True, winmode=0x800)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    _install_mutex = kernel.CreateMutexW(None, False, 'Local\\StudyFrame.Application')
    if not _install_mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    # Intentionally retained until process termination, as required by Inno.


def default_model():
    root = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[1]
    return root / 'models' / 'vosk-model-small-en-us-0.15'


def worker_pipes():
    """Windowed Windows executables have no Python stdio objects; restore pipes only."""
    if sys.platform != 'win32':
        return
    import ctypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True, winmode=0x800)
    kernel.GetStdHandle.argtypes = [ctypes.c_uint32]
    kernel.GetStdHandle.restype = ctypes.c_void_p
    kernel.GetFileType.argtypes = [ctypes.c_void_p]
    kernel.GetFileType.restype = ctypes.c_uint32
    for name, number, write in [('stdin', -10, False), ('stdout', -11, True), ('stderr', -12, True)]:
        if getattr(sys, name) is not None:
            continue
        handle = kernel.GetStdHandle(number & 0xffffffff)
        if not handle or handle == ctypes.c_void_p(-1).value or kernel.GetFileType(handle) != 3:
            raise OSError('Worker requires private parent pipes.')
        fd = msvcrt.open_osfhandle(handle, (os.O_WRONLY if write else os.O_RDONLY) | os.O_BINARY)
        stream = os.fdopen(fd, 'wb' if write else 'rb', buffering=0)
        setattr(sys, name, io.TextIOWrapper(stream, encoding='utf-8', write_through=True) if write else stream)


def main():
    if sys.argv[1:2] == ['--speech-worker']:
        try:
            worker_pipes()
        except OSError:
            return 2
        from studyframe.speech_worker import main as speech_main
        return speech_main(sys.argv[2:])
    if sys.argv[1:2] == ['--self-test']:
        from studyframe.selftest import main as selftest_main
        return selftest_main(sys.argv[2:])
    from studyframe.app import main as app_main
    return app_main()
