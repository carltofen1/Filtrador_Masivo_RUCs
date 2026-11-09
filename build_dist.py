"""
Constructor de la distribución (carpeta dist/).

Uso:
    python build_dist.py                  -> compila todo (server, launcher, bot)
    python build_dist.py launcher         -> solo el launcher (lo más común tras tocar scrapers)
    python build_dist.py server launcher  -> varios a la vez
    python build_dist.py --onefile        -> modo antiguo (un solo .exe, arranque lento)

Por defecto usa --onedir: el .exe arranca en ~1-2 s en vez de descomprimir
100 MB en cada inicio, y el antivirus lo marca menos. Todo queda "plano" en dist/:
    dist/launcher.exe  dist/_launcher_libs/
    dist/server.exe    dist/_server_libs/
    dist/bot.exe  .env  credentials.json  package.json
"""
import os
import sys
import shutil
import subprocess
import time

DIST = "dist"
OBJETIVOS = ("server", "launcher", "bot")

HIDDEN_IMPORTS_LAUNCHER = [
    # Módulos principales de procesamiento
    'procesar_sunat_paralelo',
    'procesar_drinky_paralelo',
    'procesar_segmentacion_api',
    # Scrapers
    'modules.sunat_scraper',
    'modules.drinky_scraper',
    'modules.sheets_manager',
    'modules.dni_scraper',
    # Config
    'config',
    # Dependencias de terceros que pueden no detectarse
    'gspread',
    'google.oauth2.service_account',
    'selenium',
    'selenium.webdriver',
    'selenium.webdriver.chrome.service',
    'selenium.webdriver.common.by',
    'selenium.webdriver.support.ui',
    'selenium.webdriver.support.expected_conditions',
    'undetected_chromedriver',
    'requests',
    'dotenv',
]

# Paquetes que ningún scraper importa pero PyInstaller arrastra si están instalados
# (pandas + numpy solos eran ~55 MB). Verificado importando todos los procesadores.
EXCLUDES = ['scipy', 'matplotlib', 'tkinter', 'IPython', 'notebook', 'pytest',
            'pandas', 'numpy', 'PIL', 'lxml', 'sqlite3', 'yaml', 'jinja2', 'markupsafe',
            'pytz', 'dateutil', 'bs4', 'pydoc_data']


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}")


def run_command(command, description, cwd=None):
    log(f"Ejecutando: {description}...")
    try:
        subprocess.check_call(command, shell=True, cwd=cwd)
        log(f"OK: {description}")
        return True
    except subprocess.CalledProcessError as e:
        log(f"ERROR: Falló {description}. Código: {e.returncode}")
        return False


def remove_readonly(func, path, excinfo):
    """Auxiliar para borrar archivos de solo lectura"""
    os.chmod(path, 0o777)
    func(path)


def force_remove(path):
    """Borra un archivo o carpeta con reintentos (Windows a veces los deja bloqueados)."""
    if not os.path.exists(path):
        return True
    for i in range(3):
        try:
            if os.path.isdir(path):
                shutil.rmtree(path, onerror=remove_readonly)
            else:
                os.remove(path)
            return True
        except Exception as e:
            log(f"Intento {i+1} fallido eliminando {path}: {e}")
            time.sleep(1)
    log(f"ADVERTENCIA: No se pudo eliminar {path}. ¿Está abierto el .exe? Ciérralo y reintenta.")
    return False


# ------------------------------------------------------------------ herramientas
def asegurar_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        return run_command(f'"{sys.executable}" -m pip install pyinstaller', "Instalar PyInstaller")


def asegurar_pkg():
    if shutil.which("pkg"):
        return True
    return run_command("npm install -g pkg", "Instalar pkg (Node)")


# ------------------------------------------------------------------ builds python
def build_python(nombre, script, extra_args, onefile):
    """Compila un script con PyInstaller y deja el resultado plano en dist/."""
    libs_dir = f"_{nombre}_libs"
    # Limpiar artefactos anteriores de ESTE objetivo (no toca el resto de dist/)
    for viejo in (os.path.join(DIST, f"{nombre}.exe"), os.path.join(DIST, libs_dir),
                  os.path.join(DIST, nombre)):
        if not force_remove(viejo):
            return False

    excludes = ' '.join(f'--exclude-module={m}' for m in EXCLUDES)
    if onefile:
        cmd = (f'"{sys.executable}" -m PyInstaller --noconfirm --clean --onefile --console '
               f'--distpath {DIST} --name {nombre} --paths="." {excludes} {extra_args} {script}')
        return run_command(cmd, f"Build {nombre} (onefile)")

    cmd = (f'"{sys.executable}" -m PyInstaller --noconfirm --clean --onedir --console '
           f'--contents-directory {libs_dir} '
           f'--distpath {DIST} --name {nombre} --paths="." {excludes} {extra_args} {script}')
    if not run_command(cmd, f"Build {nombre} (onedir)"):
        return False

    # PyInstaller crea dist/<nombre>/<nombre>.exe + dist/<nombre>/_<nombre>_libs/
    # Los subimos a dist/ para que .env, credentials.json y los otros .exe queden juntos.
    carpeta = os.path.join(DIST, nombre)
    for item in os.listdir(carpeta):
        shutil.move(os.path.join(carpeta, item), os.path.join(DIST, item))
    os.rmdir(carpeta)
    return True


