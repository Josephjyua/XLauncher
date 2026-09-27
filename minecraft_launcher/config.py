import ctypes
import json
import logging
import os
import re
import tempfile
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path


def memory_limit():
    """Leave at least 2 GiB and 25% for Windows; conservative fallback."""
    if os.name == 'nt':
        class MemoryStatus(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in
                ('total', 'available', 'page', 'available_page', 'virtual', 'available_virtual', 'extended')]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            gb = status.total // (1024 ** 3)
            return max(1, min(64, gb - 2, int(gb * .75)))
    return 8


def validate_username(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_]{3,16}', value):
        raise ValueError('El nombre debe tener entre 3 y 16 letras, números o guiones bajos.')
    return value


@dataclass
class Configuration:
    username: str = 'Player'
    memory_gb: int = 4
    selected_version: str | None = None
    java_path: str | None = None


class ConfigManager:
    def __init__(self, path: Path):
        self.path = path
        self.warning = None
        self.data = self.load()

    def validate(self, data):
        validate_username(data.username)
        if type(data.memory_gb) is not int or not 1 <= data.memory_gb <= memory_limit():
            raise ValueError(f'La RAM debe ser un entero entre 1 y {memory_limit()} GB.')
        for value in (data.selected_version, data.java_path):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError('La versión y la ruta de Java deben ser texto válido.')

    def load(self):
        default = Configuration(memory_gb=min(4, memory_limit()))
        if not self.path.exists():
            self.save(default)
            return default
        try:
            raw = json.loads(self.path.read_text(encoding='utf-8-sig'))
            if not isinstance(raw, dict):
                raise ValueError('Configuración inválida')
            names = {'Nombre': 'username', 'RAM': 'memory_gb', 'Version': 'selected_version', 'Java': 'java_path'}
            for old, new in names.items():
                if old in raw and new not in raw:
                    raw[new] = raw[old]
                    if old == 'RAM' and isinstance(raw[new], str) and raw[new].isdigit():
                        raw[new] = int(raw[new])
            values = asdict(default)
            values.update({k: raw[k] for k in values if k in raw})
            for key in ('selected_version', 'java_path'):
                if values[key] == '':
                    values[key] = None
            data = Configuration(**values)
            self.validate(data)
        except (ValueError, TypeError, UnicodeError):
            backup = self.path.with_name(f'configuration.invalid-{uuid.uuid4().hex}.json')
            self.path.rename(backup)
            self.warning = f'La configuración no era válida. Se conservó en {backup.name} y se restauraron los valores iniciales.'
            logging.getLogger(__name__).warning(self.warning)
            data = default
        self.save(data)
        return data

    def save(self, data):
        self.validate(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(asdict(data), stream, indent=2, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(self.path)
            self.data = data
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
