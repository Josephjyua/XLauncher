import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LauncherPaths:
    root: Path

    @classmethod
    def default(cls):
        system = platform.system()
        if system == 'Windows':
            base = Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming'))
            legacy = base / '.xlauncher'
            # Keep existing installations in place, even if both directories exist.
            # No data moves, copies or silent merging of two Minecraft directories.
            return cls(legacy if legacy.is_dir() else base / 'XLauncher')
        if system == 'Darwin':
            return cls(Path.home() / 'Library' / 'Application Support' / 'XLauncher')
        if system == 'Linux':
            base = Path(os.environ.get('XDG_DATA_HOME', ''))
            if not base.is_absolute():
                base = Path.home() / '.local' / 'share'
            return cls(base / 'XLauncher')
        raise ValueError(f'Sistema operativo no soportado: {system}')

    def ensure(self):
        for name in ('runtime', 'mods', 'disabled_mods', 'versions', 'libraries', 'assets', 'logs'):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    @property
    def config(self):
        return self.root / 'configuration.json'

    @property
    def runtime(self):
        return self.root / 'runtime'


def resource_path(relative):
    """Read-only bundled resources, never user configuration or downloaded assets."""
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError('Ruta de recurso fuera del directorio de la aplicación.')
    return path


def extra_java_candidates(system=None):
    """Platform-specific search locations are centralized here."""
    system = system or platform.system()
    if system == 'Windows':
        for variable in ('ProgramFiles', 'ProgramFiles(x86)'):
            if os.environ.get(variable):
                for vendor in ('Java', 'Eclipse Adoptium', 'Microsoft', 'Amazon Corretto'):
                    yield from (Path(os.environ[variable]) / vendor).glob('*/bin/java.exe')
    elif system == 'Linux':
        for base in (Path('/usr/lib/jvm'), Path('/usr/java'), Path('/opt/java')):
            yield from base.glob('*/bin/java')
        yield Path('/usr/bin/java')
    elif system == 'Darwin':
        for base in (Path('/Library/Java/JavaVirtualMachines'), Path.home() / 'Library/Java/JavaVirtualMachines'):
            yield from base.glob('*/Contents/Home/bin/java')
        for base in (Path('/opt/homebrew/opt'), Path('/usr/local/opt')):
            yield from base.glob('openjdk*/bin/java')
