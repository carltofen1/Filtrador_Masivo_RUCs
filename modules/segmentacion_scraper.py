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
    def __init__(self, headless=False):  # DESACTIVADO - Salesforce no funciona bien en headless
        self.url = config.SEGMENTACION_URL
        self.username = config.SEGMENTACION_USERNAME
        self.password = config.SEGMENTACION_PASSWORD
        
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        
        # Argumentos para evitar detección y mejorar compatibilidad con Salesforce
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)
        
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
    
    def buscar_tipo_cliente(self, ruc, intento=1):
        """Busca un RUC y extrae el PE Tipo de Cliente - Tiempos inteligentes con reintentos"""
        MAX_INTENTOS = 3  # Aumentado de 2 a 3 para mayor robustez
        
        try:
            if not self.logged_in:
                return None
            
            # Esperar buscador (tiempo máximo, sale antes si aparece)
            search_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Search...']"))
            )
            
            search_input.clear()
            search_input.send_keys(ruc)
            search_input.send_keys(Keys.RETURN)
            
            # Esperar inteligente: sale inmediatamente cuando aparece resultado O no encontrado
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: "No se han encontrado resultados" in d.page_source or 
                              d.find_elements(By.CSS_SELECTOR, "a.outputLookupLink")
                )
            except:
                if intento < MAX_INTENTOS:
                    self.driver.get("https://transforma.my.site.com/s/")
                    time.sleep(1)
                    return self.buscar_tipo_cliente(ruc, intento + 1)
                return "Sin Segmento"
            
            # No hay resultados = cliente no existe en Salesforce (respuesta rápida)
            if "No se han encontrado resultados" in self.driver.page_source:
                return "Sin Segmento"
            
            # Click en el cliente
            try:
                cliente_link = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.outputLookupLink"))
                )
                cliente_link.click()
                
                # ESPERA INTELIGENTE: Verificar que el VALOR del segmento ya cargó
                # No solo el label, sino el valor real (PYME, Mayores, etc.)
                segmentos_conocidos = ['PYME', 'Mayores', 'SOHO', 'Corporativo', 'Gobierno', 'Micro']
                valor_encontrado = None
                
                for _ in range(15):  # Máximo 15 intentos (15 segundos)
                    time.sleep(1)
                    html = self.driver.page_source
                    
                    # Verificar si ya cargó un valor de segmento conocido
                    for segmento in segmentos_conocidos:
                        if f'>{segmento}<' in html or f'>{segmento.upper()}<' in html:
                            valor_encontrado = segmento
                            break
                    
                    if valor_encontrado:
                        break
                    
                    # También verificar con patrón regex por si el formato es diferente
                    pattern = r'PE Tipo de Cliente.{0,500}<lightning-formatted-text[^>]*>([^<]+)</lightning-formatted-text>'
                    match = re.search(pattern, html, re.DOTALL)
                    if match and match.group(1).strip():
                        valor_encontrado = match.group(1).strip()
                        break
                
                # Si encontró valor en la espera inteligente, retornarlo directamente
                if valor_encontrado:
                    self._volver_inicio()
                    return valor_encontrado
                
            except:
                if intento < MAX_INTENTOS:
                    self.driver.get("https://transforma.my.site.com/s/")
                    time.sleep(1)
                    return self.buscar_tipo_cliente(ruc, intento + 1)
                return "Sin Segmento"
            
            # Extraer valor con múltiples patrones
            html = self.driver.page_source
            
            # Patrón 1: Específico con span
            pattern1 = r'>PE Tipo de Cliente</span>.*?<lightning-formatted-text[^>]*>([^<]+)</lightning-formatted-text>'
            match = re.search(pattern1, html, re.DOTALL)
            if match and match.group(1).strip():
                valor = match.group(1).strip()
                self._volver_inicio()
                return valor
            
            # Patrón 2: Flexible con distancia mayor
            pattern2 = r'PE Tipo de Cliente.{0,800}<lightning-formatted-text[^>]*>([^<]+)</lightning-formatted-text>'
            match = re.search(pattern2, html, re.DOTALL)
            if match and match.group(1).strip():
                valor = match.group(1).strip()
                self._volver_inicio()
                return valor
            
            # Patrón 3: Buscar directamente valores conocidos de segmento cerca del label
            segmentos_conocidos = ['PYME', 'MAYOR', 'MAYORES', 'SOHO', 'CORPORATIVO', 'GOBIERNO', 'MICRO']
            for segmento in segmentos_conocidos:
                pattern3 = rf'PE Tipo de Cliente.{{0,300}}>({segmento})<'
                match = re.search(pattern3, html, re.DOTALL | re.IGNORECASE)
                if match:
                    valor = match.group(1).strip().upper()
                    self._volver_inicio()
                    return valor
            
            # Patrón 4: Buscar en data-value o value attribute
            pattern4 = r'PE.?Tipo.?de.?Cliente.*?(?:data-value|value)=["\']([^"\']+)["\']'
            match = re.search(pattern4, html, re.DOTALL | re.IGNORECASE)
            if match and match.group(1).strip():
                valor = match.group(1).strip()
                self._volver_inicio()
                return valor
            
            # Patrón 5: Buscar en cualquier elemento después del label
            pattern5 = r'PE Tipo de Cliente</span>\s*</dt>\s*<dd[^>]*>.*?>([^<]+)<'
            match = re.search(pattern5, html, re.DOTALL)
            if match and match.group(1).strip():
                valor = match.group(1).strip()
                self._volver_inicio()
                return valor
            
            # No encontró valor - reintentar (puede ser que no cargó bien)
            if intento < MAX_INTENTOS:
                self.driver.get("https://transforma.my.site.com/s/")
                time.sleep(1)
                return self.buscar_tipo_cliente(ruc, intento + 1)
            
            self._volver_inicio()
            return "Sin Datos"
            
        except Exception as e:
            print(f"Error RUC {ruc}: {str(e)[:30]}")
            if intento < MAX_INTENTOS:
                try:
                    self.driver.get("https://transforma.my.site.com/s/")
                    time.sleep(1)
                    return self.buscar_tipo_cliente(ruc, intento + 1)
                except:
                    pass
            return None
    
    def _volver_inicio(self):
        """Vuelve al inicio de forma inteligente"""
        self.driver.get("https://transforma.my.site.com/s/")
        # Esperar que cargue el buscador (máx 3s, sale antes si aparece)
        try:
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Search...']"))
            )
        except:
            pass  # Continuar de todos modos
    
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
