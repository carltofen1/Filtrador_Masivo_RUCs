# -*- coding: utf-8 -*-
"""
Bridge Python para el Bot de WhatsApp Node.js
Ejecuta los scrapers existentes y devuelve resultados
Mantiene navegador persistente para velocidad
"""
import sys
import os
import io
import contextlib

# Forzar UTF-8 en stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Agregar el directorio padre al path para importar módulos
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re

# Scrapers persistentes (no se cierran hasta que termina el proceso)
_claro_scraper = None

def get_claro_scraper():
    """Obtiene o crea el scraper de Claro (persistente)"""
    global _claro_scraper
    from modules.claro_cobertura_scraper import ClaroCoberturaScraper
    
    if _claro_scraper is None:
        _claro_scraper = ClaroCoberturaScraper(headless=False)  # Sin headless para debug
        _claro_scraper.login()
    return _claro_scraper

def consultar_ruc(ruc):
    """Consulta SUNAT y ENTEL para un RUC"""
    from modules.sunat_scraper import SunatScraper
    from modules.entel_scraper import EntelScraper
    
    ruc = re.sub(r'\D', '', ruc)
    
    if not ruc or len(ruc) != 11:
        return """*Formato incorrecto*

Uso: .ruc NUMERO_RUC
Ejemplo: .ruc 20123456789

_El RUC debe tener 11 dígitos_"""
    
    resultado = f"Consulta RUC: {ruc}\n\n"
    datos = None
    telefono = None
    
    # Consultar SUNAT
    try:
        with contextlib.redirect_stdout(sys.stderr):
            sunat = SunatScraper()
            datos = sunat.consultar_ruc(ruc)
            sunat.close()
    except Exception as e:
        sys.stderr.write(f"Error SUNAT: {str(e)}\n")
    
    # Consultar ENTEL
    try:
        with contextlib.redirect_stdout(sys.stderr):
            entel = EntelScraper()
            telefono = entel.buscar_telefono(ruc)
            entel.close()
    except Exception as e:
        sys.stderr.write(f"Error ENTEL: {str(e)}\n")
    
    # Formatear respuesta
    if datos:
        resultado += f"""DATOS SUNAT:
Razon Social: {datos.get('razon_social', '---')}
Estado: {datos.get('estado', 'ACTIVO')}
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

def consultar_delivery(args):
    """Consulta cobertura de delivery"""
    coords = parsear_coordenadas(args)
    
    if not coords:
        return """Formato incorrecto

Uso: .delivery lat, lng
Ejemplo: .delivery -12.046, -77.042"""
    
    try:
        with contextlib.redirect_stdout(sys.stderr):
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
            return f"""Resultado de cobertura:
Cobertura por Delivery: NO

{resultado.get('error', 'Sin cobertura') if resultado else 'Error en consulta'}

Coordenadas:
Lat: {coords['lat']}
Lng: {coords['lng']}

FACC"""
    except Exception as e:
        return f"Error consultando delivery: {str(e)}"

def consultar_internet(args):
    """Consulta cobertura de internet"""
    coords = parsear_coordenadas(args)
    
    if not coords:
        return """Formato incorrecto

Uso: .internet lat, lng
Ejemplo: .internet -12.046, -77.042"""
    
    try:
        with contextlib.redirect_stdout(sys.stderr):
            scraper = get_claro_scraper()
            resultado = scraper.consultar_internet(coords['lat'], coords['lng'])
        
        if resultado and not resultado.get('error'):
            tiene_cobertura = "SI" if resultado.get('estado') == "CON COBERTURA" else "NO"
            return f"""Resultado de cobertura:
Cobertura de Internet: {tiene_cobertura}

ALAMBRICA: {resultado.get('cobertura_alambrica', 'NO')}
INALAMBRICA: {resultado.get('cobertura_inalambrica', 'NO')}
TECNOLOGIA: {resultado.get('tecnologia', '---')}
ESTADO: {resultado.get('estado', '---')}

Coordenadas:
Lat: {coords['lat']}
Lng: {coords['lng']}

FACC"""
        else:
            return f"""Resultado de cobertura:
Cobertura de Internet: NO

{resultado.get('error', 'Sin cobertura') if resultado else 'Error en consulta'}

Coordenadas:
Lat: {coords['lat']}
Lng: {coords['lng']}

FACC"""
    except Exception as e:
        return f"Error consultando internet: {str(e)}"

def parsear_coordenadas(args):
    """Extrae latitud y longitud de un string"""
    args = args.replace('📍', '').replace('Lat:', '').replace('Lng:', '')
    args = re.sub(r'[^\d\-.,\s]', '', args)
    
    match = re.search(r'(-?\d+\.?\d*)\s*[,\s]\s*(-?\d+\.?\d*)', args)
    if match:
        return {
            'lat': float(match.group(1)),
            'lng': float(match.group(2))
        }
    return None

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Uso: python python_bridge.py <comando> <args>")
        sys.exit(1)
    
    comando = sys.argv[1]
    args = sys.argv[2] if len(sys.argv) > 2 else ''
    
    if comando == 'ruc':
        print(consultar_ruc(args))
    elif comando == 'delivery':
        print(consultar_delivery(args))
    elif comando == 'internet':
        print(consultar_internet(args))
    else:
        print(f"Comando desconocido: {comando}")
        sys.exit(1)
