import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LauncherPaths:
    root: Path

    @classmethod
    def default(cls):
        return cls(Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / '.xlauncher')

    def ensure(self):
        for name in ('runtime', 'mods', 'disabled_mods', 'versions', 'libraries', 'assets', 'logs'):
            (self.root / name).mkdir(parents=True, exist_ok=True)

    @property
    def config(self):
        return self.root / 'configuration.json'

    @property
    def runtime(self):
        return self.root / 'runtime'
