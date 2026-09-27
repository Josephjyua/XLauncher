import customtkinter as ctk


class InstallationsPage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        ctk.CTkLabel(self, text='Instalaciones', font=ctk.CTkFont(size=26)).pack(pady=24)
        ctk.CTkLabel(self, text='Obtén el catálogo y elige una versión estable.\nFabric y Forge usarán el loader disponible en la librería.').pack(pady=12)
        app.action(self, 'Obtener versiones disponibles', app.fetch_versions).pack(pady=12)
        self.version = ctk.CTkComboBox(self, width=360, state='readonly', values=['Obtén el catálogo primero'])
        self.version.set('Obtén el catálogo primero')
        self.version.pack(pady=12)
        self.loader = ctk.CTkOptionMenu(self, values=['Vanilla', 'Fabric', 'Forge'])
        self.loader.pack(pady=12)
        app.action(self, 'Instalar versión', app.install_minecraft).pack(pady=12)
        ctk.CTkLabel(self, text='Las descargas pueden tardar varios minutos.\nSi falta Java para un loader, instala el runtime y repite la instalación.', wraplength=580).pack(pady=12)

    def refresh(self):
        pass
