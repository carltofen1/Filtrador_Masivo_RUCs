"""
Launcher principal para el Filtrador Masivo de RUCs
"""
import os
import sys
import subprocess
import traceback
import shutil
import urllib.request

def verificar_nodejs():
    """Verifica si Node.js está instalado en el sistema, si no lo instala automáticamente"""
    
    # Ruta donde se instala Node.js por defecto
    node_global_path = r"C:\Program Files\nodejs"
    node_exe = os.path.join(node_global_path, "node.exe")
    
    # 1. Verificar si Node.js ya está instalado globalmente
    if os.path.exists(node_exe):
        try:
            result = subprocess.run([node_exe, '--version'], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✅ Node.js encontrado: {version}")
                # Asegurar que está en el PATH
                if node_global_path not in os.environ['PATH']:
                    os.environ['PATH'] = node_global_path + os.pathsep + os.environ['PATH']
                return True
        except:
            pass
    
    # 2. Buscar en el PATH del sistema
    node_path = shutil.which('node')
    if node_path:
        try:
            result = subprocess.run(['node', '--version'], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"✅ Node.js encontrado: {version}")
                return True
        except:
            pass
    
    # 3. Buscar en otras ubicaciones comunes
    common_paths = [
        r"C:\Program Files (x86)\nodejs\node.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\nodejs\node.exe"),
    ]
    
    for path in common_paths:
        if os.path.exists(path):
            try:
                result = subprocess.run([path, '--version'], capture_output=True, text=True)
                if result.returncode == 0:
                    version = result.stdout.strip()
                    print(f"✅ Node.js encontrado en: {path} ({version})")
                    node_dir = os.path.dirname(path)
                    if node_dir not in os.environ['PATH']:
                        os.environ['PATH'] = node_dir + os.pathsep + os.environ['PATH']
                    return True
            except:
                continue
    
    # 4. No se encontró - ofrecer instalarlo
    print("\n⚠️  Node.js no está instalado en el sistema.")
    respuesta = input("¿Deseas instalarlo automáticamente? (S/N): ").strip().upper()
    
    if respuesta != 'S':
        print("❌ Node.js es necesario para el bot de WhatsApp.")
        print("Instálalo manualmente desde: https://nodejs.org")
        return False
    
    try:
        # Descargar instalador de Node.js LTS
        url = "https://nodejs.org/dist/v20.10.0/node-v20.10.0-x64.msi"
        installer = os.path.join(os.environ['TEMP'], 'node_installer.msi')
        
        print("Descargando Node.js (25 MB)...")
        urllib.request.urlretrieve(url, installer)
        
        print("Instalando Node.js globalmente (puede tomar 1 minuto)...")
        # Instalar con permisos de admin si es necesario
        subprocess.run(['msiexec', '/i', installer, '/qn', '/norestart'], shell=True, check=True)
        
        os.remove(installer)
        
        # IMPORTANTE: Agregar Node al PATH del proceso actual
        if os.path.exists(node_global_path):
            os.environ['PATH'] = node_global_path + os.pathsep + os.environ['PATH']
            print("✅ Node.js instalado correctamente!")
            print(f"   Ubicación: {node_global_path}")
            return True
        else:
            print("⚠️  La instalación parece haber fallado.")
            print("   Intenta reiniciar el programa o instalar Node.js manualmente.")
            return False
        
    except Exception as e:
        print(f"❌ Error instalando Node.js: {e}")
        print("Instálalo manualmente desde: https://nodejs.org")
        return False

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def mostrar_menu():
    clear_screen()
    print("=" * 50)
    print("   FILTRADOR MASIVO DE RUCs - MENU PRINCIPAL")
    print("=" * 50)
    print()
    print("  [1] Ejecutar SUNAT (Datos de empresas)")
    print("  [2] Ejecutar DRINKY (Teléfonos Entel)")
    print("  [3] Ejecutar SEGMENTACION (Tipo de cliente)")
    print("  [4] Ejecutar OSIPTEL (Cantidad de lineas)")

    print("  [5] Bot WhatsApp")
    print("  [6] Salir")
    print()
    print("=" * 50)
    print()

def ejecutar_sunat():
    print("\nIniciando procesador SUNAT...")
    print("-" * 40)
    try:
        from procesar_sunat_paralelo import main as sunat_main
        sunat_main()
    except Exception as e:
        print(f"\n*** ERROR EN SUNAT ***")
        print(f"Error: {str(e)}")
        print("\nDetalles del error:")
        traceback.print_exc()

def ejecutar_entel():
    print("\nIniciando Extracción de Teléfonos (Drinky)...")
    print("-" * 40)
    try:
        from procesar_drinky_paralelo import main as drinky_main
        drinky_main()
    except Exception as e:
        print(f"\n*** ERROR EN DRINKY ***")
        print(f"Error: {str(e)}")
        print("\nDetalles del error:")
        traceback.print_exc()
        input("Presione Enter para continuar...")

