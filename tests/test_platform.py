import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from minecraft_launcher.config import ConfigManager
from minecraft_launcher.paths import LauncherPaths, resource_path, extra_java_candidates
from minecraft_launcher.platform_support import adoptium_target, java_executable_name, external_environment, external_process_environment
from minecraft_launcher.services.java_manager import JavaManager, JavaInstallation, safe_extract_tar
from minecraft_launcher.services.mod_manager import ModManager


class PlatformTests(unittest.TestCase):
    def test_data_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            for system, expected in [('Windows', home / 'roaming/XLauncher'),
                                     ('Linux', home / '.local/share/XLauncher'),
                                     ('Darwin', home / 'Library/Application Support/XLauncher')]:
                with self.subTest(system=system), patch('platform.system', return_value=system), \
                        patch('pathlib.Path.home', return_value=home), \
                        patch.dict(os.environ, {'APPDATA': str(home / 'roaming')}, clear=True):
                    self.assertEqual(LauncherPaths.default().root, expected)

    def test_xdg_absolute_only(self):
        with tempfile.TemporaryDirectory() as directory, patch('platform.system', return_value='Linux'):
            with patch.dict(os.environ, {'XDG_DATA_HOME': directory}):
                self.assertEqual(LauncherPaths.default().root, Path(directory) / 'XLauncher')
            with patch.dict(os.environ, {'XDG_DATA_HOME': 'relative'}):
                self.assertEqual(LauncherPaths.default().root, Path.home() / '.local/share/XLauncher')

    def test_windows_legacy_stays_in_place_and_migrates_config(self):
        with tempfile.TemporaryDirectory() as directory, patch('platform.system', return_value='Windows'), \
                patch.dict(os.environ, {'APPDATA': directory}):
            legacy = Path(directory) / '.xlauncher'
            legacy.mkdir()
            (legacy / 'configuration.json').write_text(json.dumps({'Nombre': 'Joseph', 'RAM': '1'}))
            (legacy / 'versions').mkdir()
            sentinel = legacy / 'versions/existing.jar'
            sentinel.write_bytes(b'keep existing installation')
            # Legacy wins even if a second directory exists. No automatic merging.
            (Path(directory) / 'XLauncher').mkdir()
            paths = LauncherPaths.default()
            self.assertEqual(paths.root, legacy)
            self.assertEqual(ConfigManager(paths.config).data.username, 'Joseph')
            self.assertEqual(sentinel.read_bytes(), b'keep existing installation')
            self.assertEqual(list((Path(directory) / 'XLauncher').iterdir()), [])

    def test_names_and_api_platform_mapping(self):
        cases = [('Windows', 'AMD64', ('windows', 'x64', '.zip')),
                 ('Linux', 'x86_64', ('linux', 'x64', '.tar.gz')),
                 ('Darwin', 'x86_64', ('mac', 'x64', '.tar.gz')),
                 ('Darwin', 'arm64', ('mac', 'aarch64', '.tar.gz'))]
        for system, machine, expected in cases:
            with self.subTest(system=system, machine=machine):
                self.assertEqual(adoptium_target(system, machine), expected)
                self.assertEqual(java_executable_name(system), 'java.exe' if system == 'Windows' else 'java')
        for system, machine in [('Linux', 'i686'), ('Darwin', 'ppc'), ('FreeBSD', 'amd64')]:
            with self.assertRaises(ValueError):
                adoptium_target(system, machine)

    def test_java_home_per_platform(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = LauncherPaths(Path(directory))
            paths.ensure()
            for system in ('Windows', 'Linux', 'Darwin'):
                with patch('platform.system', return_value=system), patch.dict(os.environ, {'JAVA_HOME': directory}), \
                        patch('shutil.which', return_value=None), \
                        patch('minecraft_launcher.services.java_manager.extra_java_candidates', return_value=[]):
                    candidates = list(JavaManager(paths).candidates())
                    self.assertIn((Path(directory) / 'bin' / java_executable_name(system), 'JAVA_HOME'), candidates)

    def test_additional_search_locations(self):
        for system, fragment in [('Windows', 'bin/java.exe'), ('Linux', 'bin/java'), ('Darwin', 'Contents/Home/bin/java')]:
            patterns = []
            def glob(path, pattern):
                patterns.append(pattern)
                return iter([])
            with patch.dict(os.environ, {'ProgramFiles': 'programs'}), patch.object(Path, 'glob', glob):
                list(extra_java_candidates(system))
            self.assertTrue(any(fragment in pattern for pattern in patterns))

    def test_resources_source_and_frozen(self):
        self.assertTrue(resource_path('assets/icons/README.md').is_file())
        with tempfile.TemporaryDirectory() as directory, patch.object(sys, '_MEIPASS', directory, create=True):
            self.assertEqual(resource_path('assets/icons/xlauncher.png'), (Path(directory) / 'assets/icons/xlauncher.png').resolve())
            with self.assertRaises(ValueError):
                resource_path('../outside')

    def test_frozen_environment_restores_system_libraries(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(sys, 'frozen', True, create=True), \
                patch.object(sys, '_MEIPASS', directory, create=True), \
                patch.dict(os.environ, {'LD_LIBRARY_PATH': directory, 'LD_LIBRARY_PATH_ORIG': '/system/libs',
                                        'PATH': os.pathsep.join([directory, str(Path(directory).parent)])}):
            clean = external_environment()
            self.assertEqual(clean['LD_LIBRARY_PATH'], '/system/libs')
            self.assertNotIn(directory, clean['PATH'].split(os.pathsep))
            with external_process_environment():
                self.assertEqual(os.environ['LD_LIBRARY_PATH'], '/system/libs')
            self.assertEqual(os.environ['LD_LIBRARY_PATH'], directory)

    def test_folder_open_commands_preserve_spaces(self):
        paths = LauncherPaths(Path(tempfile.gettempdir()) / 'with spaces')
        for system, command in [('Darwin', 'open'), ('Linux', 'xdg-open')]:
            with patch('platform.system', return_value=system), patch('subprocess.Popen') as popen:
                ModManager(paths).open_folder()
                self.assertEqual(popen.call_args.args[0], [command, str(paths.root / 'mods')])
                self.assertNotIn('shell', popen.call_args.kwargs)

    def test_java_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix='java path ') as directory:
            executable = Path(directory) / java_executable_name()
            executable.touch()
            with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, '', 'openjdk version "21"')) as run:
                JavaManager(LauncherPaths(Path(directory))).inspect(executable, 'test')
                self.assertEqual(run.call_args.args[0], [str(executable.resolve()), '-version'])


