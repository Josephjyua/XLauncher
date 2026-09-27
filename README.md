# XLauncher

MVP de launcher gráfico de Minecraft Java para Windows 10/11, escrito en Python y CustomTkinter. Instala Minecraft, Fabric y Forge mediante `minecraft-launcher-lib`, administra Java privado y mods locales.

## Ejecutar

Requisitos: Windows de 64 bits, Python 3.10 o posterior con Tkinter, conexión a Internet para descargar versiones. Java se puede configurar o instalar desde la aplicación; no hace falta tenerlo para abrirla.

En PowerShell, desde el directorio del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

En CMD la activación es `.venv\Scripts\activate.bat`. Para abrir sin consola usa `pythonw main.py` desde el entorno virtual.

## Uso

1. En **Ajustes**, guarda tu nombre local (3–16 letras, números o `_`) y RAM. Opcionalmente selecciona `java.exe`. La RAM deja espacio para Windows.
2. En **Instalaciones**, pulsa **Obtener versiones disponibles**, selecciona una versión y Vanilla, Fabric o Forge, y pulsa **Instalar versión**. Las operaciones se ejecutan en segundo plano; se permite una a la vez.
3. Para Fabric/Forge, instala el Java solicitado si falta y vuelve a pulsar instalar. La versión resultante aparecerá en **Jugar**. Los instaladores oficiales de loaders y sus procesadores pueden ejecutar Java mediante la librería.
4. En **Jugar**, selecciona una instalación y pulsa **JUGAR**. Se valida Java antes de iniciar. Si falta, puedes descargarlo con **Instalar Java para XLauncher**.
5. En **Mods**, importa archivos `.jar`, actívalos/desactívalos o elimínalos con confirmación. No se sobrescriben nombres existentes. Los mods deben corresponder a tu versión y loader; algunos requieren Fabric API u otras dependencias que debes importar también. Python no ejecuta los mods; Minecraft los cargará al jugar.

## Datos y Java

Todo se guarda en `%APPDATA%\.xlauncher`: `configuration.json`, `runtime`, `mods`, `disabled_mods`, `versions`, `libraries`, `assets`, `logs` y los directorios del juego. Se migran automáticamente `Nombre`, `RAM`, `Version`, `Java`. Una configuración inválida se conserva como `configuration.invalid-<id>.json` antes de crear valores iniciales.

Java se busca en este orden: ruta manual, runtimes privados validados, `JAVA_HOME`, `PATH` y carpetas habituales de Windows. Se ejecuta `java -version` con timeout para cada candidato. La selección exige la versión mayor indicada por los metadatos de Minecraft (incluida herencia de loaders), con reglas documentadas para versiones estables antiguas.

El runtime privado usa la API oficial HTTPS de Eclipse Adoptium, descarga Temurin JDK ZIP a un directorio temporal, verifica SHA-256 contra la API, rechaza rutas peligrosas y enlaces, y comprueba la versión ejecutable antes de publicarlo en `runtime`. No modifica PATH, JAVA_HOME ni instala globalmente. Si no hay paquete adecuado, informa del error; puedes configurar Java manualmente. Sin una instalación seleccionada, el botón ofrece Java 21.

Registro de la aplicación: `logs/xlauncher.log`, con rotación. Cada ejecución del juego tiene un archivo `logs/minecraft-*.log`. No se guardan credenciales ni se registra el comando de lanzamiento.

## Arquitectura

- `main.py`: entrypoint; `app.py`: composición de servicios y GUI.
- `config.py`, `paths.py`, `logging_config.py`: configuración validada/atómica, rutas y registro.
- `services/java_manager.py`: detección, compatibilidad, descarga y extracción segura.
- `services/minecraft_service.py`: catálogo, instalación y lanzamiento con `Popen`.
- `services/mod_manager.py`: importación y activación reversible de mods.
- `services/network.py`: HTTPS y timeouts de Requests, incluyendo llamadas de launcher-lib.
- `ui/main_window.py` y `ui/pages/`: navegación y tareas con cola; solo el hilo principal actualiza Tkinter.

## Comprobaciones

```powershell
python -m compileall -q main.py minecraft_launcher tests
python -m unittest discover -s tests -v
```

Los tests usan carpetas temporales y mocks; no descargan Minecraft ni Java. La prueba gráfica crea una ventana oculta y requiere una sesión de escritorio con Tk disponible.

## Limitaciones del MVP

- Solo perfil local sin credenciales. No hay autenticación Microsoft/Mojang, verificación de propiedad ni acceso a servidores que exigen sesión oficial. No es una implementación de autenticación oficial.
- Una carpeta de juego y mods compartida; no hay perfiles aislados ni resolución automática de dependencias de mods. Importa únicamente mods de confianza.
- El catálogo muestra versiones estables. Las instalaciones locales con metadatos compatibles pueden seleccionarse. No se adivina Java para generaciones desconocidas.
- Forge/Fabric dependen de la compatibilidad real y los instaladores de la librería. No se garantiza que todos los loaders antiguos funcionen con los instaladores actuales.
- No hay cancelación ni reanudación propia de descargas; espera para cerrar durante una operación. Los timeouts limitan las esperas de red por conexión/lectura, no la duración total de una instalación. Los procesadores de terceros pueden tardar.
- Las instalaciones interrumpidas por XLauncher se marcan incompletas; vuelve a instalarlas para repararlas. No se certifica la integridad de instalaciones legacy hasta ejecutar la reparación.
- No hay empaquetado `.exe`, actualizador, descarga de mods ni pruebas reales de juego automatizadas. Las pruebas no instalan Minecraft/Java ni validan un lanzamiento real.
