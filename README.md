# XLauncher

Launcher gráfico de Minecraft Java para Windows 10/11, Linux x86_64 y macOS (Intel y Apple Silicon), escrito en Python y CustomTkinter. Instala Minecraft, Fabric y Forge mediante `minecraft-launcher-lib`, administra Java privado y mods locales.

## Ejecutar

Desde source: Python 3.10 o posterior con Tkinter y una sesión gráfica. Los builds CI usan Python 3.12. Los paquetes standalone no necesitan Python instalado. Se requiere Internet para descargar versiones; Java se puede configurar o instalar desde la aplicación y no es necesario para abrirla.

En PowerShell, desde el directorio del proyecto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

En CMD la activación es `.venv\Scripts\activate.bat`. Para abrir sin consola usa `pythonw main.py` desde el entorno virtual.

En Linux/macOS activa el entorno con `source .venv/bin/activate`. En Debian/Ubuntu, para ejecutar o construir desde source, instala `python3-venv python3-tk`; para abrir la carpeta de mods se utiliza `xdg-open` (paquete `xdg-utils`). macOS utiliza `open`.

## Uso

1. En **Ajustes**, guarda tu nombre local (3–16 letras, números o `_`) y RAM. Opcionalmente selecciona `java.exe` (Windows) o `java` (Linux/macOS). La RAM se limita según la memoria detectada en Windows; en otros sistemas se conserva el límite conservador de 8 GB.
2. En **Instalaciones**, pulsa **Obtener versiones disponibles**, selecciona una versión y Vanilla, Fabric o Forge, y pulsa **Instalar versión**. Las operaciones se ejecutan en segundo plano; se permite una a la vez.
3. Para Fabric/Forge, instala el Java solicitado si falta y vuelve a pulsar instalar. La versión resultante aparecerá en **Jugar**. Los instaladores oficiales de loaders y sus procesadores pueden ejecutar Java mediante la librería.
4. En **Jugar**, selecciona una instalación y pulsa **JUGAR**. Se valida Java antes de iniciar. Si falta, puedes descargarlo con **Instalar Java para XLauncher**.
5. En **Mods**, importa archivos `.jar`, actívalos/desactívalos o elimínalos con confirmación. No se sobrescriben nombres existentes. Los mods deben corresponder a tu versión y loader; algunos requieren Fabric API u otras dependencias que debes importar también. Python no ejecuta los mods; Minecraft los cargará al jugar.

## Datos y Java

Los datos modificables se guardan fuera del ejecutable y del `.app`:

| Sistema | Directorio |
| --- | --- |
| Windows nuevo | `%APPDATA%\XLauncher` |
| Windows con datos legacy | `%APPDATA%\.xlauncher` (se conserva en uso) |
| Linux | `~/.local/share/XLauncher` o `$XDG_DATA_HOME/XLauncher` si XDG_DATA_HOME es absoluto |
| macOS | `~/Library/Application Support/XLauncher` |

Si `.xlauncher` ya existe en Windows, tiene prioridad incluso si también existe `XLauncher`. No se copian, renombran ni mezclan instalaciones automáticamente: esto evita duplicar gigabytes y romper rutas de Java guardadas. Se puede seguir usando el directorio legacy indefinidamente. Toda esta decisión está centralizada en `paths.py`.

Dentro están `configuration.json`, `runtime`, `mods`, `disabled_mods`, `versions`, `libraries`, `assets`, `logs` y los directorios del juego. Se migran automáticamente `Nombre`, `RAM`, `Version`, `Java`. Una configuración inválida se conserva como `configuration.invalid-<id>.json` antes de crear valores iniciales.

Java se busca en este orden: ruta manual, runtimes privados validados, `JAVA_HOME`, `PATH` y carpetas habituales de cada plataforma (proveedores Windows, `/usr/lib/jvm` en Linux y JavaVirtualMachines/Homebrew en macOS). Se ejecuta `java -version` con timeout para cada candidato. La selección exige la versión mayor indicada por los metadatos de Minecraft (incluida herencia de loaders), con reglas documentadas para versiones estables antiguas.

