import customtkinter as ctk


class HomePage(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        ctk.CTkLabel(self, text='Minecraft', font=ctk.CTkFont(size=30, weight='bold')).pack(pady=24)
        ctk.CTkLabel(self, text='Perfil local sin credenciales · Sin autenticación Microsoft/Mojang').pack(pady=6)
        self.info = ctk.CTkLabel(self, text='')
        self.info.pack(pady=12)
        self.version = ctk.CTkComboBox(self, width=360, state='readonly', command=app.select_version)
        self.version.pack(pady=12)
        self.java = ctk.CTkLabel(self, text='Java: pendiente de detección', wraplength=620)
        self.java.pack(pady=12)
        app.action(self, 'JUGAR', app.play).pack(pady=10)
        app.action(self, 'Detectar Java compatible', app.detect_java).pack(pady=5)
        app.action(self, 'Instalar Java para XLauncher', app.install_java).pack(pady=5)
        ctk.CTkButton(self, text='Ir a Instalaciones', command=lambda: app.show('Instalaciones')).pack(pady=10)

    def refresh(self):
        config = self.app.config.data
        versions = self.app.minecraft.installed()
        self.version.configure(values=versions or ['Sin versiones instaladas'])
        self.version.set(config.selected_version if config.selected_version in versions else (versions[0] if versions else 'Sin versiones instaladas'))
        loader = 'Fabric' if 'fabric' in self.version.get().lower() else 'Forge' if 'forge' in self.version.get().lower() else 'Vanilla'
        self.info.configure(text=f'Jugador: {config.username}  ·  RAM: {config.memory_gb} GB  ·  {loader}')
