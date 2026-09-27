import json
import hashlib
import io
import os
import stat
import subprocess
import tempfile
import unittest
import zipfile
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from minecraft_launcher.config import ConfigManager, Configuration, memory_limit
from minecraft_launcher.paths import LauncherPaths
from minecraft_launcher.services.java_manager import JavaInstallation, JavaManager, get_required_java_major, parse_java_major, safe_extract_zip
from minecraft_launcher.services.minecraft_service import JavaRequired, MinecraftService
from minecraft_launcher.services.mod_manager import ModManager


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.paths = LauncherPaths(Path(self.temp.name))
        self.paths.ensure()


class ConfigTests(WorkspaceTest):
    def test_first_start_and_atomic_save(self):
        manager = ConfigManager(self.paths.config)
        self.assertEqual(manager.data.username, 'Player')
        manager.save(replace(manager.data, username='Joseph', memory_gb=1))
        self.assertEqual(ConfigManager(self.paths.config).data.username, 'Joseph')
        self.assertEqual(list(self.paths.root.glob('tmp*')), [])

    def test_legacy_migration(self):
        self.paths.config.write_text(json.dumps({'Nombre': 'Joseph', 'RAM': '1', 'Version': '1.20.4', 'Java': ''}))
        manager = ConfigManager(self.paths.config)
        self.assertEqual(manager.data.memory_gb, 1)
        self.assertEqual(manager.data.selected_version, '1.20.4')
        self.assertIsNone(manager.data.java_path)
        self.assertNotIn('Nombre', json.loads(self.paths.config.read_text()))

    def test_corrupt_and_wrong_types(self):
        for value in ('{broken', '[]', '{"memory_gb": true}', '{"username": 42}'):
            with self.subTest(value=value):
                self.paths.config.write_text(value)
                manager = ConfigManager(self.paths.config)
                self.assertEqual(manager.data.username, 'Player')
                self.assertIsNotNone(manager.warning)
        self.assertEqual(len(list(self.paths.root.glob('configuration.invalid-*.json'))), 4)

    def test_invalid_save_does_not_replace(self):
        manager = ConfigManager(self.paths.config)
        original = self.paths.config.read_bytes()
        for data in (replace(manager.data, username='../bad'), replace(manager.data, memory_gb=memory_limit() + 1)):
            with self.assertRaises(ValueError):
                manager.save(data)
        self.assertEqual(original, self.paths.config.read_bytes())


