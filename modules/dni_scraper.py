# -*- coding: utf-8 -*-
"""
Módulo para consultar DNI usando la API de MiAPI Cloud
Incluye datos completos: nombres, dirección, ubigeo
"""
import os
import requests
from typing import Dict, Optional

class DniScraper:
    def __init__(self, api_token: str = None):
        # Token de MiAPI Cloud - leer de variable de entorno para seguridad
        self.api_token = api_token or os.getenv('MIAPI_TOKEN', '')
        if not self.api_token:
            print("⚠️ MIAPI_TOKEN no configurado en .env")
        self.base_url = "https://miapi.cloud/v1/dni"
    
    def consultar_dni(self, numero_dni: str) -> Optional[Dict]:
        """
        Consulta los datos completos de una persona por su DNI
        Incluye: nombres, dirección, distrito, provincia, departamento, ubigeo
        
        Args:
            numero_dni: Número de DNI de 8 dígitos
            
        Returns:
            Dict con los datos o None si hay error
        """
        # Limpiar el DNI (solo dígitos)
        numero_dni = ''.join(filter(str.isdigit, numero_dni))
        
        if len(numero_dni) != 8:
            print(f"DNI inválido: {numero_dni} (debe tener 8 dígitos)")
            return None
        
        try:
            url = f"{self.base_url}/{numero_dni}"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    datos = data.get('datos', {})
                    domicilio = datos.get('domiciliado', {})
                    
                    return {
                        'dni': datos.get('dni', numero_dni),
                        'nombres': datos.get('nombres', ''),
                        'apellido_paterno': datos.get('ape_paterno', ''),
                        'apellido_materno': datos.get('ape_materno', ''),
                        'nombre_completo': f"{datos.get('ape_paterno', '')} {datos.get('ape_materno', '')} {datos.get('nombres', '')}".strip(),
                        # Datos de domicilio
                        'direccion': domicilio.get('direccion', ''),
                        'distrito': domicilio.get('distrito', ''),
                        'provincia': domicilio.get('provincia', ''),
                        'departamento': domicilio.get('departamento', ''),
                        'ubigeo': domicilio.get('ubigeo', '')
                    }
                else:
                    print(f"API respondió sin éxito: {data}")
                    return None
                    
            elif response.status_code == 404:
                print(f"DNI {numero_dni} no encontrado")
                return None
            elif response.status_code == 401:
                print("Error de autenticación - Token inválido o expirado")
                return None
            else:
                print(f"Error API: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.Timeout:
            print("Timeout consultando API DNI")
            return None
        except Exception as e:
            print(f"Error consultando DNI: {e}")
            return None
    
    def close(self):
        """No hay que cerrar nada, es solo API REST"""
        pass


if __name__ == "__main__":
    # Test rápido
    scraper = DniScraper()
    resultado = scraper.consultar_dni("70450683")
    
    if resultado:
        print("="*50)
        print("DATOS DNI COMPLETOS:")
        print("="*50)
        print(f"DNI: {resultado['dni']}")
        print(f"Nombres: {resultado['nombres']}")
        print(f"Apellido Paterno: {resultado['apellido_paterno']}")
        print(f"Apellido Materno: {resultado['apellido_materno']}")
        print(f"Nombre Completo: {resultado['nombre_completo']}")
        print()
        print("DOMICILIO:")
        print(f"Dirección: {resultado['direccion']}")
        print(f"Distrito: {resultado['distrito']}")
        print(f"Provincia: {resultado['provincia']}")
        print(f"Departamento: {resultado['departamento']}")
        print(f"Ubigeo: {resultado['ubigeo']}")
    else:
        print("No se pudo consultar el DNI")
