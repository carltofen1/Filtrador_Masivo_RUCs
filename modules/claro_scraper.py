from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from typing import Dict, Optional
import time
import config

class ClaroScraper:
    def __init__(self):
        self.driver = None
        self.logged_in = False
        
    def _init_driver(self):
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.maximize_window()
            print("Driver de Chrome inicializado")
    
    def login(self):
        if self.logged_in:
            print("Ya está logueado")
            return True
        
        try:
            self._init_driver()
            
            print("Iniciando login en Claro...")
            self.driver.get(config.CLARO_URL)
            
            self.logged_in = True
            print("Login exitoso")
            return True
            
        except Exception as e:
            print(f"Error en login: {str(e)}")
            return False
    
    def buscar_por_ruc(self, ruc: str) -> Optional[Dict]:
        if not self.logged_in:
            if not self.login():
                return None
        
        try:
            print(f"Buscando RUC {ruc} en Claro...")
            
            result = {
                'telefonos': 'PENDIENTE_CONFIGURAR',
                'operador': 'PENDIENTE_CONFIGURAR',
                'cantidad_lineas': 'PENDIENTE_CONFIGURAR'
            }
            
            print(f"Datos encontrados para RUC {ruc}")
            return result
            
        except Exception as e:
            print(f"Error al buscar RUC {ruc}: {str(e)}")
            return None
    
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logged_in = False
            print("Navegador cerrado")
