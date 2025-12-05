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
            print("Navegador Chrome inicializado")
    
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
                    
                    # Navegar a Operaciones para "calentar" la sesion
                    self.driver.get(self.url_operaciones)
                    time.sleep(1)
                    
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
            time.sleep(0.5)
            
            # Ingresar RUC
            ruc_input = self.wait.until(
                EC.presence_of_element_located((By.ID, "ruc"))
            )
            ruc_input.clear()
            ruc_input.send_keys(ruc)
            
            # Click en Filtro
            self.driver.find_element(By.ID, "filter").click()
            
            # Esperar y leer
            for i in range(30):
                time.sleep(0.5)
                try:
                    info = self.driver.find_element(By.ID, "data-table_info")
                    
                    if "0 to 0" in info.text:
                        return None
                    
                    if "Showing" in info.text:
                        tbody = self.driver.find_element(By.CSS_SELECTOR, "#data-table tbody")
                        filas = tbody.find_elements(By.TAG_NAME, "tr")
                        
                        if filas:
                            # Buscar en TODAS las filas hasta encontrar telefono valido
                            for fila in filas:
                                celdas = fila.find_elements(By.TAG_NAME, "td")
                                if len(celdas) >= 5:
                                    tel = celdas[4].text.strip()
                                    if tel:
                                        telefono = tel.replace(' ', '').replace('-', '')
                                        if telefono.isdigit() and len(telefono) >= 8:
                                            print(f"Telefono: {telefono}")
                                            return telefono
                            # Si ninguna fila tiene telefono valido
                            return None
                except:
                    pass
            
            return None
                
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logged_in = False
            print("Navegador cerrado")