El runtime privado usa la API oficial HTTPS de Eclipse Adoptium y solicita Temurin JDK para el sistema y arquitectura detectados: Windows x64/ARM64, Linux x64, macOS x64/ARM64. No se construyen URLs de binarios: se usa el enlace devuelto por la API. Descarga ZIP (Windows) o TAR.GZ (Linux/macOS) a un directorio temporal, verifica SHA-256, rechaza traversal y entradas especiales, y comprueba `java -version` antes de publicar el runtime. Los TAR conservan permisos ejecutables sin setuid; solo admiten enlaces internos verificados a archivos/directorios normales y no enlaces como ancestros de extracción. ZIP sigue rechazando enlaces.

Java permanece separado del Python empaquetado: no se incluye en los builds. No modifica PATH/JAVA_HOME globalmente ni instala Java en el sistema. Si no hay paquete para esa combinación de versión/sistema/arquitectura, informa del error; puedes configurar Java manualmente. Sin una instalación seleccionada, el botón ofrece Java 21. Bajo Rosetta se usa la arquitectura del proceso; utiliza el build nativo apropiado.

Registro de la aplicación: `logs/xlauncher.log`, con rotación. Cada ejecución del juego tiene un archivo `logs/minecraft-*.log`. No se guardan credenciales ni se registra el comando de lanzamiento.

## Arquitectura

- `main.py`: entrypoint; `app.py`: composición de servicios y GUI.
- `config.py`, `paths.py`, `logging_config.py`: configuración validada/atómica, rutas y registro.
- `platform_support.py`: nombres de ejecutables, selección de paquetes Java y aislamiento del entorno PyInstaller para procesos externos (incluyendo instaladores de loaders).
- `services/java_manager.py`: detección, compatibilidad, descarga y extracción segura.
- `services/minecraft_service.py`: catálogo, instalación y lanzamiento con `Popen`.
- `services/mod_manager.py`: importación y activación reversible de mods.
- `services/network.py`: HTTPS y timeouts de Requests, incluyendo llamadas de launcher-lib.
- `ui/main_window.py` y `ui/pages/`: navegación y tareas con cola; solo el hilo principal actualiza Tkinter.

## Comprobaciones

```powershell
python -m compileall -q main.py minecraft_launcher tests
python -m unittest discover -s tests -v
# Con requirements-dev.txt instalado:
python -m pytest
```

Los tests usan carpetas temporales y mocks; no descargan Minecraft ni Java. La prueba gráfica crea una ventana oculta y requiere una sesión de escritorio con Tk disponible.

## Building XLauncher

PyInstaller genera aplicaciones para **el sistema y la arquitectura donde se ejecuta**. No hay cross-compilation desde Windows. El spec versionado `XLauncher.spec` usa `main.py`, incluye los temas/fuentes de CustomTkinter, metadatos y módulos de minecraft-launcher-lib, Tcl/Tk y recursos de `assets/`.

Prepara un entorno limpio en cada sistema, actívalo como se indicó arriba y ejecuta:

```text
python -m pip install -r requirements-dev.txt -c constraints-build.txt
python -m pytest
python -m PyInstaller XLauncher.spec
```

El comando de construcción es el mismo en Windows, Linux y macOS. `requirements.txt` mantiene solo dependencias runtime; `requirements-dev.txt` añade PyInstaller y pytest. `constraints-build.txt` fija las versiones utilizadas en CI para evitar cambios involuntarios. Esto hace repetible el conjunto de dependencias, sin prometer binarios idénticos byte a byte entre distintas imágenes de runners.

Se usa **onedir**, priorizando estabilidad e inicio rápido sin extraer todas las dependencias a un temporal en cada arranque. Distribuye la carpeta completa, nunca solo el `.exe` o binario interno.

| Sistema | Resultado |
| --- | --- |
| Windows | `dist/XLauncher/XLauncher.exe` junto con `_internal/` (sin consola) |
| Linux | `dist/XLauncher/XLauncher` junto con `_internal/` |
| macOS | `dist/XLauncher.app` (también se genera la carpeta intermedia `dist/XLauncher/`) |

`build/` contiene archivos intermedios, diagnóstico de imports y `warn-XLauncher.txt`. `dist/` contiene los distribuibles. Ambos directorios se ignoran en Git; **XLauncher.spec sí se versiona**. Para repetir un build sin preguntas: `python -m PyInstaller --noconfirm --clean XLauncher.spec`.

