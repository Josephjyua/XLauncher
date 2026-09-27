from dataclasses import replace
from tkinter import filedialog
import customtkinter as ctk
from ...config import memory_limit
from ...platform_support import java_executable_name


class SettingsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        ctk.CTkLabel(self, text='Ajustes', font=ctk.CTkFont(size=26)).pack(pady=20)
        self.fields = {}
        for key, label in [('username', 'Nombre del jugador (perfil local)'), ('memory_gb', f'RAM en GB (1–{memory_limit()})'), ('java_path', f'Java manual (opcional, {java_executable_name()})')]:
            ctk.CTkLabel(self, text=label).pack(pady=(10, 2))
            entry = ctk.CTkEntry(self, width=470)
            entry.pack(pady=4)
            self.fields[key] = entry
        app.action(self, f'Buscar {java_executable_name()}', self.browse).pack(pady=8)
        app.action(self, 'Guardar ajustes', self.save).pack(pady=8)
        ctk.CTkLabel(self, text='Deja Java vacío para detección automática.\nNo se guardan contraseñas ni tokens.').pack(pady=10)

    def browse(self):
        executable = java_executable_name()
        path = filedialog.askopenfilename(parent=self, title=f'Selecciona {executable}', filetypes=[('Java', executable)])
        if path:
            self.fields['java_path'].delete(0, 'end')
            self.fields['java_path'].insert(0, path)

    def save(self):
        try:
            data = replace(self.app.config.data, username=self.fields['username'].get().strip(),
                           memory_gb=int(self.fields['memory_gb'].get()), java_path=self.fields['java_path'].get().strip() or None)
            self.app.config.save(data)
            self.app.status.configure(text='Ajustes guardados.')
            self.app.home.refresh()
            self.app.detect_java()
        except (ValueError, OSError) as error:
            self.app.error(error)

    def refresh(self):
        for key, entry in self.fields.items():
            entry.delete(0, 'end')
            entry.insert(0, str(getattr(self.app.config.data, key) or ''))