class JavaTests(WorkspaceTest):
    @unittest.skipUnless(os.name == 'nt', 'Runtime privado para Windows')
    def test_private_runtime_verified_before_commit(self):
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, 'w') as archive:
            archive.writestr('jdk-21/bin/java.exe', b'fake-executable-for-test')
        content = payload.getvalue()
        checksum = hashlib.sha256(content).hexdigest()
        metadata = Mock()
        metadata.json.return_value = [{'binary': {'package': {'link': 'https://github.com/adoptium/temurin21-binaries/releases/download/test/test.zip', 'checksum': checksum}}}]
        download = Mock()
        download.url = 'https://release-assets.githubusercontent.com/test.zip'
        download.headers = {'Content-Length': str(len(content))}
        download.iter_content.return_value = [content]
        download.__enter__ = Mock(return_value=download)
        download.__exit__ = Mock(return_value=False)
        manager = JavaManager(self.paths)

        def verified(path, source):
            self.assertEqual(list(self.paths.runtime.glob('temurin-*')), [])
            self.assertTrue(path.is_file())
            return JavaInstallation(path.resolve(), 21, source)

        with patch('requests.get', side_effect=[metadata, download]), \
                patch('platform.machine', return_value='AMD64'), patch.object(manager, 'inspect', side_effect=verified):
            result = manager.install(21, lambda *_: None)
        self.assertTrue(result.path.is_file())
        self.assertEqual(len(list(self.paths.runtime.glob('temurin-*/runtime.json'))), 1)
        self.assertEqual(list(self.paths.runtime.glob('.staging-*')), [])

    @unittest.skipUnless(os.name == 'nt', 'Runtime privado para Windows')
    def test_bad_checksum_never_executes_or_commits(self):
        metadata = Mock()
        metadata.json.return_value = [{'binary': {'package': {'link': 'https://github.com/adoptium/test/releases/download/test/test.zip', 'checksum': '0' * 64}}}]
        download = Mock()
        download.url = 'https://github.com/adoptium/test.zip'
        download.headers = {}
        download.iter_content.return_value = [b'invalid']
        download.__enter__ = Mock(return_value=download)
        download.__exit__ = Mock(return_value=False)
        manager = JavaManager(self.paths)
        with patch('requests.get', side_effect=[metadata, download]), patch('platform.machine', return_value='AMD64'), \
                patch.object(manager, 'inspect') as inspect:
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                manager.install(21, lambda *_: None)
            inspect.assert_not_called()
        self.assertEqual(list(self.paths.runtime.iterdir()), [])

    def test_parse(self):
        for value, expected in [('java version "1.8.0_412"', 8), ('openjdk version "21.0.2" 2024', 21),
                                ('openjdk 17.0.10 2024', 17), ('java version "16-ea"', 16), ('not java', None)]:
            self.assertEqual(parse_java_major(value), expected)

    def test_compatibility(self):
        for version, expected in [('1.7.10', 8), ('1.16.5', 8), ('1.17.1', 16), ('1.18', 17),
                                  ('1.20.4', 17), ('1.20.5', 21), ('1.21.8', 21)]:
            self.assertEqual(get_required_java_major(version), expected)
        self.assertEqual(get_required_java_major('future', {'javaVersion': {'majorVersion': 25}}), 25)
        with self.assertRaises(ValueError):
            get_required_java_major('26w01a')

    def test_validate_and_detection_order(self):
        manager = JavaManager(self.paths)
        executable = self.paths.root / 'java.exe'
        executable.touch()
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 0, '', 'openjdk version "21.0.1"')) as run:
            self.assertEqual(manager.inspect(executable, 'test').major_version, 21)
            self.assertEqual(run.call_args.kwargs['timeout'], 10)
        with patch('subprocess.run', return_value=subprocess.CompletedProcess([], 1, '', 'openjdk version "21"')):
            self.assertIsNone(manager.inspect(executable, 'test'))
        with patch.object(manager, 'candidates', return_value=iter([(Path('manual'), 'manual'), (Path('private'), 'private')])), \
                patch.object(manager, 'inspect', side_effect=[JavaInstallation(Path('manual'), 8, 'manual'), JavaInstallation(Path('private'), 21, 'private')]):
            self.assertEqual(manager.find(21).source, 'private')
        with patch.object(manager, 'candidates', return_value=iter([])):
            self.assertIsNone(manager.find(21))

    def test_extract_safe_and_traversal(self):
        archive = self.paths.root / 'runtime.zip'
        target = self.paths.root / 'extract'
        with zipfile.ZipFile(archive, 'w') as bundle:
            bundle.writestr('jdk/bin/java.exe', b'test')
        safe_extract_zip(archive, target)
        self.assertEqual((target / 'jdk/bin/java.exe').read_bytes(), b'test')
        for name in ('../escape', '/absolute', 'C:/escape', 'jdk/../../escape', '..\\escape', 'jdk/file:stream', 'jdk/CON.txt', 'jdk/foo.'):
            with self.subTest(name=name):
                with zipfile.ZipFile(archive, 'w') as bundle:
                    bundle.writestr(name, b'test')
                with self.assertRaises(ValueError):
                    safe_extract_zip(archive, target)
        with zipfile.ZipFile(archive, 'w') as bundle:
            info = zipfile.ZipInfo('link')
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            bundle.writestr(info, '../outside')
        with self.assertRaises(ValueError):
            safe_extract_zip(archive, target)


class ModsTests(WorkspaceTest):
    def test_lifecycle(self):
        manager = ModManager(self.paths)
        source = self.paths.root / 'example.jar'
        source.write_bytes(b'example')
        manager.import_mod(source)
        self.assertEqual(manager.list_mods(), [('example.jar', True)])
        with self.assertRaises(ValueError):
            manager.import_mod(source)
        manager.toggle('example.jar', True)
        self.assertEqual(manager.list_mods(), [('example.jar', False)])
        manager.toggle('example.jar', False)
        manager.delete('example.jar', True)
        self.assertEqual(manager.list_mods(), [])

    def test_validation_and_collision(self):
        manager = ModManager(self.paths)
        with self.assertRaises(ValueError):
            manager.import_mod(self.paths.config)
        for name in ('../outside.jar', 'C:outside.jar', 'bad.txt'):
            with self.assertRaises(ValueError):
                manager.delete(name, True)
        for folder in ('mods', 'disabled_mods'):
            (self.paths.root / folder / 'same.jar').write_bytes(b'original')
        with self.assertRaises(ValueError):
            manager.toggle('same.jar', True)
        self.assertEqual((self.paths.root / 'disabled_mods/same.jar').read_bytes(), b'original')


