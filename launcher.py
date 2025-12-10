"""
Launcher principal para el Filtrador Masivo de RUCs
Permite ejecutar los scrapers de SUNAT, Entel y Segmentación desde un menú
"""
import os
import sys
import traceback

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
    print("  [4] Salir")
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

def main():
    try:
        while True:
            mostrar_menu()
            opcion = input("Selecciona una opcion (1-4): ").strip()
            
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
