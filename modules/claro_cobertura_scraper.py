"""
Scraper para el Portal de Factibilidad de Claro
Consulta cobertura de internet y delivery usando coordenadas
"""
import os
import sys
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

# Importar config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from config import FACTIBILIDAD_USERNAME, FACTIBILIDAD_PASSWORD, FACTIBILIDAD_URL
except ImportError:
    FACTIBILIDAD_USERNAME = 'D99957628'
    FACTIBILIDAD_PASSWORD = 'Europa1234*'
    FACTIBILIDAD_URL = 'https://172.19.90.243/portalfactibilidad/public/'

class ClaroCoberturaScraper:
    """Scraper para consultar cobertura en el portal de Factibilidad de Claro"""
    
    BASE_URL = FACTIBILIDAD_URL.rstrip('/')
    
    def __init__(self, username=None, password=None, headless=False):
        self.username = username or FACTIBILIDAD_USERNAME
        self.password = password or FACTIBILIDAD_PASSWORD
        self.headless = headless
        self.driver = None
        self.logged_in = False
    
    def _init_driver(self):
        """Inicializa el driver de Chrome con opciones necesarias"""
        if self.driver:
            return
        
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')
        
        # Ignorar errores de certificado SSL
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument('--allow-insecure-localhost')
        options.add_argument('--disable-web-security')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        # Aceptar certificados inseguros
        options.set_capability('acceptInsecureCerts', True)
        
        # Selenium 4.6+ auto-detecta y descarga ChromeDriver correcto
        self.driver = webdriver.Chrome(options=options)
        self.driver.set_page_load_timeout(30)
    
    def _check_session_expired(self):
        """Verifica si la sesión expiró (redirigido a login)"""
        current_url = self.driver.current_url
        return '/login' in current_url or 'Login' in self.driver.title
    
    def login(self):
        """Inicia sesión en el portal de Factibilidad"""
        self._init_driver()
        
        try:
            self.driver.get(f"{self.BASE_URL}/login")
            time.sleep(3)  # Esperar más por el certificado SSL
            
            # Esperar a que cargue el formulario
            wait = WebDriverWait(self.driver, 15)
            
            # Ingresar usuario (primer input de texto)
            try:
                user_input = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[type='text']")
                ))
            except:
                # Intentar otro selector
                user_input = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input:not([type='password']):not([type='hidden'])")
                ))
            
            user_input.clear()
            user_input.send_keys(self.username)
            time.sleep(0.5)
            
            # Ingresar contraseña
            pass_input = self.driver.find_element(By.ID, "inputPass")
            pass_input.clear()
            pass_input.send_keys(self.password)
            time.sleep(0.5)
            
            # Click en Acceder
            login_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_btn.click()
            time.sleep(3)
            
            # Manejar modal de sesión existente
            try:
                continuar_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Continuar')]")
                continuar_btn.click()
                time.sleep(2)
            except:
                pass
            
            # Verificar login exitoso
            if '/login' not in self.driver.current_url:
                self.logged_in = True
                return True
            else:
                return False
                
        except Exception as e:
            return False
    
    def _ensure_logged_in(self):
        """Asegura que la sesión esté activa, reloguea si es necesario"""
        if not self.driver:
            return self.login()
        
        if self._check_session_expired():
            print("⚠️ Sesión expirada, relogueando...")
            self.logged_in = False
            return self.login()
        
        return self.logged_in
    
    def consultar_internet(self, lat, lng):
        """
        Consulta cobertura de internet por coordenadas
        
        Args:
            lat: Latitud (ej: -12.046374)
            lng: Longitud (ej: -77.042793)
        
        Returns:
            dict con información de cobertura o None si hay error
        """
        if not self._ensure_logged_in():
            return {"error": "No se pudo iniciar sesión"}
        
        try:
            print(f"🔍 Consultando cobertura de internet para: {lat}, {lng}")
            
            # Navegar a búsqueda por coordenadas
            self.driver.get(f"{self.BASE_URL}/buscar-casa-coordenada/31")
            time.sleep(2)
            
            wait = WebDriverWait(self.driver, 10)
            
            # Ingresar coordenadas
            coord_input = wait.until(EC.presence_of_element_located(
                (By.ID, "input_lat_lon")
            ))
            coord_input.clear()
            coord_input.send_keys(f"{lat}, {lng}")
            
            # Click en Buscar
            buscar_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Buscar')]")
            buscar_btn.click()
            time.sleep(3)
            
            # Click en Confirmar
            try:
                confirmar_btn = wait.until(EC.element_to_be_clickable(
                    (By.XPATH, "//button[contains(text(), 'Confirmar')]")
                ))
                confirmar_btn.click()
                time.sleep(2)
            except TimeoutException:
                return {"error": "No se encontró cobertura para estas coordenadas", "lat": lat, "lng": lng}
            
            # Extraer resultados del modal
            result = self._extraer_resultado_internet()
            result["lat"] = lat
            result["lng"] = lng
            
            return result
            
        except Exception as e:
            print(f"❌ Error consultando internet: {str(e)}")
            return {"error": str(e), "lat": lat, "lng": lng}
    
    def _extraer_resultado_internet(self):
        """Extrae la información del modal de cobertura de internet"""
        result = {
            "tipo": "INTERNET",
            "cobertura_alambrica": "NO",
            "cobertura_inalambrica": "NO",
            "tecnologia": "---",
            "plano": "---",
            "velocidad": "---",
            "vendor": "---",
            "estado": "SIN COBERTURA"
        }
        
        try:
            # Método 1: Buscar en tabla del modal
            try:
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tr, .modal-body tr, #coberturaModal tr")
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 2:
                            label = cells[0].text.strip().upper()
                            value = cells[1].text.strip()
                            
                            if "PLANO" in label and value:
                                result["plano"] = value
                            elif "TECNOLOG" in label and value:
                                result["tecnologia"] = value.upper()
                            elif "VELOCIDAD" in label and value:
                                result["velocidad"] = value
                            elif "VENDOR" in label and value:
                                result["vendor"] = value.upper()
                    except:
                        continue
            except:
                pass
            
            # Método 2: Buscar en texto de página
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.upper()
            
            # Detectar cobertura
            if "CON COBERTURA" in page_text:
                result["estado"] = "CON COBERTURA"
                result["cobertura_alambrica"] = "SI"
            
            if "CON COBERTURA ALÁMBRICA" in page_text or "CON COBERTURA ALAMBRICA" in page_text:
                result["cobertura_alambrica"] = "SI"
            
            if "CON COBERTURA INALÁMBRICA" in page_text or "CON COBERTURA INALAMBRICA" in page_text:
                result["cobertura_inalambrica"] = "SI"
            
            # Si no encontró en tabla, buscar en texto
            if result["plano"] == "---":
                match = re.search(r'PLANO\s+([A-Z0-9\-]+)', page_text)
                if match:
                    result["plano"] = match.group(1)
            
            if result["tecnologia"] == "---":
                tecnologias = ["FTTH", "HFC", "IFI 5G", "IFI LIMITADO", "COBRE"]
                for tec in tecnologias:
                    if tec in page_text:
                        result["tecnologia"] = tec
                        break
            
            if result["velocidad"] == "---":
                match = re.search(r'VELOCIDAD[^\d]*(\d+\s*MB)', page_text)
                if match:
                    result["velocidad"] = match.group(1)
            
            if result["vendor"] == "---":
                vendors = ["HUAWEI", "ZTE", "NOKIA", "CALIX"]
                for v in vendors:
                    if v in page_text:
                        result["vendor"] = v
                        break
            
            # Determinar estado final
            if result["cobertura_alambrica"] == "SI" or result["cobertura_inalambrica"] == "SI":
                result["estado"] = "CON COBERTURA"
                
        except Exception as e:
            result["error"] = f"Error extrayendo datos: {str(e)}"
        
        return result
    
    def consultar_delivery(self, lat, lng):
        """
        Consulta cobertura de delivery por coordenadas
        
        Args:
            lat: Latitud (ej: -12.046374)
            lng: Longitud (ej: -77.042793)
        
        Returns:
            dict con información de cobertura delivery
        """
        if not self._ensure_logged_in():
            return {"error": "No se pudo iniciar sesión"}
        
        try:
            # Navegar a cobertura delivery
            self.driver.get(f"{self.BASE_URL}/cobertura-delivery")
            time.sleep(3)
            
            wait = WebDriverWait(self.driver, 15)
            
            # Esperar a que cargue el mapa
            time.sleep(2)
            
            # Click en la LUPA para abrir panel de búsqueda
            try:
                lupa_btn = wait.until(EC.element_to_be_clickable(
                    (By.ID, "btn_search_dir")
                ))
                lupa_btn.click()
                time.sleep(1.5)
            except:
                # Intentar con otro selector
                try:
                    lupa_btn = self.driver.find_element(By.CSS_SELECTOR, "[id*='search'], .btn-search, button[title*='Buscar']")
                    lupa_btn.click()
                    time.sleep(1.5)
                except:
                    pass
            
            # Click en tab "Coordenadas"
            try:
                # Buscar en los tabs del panel
                tabs = self.driver.find_elements(By.CSS_SELECTOR, ".btn_searcher_tab button, .nav-tabs a, .nav-link")
                for tab in tabs:
                    if 'Coordenadas' in tab.text or 'coordenadas' in tab.text.lower():
                        tab.click()
                        time.sleep(1)
                        break
            except:
                pass
            
            # Ingresar coordenadas
            try:
                coord_input = wait.until(EC.presence_of_element_located(
                    (By.ID, "input_coordenadas")
                ))
            except:
                coord_input = wait.until(EC.presence_of_element_located(
                    (By.CSS_SELECTOR, "input[placeholder*='coordenadas'], input[id*='coord']")
                ))
            
            coord_input.clear()
            coord_input.send_keys(f"{lat}, {lng}")
            time.sleep(0.5)
            
            # Click en Buscar
            try:
                buscar_btn = self.driver.find_element(By.ID, "btn_search")
            except:
                buscar_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Buscar')]")
            buscar_btn.click()
            time.sleep(3)
            
            # Click en Confirmar
            try:
                confirmar_btn = wait.until(EC.element_to_be_clickable(
                    (By.ID, "btn_confirmar")
                ))
                confirmar_btn.click()
                time.sleep(2)
            except:
                try:
                    confirmar_btn = wait.until(EC.element_to_be_clickable(
                        (By.XPATH, "//button[contains(text(), 'Confirmar')]")
                    ))
                    confirmar_btn.click()
                    time.sleep(2)
                except TimeoutException:
                    return {"error": "No se encontró cobertura delivery para estas coordenadas", "lat": lat, "lng": lng}
            
            # Extraer resultados
            result = self._extraer_resultado_delivery()
            result["lat"] = lat
            result["lng"] = lng
            
            return result
            
        except Exception as e:
            print(f"❌ Error consultando delivery: {str(e)}")
            return {"error": str(e), "lat": lat, "lng": lng}
    
    def _extraer_resultado_delivery(self):
        """Extrae la información del modal de cobertura delivery"""
        result = {
            "tipo": "DELIVERY",
            "distrito": "---",
            "plano": "---",
            "zona_toa": "---",
            "color": "---",
            "estado": "SIN COBERTURA",
            "condicion": "---",
            "tiene_cobertura": False
        }
        
        try:
            # Método 1: Buscar en tabla del modal
            try:
                # Buscar todas las filas de tabla
                rows = self.driver.find_elements(By.CSS_SELECTOR, "table tr, .modal-body tr, #coberturaModal tr")
                for row in rows:
                    try:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        if len(cells) >= 2:
                            label = cells[0].text.strip().upper()
                            value = cells[1].text.strip()
                            
                            if "DISTRITO" in label and value:
                                result["distrito"] = value
                            elif "PLANO" in label and value:
                                result["plano"] = value
                            elif "ZONA" in label and "TOA" in label and value:
                                result["zona_toa"] = value
                            elif "COLOR" in label and value:
                                result["color"] = value.upper()
                            elif "ESTADO" in label and value:
                                result["estado"] = value.upper()
                            elif "CONDICION" in label and value:
                                result["condicion"] = value.upper()
                    except:
                        continue
            except:
                pass
            
            # Método 2: Buscar en texto de página si no encontró
            page_text = self.driver.find_element(By.TAG_NAME, "body").text.upper()
            
            # Si no encontró distrito, buscar en texto
            if result["distrito"] == "---":
                # Buscar patrón DISTRITO seguido de texto
                lines = page_text.split('\n')
                for i, line in enumerate(lines):
                    if 'DISTRITO' in line and i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if next_line and not any(x in next_line for x in ['PLANO', 'ZONA', 'COLOR']):
                            result["distrito"] = next_line
                            break
                        # Buscar en misma línea
                        parts = line.split('DISTRITO')
                        if len(parts) > 1:
                            val = parts[1].strip().split()[0] if parts[1].strip() else ""
                            if val and val not in [':', '']:
                                result["distrito"] = val
                                break
            
            # Similar para plano
            if result["plano"] == "---":
                match = re.search(r'PLANO\s+([A-Z0-9\-]+)', page_text)
                if match:
                    result["plano"] = match.group(1)
            
            # Similar para zona_toa
            if result["zona_toa"] == "---":
                match = re.search(r'ZONA[_\s]*TOA\s+(\d+)', page_text)
                if match:
                    result["zona_toa"] = match.group(1)
            
            # Color si no se encontró
            if result["color"] == "---":
                colores = ["AZUL", "CELESTE", "VERDE", "AMARILLO", "ROJO", "NARANJA"]
                for color in colores:
                    if color in page_text:
                        result["color"] = color
                        break
            
            # Estado
            if "CON COBERTURA" in page_text:
                result["tiene_cobertura"] = True
                match = re.search(r'CON COBERTURA\s*\(([^)]+)\)', page_text)
                if match:
                    result["estado"] = f"CON COBERTURA ({match.group(1).strip()})"
                else:
                    result["estado"] = "CON COBERTURA"
            
            # Condición
            if result["condicion"] == "---":
                if "LUNES A DOMINGO" in page_text:
                    result["condicion"] = "LUNES A DOMINGO"
                elif "LUNES A VIERNES" in page_text:
                    result["condicion"] = "LUNES A VIERNES"
                    
        except Exception as e:
            result["error"] = f"Error extrayendo datos: {str(e)}"
        
        return result
    
    def formatear_respuesta_internet(self, result):
        """Formatea la respuesta de internet para WhatsApp"""
        if "error" in result and result.get("error"):
            return f"""⚠️ Error en consulta:
{result.get('error', 'Error desconocido')}

📍 Coordenadas:
Lat: {result.get('lat', 'N/A')}
Lng: {result.get('lng', 'N/A')}"""
        
        emoji = "✅" if result.get("estado") == "CON COBERTURA" else "❌"
        
        return f"""📡 Resultado de cobertura:
🌐 Cobertura de Internet {emoji}

- ALÁMBRICA: {result.get('cobertura_alambrica', 'NO')}
- INALÁMBRICA: {result.get('cobertura_inalambrica', 'NO')}
- TECNOLOGÍA: {result.get('tecnologia', 'N/A')}
- ESTADO: {result.get('estado', 'DESCONOCIDO')}

📍 Coordenadas:
Lat: {result.get('lat', 'N/A')}
Lng: {result.get('lng', 'N/A')}

FACC"""
    
    def formatear_respuesta_delivery(self, result):
        """Formatea la respuesta de delivery para WhatsApp"""
        if "error" in result and result.get("error"):
            return f"""⚠️ Error en consulta:
{result.get('error', 'Error desconocido')}

📍 Coordenadas:
Lat: {result.get('lat', 'N/A')}
Lng: {result.get('lng', 'N/A')}"""
        
        tiene_cobertura = "CON COBERTURA" in result.get("estado", "")
        emoji = "✅" if tiene_cobertura else "❌"
        
        return f"""📡 Resultado de cobertura:
📦 Cobertura por Delivery {emoji}

- DISTRITO: {result.get('distrito', '---')}
- PLANO: {result.get('plano', '---')}
- ZONA_TOA: {result.get('zona_toa', '---')}
- COLOR: {result.get('color', '---')}
- ESTADO: {result.get('estado', 'DESCONOCIDO')}
- CONDICION: {result.get('condicion', '---')}

📍 Coordenadas:
Lat: {result.get('lat', 'N/A')}
Lng: {result.get('lng', 'N/A')}

FACC"""
    
    def close(self):
        """Cierra el navegador"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logged_in = False
            print("🔒 Navegador cerrado")


# Para pruebas directas
if __name__ == "__main__":
    scraper = ClaroCoberturaScraper()
    
    try:
        # Probar login
        if scraper.login():
            # Probar consulta delivery
            result = scraper.consultar_delivery(-12.046374, -77.042793)
            print("\n" + scraper.formatear_respuesta_delivery(result))
            
            # Probar consulta internet
            result = scraper.consultar_internet(-12.046374, -77.042793)
            print("\n" + scraper.formatear_respuesta_internet(result))
    finally:
        scraper.close()
