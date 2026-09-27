import logging
import queue
import threading
from dataclasses import replace
from tkinter import messagebox

import customtkinter as ctk
import requests
from minecraft_launcher_lib.exceptions import UnsupportedVersion, VersionNotFound

from ..services.minecraft_service import JavaRequired
from .pages.home_page import HomePage
from .pages.installations_page import InstallationsPage
from .pages.mods_page import ModsPage
from .pages.settings_page import SettingsPage


class MainWindow(ctk.CTk):
    def __init__(self, paths, config, java, minecraft, mods):
        super().__init__()
        self.paths, self.config, self.java_manager = paths, config, java
        self.minecraft, self.mods = minecraft, mods
        self.busy = False
        self.events = queue.Queue()
        self.buttons = []
        self.catalog = []
        self.missing_major = None
        self.pending_progress = None
        self.progress_lock = threading.Lock()
        self.title('XLauncher')
        self.geometry('980x700')
        self.minsize(850, 640)
        self.protocol('WM_DELETE_WINDOW', self.close)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        sidebar = ctk.CTkFrame(self, width=170)
        sidebar.grid(row=0, column=0, rowspan=3, sticky='nsew', padx=8, pady=8)
        ctk.CTkLabel(sidebar, text='XLauncher', font=ctk.CTkFont(size=23, weight='bold')).pack(padx=15, pady=25)
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=1, sticky='nsew', padx=8, pady=8)
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)
        self.status = ctk.CTkLabel(self, text='Listo.', wraplength=700, anchor='w')
        self.status.grid(row=1, column=1, sticky='ew', padx=12, pady=6)
        self.progress = ctk.CTkProgressBar(self)
        self.progress.grid(row=2, column=1, sticky='ew', padx=12, pady=(0, 14))
        self.progress.set(0)
        self.home = HomePage(self.container, self)
        self.installations = InstallationsPage(self.container, self)
        self.pages = {'Jugar': self.home, 'Instalaciones': self.installations,
                      'Mods': ModsPage(self.container, self), 'Ajustes': SettingsPage(self.container, self)}
        for name, page in self.pages.items():
            page.grid(row=0, column=0, sticky='nsew')
            ctk.CTkButton(sidebar, text=name.upper(), command=lambda n=name: self.show(n)).pack(padx=10, pady=8)
        self.show('Jugar')
        self.after(80, self.poll_events)
        self.after(150, self.detect_java)
        if config.warning:
            self.after(250, lambda: messagebox.showwarning('Configuración recuperada', config.warning, parent=self))

    def action(self, parent, text, command):
        button = ctk.CTkButton(parent, text=text, command=command, width=250)
        self.buttons.append(button)
        return button

    def show(self, name):
        try:
            self.pages[name].refresh()
            self.pages[name].tkraise()
        except (OSError, ValueError) as error:
            self.error(error)

    def set_busy(self, value):
        self.busy = value
        for button in self.buttons:
            button.configure(state='disabled' if value else 'normal')
        self.home.version.configure(state='disabled' if value else 'readonly')
        self.installations.version.configure(state='disabled' if value else 'readonly')
        self.installations.loader.configure(state='disabled' if value else 'normal')

    def report_progress(self, status, fraction):
        # Coalesce callbacks: asset downloads can report thousands per second.
        with self.progress_lock:
            self.pending_progress = (status, fraction)

    def run_task(self, label, work, done=None):
        if self.busy:
            return
        self.set_busy(True)
        self.status.configure(text=label)
        self.progress.configure(mode='indeterminate')
        self.progress.start()

        def worker():
            try:
                result = work()
                self.events.put(('done', result, done))
            except Exception as error:
                # Boundary for third-party libraries: preserve the GUI and log details.
                logging.getLogger(__name__).exception('Falló la operación: %s', label)
                self.events.put(('error', error, None))

        threading.Thread(target=worker, name='xlauncher-worker', daemon=True).start()

    def poll_events(self):
        with self.progress_lock:
            progress, self.pending_progress = self.pending_progress, None
        if progress and self.busy:
            status, fraction = progress
            self.status.configure(text=status)
            if fraction is not None:
                self.progress.stop()
                self.progress.configure(mode='determinate')
                self.progress.set(max(0, min(1, fraction)))
        try:
            while True:
                event, value, callback = self.events.get_nowait()
                self.progress.stop()
                self.progress.configure(mode='determinate')
                self.progress.set(1 if event == 'done' else 0)
                self.set_busy(False)
                if event == 'error':
                    self.error(value)
                else:
                    self.status.configure(text='Operación completada.')
                    if callback:
                        try:
                            callback(value)
                        except Exception as error:
                            # Completion handlers must not stop the event pump.
                            logging.getLogger(__name__).exception('Falló la actualización de la interfaz')
                            self.error(error)
        except queue.Empty:
            pass
        self.after(80, self.poll_events)

    def report_callback_exception(self, exception, value, traceback):
        logging.getLogger(__name__).error('Error de interfaz', exc_info=(exception, value, traceback))
        self.error(value)

    def error(self, error):
        if isinstance(error, JavaRequired):
            self.missing_major = error.major
            self.home.java.configure(text=str(error))
            self.status.configure(text=str(error))
            if messagebox.askyesno('Java requerido', f'{error}\n\n¿Descargar el runtime privado verificado de Adoptium?', parent=self):
                self.install_java(error.major)
            return
        if isinstance(error, requests.RequestException):
            message = 'No fue posible completar la descarga. Revisa tu conexión e inténtalo de nuevo.'
        elif isinstance(error, (UnsupportedVersion, VersionNotFound)):
            message = 'La versión no está disponible o no es compatible con el loader seleccionado.'
        elif isinstance(error, ValueError):
            message = str(error)
        elif isinstance(error, OSError):
            message = 'No se pudo acceder a un archivo o iniciar el programa. Revisa las rutas y permisos.'
        else:
            message = 'No se pudo completar la operación. Revisa logs/xlauncher.log para ver los detalles.'
        self.status.configure(text=message)
        messagebox.showerror('XLauncher', message, parent=self)

    def selected(self):
        version = self.home.version.get()
        return version if version in self.minecraft.installed() else None

    def select_version(self, version):
        try:
            self.config.save(replace(self.config.data, selected_version=version))
            self.home.refresh()
            self.detect_java()
        except (OSError, ValueError) as error:
            self.error(error)

    def detect_java(self):
        version, manual = self.selected(), self.config.data.java_path

        def detect():
            major = self.minecraft.required_java(version) if version else None
            return major, self.java_manager.find(major, manual)

        def done(result):
            major, java = result
            self.missing_major = major if java is None else None
            self.home.java.configure(text=f'Java {java.major_version} · {java.source}\n{java.path}' if java else
                                     f'No se encontró Java {major or ""} compatible. Instala Java para XLauncher.')
            self.status.configure(text='Detección de Java completada.')

        self.run_task('Detectando Java…', detect, done)

    def install_java(self, major=None):
        if self.busy:
            return
        try:
            version = self.selected()
            major = major or self.missing_major or (self.minecraft.required_java(version) if version else 21)
            self.run_task(f'Preparando Java {major}…', lambda: self.java_manager.install(major, self.report_progress),
                          lambda _: self.detect_java())
        except (ValueError, OSError) as error:
            self.error(error)

    def fetch_versions(self):
        def done(versions):
            self.catalog = versions
            self.installations.version.configure(values=versions or ['No hay versiones disponibles'])
            self.installations.version.set(versions[0] if versions else 'No hay versiones disponibles')
        self.run_task('Obteniendo catálogo de Minecraft…', self.minecraft.available, done)

    def install_minecraft(self):
        version, loader = self.installations.version.get(), self.installations.loader.get()
        if version not in self.catalog:
            self.error(ValueError('Obtén el catálogo y selecciona una versión.'))
            return
        if self.minecraft.process and self.minecraft.process.poll() is None:
            self.error(ValueError('Cierra Minecraft antes de instalar versiones.'))
            return
        if version in self.minecraft.installed() and loader == 'Vanilla':
            if not messagebox.askyesno('Revisar instalación', 'La versión ya está instalada. ¿Revisar y reparar sus archivos?', parent=self):
                return
        manual = self.config.data.java_path

        def done(installed):
            self.config.save(replace(self.config.data, selected_version=installed))
            self.show('Jugar')
            self.detect_java()
        self.run_task(f'Instalando {loader} {version}…',
                      lambda: self.minecraft.install(version, loader, manual, self.report_progress), done)

    def play(self):
        version = self.selected()
        if not version:
            self.show('Instalaciones')
            self.status.configure(text='No hay versiones instaladas. Obtén el catálogo para instalar Minecraft.')
            return
        try:
            config = replace(self.config.data, selected_version=version)
            self.config.save(config)
        except (OSError, ValueError) as error:
            self.error(error)
            return

        def done(result):
            process, log = result
            self.status.configure(text='Minecraft está ejecutándose.')
            self.after(1000, lambda: self.watch_game(process, log))
        self.run_task('Preparando Minecraft…', lambda: self.minecraft.launch(config), done)

    def watch_game(self, process, log):
        code = process.poll()
        if code is None:
            self.after(1000, lambda: self.watch_game(process, log))
        elif code != 0:
            self.error(ValueError(f'Minecraft terminó con un error ({code}). Detalles en logs/{log.name}.'))
        elif not self.busy:
            self.status.configure(text='Minecraft se cerró.')

    def close(self):
        if self.busy:
            messagebox.showinfo('Operación en curso', 'Espera a que finalice la operación antes de cerrar XLauncher.', parent=self)
            return
        self.destroy()