class MinecraftTests(WorkspaceTest):
    def setUp(self):
        super().setUp()
        self.java = Mock()
        self.service = MinecraftService(self.paths, self.java)

    def metadata(self, version, data):
        path = self.service._metadata_path(version)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'id': version, 'type': 'release', 'releaseTime': '2024-01-01T00:00:00+00:00', **data}))

    def test_empty_and_missing_java(self):
        self.assertEqual(self.service.installed(), [])
        with self.assertRaisesRegex(ValueError, 'no está instalada'):
            self.service.launch(Configuration(memory_gb=1))
        self.java.find.return_value = None
        with self.assertRaises(JavaRequired) as error:
            self.service.compatible_java('1.21', None)
        self.assertEqual(error.exception.major, 21)

    def test_metadata_inheritance_and_cycle(self):
        self.metadata('1.21', {'javaVersion': {'majorVersion': 21}})
        self.metadata('fabric-local', {'inheritsFrom': '1.21'})
        self.assertEqual(self.service.required_java('fabric-local'), 21)
        self.metadata('cycle', {'inheritsFrom': 'cycle'})
        with self.assertRaises(ValueError):
            self.service.required_java('cycle')

    def test_launch_command(self):
        self.metadata('1.21', {'javaVersion': {'majorVersion': 21}})
        self.java.find.return_value = JavaInstallation(Path('java.exe'), 21, 'test')
        with patch('minecraft_launcher_lib.command.get_minecraft_command', return_value=['java.exe', 'main']) as command, \
                patch('subprocess.Popen') as popen:
            self.service.launch(Configuration(username='Joseph', memory_gb=1, selected_version='1.21'))
            options = command.call_args.args[2]
            self.assertEqual(options['token'], '')
            self.assertEqual(options['jvmArguments'], ['-Xms512M', '-Xmx1G'])
            self.assertEqual(popen.call_args.args[0], ['java.exe', 'main'])
            self.assertNotIn('shell', popen.call_args.kwargs)

    def test_install_failure_is_incomplete_and_unlocks(self):
        self.metadata('1.21', {})
        with patch('minecraft_launcher_lib.install.install_minecraft_version', side_effect=OSError('network')):
            with self.assertRaises(OSError):
                self.service.install('1.21', 'Vanilla', None, lambda *_: None)
        self.assertNotIn('1.21', self.service.installed())
        self.assertFalse(self.service.install_lock.locked())
        with patch('minecraft_launcher_lib.install.install_minecraft_version'):
            self.service.install('1.21', 'Vanilla', None, lambda *_: None)
        self.assertIn('1.21', self.service.installed())

    def test_fabric_and_forge_call_supported_api(self):
        self.metadata('1.21', {'javaVersion': {'majorVersion': 21}})
        self.java.find.return_value = JavaInstallation(Path('java.exe'), 21, 'test')
        for name in ('Fabric', 'Forge'):
            loader = Mock()
            loader.get_installed_version.return_value = name.lower() + '-local'
            with patch('minecraft_launcher_lib.install.install_minecraft_version'), \
                    patch('minecraft_launcher.services.minecraft_service.get_mod_loader', return_value=loader):
                self.assertEqual(self.service.install('1.21', name, None, lambda *_: None), name.lower() + '-local')
                self.assertEqual(loader.install.call_args.kwargs['java'], 'java.exe')


class NetworkTests(unittest.TestCase):
    def test_https_timeout_and_http_errors(self):
        import requests
        from minecraft_launcher.services.network import configure_network
        response = Mock()
        # A plain function preserves Session method binding in this isolated patch.
        calls = []

        def original(session, request, **kwargs):
            calls.append(kwargs)
            return response

        with patch.object(requests.sessions.Session, 'send', original):
            configure_network()
            session = requests.Session()
            request = requests.Request('GET', 'https://example.org').prepare()
            session.send(request)
            self.assertEqual(calls[0]['timeout'], (15, 60))
            response.raise_for_status.assert_called_once()
            with self.assertRaises(requests.RequestException):
                session.send(requests.Request('GET', 'http://example.org').prepare())


if __name__ == '__main__':
    unittest.main()
