# -*- coding: utf-8 -*-
"""
Servidor Python para el Bot de WhatsApp
Mantiene los navegadores abiertos y recibe comandos por HTTP
"""
import sys
import os
import io
import re
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import contextlib

# Forzar UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Path para imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.sunat_scraper import SunatScraper
from modules.entel_scraper import EntelScraper
from modules.claro_cobertura_scraper import ClaroCoberturaScraper
from modules.dni_scraper import DniScraper

# Scrapers persistentes
claro_scraper = None
sunat_scraper = None
entel_scraper = None
dni_scraper = None

# Keep-alive para mantener sesión Claro activa
KEEP_ALIVE_INTERVAL = 45 * 60  # 45 minutos en segundos
keep_alive_thread = None
keep_alive_running = True

def keep_alive_claro():
    """Thread que mantiene la sesión de Claro activa haciendo consultas periódicas"""
    global claro_scraper, keep_alive_running
    
    # Coordenadas de prueba (centro de Lima)
    lat_test = -12.0464
    lng_test = -77.0428
    
    while keep_alive_running:
        time.sleep(KEEP_ALIVE_INTERVAL)
        
        if not keep_alive_running:
            break
            
        if claro_scraper is not None:
            try:
                print(f"[Keep-Alive] Manteniendo sesión Claro activa...")
                # Hacer una consulta dummy para mantener la sesión
                claro_scraper.consultar_internet(lat_test, lng_test)
                print(f"[Keep-Alive] Sesión Claro OK - Próximo refresh en {KEEP_ALIVE_INTERVAL // 60} min")
            except Exception as e:
                print(f"[Keep-Alive] Error, reintentando login: {str(e)[:50]}")
                try:
                    # Reintentar login si falló
                    claro_scraper.login()
                    print("[Keep-Alive] Re-login exitoso")
                except Exception as e2:
                    print(f"[Keep-Alive] Error en re-login: {str(e2)[:50]}")

def start_keep_alive():
    """Inicia el thread de keep-alive"""
    global keep_alive_thread
    keep_alive_thread = threading.Thread(target=keep_alive_claro, daemon=True)
    keep_alive_thread.start()
    print(f"[Keep-Alive] Iniciado - Refresh cada {KEEP_ALIVE_INTERVAL // 60} minutos")

def get_claro_scraper():
    global claro_scraper
    if claro_scraper is None:
        print("Iniciando scraper Claro...")
        claro_scraper = ClaroCoberturaScraper(headless=True)
        claro_scraper.login()
        print("Scraper Claro listo!")
    return claro_scraper

def consultar_ruc(ruc):
    global sunat_scraper, entel_scraper
    
    ruc = re.sub(r'\D', '', ruc)
    if not ruc or len(ruc) != 11:
        return "Formato incorrecto\n\nUso: .ruc NUMERO_RUC\nEjemplo: .ruc 20123456789"
    
    resultado = f"Consulta RUC: {ruc}\n\n"
    datos = None
    telefono = None
    
    try:
        if sunat_scraper is None:
            sunat_scraper = SunatScraper()
        datos = sunat_scraper.consultar_ruc(ruc)
    except Exception as e:
        print(f"Error SUNAT: {e}")
    
    try:
        if entel_scraper is None:
            entel_scraper = EntelScraper()
        telefono = entel_scraper.buscar_telefono(ruc)
    except Exception as e:
        print(f"Error ENTEL: {e}")
    
    if datos:
        resultado += f"""DATOS SUNAT:
Razon Social: {datos.get('razon_social', '---')}
Estado: {datos.get('estado_contribuyente', '---')}
Representante: {datos.get('representante_legal', '---')}
DNI: {datos.get('documento_identidad', '---')}
Direccion: {datos.get('direccion', '---')}
Distrito: {datos.get('distrito', '---')}
Provincia: {datos.get('provincia', '---')}
Departamento: {datos.get('departamento', '---')}

"""
    else:
        resultado += "DATOS SUNAT: No disponible\n\n"
    
    resultado += f"TELEFONO ENTEL: {telefono or 'Sin registro'}"
    return resultado

def consultar_dni_api(dni):
    """Consulta datos completos de una persona por DNI combinando MiAPI Cloud + PERUDEVS"""
    global dni_scraper
    
    dni = re.sub(r'\D', '', dni)
    if not dni or len(dni) != 8:
        return "Formato incorrecto\n\nUso: .dni NUMERO_DNI\nEjemplo: .dni 12345678"
    
    try:
        if dni_scraper is None:
            dni_scraper = DniScraper()
        
        datos = dni_scraper.consultar_dni(dni)
        
        if datos:
            edad = datos.get('edad', 0)
            edad_str = f"{edad} años" if edad > 0 else "---"
            
            return f"""📋 Consulta DNI: {dni}

👤 DATOS PERSONALES:
Nombre: {datos.get('nombre_completo', '---')}
Fecha Nacimiento: {datos.get('fecha_nacimiento', '---')}
Edad: {edad_str}
Género: {datos.get('genero', '---')}
Código Verificación: {datos.get('codigo_verificacion', '---')}

📍 DOMICILIO:
Dirección: {datos.get('direccion', '---')}
Distrito: {datos.get('distrito', '---')}
Provincia: {datos.get('provincia', '---')}
Departamento: {datos.get('departamento', '---')}
Ubigeo: {datos.get('ubigeo', '---')}"""
        else:
            return f"Consulta DNI: {dni}\n\nNo se encontraron datos para este DNI"
            
    except Exception as e:
        print(f"Error DNI: {e}")
        return f"Error consultando DNI: {str(e)}"


