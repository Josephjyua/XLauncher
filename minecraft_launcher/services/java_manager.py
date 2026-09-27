import hashlib
import json
import logging
import os
import platform
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

import requests


def parse_java_major(output):
    match = re.search(r'(?:openjdk|java)\s+(?:version\s+)?["\']?(\d+)(?:\.(\d+))?', output, re.I)
    if not match:
        return None
    return int(match[2]) if match[1] == '1' and match[2] else int(match[1])


def get_required_java_major(minecraft_version, metadata=None):
    """Prefer Mojang javaVersion metadata. Stable fallback: <=1.16: 8,
    1.17: 16, 1.18–1.20.4: 17, 1.20.5–1.21: 21.
    Unknown generations/snapshots require metadata instead of guessing.
    Loaders are resolved through their inheritsFrom metadata by MinecraftService.
    """
    if metadata and isinstance(metadata.get('javaVersion'), dict):
        major = metadata['javaVersion'].get('majorVersion')
        if type(major) is int and 8 <= major <= 99:
            return major
    match = re.fullmatch(r'1\.(\d+)(?:\.(\d+))?', minecraft_version)
    if not match:
        raise ValueError('No se pudo determinar el Java requerido. Instala primero la versión vanilla correspondiente.')
    minor, patch = int(match[1]), int(match[2] or 0)
    if minor <= 16:
        return 8
    if minor == 17:
        return 16
    if minor < 20 or (minor == 20 and patch < 5):
        return 17
    if minor <= 21:
        return 21
    raise ValueError('Esta generación requiere metadatos de Java actualizados.')


def safe_extract_zip(archive, destination):
    """Reject traversal, Windows ADS/device paths, links and excessive expansion.

    A fresh staging directory is required; only ZIP is supported on Windows.
    """
    destination = Path(destination).resolve()
    reserved = {'CON', 'PRN', 'AUX', 'NUL'} | {f'{x}{i}' for x in ('COM', 'LPT') for i in range(1, 10)}
    with zipfile.ZipFile(archive) as bundle:
        if sum(item.file_size for item in bundle.infolist()) > 3 * 1024 ** 3:
            raise ValueError('El archivo Java es demasiado grande.')
        targets = set()
        for item in bundle.infolist():
            name = item.filename.replace('\\', '/')
            relative = PurePosixPath(name)
            if (relative.is_absolute() or not relative.parts or any(
                    part in ('.', '..') or ':' in part or part.endswith((' ', '.'))
                    or part.split('.')[0].upper() in reserved for part in relative.parts)
                    or stat.S_ISLNK(item.external_attr >> 16)):
                raise ValueError('El ZIP contiene una ruta insegura.')
            target = (destination / Path(*relative.parts)).resolve()
            if not target.is_relative_to(destination) or str(target).lower() in targets:
                raise ValueError('El ZIP contiene rutas inválidas o duplicadas.')
            targets.add(str(target).lower())
        for item in bundle.infolist():
            target = destination / Path(*PurePosixPath(item.filename.replace('\\', '/')).parts)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)


@dataclass(frozen=True)
class JavaInstallation:
    path: Path
    major_version: int
    source: str


