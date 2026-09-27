"""Isolated packaged GUI smoke test; never opens existing launcher data."""
import json
import logging
import tempfile
import time
from pathlib import Path

from . import __version__
from .paths import LauncherPaths, resource_path


def smoke_test(report=None):
    result = {'version': __version__, 'ok': False}
    try:
        from .app import create_app
        with tempfile.TemporaryDirectory(prefix='xlauncher-smoke-') as directory:
            app = None
            try:
                paths = LauncherPaths(Path(directory))
                app = create_app(paths, detect_java_on_start=False)
                app.withdraw()
                if not resource_path('assets/icons/README.md').is_file():
                    raise RuntimeError('Faltan los recursos empaquetados.')
                if app.minecraft.installed():
                    raise RuntimeError('La prueba debe usar una carpeta vacía.')
                for page in app.pages:
                    app.show(page)
                    app.update_idletasks()
                deadline = time.monotonic() + .5
                while time.monotonic() < deadline:
                    app.update()
                    time.sleep(.01)
                if not paths.config.is_file() or not (paths.root / 'logs/xlauncher.log').is_file():
                    raise RuntimeError('No se pudo escribir la configuración o el log temporal.')
                result['ok'] = True
            finally:
                if app:
                    for timer in app.tk.call('after', 'info'):
                        app.after_cancel(timer)
                    app.destroy()
                logging.shutdown()
    except Exception as error:
        # Diagnostic boundary; machine-readable failure instead of a modal dialog in CI.
        result.update(ok=False, error=f'{type(error).__name__}: {error}')
    if report:
        Path(report).write_text(json.dumps(result, indent=2), encoding='utf-8')
    return 0 if result['ok'] else 1
