import os
import shutil
import logging
from pathlib import Path


class ModManager:
    def __init__(self, paths):
        self.enabled = paths.root / 'mods'
        self.disabled = paths.root / 'disabled_mods'

    def list_mods(self):
        return [(p.name, enabled) for folder, enabled in ((self.enabled, True), (self.disabled, False))
                for p in sorted(folder.iterdir()) if p.is_file() and not p.is_symlink() and p.suffix.lower() == '.jar']

    def _path(self, name, enabled):
        if Path(name).name != name or '/' in name or '\\' in name or ':' in name or Path(name).suffix.lower() != '.jar':
            raise ValueError('Nombre de mod inválido.')
        result = (self.enabled if enabled else self.disabled) / name
        if result.is_symlink():
            raise ValueError('No se permiten enlaces simbólicos para mods.')
        return result

    def import_mod(self, source):
        source = Path(source)
        if not source.is_file() or source.suffix.lower() != '.jar':
            raise ValueError('Selecciona un archivo .jar.')
        destination = self._path(source.name, True)
        if destination.exists() or self._path(source.name, False).exists():
            raise ValueError('Ya existe un mod con ese nombre. No se sobrescribió.')
        with source.open('rb') as src:
            # Acquire exclusive ownership before cleanup; never remove a racing file.
            with destination.open('xb') as dst:
                try:
                    shutil.copyfileobj(src, dst)
                except OSError:
                    dst.close()
                    destination.unlink(missing_ok=True)
                    raise
        logging.getLogger(__name__).info('Mod importado: %s', source.name)

    def toggle(self, name, enabled):
        source = self._path(name, enabled)
        target = self._path(name, not enabled)
        if target.exists():
            raise ValueError('Ya existe un mod con ese nombre en la carpeta de destino.')
        source.rename(target)
        logging.getLogger(__name__).info('Mod %s: %s', 'desactivado' if enabled else 'activado', name)

    def delete(self, name, enabled):
        self._path(name, enabled).unlink()
        logging.getLogger(__name__).info('Mod eliminado: %s', name)

    def open_folder(self):
        os.startfile(self.enabled)