def build_server(onefile):
    log("Compilando Servidor Python (bot WhatsApp)...")
    return build_python("server", "whatsapp-bot-node/python_server.py", "", onefile)


def build_launcher(onefile):
    log("Compilando Launcher con menú de scrapers...")
    hidden = ' '.join(f'--hidden-import={h}' for h in HIDDEN_IMPORTS_LAUNCHER)
    return build_python("launcher", "launcher.py", hidden, onefile)


def build_bot():
    log("Compilando Bot Node.js...")
    if not asegurar_pkg():
        return False
    force_remove(os.path.join(DIST, "bot.exe"))
    # --compress Brotli reduce bastante el .exe a cambio de ~1 s más al arrancar
    if run_command('npx pkg . -t node18-win-x64 --compress Brotli --output ../dist/bot.exe',
                   "Build Node Bot", cwd="whatsapp-bot-node"):
        return True

    log("Intentando método alternativo: Copia de fuentes (Portable)")
    dist_src = os.path.join(DIST, "bot-source")
    force_remove(dist_src)
    ignore = shutil.ignore_patterns("node_modules", ".git", "*.exe", "build",
                                    "__pycache__", ".wwebjs_*")
    shutil.copytree("whatsapp-bot-node", dist_src, ignore=ignore)
    log(f"Fuentes copiadas a {dist_src}.")
    return True


# ------------------------------------------------------------------ main
def copiar_archivos_externos():
    shutil.copy("whatsapp-bot-node/package.json", os.path.join(DIST, "package.json"))

    for archivo, aviso in ((".env", "Las credenciales/APIs no funcionarán."),
                           ("credentials.json", "Google Sheets no funcionará.")):
        if os.path.exists(archivo):
            shutil.copy(archivo, os.path.join(DIST, archivo))
            log(f"Archivo {archivo} copiado a dist/")
        else:
            log(f"⚠️ ADVERTENCIA: No se encontró {archivo}. {aviso}")


def limpiar_temporales():
    force_remove("build")
    for spec in ("server.spec", "launcher.spec"):
        force_remove(spec)


def main():
    args = [a.lower() for a in sys.argv[1:]]
    onefile = "--onefile" in args
    objetivos = [a for a in args if a in OBJETIVOS] or list(OBJETIVOS)
    desconocidos = [a for a in args if a not in OBJETIVOS and a != "--onefile"]
    if desconocidos:
        print(f"Argumentos no reconocidos: {desconocidos}")
        print(__doc__)
        return 1

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print("==================================================")
    print("   CONSTRUCTOR DE DISTRIBUCIÓN")
    print(f"   Objetivos: {', '.join(objetivos)}  |  Modo: {'onefile' if onefile else 'onedir'}")
    print("==================================================")
    inicio = time.time()
    os.makedirs(DIST, exist_ok=True)

    if ("server" in objetivos or "launcher" in objetivos) and not asegurar_pyinstaller():
        return 1

    pasos = {"server": lambda: build_server(onefile),
             "launcher": lambda: build_launcher(onefile),
             "bot": build_bot}
    fallidos = [obj for obj in objetivos if not pasos[obj]()]

    copiar_archivos_externos()
    limpiar_temporales()

    print("\n==================================================")
    print(f"   BUILD {'CON ERRORES' if fallidos else 'FINALIZADO'} en {(time.time()-inicio)/60:.1f} min")
    print("==================================================")
    if fallidos:
        print(f"Fallaron: {', '.join(fallidos)}")
    print("Contenido de dist/:")
    for f in sorted(os.listdir(DIST)):
        print(f" - {f}{'/' if os.path.isdir(os.path.join(DIST, f)) else ''}")
    return 1 if fallidos else 0


if __name__ == "__main__":
    sys.exit(main())
