"""OS conventions and external-process isolation for source and frozen builds."""
import ctypes
import os
import platform
import sys
import threading
from contextlib import contextmanager
from pathlib import Path


def java_executable_name(system=None):
    return 'java.exe' if (system or platform.system()) == 'Windows' else 'java'


def adoptium_target(system=None, machine=None):
    system = system or platform.system()
    machine = (machine or platform.machine()).lower()
    architecture = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'aarch64', 'aarch64': 'aarch64'}.get(machine)
    systems = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'mac'}
    supported = {('Windows', 'x64'), ('Linux', 'x64'), ('Darwin', 'x64'), ('Darwin', 'aarch64'), ('Windows', 'aarch64')}
    if (system, architecture) not in supported:
        raise ValueError(f'No se ofrece Java privado para {system} / {machine}. Configura Java manualmente.')
    return systems[system], architecture, '.zip' if system == 'Windows' else '.tar.gz'


def external_environment():
    """Undo PyInstaller library search changes for Java/system applications."""
    env = os.environ.copy()
    if not getattr(sys, 'frozen', False):
        return env
    for key in ('LD_LIBRARY_PATH', 'LIBPATH'):
        if key + '_ORIG' in env:
            env[key] = env[key + '_ORIG']
        else:
            env.pop(key, None)
    bundle = Path(sys._MEIPASS).resolve()
    for key in ('PATH', 'DYLD_LIBRARY_PATH'):
        if key in env:
            env[key] = os.pathsep.join(part for part in env[key].split(os.pathsep)
                                       if part and not Path(part).resolve().is_relative_to(bundle))
    return env


_process_lock = threading.RLock()


@contextmanager
def external_process_environment():
    """Also covers subprocesses created internally by minecraft-launcher-lib.

    The launcher runs one worker at a time. Lock nested external-process calls;
    restore the launcher environment immediately after spawn/install completes.
    """
    if not getattr(sys, 'frozen', False):
        yield os.environ.copy()
        return
    with _process_lock:
        clean = external_environment()
        keys = ('PATH', 'LD_LIBRARY_PATH', 'LIBPATH', 'DYLD_LIBRARY_PATH')
        previous = {key: os.environ.get(key) for key in keys}
        dll_path = None
        if os.name == 'nt':
            buffer = ctypes.create_unicode_buffer(32768)
            ctypes.windll.kernel32.GetDllDirectoryW(len(buffer), buffer)
            dll_path = buffer.value
            ctypes.windll.kernel32.SetDllDirectoryW(None)
        try:
            for key in keys:
                if key in clean:
                    os.environ[key] = clean[key]
                else:
                    os.environ.pop(key, None)
            yield clean
        finally:
            for key, value in previous.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            if dll_path is not None:
                ctypes.windll.kernel32.SetDllDirectoryW(dll_path or None)