def consultar_delivery(args):
    coords = parsear_coordenadas(args)
    if not coords:
        return "Formato incorrecto\n\nUso: .delivery lat, lng\nEjemplo: .delivery -12.046, -77.042"
    
    try:
        scraper = get_claro_scraper()
        resultado = scraper.consultar_delivery(coords['lat'], coords['lng'])
        
        if resultado and not resultado.get('error'):
            tiene_cobertura = "SI" if "CON COBERTURA" in resultado.get('estado', '') else "NO"
            return f"""Resultado de cobertura:
Cobertura por Delivery: {tiene_cobertura}

DISTRITO: {resultado.get('distrito', '---')}
PLANO: {resultado.get('plano', '---')}
ZONA_TOA: {resultado.get('zona_toa', '---')}
COLOR: {resultado.get('color', '---')}
ESTADO: {resultado.get('estado', '---')}
CONDICION: {resultado.get('condicion', '---')}

Coordenadas:
Lat: {coords['lat']}
Lng: {coords['lng']}

FACC"""
        else:
            error_msg = resultado.get('error', 'Sin cobertura') if resultado else 'Error'
            return f"Resultado de cobertura:\nCobertura por Delivery: NO\n\n{error_msg}\n\nCoord: {coords['lat']}, {coords['lng']}\n\nFACC"
    except Exception as e:
        return f"Error: {str(e)}"

def consultar_internet(args):
    coords = parsear_coordenadas(args)
    if not coords:
        return "Formato incorrecto\n\nUso: .internet lat, lng\nEjemplo: .internet -12.046, -77.042"
    
    try:
        scraper = get_claro_scraper()
        resultado = scraper.consultar_internet(coords['lat'], coords['lng'])
        
        if resultado and not resultado.get('error'):
            tiene_cobertura = "SI" if resultado.get('estado') == "CON COBERTURA" else "NO"
            return f"""Resultado de cobertura:
Cobertura de Internet: {tiene_cobertura}

PLANO: {resultado.get('plano', '---')}
TECNOLOGIA: {resultado.get('tecnologia', '---')}
VELOCIDAD: {resultado.get('velocidad', '---')}
VENDOR: {resultado.get('vendor', '---')}
ESTADO: {resultado.get('estado', '---')}

Coordenadas:
Lat: {coords['lat']}
Lng: {coords['lng']}

FACC"""
        else:
            error_msg = resultado.get('error', 'Sin cobertura') if resultado else 'Error'
            return f"Resultado de cobertura:\nCobertura de Internet: NO\n\n{error_msg}\n\nCoord: {coords['lat']}, {coords['lng']}\n\nFACC"
    except Exception as e:
        return f"Error: {str(e)}"

def parsear_coordenadas(args):
    args = args.replace('📍', '').replace('Lat:', '').replace('Lng:', '')
    args = re.sub(r'[^\d\-.,\s]', '', args)
    match = re.search(r'(-?\d+\.?\d*)\s*[,\s]\s*(-?\d+\.?\d*)', args)
    if match:
        return {'lat': float(match.group(1)), 'lng': float(match.group(2))}
    return None

class CommandHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Silenciar logs HTTP
    
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length).decode('utf-8')
        data = json.loads(body)
        
        comando = data.get('comando', '')
        args = data.get('args', '')
        
        print(f"Comando: {comando} {args[:30]}...")
        
        if comando == 'ruc':
            resultado = consultar_ruc(args)
        elif comando == 'dni':
            resultado = consultar_dni_api(args)
        elif comando == 'delivery':
            resultado = consultar_delivery(args)
        elif comando == 'internet':
            resultado = consultar_internet(args)
        else:
            resultado = f"Comando desconocido: {comando}"
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps({'resultado': resultado}).encode('utf-8'))

if __name__ == '__main__':
    PORT = 5555
    print("="*50)
    print("  SERVIDOR DE SCRAPERS - Bot WhatsApp")
    print("="*50)
    print(f"Puerto: {PORT}")
    print()
    
    # Pre-iniciar scrapers
    print("Inicializando scrapers...")
    get_claro_scraper()
    
    # Iniciar keep-alive para mantener sesión Claro activa
    start_keep_alive()
    
    print()
    print("Servidor listo! Esperando comandos...")
    print()
    
    server = HTTPServer(('localhost', PORT), CommandHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
        keep_alive_running = False
        if claro_scraper:
            claro_scraper.close()
        if sunat_scraper:
            sunat_scraper.close()
        if entel_scraper:
            entel_scraper.close()
