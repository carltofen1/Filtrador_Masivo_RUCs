# -*- coding: utf-8 -*-
"""
Módulo para consultar DNI combinando 2 APIs:
- MiAPI Cloud: Dirección y ubigeo
- PERUDEVS: Fecha nacimiento, género, código verificación
"""
import os
import requests
from typing import Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class DniScraper:
    def __init__(self, miapi_token: str = None, perudevs_key: str = None):
        # Token de MiAPI Cloud (para dirección)
        self.miapi_token = miapi_token or os.getenv('MIAPI_TOKEN', '')
        # Token de PERUDEVS (para fecha nacimiento y género)
        self.perudevs_key = perudevs_key or os.getenv('PERUDEVS_KEY', '')
        
        self.miapi_url = "https://miapi.cloud/v1/dni"
        self.perudevs_url = "https://api.perudevs.com/api/v1/dni/complete"
        
        if not self.miapi_token:
            print("⚠️ MIAPI_TOKEN no configurado en .env")
        if not self.perudevs_key:
            print("⚠️ PERUDEVS_KEY no configurado en .env")
    
    def _calcular_edad(self, fecha_nacimiento: str) -> int:
        """Calcula la edad a partir de fecha en formato DD/MM/YYYY"""
        try:
            fecha = datetime.strptime(fecha_nacimiento, "%d/%m/%Y")
            hoy = datetime.now()
            edad = hoy.year - fecha.year
            if (hoy.month, hoy.day) < (fecha.month, fecha.day):
                edad -= 1
            return edad
        except:
            return 0
    
    def _consultar_miapi(self, dni: str) -> Dict:
        """Consulta MiAPI Cloud para obtener dirección"""
        try:
            url = f"{self.miapi_url}/{dni}"
            headers = {
                "Authorization": f"Bearer {self.miapi_token}",
                "Content-Type": "application/json"
            }
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    datos = data.get('datos', {})
                    domicilio = datos.get('domiciliado', {})
                    return {
                        'direccion': domicilio.get('direccion', ''),
                        'distrito': domicilio.get('distrito', ''),
                        'provincia': domicilio.get('provincia', ''),
                        'departamento': domicilio.get('departamento', ''),
                        'ubigeo': domicilio.get('ubigeo', '')
                    }
        except Exception as e:
            print(f"Error MiAPI: {e}")
        return {}
    
    def _consultar_perudevs(self, dni: str) -> Dict:
        """Consulta PERUDEVS para obtener datos personales"""
        try:
            url = f"{self.perudevs_url}?document={dni}&key={self.perudevs_key}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('estado'):
                    resultado = data.get('resultado', {})
                    fecha_nac = resultado.get('fecha_nacimiento', '')
                    genero_code = resultado.get('genero', '')
                    
                    return {
                        'nombres': resultado.get('nombres', ''),
                        'apellido_paterno': resultado.get('apellido_paterno', ''),
                        'apellido_materno': resultado.get('apellido_materno', ''),
                        'nombre_completo': resultado.get('nombre_completo', ''),
                        'fecha_nacimiento': fecha_nac,
                        'edad': self._calcular_edad(fecha_nac),
                        'genero': 'Masculino' if genero_code == 'M' else 'Femenino' if genero_code == 'F' else genero_code,
                        'codigo_verificacion': resultado.get('codigo_verificacion', '')
                    }
        except Exception as e:
            print(f"Error PERUDEVS: {e}")
        return {}
    
    
    def consultar_dni(self, numero_dni: str) -> Optional[Dict]:
        """
        Consulta los datos completos de una persona por su DNI
        Combina datos de MiAPI Cloud (dirección) + PERUDEVS (edad/género)
        """
        # Limpiar el DNI
        numero_dni = ''.join(filter(str.isdigit, numero_dni))
        
        if len(numero_dni) != 8:
            print(f"DNI inválido: {numero_dni} (debe tener 8 dígitos)")
            return None
        
        # Consultar ambas APIs
        datos_perudevs = self._consultar_perudevs(numero_dni)
        datos_miapi = self._consultar_miapi(numero_dni)
        
        # Si al menos una API respondió, combinar resultados
        if datos_perudevs or datos_miapi:
            return {
                'dni': numero_dni,
                # Datos personales (PERUDEVS)
                'nombres': datos_perudevs.get('nombres', ''),
                'apellido_paterno': datos_perudevs.get('apellido_paterno', ''),
                'apellido_materno': datos_perudevs.get('apellido_materno', ''),
                'nombre_completo': datos_perudevs.get('nombre_completo', ''),
                'fecha_nacimiento': datos_perudevs.get('fecha_nacimiento', ''),
                'edad': datos_perudevs.get('edad', 0),
                'genero': datos_perudevs.get('genero', ''),
                'codigo_verificacion': datos_perudevs.get('codigo_verificacion', ''),
                # Domicilio (MiAPI Cloud)
                'direccion': datos_miapi.get('direccion', ''),
                'distrito': datos_miapi.get('distrito', ''),
                'provincia': datos_miapi.get('provincia', ''),
                'departamento': datos_miapi.get('departamento', ''),
                'ubigeo': datos_miapi.get('ubigeo', '')
            }
        
        return None
    
    def close(self):
        """No hay que cerrar nada, es solo API REST"""
        pass


if __name__ == "__main__":
    # Test rápido
    scraper = DniScraper()
    dni_prueba = "70450683" 
    print(f"Probando DNI: {dni_prueba}")
    resultado = scraper.consultar_dni(dni_prueba)
    
    if resultado:
        print("="*50)
        print("DATOS DNI COMPLETOS:")
        print("="*50)
        print(f"DNI: {resultado['dni']}")
        print(f"Nombre Completo: {resultado['nombre_completo']}")
        print(f"Edad: {resultado['edad']} años")
        print(f"Perfil: {resultado.get('perfil_url', 'No encontrado')}")

