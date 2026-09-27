import logging
import tkinter as tk
from tkinter import messagebox

from .config import ConfigManager
from .logging_config import configure_logging
from .paths import LauncherPaths


def create_app(paths=None):
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
    return MainWindow(paths, config, java, MinecraftService(paths, java), ModManager(paths))


def main():
    try:
        app = create_app()
        app.mainloop()
    except (ImportError, OSError, ValueError, tk.TclError):
        logging.getLogger(__name__).exception('No se pudo iniciar XLauncher')
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror('XLauncher', 'No se pudo iniciar la aplicación. Comprueba las dependencias\n(pip install -r requirements.txt) y los permisos del directorio de datos.', parent=root)
        root.destroy()
