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
    """Verifica si Node.js está instalado, si no lo instala automáticamente"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, shell=True)
        if result.returncode == 0:
            return True
    except:
        pass
    
    print("\n⚠️  Node.js no está instalado.")
    print("Descargando e instalando automáticamente...")
    
    try:
        # Descargar instalador de Node.js LTS
        url = "https://nodejs.org/dist/v20.10.0/node-v20.10.0-x64.msi"
        installer = os.path.join(os.environ['TEMP'], 'node_installer.msi')
        
        print("Descargando Node.js (25 MB)...")
        urllib.request.urlretrieve(url, installer)
        
        print("Instalando Node.js (puede tomar 1 minuto)...")
        subprocess.run(['msiexec', '/i', installer, '/qn'], shell=True, check=True)
        
        os.remove(installer)
        print("✅ Node.js instalado correctamente!")
        return True
        
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
    print("  [2] Ejecutar NUMEROS (Telefonos Entel)")
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
    print("\nIniciando procesador de NUMEROS (Entel)...")
    print("-" * 40)
    try:
        from procesar_entel_paralelo import main as entel_main
        entel_main()
    except Exception as e:
        print(f"\n*** ERROR EN ENTEL ***")
        print(f"Error: {str(e)}")
        print("\nDetalles del error:")
        traceback.print_exc()

def ejecutar_segmentacion():
    print("\nIniciando procesador de SEGMENTACION...")
    print("-" * 40)
    try:
        from procesar_segmentacion_paralelo import main as segmentacion_main
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
    
    # Verificar Node.js
    if not verificar_nodejs():
        input("\nPresiona ENTER para continuar...")
        return
    
    try:
        bot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'whatsapp-bot-node')
        if not os.path.exists(bot_path):
            print("ERROR: No se encontro la carpeta whatsapp-bot-node")
            return
        
        # Verificar si necesita npm install
        node_modules = os.path.join(bot_path, 'node_modules')
        if not os.path.exists(node_modules):
            print("Instalando dependencias de Node.js (primera vez)...")
            subprocess.run(['npm', 'install'], cwd=bot_path, shell=True)
        
        # Iniciar servidor Python en segundo plano
        print("Iniciando servidor de scrapers...")
        import threading
        import time
        
        def run_python_server():
            subprocess.run(['python', 'python_server.py'], cwd=bot_path, shell=True)
        
        server_thread = threading.Thread(target=run_python_server, daemon=True)
        server_thread.start()
        
        # Esperar a que el servidor inicie
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