Iconos opcionales: `assets/icons/xlauncher.ico`, `assets/icons/xlauncher.png`, `assets/icons/xlauncher.icns`. No hay un diseño inventado ni un icono definitivo incluido; el build funciona sin ellos. La versión está en `minecraft_launcher/__init__.py`, disponible para UI, logs, opciones de Minecraft y metadatos del build. `resource_path()` usa la raíz de source o `sys._MEIPASS` para recursos de solo lectura; nunca se guardan logs/configuración allí.

Para comprobar un build sin tocar tus instalaciones ni descargar Minecraft/Java:

```text
# Windows
python scripts/check_bundle.py dist/XLauncher/XLauncher.exe
# Linux (en CI/headless, anteponer xvfb-run -a)
python scripts/check_bundle.py dist/XLauncher/XLauncher
# macOS
python scripts/check_bundle.py dist/XLauncher.app/Contents/MacOS/XLauncher
```

La comprobación arranca la GUI oculta, recorre sus páginas, valida recursos y escritura de configuración/logs en un temporal, y termina. No detecta ni ejecuta Java. El ejecutable también entiende `--smoke-test --smoke-report <archivo.json>`.

### GitHub Actions

Sube estos archivos al repositorio y ve a **Actions → Build XLauncher → Run workflow**. También se ejecuta al subir tags `v*`. Cada job instala dependencias, compila, ejecuta `python -m pytest` (Xvfb en Linux), construye con PyInstaller y comprueba el ejecutable. Si un paso falla, no se sube el artifact de ese job. No se publican GitHub Releases.

Los artifacts se descargan en la sección **Artifacts** de la ejecución, con retención de 14 días:

- `XLauncher-Windows-x86_64` — `windows-latest`, ZIP de la carpeta completa.
- `XLauncher-Linux-x86_64` — `ubuntu-latest`, TAR.GZ para conservar permisos.
- `XLauncher-macOS-arm64` — `macos-latest`, ZIP del `.app` creado con `ditto`.
- `XLauncher-macOS-x86_64` — `macos-15-intel`, build Intel nativo, ZIP del `.app`.

Las etiquetas `latest` pueden cambiar de imagen con el tiempo; el build ARM usa Python arm64 explícito y el Intel su runner separado. Linux necesita un escritorio X11/XWayland y bibliotecas gráficas del sistema; PyInstaller no empaqueta el kernel, glibc ni drivers de GPU. Un build generado en Ubuntu reciente puede no funcionar en distribuciones con glibc más antigua; construye en una base más antigua si necesitas ampliar compatibilidad.

Los paquetes no tienen firma de editor ni notarización. Windows/macOS pueden mostrar advertencias del sistema; no se desactivan esas protecciones. No hay MSI/DMG/DEB ni instaladores. La compatibilidad real de Minecraft/mods antiguos en macOS ARM sigue dependiendo del juego, sus bibliotecas nativas y el loader.

## Limitaciones del MVP

- Solo perfil local sin credenciales. No hay autenticación Microsoft/Mojang, verificación de propiedad ni acceso a servidores que exigen sesión oficial. No es una implementación de autenticación oficial.
- Una carpeta de juego y mods compartida; no hay perfiles aislados ni resolución automática de dependencias de mods. Importa únicamente mods de confianza.
- El catálogo muestra versiones estables. Las instalaciones locales con metadatos compatibles pueden seleccionarse. No se adivina Java para generaciones desconocidas.
- Forge/Fabric dependen de la compatibilidad real y los instaladores de la librería. No se garantiza que todos los loaders antiguos funcionen con los instaladores actuales.
- No hay cancelación ni reanudación propia de descargas; espera para cerrar durante una operación. Los timeouts limitan las esperas de red por conexión/lectura, no la duración total de una instalación. Los procesadores de terceros pueden tardar.
- Las instalaciones interrumpidas por XLauncher se marcan incompletas; vuelve a instalarlas para repararlas. No se certifica la integridad de instalaciones legacy hasta ejecutar la reparación.
- No hay actualizador, descarga de mods ni pruebas reales de juego automatizadas. Las pruebas no instalan Minecraft/Java ni validan una partida real.
