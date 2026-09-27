import logging
import argparse
import sys
import tkinter as tk
from tkinter import messagebox

from .config import ConfigManager
from .logging_config import configure_logging
from .paths import LauncherPaths


def create_app(paths=None, detect_java_on_start=True):
    from .ui.main_window import MainWindow
    from .services.java_manager import JavaManager
    from .services.minecraft_service import MinecraftService
    from .services.mod_manager import ModManager
    from .services.network import configure_network
    paths = paths or LauncherPaths.default()
    paths.ensure()
    configure_logging(paths)
    configure_network()
    config = ConfigManager(paths.config)
    java = JavaManager(paths)
    return MainWindow(paths, config, java, MinecraftService(paths, java), ModManager(paths), detect_java_on_start)


def main():
    parser = argparse.ArgumentParser(description='XLauncher')
    parser.add_argument('--smoke-test', action='store_true', help='Prueba aislada de arranque, sin red ni datos del usuario')
    parser.add_argument('--smoke-report', help='Archivo JSON de resultado de la prueba de arranque')
    arguments = parser.parse_args()
    if arguments.smoke_test:
        from .diagnostics import smoke_test
        return smoke_test(arguments.smoke_report)
    try:
        app = create_app()
        app.mainloop()
    except (ImportError, OSError, ValueError, tk.TclError):
        logging.getLogger(__name__).exception('No se pudo iniciar XLauncher')
        root = tk.Tk()
        root.withdraw()
        advice = 'Vuelve a extraer el paquete completo de XLauncher.' if getattr(sys, 'frozen', False) else 'Comprueba las dependencias (pip install -r requirements.txt).'
        messagebox.showerror('XLauncher', f'No se pudo iniciar la aplicación. {advice}\nRevisa también los permisos del directorio de datos.', parent=root)
        root.destroy()
        return 1
    return 0
