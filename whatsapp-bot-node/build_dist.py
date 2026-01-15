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
    print("      CONSTRUCTOR DE DISTRIBUCIÓN (BUILD)")
    print("==================================================")
    
    # 0. Preparar carpetas
    force_remove_dir("dist")
    os.makedirs("dist", exist_ok=True)

    # 1. Instalar dependencias de build si faltan
    log("Verificando herramientas de build...")
    run_command("npm install -g pkg", "Instalar pkg (Node)")
    run_command("pip install pyinstaller", "Instalar PyInstaller (Python)")

    # 2. Compilar Python Server
    log("Compilando Servidor Python...")
    # --onefile para un solo exe, --distpath para ponerlo en dist
    # --paths=.. agrega el directorio padre para encontrar 'modules' (los scrapers)
    if not run_command('pyinstaller --onefile --distpath dist --name server --paths=".." python_server.py', "Build Server Python"):
        print("Error crítico construyendo server.")
        return

    # 3. Compilar Launcher
    log("Compilando Launcher...")
    if not run_command("pyinstaller --onefile --distpath dist --name launcher launcher.py", "Build Launcher"):
        print("Error crítico construyendo launcher.")
        return

    # 4. Compilar Node.js Bot
    log("Compilando Bot Node.js...")
    # --output dist/bot.exe fuerza el nombre de salida directamente
    if not run_command("npx pkg . -t node18-win-x64 --output dist/bot.exe", "Build Node Bot"):
        print("Error crítico construyendo bot node.")
        # Fallback
        log("Intentando método alternativo: Copia de fuentes (Portable)")
        dist_src = os.path.join("dist", "bot-source")
        shutil.copytree(".", dist_src, ignore=shutil.ignore_patterns("dist", "node_modules", ".git", "*.exe", "build", "__pycache__"))
        log(f"Fuentes copiadas a {dist_src}. Deberás correr 'npm install' y 'node index.js' en destino si el exe falla.")

    # 5. Copiar dependencias externas necesarias (Puppeteer Chromium si no está embebido)
    # pkg no incluye el navegador chromium por defecto. El usuario en el otro PC debe tener Chrome instalado o
    # debemos copiar una versión local de chromium.
    # Por simplicidad, asumiremos que puppeteer-core usará el Chrome instalado o descargará uno.
    # Pero para asegurar, copiamos package.json por si acaso se requiere reinstalar.
    
    shutil.copy("package.json", os.path.join("dist", "package.json"))
    
    # Copiar archivo .env si existe (contiene claves de API)
    if os.path.exists(".env"):
        shutil.copy(".env", os.path.join("dist", ".env"))
        log("Archivo .env copiado a dist/")
    elif os.path.exists(os.path.join("..", ".env")):
        shutil.copy(os.path.join("..", ".env"), os.path.join("dist", ".env"))
        log("Archivo .env copiado desde directorio padre a dist/")
    else:
        log("ADVERTENCIA: No se encontró archivo .env. Las APIs de DNI no funcionarán.")
        log("  Crea un archivo .env basándote en .env.example")
    
    # Limpieza de PyInstaller
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
    print("NOTA: Para el bot de Node compilado (index.exe), asegúrate")
    print("de que Puppeteer pueda encontrar Chrome/Chromium en la PC destino.")
    print("Si falla, copia la carpeta 'node_modules' original también.")

if __name__ == "__main__":
    main()
