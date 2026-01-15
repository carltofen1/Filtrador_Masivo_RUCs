import os
import subprocess
import shutil
import time

def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

def run_command(command, description):
    log(f"Ejecutando: {description}...")
    try:
        subprocess.check_call(command, shell=True)
        log(f"OK: {description}")
    except subprocess.CalledProcessError as e:
        log(f"ERROR: Falló {description}. Código: {e.returncode}")
        return False
    return True

def remove_readonly(func, path, excinfo):
    """Auxiliar para borrar archivos de solo lectura"""
    os.chmod(path, 0o777)
    func(path)

def force_remove_dir(path):
    """Borra un directorio forzosamente con reintentos"""
    if not os.path.exists(path): return
    
    log(f"Eliminando carpeta antigua: {path}...")
    for i in range(3):
        try:
            shutil.rmtree(path, onerror=remove_readonly)
            break
        except Exception as e:
            log(f"Intento {i+1} fallido eliminando {path}: {e}")
            time.sleep(1)

    if os.path.exists(path):
        log(f"ADVERTENCIA: No se pudo eliminar completamente {path}. El build podría fallar.")

def main():
    os.system('cls')
    print("==================================================")
    print("   CONSTRUCTOR DE DISTRIBUCIÓN (BUILD ROOT)")
    print("==================================================")
    
    # Estamos en la raíz: Filtrador_Masivo_RUCs
    
    # 0. Preparar carpetas
    force_remove_dir("dist")
    os.makedirs("dist", exist_ok=True)

    # 1. Instalar dependencias de build si faltan
    log("Verificando herramientas de build...")
    run_command("npm install -g pkg", "Instalar pkg (Node)")
    run_command("pip install pyinstaller", "Instalar PyInstaller (Python)")

    # 2. Compilar Python Server
    log("Compilando Servidor Python...")
    # El script está en whatsapp-bot-node/python_server.py
    # Los modulos están en ./modules (la raíz actual)
    # --paths="." incluye la raíz en el path de búsqueda de Python
    cmd_server = 'pyinstaller --onefile --distpath dist --name server --paths="." whatsapp-bot-node/python_server.py'
    if not run_command(cmd_server, "Build Server Python"):
        print("Error crítico construyendo server.")
        return

    # 3. Compilar Launcher (el de la RAIZ que tiene el menú completo)
    log("Compilando Launcher con menú de scrapers...")
    # Usamos launcher.py de la raíz (no el de whatsapp-bot-node)
    # --paths="." para que encuentre los módulos
    # --clean para forzar rebuild limpio
    # --hidden-import para los imports dinámicos que PyInstaller no detecta
    hidden_imports = [
        # Módulos principales de procesamiento
        'procesar_sunat_paralelo',
        'procesar_entel_paralelo', 
        'procesar_segmentacion_paralelo',
        'procesar_osiptel_paralelo',
        # Scrapers
        'modules.sunat_scraper',
        'modules.entel_scraper',
        'modules.segmentacion_scraper',
        'modules.osiptel_scraper',
        'modules.sheets_manager',
        'modules.dni_scraper',
        # Config
        'config',
        # Dependencias de terceros que pueden no detectarse
        'gspread',
        'oauth2client',
        'oauth2client.service_account',
        'selenium',
        'selenium.webdriver',
        'selenium.webdriver.chrome.service',
        'selenium.webdriver.common.by',
        'selenium.webdriver.support.ui',
        'selenium.webdriver.support.expected_conditions',
        'requests',
        'dotenv',
    ]
    hidden_str = ' '.join([f'--hidden-import={h}' for h in hidden_imports])
    cmd_launcher = f'pyinstaller --onefile --clean --distpath dist --name launcher --paths="." {hidden_str} launcher.py'
    if not run_command(cmd_launcher, "Build Launcher"):
        print("Error crítico construyendo launcher.")
        return

    # 4. Compilar Node.js Bot
    log("Compilando Bot Node.js...")
    # Entramos a whatsapp-bot-node, ejecutamos pkg, y mandamos el output a ../dist/bot.exe
    # Usamos && para encadenar comandos en Windows
    cmd_node = 'cd whatsapp-bot-node && npx pkg . -t node18-win-x64 --output ../dist/bot.exe'
    
    if not run_command(cmd_node, "Build Node Bot"):
        print("Error crítico construyendo bot node.")
        # Fallback manual
        log("Intentando método alternativo: Copia de fuentes (Portable)")
        dist_src = os.path.join("dist", "bot-source")
        # Copiamos la carpeta del bot ignorando cosas pesadas
        ignore_patterns = shutil.ignore_patterns("node_modules", ".git", "*.exe", "build", "__pycache__", ".wwebjs_*")
        shutil.copytree("whatsapp-bot-node", dist_src, ignore=ignore_patterns)
        log(f"Fuentes copiadas a {dist_src}.")

    # 5. Copiar dependencias externas
    # Copiamos package.json al lado del ejecutable por si acaso
    shutil.copy("whatsapp-bot-node/package.json", os.path.join("dist", "package.json"))
    
    # Copiar archivo .env (contiene claves de API para DNI)
    if os.path.exists(".env"):
        shutil.copy(".env", os.path.join("dist", ".env"))
        log("Archivo .env copiado a dist/")
    else:
        log("⚠️ ADVERTENCIA: No se encontró archivo .env. Las APIs de DNI no funcionarán.")
    
    # Copiar credentials.json (para Google Sheets)
    if os.path.exists("credentials.json"):
        shutil.copy("credentials.json", os.path.join("dist", "credentials.json"))
        log("Archivo credentials.json copiado a dist/")
    else:
        log("⚠️ ADVERTENCIA: No se encontró credentials.json. Google Sheets no funcionará.")
    
    # Limpieza de PyInstaller (archivos generados en la raíz)
    if os.path.exists("build"): shutil.rmtree("build")
    if os.path.exists("server.spec"): os.remove("server.spec")
    if os.path.exists("launcher.spec"): os.remove("launcher.spec")

    print("\n")
    print("==================================================")
    print("   BUILD FINALIZADO")
    print("==================================================")
    print("Archivos en la carpeta 'dist/':")
    for f in os.listdir("dist"):
        print(f" - {f}")
    print("\n")

if __name__ == "__main__":
    main()
