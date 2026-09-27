import hashlib
import json
import logging
import re
import subprocess
import threading
import uuid
from datetime import datetime

import minecraft_launcher_lib as mll
from minecraft_launcher_lib.mod_loader import get_mod_loader

from .java_manager import get_required_java_major
from ..config import validate_username, memory_limit
from .. import __version__
from ..platform_support import external_process_environment


class JavaRequired(ValueError):
    def __init__(self, major):
        self.major = major
        super().__init__(f'No se encontró Java {major} compatible. Puedes instalarlo para XLauncher.')


class MinecraftService:
    def __init__(self, paths, java_manager):
        self.paths = paths
        self.java = java_manager
        self.install_lock = threading.Lock()
        self.process = None

    def _metadata_path(self, version):
        if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9_.+\-]+', version) or version in ('.', '..'):
            raise ValueError('Identificador de versión inválido.')
        path = self.paths.root / 'versions' / version / f'{version}.json'
        if not path.resolve().is_relative_to((self.paths.root / 'versions').resolve()):
            raise ValueError('Ruta de versión inválida.')
        return path

    def installed(self):
        # Isolate damaged legacy entries so one bad JSON does not break the home page.
        try:
            versions = mll.utils.get_installed_versions(str(self.paths.root))
        except (OSError, ValueError, KeyError, TypeError):
            logging.getLogger(__name__).exception('No se pudo leer el catálogo local.')
            versions = []
            for directory in (self.paths.root / 'versions').iterdir():
                try:
                    data = json.loads(self._metadata_path(directory.name).read_text(encoding='utf-8'))
                    if isinstance(data, dict) and data.get('id') == directory.name:
                        versions.append(data)
                except (OSError, ValueError, KeyError, TypeError):
                    continue
        result = []
        for item in versions:
            try:
                path = self._metadata_path(item['id'])
                if not (path.parent / '.xlauncher-incomplete').exists():
                    result.append(item['id'])
            except (ValueError, KeyError, TypeError):
                continue
        return sorted(result, reverse=True)

    def available(self):
        return [item['id'] for item in mll.utils.get_version_list() if item['type'] == 'release']

    def required_java(self, version, seen=None):
        seen = set() if seen is None else seen
        if version in seen or len(seen) > 10:
            raise ValueError('Los metadatos de la instalación contienen una herencia inválida.')
        seen.add(version)
        path = self._metadata_path(version)
        metadata = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if not isinstance(metadata, dict):
            raise ValueError('Los metadatos de la instalación no son válidos. Reinstala la versión.')
        if metadata.get('javaVersion'):
            return get_required_java_major(version, metadata)
        if metadata.get('inheritsFrom'):
            return self.required_java(metadata['inheritsFrom'], seen)
        return get_required_java_major(version)

    def compatible_java(self, version, manual):
        major = self.required_java(version)
        java = self.java.find(major, manual)
        if java is None:
            raise JavaRequired(major)
        return java

    def install(self, version, loader, manual, progress):
        self._metadata_path(version)
        if not self.install_lock.acquire(blocking=False):
            raise ValueError('Ya hay una instalación en curso.')
        maximum = 0
        status = 'Instalando Minecraft…'

        def set_max(value):
            nonlocal maximum
            maximum = value

        def set_status(value):
            nonlocal status
            status = value
            progress(status, None)

        callback = {'setMax': set_max, 'setStatus': set_status,
                    'setProgress': lambda value: progress(status, value / maximum if maximum else None)}

        def mark(target):
            path = self._metadata_path(target).parent
            path.mkdir(parents=True, exist_ok=True)
            marker = path / '.xlauncher-incomplete'
            marker.touch()
            return marker

        try:
            if loader not in ('Vanilla', 'Fabric', 'Forge'):
                raise ValueError('Loader no soportado.')
            mod_loader = get_mod_loader(loader.lower()) if loader != 'Vanilla' else None
            if mod_loader and not mod_loader.is_minecraft_version_supported(version):
                raise ValueError(f'{loader} no soporta esta versión.')
            marker = mark(version)
            mll.install.install_minecraft_version(version, str(self.paths.root), callback=callback)
            marker.unlink()
            installed = version
            if mod_loader:
                java = self.compatible_java(version, manual)
                loader_version = mod_loader.get_latest_loader_version(version)
                installed = mod_loader.get_installed_version(version, loader_version)
                marker = mark(installed)
                with external_process_environment():
                    mod_loader.install(version, str(self.paths.root), loader_version=loader_version,
                                       callback=callback, java=str(java.path))
                marker.unlink()
            logging.getLogger(__name__).info('Instalación completada: %s (%s)', installed, loader)
            return installed
        finally:
            self.install_lock.release()

    def launch(self, config):
        validate_username(config.username)
        if type(config.memory_gb) is not int or not 1 <= config.memory_gb <= memory_limit():
            raise ValueError('La memoria configurada no es válida. Revisa Ajustes.')
        if self.process is not None and self.process.poll() is None:
            raise ValueError('Minecraft ya está ejecutándose.')
        if config.selected_version not in self.installed():
            raise ValueError('La versión seleccionada no está instalada.')
        java = self.compatible_java(config.selected_version, config.java_path)
        # Java's UUID.nameUUIDFromBytes for an offline profile; no fake authentication.
        offline_uuid = uuid.UUID(bytes=hashlib.md5(('OfflinePlayer:' + config.username).encode('utf-8')).digest(), version=3)
        options = {'username': config.username, 'uuid': str(offline_uuid), 'token': '',
                   'executablePath': str(java.path), 'gameDirectory': str(self.paths.root),
                   'jvmArguments': ['-Xms512M', f'-Xmx{config.memory_gb}G'],
                   'launcherName': 'XLauncher', 'launcherVersion': __version__}
        command = mll.command.get_minecraft_command(config.selected_version, str(self.paths.root), options)
        log = self.paths.root / 'logs' / f'minecraft-{datetime.now():%Y%m%d-%H%M%S-%f}.log'
        with log.open('wb') as output, external_process_environment() as environment:
            self.process = subprocess.Popen(command, cwd=self.paths.root, stdout=output, stderr=subprocess.STDOUT,
                                            stdin=subprocess.DEVNULL,
                                            env=environment,
                                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        logging.getLogger(__name__).info('Minecraft iniciado: %s, Java %s', config.selected_version, java.major_version)
        return self.process, log