class JavaManager:
    def __init__(self, paths):
        self.paths = paths

    def inspect(self, path, source):
        path = Path(path).expanduser()
        if not path.is_file():
            return None
        try:
            result = subprocess.run([str(path), '-version'], capture_output=True, text=True,
                                    errors='replace', timeout=10,
                                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            major = parse_java_major(result.stdout + result.stderr)
            if result.returncode == 0 and major:
                return JavaInstallation(path.resolve(), major, source)
        except (OSError, subprocess.SubprocessError):
            logging.getLogger(__name__).info('No se pudo validar un candidato de Java.')
        return None

    def candidates(self, manual=None):
        if manual:
            yield Path(manual), 'Configurado'
        # Only committed runtimes are considered, never staging/download directories.
        for marker in self.paths.runtime.glob('temurin-*/runtime.json'):
            try:
                relative = json.loads(marker.read_text(encoding='utf-8'))['java']
                path = (marker.parent / relative).resolve()
                if path.is_relative_to(marker.parent.resolve()):
                    yield path, 'Privado de XLauncher'
            except (OSError, ValueError, KeyError, TypeError):
                continue
        if os.environ.get('JAVA_HOME'):
            yield Path(os.environ['JAVA_HOME']) / 'bin' / 'java.exe', 'JAVA_HOME'
        executable = shutil.which('java')
        if executable:
            yield Path(executable), 'PATH'
        for variable in ('ProgramFiles', 'ProgramFiles(x86)'):
            if os.environ.get(variable):
                for vendor in ('Java', 'Eclipse Adoptium', 'Microsoft', 'Amazon Corretto'):
                    for path in (Path(os.environ[variable]) / vendor).glob('*/bin/java.exe'):
                        yield path, 'Detectado en Windows'

    def find(self, required=None, manual=None):
        seen = set()
        for path, source in self.candidates(manual):
            key = str(path).lower()
            if key in seen:
                continue
            seen.add(key)
            java = self.inspect(path, source)
            # Exact major is conservative for older Minecraft and mod loaders.
            if java and (required is None or java.major_version == required):
                return java
        return None

    def install(self, major, progress):
        if os.name != 'nt':
            raise ValueError('El runtime privado está disponible únicamente en Windows.')
        machine = platform.machine().lower()
        architecture = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'aarch64', 'aarch64': 'aarch64'}.get(machine)
        if not architecture:
            raise ValueError('La arquitectura de Windows no está soportada por el instalador de Java.')
        progress('Consultando Eclipse Adoptium…', None)
        # Official Adoptium v3 assets API; never synthesize a binary download URL.
        response = requests.get(f'https://api.adoptium.net/v3/assets/latest/{int(major)}/hotspot',
                                params={'architecture': architecture, 'image_type': 'jdk', 'os': 'windows', 'vendor': 'eclipse'}, timeout=(15, 60))
        response.raise_for_status()
        assets = response.json()
        if not isinstance(assets, list) or not assets:
            raise ValueError(f'Adoptium no ofrece un paquete compatible de Java {major}. Configura un Java manual.')
        package = assets[0]['binary']['package']
        link, checksum = package['link'], package['checksum']
        parsed = urlsplit(link)
        if (parsed.scheme != 'https' or parsed.hostname not in ('github.com', 'api.adoptium.net')
                or (parsed.hostname == 'github.com' and not parsed.path.startswith('/adoptium/'))
                or not parsed.path.lower().endswith('.zip') or not re.fullmatch('[0-9a-fA-F]{64}', checksum)):
            raise ValueError('La API no devolvió un paquete Java verificable de una fuente admitida.')
        with tempfile.TemporaryDirectory(dir=self.paths.runtime, prefix='.staging-') as temp:
            staging = Path(temp)
            archive = staging / 'java.zip'
            digest = hashlib.sha256()
            received = 0
            with requests.get(link, stream=True, timeout=(15, 60)) as download:
                download.raise_for_status()
                if urlsplit(download.url).scheme != 'https':
                    raise ValueError('La descarga no utiliza HTTPS.')
                total = int(download.headers.get('Content-Length', 0))
                with archive.open('xb') as output:
                    for chunk in download.iter_content(256 * 1024):
                        received += len(chunk)
                        if received > 600 * 1024 ** 2:
                            raise ValueError('El paquete supera el tamaño permitido.')
                        digest.update(chunk)
                        output.write(chunk)
                        progress('Descargando Java…', received / total if total else None)
            if digest.hexdigest().lower() != checksum.lower():
                raise ValueError('La verificación SHA-256 de Java falló.')
            unpacked = staging / 'unpacked'
            unpacked.mkdir()
            progress('Verificando y extrayendo Java…', None)
            safe_extract_zip(archive, unpacked)
            candidates = list(unpacked.glob('*/bin/java.exe'))
            java = self.inspect(candidates[0], 'Privado de XLauncher') if len(candidates) == 1 else None
            if java is None or java.major_version != major:
                raise ValueError('El Java descargado no pasó la verificación de versión.')
            relative = java.path.relative_to(unpacked.resolve())
            (unpacked / 'runtime.json').write_text(json.dumps({'java': relative.as_posix(), 'major': major}), encoding='utf-8')
            destination = self.paths.runtime / f'temurin-{major}-{uuid.uuid4().hex[:8]}'
            unpacked.rename(destination)
            logging.getLogger(__name__).info('Runtime privado Java %s instalado y verificado.', major)
            return JavaInstallation(destination / relative, major, 'Privado de XLauncher')
