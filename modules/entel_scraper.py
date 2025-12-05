from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Optional
import time
import config

class EntelScraper:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.url_login = config.ENTEL_URL
        self.url_operaciones = 'https://entel.insolutions.pe/entelid-portal/Operation'
        self.logged_in = False
    
    def _init_driver(self):
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 15)
            print("Navegador Chrome inicializado (headless)")
    
    def login(self) -> bool:
        try:
            self._init_driver()
            self.driver.get(self.url_login)
            time.sleep(1)
            
            # Verificar si ya estamos logueados (si existe el menu de operaciones)
            try:
                self.driver.find_element(By.CSS_SELECTOR, "a[href='/entelid-portal/Operation']")
                print("Sesion ya iniciada")
                self.logged_in = True
                return True
            except:
                pass
            
            # Si no, hacer login
            try:
                email_input = self.wait.until(
                    EC.presence_of_element_located((By.ID, "Email"))
                )
                email_input.clear()
                email_input.send_keys(config.ENTEL_USERNAME)
                
                password_input = self.driver.find_element(By.ID, "Password")
                password_input.clear()
                password_input.send_keys(config.ENTEL_PASSWORD)
                
                # Marcar "Mantenerme conectado"
                try:
                    remember_checkbox = self.driver.find_element(By.ID, "RememberMe")
                    if not remember_checkbox.is_selected():
                        remember_checkbox.click()
                except:
                    pass
                
                print("Credenciales ingresadas")
                
                # Verificar si hay captcha visible
                captcha_visible = False
                try:
                    recaptcha = self.driver.find_element(By.ID, "recaptcha")
                    # Verificar si el iframe del recaptcha existe y es visible
                    iframes = recaptcha.find_elements(By.TAG_NAME, "iframe")
                    if iframes and any(iframe.is_displayed() for iframe in iframes):
                        captcha_visible = True
                except:
                    pass
                
                if captcha_visible:
                    print("CAPTCHA detectado. Resuelvelo y presiona ENTER...")
                    input()
                else:
                    # Click automatico en el boton de login
                    login_btn = self.driver.find_element(By.ID, "btnLgn")
                    login_btn.click()
                    print("Login automatico...")
                
                # Esperar a que el login sea exitoso
                time.sleep(2)
                
                # Verificar login exitoso
                try:
                    self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a[href='/entelid-portal/Operation']"))
                    )
                    print("Login exitoso")
                    self.logged_in = True
                    return True
                except:
                    print("Error: No se pudo verificar el login")
                    return False
                    
            except Exception as e:
                print(f"Error en login: {e}")
                return False
                
        except Exception as e:
            print(f"Error inicializando driver: {e}")
            return False
    
    def buscar_telefono(self, ruc: str) -> Optional[str]:
        if not self.logged_in:
            if not self.login():
                return None
        
        try:
            # Ir a Operaciones
            self.driver.get(self.url_operaciones)
            
            # Ingresar RUC
            ruc_input = self.wait.until(
                EC.presence_of_element_located((By.ID, "ruc"))
            )
            ruc_input.clear()
            ruc_input.send_keys(ruc)
            
            # Click en Filtro
            filter_btn = self.driver.find_element(By.ID, "filter")
            filter_btn.click()
            
            # Esperar a que la tabla termine de cargar
            max_intentos = 15
            tabla_cargada = False
            for intento in range(max_intentos):
                time.sleep(0.3)
                try:
                    info = self.driver.find_element(By.ID, "data-table_info")
                    info_text = info.text
                    
                    # Si dice 0 resultados, salir
                    if "0 to 0" in info_text or "0 entries" in info_text:
                        return None
                    
                    # Verificar que hay resultados Y que las filas estan cargadas
                    if "Showing" in info_text and "Loading" not in info_text:
                        tbody = self.driver.find_element(By.CSS_SELECTOR, "#data-table tbody")
                        filas = tbody.find_elements(By.TAG_NAME, "tr")
                        if filas and len(filas) > 0:
                            celdas = filas[0].find_elements(By.TAG_NAME, "td")
                            if len(celdas) >= 5 and celdas[4].text.strip():
                                tabla_cargada = True
                                break
                except:
                    pass
            
            if not tabla_cargada:
                return None
            
            # Buscar el telefono en la tabla
            try:
                tbody = self.driver.find_element(By.CSS_SELECTOR, "#data-table tbody")
                filas = tbody.find_elements(By.TAG_NAME, "tr")
                
                if not filas:
                    return None
                
                # El telefono esta en la 5ta columna (indice 4)
                primera_fila = filas[0]
                celdas = primera_fila.find_elements(By.TAG_NAME, "td")
                
                if len(celdas) >= 5:
                    telefono = celdas[4].text.strip()
                    # Validar telefono: 9 digitos empezando con 9, o 11 digitos empezando con 519
                    if telefono and telefono.isdigit():
                        if (len(telefono) == 9 and telefono.startswith('9')) or \
                           (len(telefono) == 11 and telefono.startswith('519')):
                            print(f"Telefono: {telefono}")
                            return telefono
                    return None
                else:
                    return None
                    
            except Exception as e:
                print(f"Error tabla: {e}")
                return None
                
        except Exception as e:
            print(f"Error buscando telefono para RUC {ruc}: {e}")
            return None
    
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logged_in = False
            print("Navegador cerrado")
