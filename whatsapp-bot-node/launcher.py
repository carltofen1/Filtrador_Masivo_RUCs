import os
import sys
import subprocess
import time
import shutil

def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}")

def kill_process(process_name):
    """Mata un proceso por nombre usando taskkill en Windows"""
    try:
        subprocess.run(f"taskkill /F /IM {process_name}", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        # log(f"Procesos {process_name} terminados.")
    except Exception as e:
        log(f"Error matando {process_name}: {e}")

def clean_session():
    """Elimina carpetas de sesión y caché"""
    folders = [".wwebjs_auth", ".wwebjs_cache"]
    for folder in folders:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                log(f"Eliminado: {folder}")
            except Exception as e:
                log(f"No se pudo eliminar {folder}: {e}")

def main():
    os.system('cls')
    print("==================================================")
    print("   LAUNCHER DE BOT WHATSAPP + PYTHON SERVER")
    print("==================================================")
    print("")

    # 1. Matar procesos zombies
    log("Limpiando procesos anteriores...")
    # kill_process("chrome.exe") # Deshabilitado para no cerrar el navegador del usuario
    kill_process("node.exe")
    kill_process("server.exe")
    kill_process("bot.exe")

    # 2. NO limpiar sesión - mantener el login de WhatsApp
    # clean_session()  # DESHABILITADO: mantener sesión entre reinicios

    # 3. Iniciar Servidor Python
    log("Iniciando Servidor Python (Backend)...")

    # Detectar si estamos corriendo compilados (frozen) o como script
    if getattr(sys, 'frozen', False):
        # MODO EMPAQUETADO (EXE)
        server_exe = "server.exe"
        node_exe = "bot.exe"

        # Configuración para ocultar ventana
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # Abrir archivo de log para el server (así no perdemos errores)
        try:
             logfile = open("server.log", "w")
             # Ejecutar server.exe OCULTO y redirigir output a log
             subprocess.Popen([server_exe], startupinfo=startupinfo, stdout=logfile, stderr=logfile)
        except Exception as e:
             log(f"Error iniciando server: {e}")
        
        time.sleep(2)
        
        log("Iniciando BOT...")
        print("\n   >>> ESCANEA EL CÓDIGO QR A CONTINUACIÓN <<<\n")
        
        if os.path.exists(node_exe):
            log("Modo: Ejecutable Nativo (bot.exe)")
            try:
                subprocess.run(node_exe, shell=True)
            except KeyboardInterrupt:
                log("Deteniendo launcher...")
        elif os.path.exists("bot-source/index.js"):
            log("Modo: Código Fuente (Portable). Requiere Node.js instalado.")
            try:
                subprocess.run("node bot-source/index.js", shell=True)
            except KeyboardInterrupt:
                log("Deteniendo launcher...")
        else:
            log("ERROR: No se encuentra bot.exe ni bot-source/index.js")
            time.sleep(5)
            
    else:
        # MODO SCRIPT (Desarrollo)
        python_cmd = "python python_server.py"
        # En modo desarrollo, también ocultamos pero logueamos
        try:
             logfile = open("server.log", "w")
             subprocess.Popen(python_cmd, shell=True, stdout=logfile, stderr=logfile)
        except Exception as e:
             log(f"Error iniciando server script: {e}")

        time.sleep(2)

        log("Iniciando BOT de Node.js...")
        print("\n   >>> ESCANEA EL CÓDIGO QR A CONTINUACIÓN <<<\n")
        try:
            subprocess.run("node index.js", shell=True)
        except KeyboardInterrupt:
            log("Deteniendo launcher...")
    print("\n   >>> ESCANEA EL CÓDIGO QR A CONTINUACIÓN <<<\n")
    
    try:
        # Ejecutamos node directamente en esta ventana para ver el QR
        subprocess.run("node index.js", shell=True)
    except KeyboardInterrupt:
        log("Deteniendo launcher...")

if __name__ == "__main__":
    main()