def ejecutar_segmentacion():
    print("\nIniciando procesador de SEGMENTACION (100% API)...")
    print("-" * 40)
    try:
        from procesar_segmentacion_api import main as segmentacion_main
        segmentacion_main()
    except Exception as e:
        print(f"\n*** ERROR EN SEGMENTACION ***")
        print(f"Error: {str(e)}")
        print("\nDetalles del error:")
        traceback.print_exc()

def ejecutar_osiptel():
    print("\nIniciando procesador de OSIPTEL...")
    print("-" * 40)
    try:
        from procesar_osiptel_paralelo import main as osiptel_main
        osiptel_main()
    except Exception as e:
        print(f"\n*** ERROR EN OSIPTEL ***")
        print(f"Error: {str(e)}")
        print("\nDetalles del error:")
        traceback.print_exc()



def ejecutar_whatsapp_bot():
    print("\nIniciando Bot de WhatsApp...")
    print("-" * 40)
    
    try:
        # Obtener directorio del ejecutable
        if getattr(sys, 'frozen', False):
            # === MODO EMPAQUETADO (EXE) ===
            base_path = os.path.dirname(sys.executable)
            server_exe = os.path.join(base_path, 'server.exe')
            bot_exe = os.path.join(base_path, 'bot.exe')
            
            if not os.path.exists(server_exe):
                print(f"ERROR: No se encontró server.exe en {base_path}")
                return
            if not os.path.exists(bot_exe):
                print(f"ERROR: No se encontró bot.exe en {base_path}")
                return
            
            # Iniciar servidor Python en segundo plano (oculto)
            print("Iniciando servidor de scrapers...")
            import threading
            import time
            
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            # Log del server
            log_path = os.path.join(base_path, 'server.log')
            logfile = open(log_path, 'w')
            subprocess.Popen([server_exe], startupinfo=startupinfo, stdout=logfile, stderr=logfile, cwd=base_path)
            
            time.sleep(3)
            
            print("Iniciando bot de WhatsApp...")
            print("\n   >>> ESCANEA EL CÓDIGO QR A CONTINUACIÓN <<<\n")
            
            # Ejecutar bot.exe en primer plano
            subprocess.run([bot_exe], cwd=base_path, shell=True)
            
        else:
            # === MODO SCRIPT (Desarrollo) ===
            base_path = os.path.dirname(os.path.abspath(__file__))
            
            # Verificar Node.js
            if not verificar_nodejs():
                input("\nPresiona ENTER para continuar...")
                return
            
            bot_path = os.path.join(base_path, 'whatsapp-bot-node')
            if not os.path.exists(bot_path):
                print(f"ERROR: No se encontró la carpeta whatsapp-bot-node")
                print(f"Buscando en: {bot_path}")
                return
            
            # Verificar si necesita npm install
            node_modules = os.path.join(bot_path, 'node_modules')
            wwebjs_exists = os.path.exists(os.path.join(node_modules, 'whatsapp-web.js'))
            if not os.path.exists(node_modules) or not wwebjs_exists:
                print("Instalando dependencias de Node.js (primera vez, puede tardar)...")
                subprocess.run(['npm', 'install'], cwd=bot_path, shell=True)
            
            # Iniciar servidor Python en segundo plano
            print("Iniciando servidor de scrapers...")
            import threading
            import time
            
            def run_python_server():
                subprocess.run(['python', 'python_server.py'], cwd=bot_path, shell=True)
            
            server_thread = threading.Thread(target=run_python_server, daemon=True)
            server_thread.start()
            
            time.sleep(5)
            
            print("Iniciando bot de WhatsApp...")
            print()
            
            # Ejecutar bot Node.js
            subprocess.run(['npm', 'start'], cwd=bot_path, shell=True)
        
    except Exception as e:
        print(f"\n*** ERROR EN WHATSAPP BOT ***")
        print(f"Error: {str(e)}")
        print("\nDetalles del error:")
        traceback.print_exc()

def main():
    try:
        while True:
            mostrar_menu()
            opcion = input("Selecciona una opcion (1-6): ").strip()
            
            if opcion == "1":
                ejecutar_sunat()
                input("\n\nPresiona ENTER para volver al menu...")
            
            elif opcion == "2":
                ejecutar_entel()
                input("\n\nPresiona ENTER para volver al menu...")
            
            elif opcion == "3":
                ejecutar_segmentacion()
                input("\n\nPresiona ENTER para volver al menu...")
            
            elif opcion == "4":
                ejecutar_osiptel()
                input("\n\nPresiona ENTER para volver al menu...")
            

            
            elif opcion == "5":
                ejecutar_whatsapp_bot()
                input("\n\nPresiona ENTER para volver al menu...")
            
            elif opcion == "6":
                print("\n¡Hasta luego!")
                sys.exit(0)
            
            else:
                print("\nOpcion no valida. Intenta de nuevo.")
                input("Presiona ENTER para continuar...")
    except Exception as e:
        print(f"\n*** ERROR FATAL ***")
        print(f"Error: {str(e)}")
        print("\nDetalles del error:")
        traceback.print_exc()
        input("\n\nPresiona ENTER para cerrar...")

if __name__ == "__main__":
    main()
