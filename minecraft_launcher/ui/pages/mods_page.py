from tkinter import filedialog, messagebox
import customtkinter as ctk


class ModsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        ctk.CTkLabel(self, text='Mods', font=ctk.CTkFont(size=26)).pack(pady=20)
        ctk.CTkLabel(self, text='Carpeta compartida entre versiones. Usa mods compatibles con tu loader.\nCierra Minecraft antes de modificar los mods.').pack(pady=8)
        app.action(self, 'Importar .jar', self.import_mod).pack(pady=5)
        app.action(self, 'Abrir carpeta de mods', self.open_folder).pack(pady=5)
        self.rows = ctk.CTkScrollableFrame(self)
        self.rows.pack(fill='both', expand=True, padx=14, pady=14)

    def check_running(self):
        process = self.app.minecraft.process
        if process and process.poll() is None:
            raise ValueError('Cierra Minecraft antes de modificar los mods.')

    def open_folder(self):
        try:
            self.app.mods.open_folder()
        except OSError as error:
            self.app.error(error)

    def import_mod(self):
        path = filedialog.askopenfilename(parent=self, title='Importar mod', filetypes=[('Mod Java', '*.jar')])
        if path:
            try:
                self.check_running()
                self.app.run_task('Importando mod…', lambda: self.app.mods.import_mod(path), lambda _: self.refresh())
            except ValueError as error:
                self.app.error(error)

    def change(self, name, enabled, delete=False):
        if self.app.busy:
            return
        try:
            self.check_running()
            if delete:
                if not messagebox.askyesno('Eliminar mod', f'¿Eliminar permanentemente {name}?', parent=self):
                    return
                self.app.mods.delete(name, enabled)
            else:
                self.app.mods.toggle(name, enabled)
            self.refresh()
        except (OSError, ValueError) as error:
            self.app.error(error)

    def refresh(self):
        for child in self.rows.winfo_children():
            child.destroy()
        for name, enabled in self.app.mods.list_mods():
            row = ctk.CTkFrame(self.rows)
            row.pack(fill='x', pady=4)
            ctk.CTkLabel(row, text=name, wraplength=300).pack(side='left', padx=8)
            ctk.CTkButton(row, width=80, text='Eliminar', command=lambda n=name, e=enabled: self.change(n, e, True)).pack(side='right', padx=4, pady=8)
            ctk.CTkButton(row, width=90, text='Desactivar' if enabled else 'Activar', command=lambda n=name, e=enabled: self.change(n, e)).pack(side='right', padx=4)
