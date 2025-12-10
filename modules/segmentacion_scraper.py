"""
Scraper para el portal de Segmentación (Salesforce/Claro)
Extrae el tipo de cliente (PYME, etc.) por RUC
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import re
import config

class SegmentacionScraper:
    def __init__(self, headless=True):
        self.url = config.SEGMENTACION_URL
        self.username = config.SEGMENTACION_USERNAME
        self.password = config.SEGMENTACION_PASSWORD
        
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        # Optimizaciones para bajo consumo
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-notifications')
        options.add_argument('--blink-settings=imagesEnabled=false')  # No cargar imágenes
        options.add_argument('--disable-animations')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 15)
        self.logged_in = False
    
    def login(self):
        """Inicia sesión en el portal de Segmentación"""
        try:
            print("Navegando al portal de Segmentación...")
            self.driver.get(self.url)
            
            # Esperar formulario de login
            username_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Usuario']"))
            )
            
            username_input.clear()
            username_input.send_keys(self.username)
            
            password_input = self.driver.find_element(By.CSS_SELECTOR, "input[placeholder='Contraseña']")
            password_input.clear()
            password_input.send_keys(self.password)
            
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button.loginButton")
            login_button.click()
            
            # Esperar buscador
            self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Search...']"))
            )
            
            print("Login exitoso en Segmentación")
            self.logged_in = True
            return True
            
        except Exception as e:
            print(f"Error en login de Segmentación: {str(e)}")
            return False
    
    def buscar_tipo_cliente(self, ruc):
        """Busca un RUC y extrae el PE Tipo de Cliente"""
        try:
            if not self.logged_in:
                return None
            
            # Esperar buscador
            search_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Search...']"))
            )
            
            search_input.clear()
            search_input.send_keys(ruc)
            search_input.send_keys(Keys.RETURN)
            
            # Esperar resultados (máx 5 seg)
            time.sleep(2)
            
            # Verificar si no hay resultados
            if "No se han encontrado resultados" in self.driver.page_source:
                return "Sin Segmento"
            
            # Hacer click en el cliente
            try:
                cliente_link = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.outputLookupLink"))
                )
                cliente_link.click()
                
                # Esperar a que cargue el formulario
                WebDriverWait(self.driver, 8).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "span.test-id__field-label"))
                )
                time.sleep(1)
                
            except:
                return "Sin Segmento"
            
            # Extraer con regex
            html = self.driver.page_source
            
            pattern = r'>PE Tipo de Cliente</span>.*?<lightning-formatted-text[^>]*>([^<]+)</lightning-formatted-text>'
            match = re.search(pattern, html, re.DOTALL)
            if match:
                valor = match.group(1).strip()
                if valor:
                    self.driver.get("https://transforma.my.site.com/s/")
                    time.sleep(1)
                    return valor
            
            self.driver.get("https://transforma.my.site.com/s/")
            time.sleep(1)
            return "Sin Datos"
            
        except Exception as e:
            print(f"Error RUC {ruc}: {str(e)[:30]}")
            return None
    
    def close(self):
        """Cierra el navegador"""
        try:
            self.driver.quit()
        except:
            pass
    
    def _extraer_campo(self, nombre_campo):
        """Extrae el valor de un campo dado su nombre de etiqueta del HTML"""
        import re
        try:
            time.sleep(1)
            
            # Obtener todo el HTML de la página
            html = self.driver.page_source
            
            # Buscar el patrón: field-label="PE Tipo de Cliente" ... >VALOR<
            # Patrón 1: buscar entre field-label y el siguiente lightning-formatted-text
            pattern1 = r'field-label="' + re.escape(nombre_campo) + r'"[^>]*>.*?<lightning-formatted-text[^>]*>([^<]+)</lightning-formatted-text>'
            match = re.search(pattern1, html, re.DOTALL)
            if match:
                valor = match.group(1).strip()
                if valor:
                    print(f"  -> {nombre_campo}: {valor}")
                    return valor
            
            # Patrón 2: buscar el span del label y el siguiente valor
            pattern2 = r'<span[^>]*class="test-id__field-label"[^>]*>' + re.escape(nombre_campo) + r'</span>.*?<lightning-formatted-text[^>]*data-output-element-id="output-field"[^>]*>([^<]*)</lightning-formatted-text>'
            match = re.search(pattern2, html, re.DOTALL)
            if match:
                valor = match.group(1).strip()
                if valor:
                    print(f"  -> {nombre_campo}: {valor}")
                    return valor
            
            # Patrón 3: buscar PE_Tipo_de_Cliente en data-target-selection-name
            pattern3 = r'data-target-selection-name="[^"]*PE_Tipo_de_Cliente[^"]*"[^>]*>.*?<lightning-formatted-text[^>]*>([^<]+)</lightning-formatted-text>'
            match = re.search(pattern3, html, re.DOTALL)
            if match:
                valor = match.group(1).strip()
                if valor:
                    print(f"  -> {nombre_campo}: {valor}")
                    return valor
            
            print(f"  -> {nombre_campo}: No encontrado")
            return None
            
        except Exception as e:
            print(f"Error extrayendo campo '{nombre_campo}': {str(e)}")
            return None
    
    def close(self):
        """Cierra el navegador"""
        try:
            self.driver.quit()
        except:
            pass
