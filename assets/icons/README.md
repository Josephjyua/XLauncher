# Application icons

No final icon is included. Optional files recognized by the build:

- `xlauncher.ico`: Windows executable/window.
- `xlauncher.png`: Tk window icon (Linux/macOS; fallback on Windows).
- `xlauncher.icns`: macOS application bundle.

Add the approved artwork at these exact paths and rebuild. Missing icons do not
prevent builds; the OS/PyInstaller default is used. Do not put writable user data
here. `minecraft_launcher.paths.resource_path()` resolves these bundled assets.