class TarTests(unittest.TestCase):
    def archive(self, file, name='jdk/bin/java', kind=tarfile.REGTYPE, linkname=''):
        with tarfile.open(file, 'w:gz') as archive:
            item = tarfile.TarInfo(name)
            item.type, item.linkname, item.mode = kind, linkname, 0o4755
            item.size = 4 if kind == tarfile.REGTYPE else 0
            archive.addfile(item, io.BytesIO(b'java') if item.size else None)

    def test_regular_file_and_execute_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.archive(root / 'java.tar.gz')
            safe_extract_tar(root / 'java.tar.gz', root / 'out')
            java = root / 'out/jdk/bin/java'
            self.assertEqual(java.read_bytes(), b'java')
            if os.name != 'nt':
                self.assertEqual(java.stat().st_mode & 0o7777, 0o755)

    def test_unsafe_members_and_links_rejected(self):
        cases = [('../escape', tarfile.REGTYPE, ''), ('/absolute', tarfile.REGTYPE, ''),
                 ('C:/escape', tarfile.REGTYPE, ''), ('jdk/fifo', tarfile.FIFOTYPE, ''),
                 ('jdk/link', tarfile.SYMTYPE, '../../escape'),
                 ('jdk/link', tarfile.LNKTYPE, '../escape'),
                 ('jdk/link', tarfile.SYMTYPE, '/absolute')]
        for name, kind, link in cases:
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.archive(root / 'java.tar.gz', name, kind, link)
                with self.assertRaises(ValueError):
                    safe_extract_tar(root / 'java.tar.gz', root / 'out')

    def test_internal_hardlink_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with tarfile.open(root / 'java.tar.gz', 'w:gz') as archive:
                item = tarfile.TarInfo('jdk/lib/data')
                item.size = 4
                archive.addfile(item, io.BytesIO(b'data'))
                link = tarfile.TarInfo('jdk/lib/copy')
                link.type, link.linkname = tarfile.LNKTYPE, 'jdk/lib/data'
                archive.addfile(link)
            safe_extract_tar(root / 'java.tar.gz', root / 'out')
            self.assertEqual((root / 'out/jdk/lib/copy').read_bytes(), b'data')

    def test_unix_downloads_use_tar_and_correct_api_target(self):
        for system, machine, binary in [('Linux', 'x86_64', 'jdk/bin/java'),
                                         ('Darwin', 'arm64', 'jdk/Contents/Home/bin/java'),
                                         ('Darwin', 'x86_64', 'jdk/Contents/Home/bin/java')]:
            with self.subTest(system=system, machine=machine), tempfile.TemporaryDirectory() as directory:
                paths = LauncherPaths(Path(directory))
                paths.ensure()
                payload = io.BytesIO()
                with tarfile.open(fileobj=payload, mode='w:gz') as archive:
                    item = tarfile.TarInfo(binary)
                    item.size, item.mode = 4, 0o755
                    archive.addfile(item, io.BytesIO(b'java'))
                content = payload.getvalue()
                metadata = Mock()
                metadata.json.return_value = [{'binary': {'package': {
                    'link': 'https://github.com/adoptium/test/releases/download/test/java.tar.gz',
                    'checksum': hashlib.sha256(content).hexdigest()}}}]
                download = Mock()
                download.url, download.headers = 'https://github.com/adoptium/java.tar.gz', {}
                download.iter_content.return_value = [content]
                download.__enter__, download.__exit__ = Mock(return_value=download), Mock(return_value=False)
                manager = JavaManager(paths)
                with patch('platform.system', return_value=system), patch('platform.machine', return_value=machine), \
                        patch('requests.get', side_effect=[metadata, download]) as get, \
                        patch.object(manager, 'inspect', side_effect=lambda path, source: JavaInstallation(path.resolve(), 21, source)):
                    java = manager.install(21, lambda *_: None)
                self.assertTrue(java.path.is_file())
                self.assertEqual(get.call_args_list[0].kwargs['params']['os'], 'mac' if system == 'Darwin' else 'linux')
                self.assertEqual(list(paths.runtime.glob('.staging-*')), [])
