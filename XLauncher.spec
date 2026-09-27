# -*- mode: python ; coding: utf-8 -*-
"""Native onedir build: python -m PyInstaller XLauncher.spec"""
import ast
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH)
module = ast.parse((root / 'minecraft_launcher' / '__init__.py').read_text(encoding='utf-8'))
version = next(ast.literal_eval(node.value) for node in module.body
               if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '__version__' for t in node.targets))
icons = root / 'assets' / 'icons'
icon = icons / ('xlauncher.icns' if sys.platform == 'darwin' else 'xlauncher.ico')
data = collect_data_files('customtkinter') + collect_data_files('minecraft_launcher_lib')
data += copy_metadata('minecraft-launcher-lib') + copy_metadata('customtkinter')
data += [(str(root / 'assets'), 'assets')]

windows_version = None
if sys.platform == 'win32':
    from PyInstaller.utils.win32.versioninfo import VSVersionInfo, FixedFileInfo, StringFileInfo, StringTable, StringStruct, VarFileInfo, VarStruct
    numbers = tuple(int(part) for part in version.split('.')) + (0,)
    windows_version = VSVersionInfo(
        ffi=FixedFileInfo(filevers=numbers, prodvers=numbers, mask=0x3f, flags=0,
                         OS=0x40004, fileType=1, subtype=0, date=(0, 0)),
        kids=[StringFileInfo([StringTable('040904B0', [
            StringStruct('FileDescription', 'XLauncher'), StringStruct('ProductName', 'XLauncher'),
            StringStruct('FileVersion', version), StringStruct('ProductVersion', version),
            StringStruct('OriginalFilename', 'XLauncher.exe')])]),
            VarFileInfo([VarStruct('Translation', [1033, 1200])])])

a = Analysis(
    [str(root / 'main.py')], pathex=[str(root)], binaries=[], datas=data,
    hiddenimports=collect_submodules('minecraft_launcher_lib'),
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[], noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='XLauncher',
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon=str(icon) if icon.is_file() and sys.platform in ('win32', 'darwin') else None,
    version=windows_version,
)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='XLauncher')
if sys.platform == 'darwin':
    app = BUNDLE(
        collection, name='XLauncher.app', icon=str(icon) if icon.is_file() else None,
        bundle_identifier='org.xlauncher.launcher', version=version,
        info_plist={'CFBundleShortVersionString': version, 'CFBundleVersion': version,
                    'NSHighResolutionCapable': True},
    )
