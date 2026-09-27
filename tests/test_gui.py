import logging
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from minecraft_launcher.app import create_app
from minecraft_launcher.paths import LauncherPaths


class GuiSmokeTests(unittest.TestCase):
    def test_start_without_configuration_java_or_versions_and_corrupt_config(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as directory:
                paths = LauncherPaths(Path(directory))
                if corrupt:
                    paths.config.write_text('{corrupt')
                app = None
                try:
                    with patch('minecraft_launcher.services.java_manager.JavaManager.find', return_value=None), \
                            patch('tkinter.messagebox.showwarning'), patch('tkinter.messagebox.showerror') as error, \
                            patch('requests.sessions.Session.request', side_effect=AssertionError('Unexpected network request')):
                        app = create_app(paths)
                        app.withdraw()
                        deadline = time.monotonic() + 1
                        while time.monotonic() < deadline:
                            app.update()
                            time.sleep(.01)
                        self.assertFalse(app.busy)
                        self.assertEqual(app.minecraft.installed(), [])
                        self.assertIn('No se encontró Java', app.home.java.cget('text'))
                        for page in app.pages:
                            app.show(page)
                            app.update_idletasks()
                        app.play()
                        self.assertIn('No hay versiones', app.status.cget('text'))
                        error.assert_not_called()
                        # An error in a completion callback must not kill the event pump.
                        def fail(_):
                            raise ValueError('Test de callback')
                        app.run_task('Test', lambda: 1, fail)
                        deadline = time.monotonic() + .3
                        while time.monotonic() < deadline:
                            app.update()
                            time.sleep(.01)
                        self.assertFalse(app.busy)
                        error.assert_called_once()
                        completed = []
                        app.run_task('Test siguiente', lambda: 2, completed.append)
                        deadline = time.monotonic() + .3
                        while time.monotonic() < deadline:
                            app.update()
                            time.sleep(.01)
                        self.assertEqual(completed, [2])
                finally:
                    if app:
                        for timer in app.tk.call('after', 'info'):
                            app.after_cancel(timer)
                        app.destroy()
                    logging.shutdown()


if __name__ == '__main__':
    unittest.main()
