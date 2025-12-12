"""
Scraper para OSIPTEL - Checa tus líneas
Extrae la cantidad de líneas telefónicas registradas por RUC
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import re

class OsiptelScraper:
    def __init__(self, headless=True):
        self.url = "https://checatuslineas.osiptel.gob.pe"
        
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-notifications')
        options.add_argument('--disable-infobars')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--disable-plugins')
        options.add_argument('--dns-prefetch-disable')
        options.add_argument('--blink-settings=imagesEnabled=false')
        options.page_load_strategy = 'eager'  # Carga ultra rápida: solo espera al DOM
        
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        # Optimización agresiva: Bloquear imágenes, CSS, fuentes, etc.
        prefs = {
            "profile.managed_default_content_settings.images": 2,
            "profile.managed_default_content_settings.stylesheets": 2,
            "profile.managed_default_content_settings.fonts": 2,
            "profile.managed_default_content_settings.popups": 2,
            "profile.managed_default_content_settings.geolocation": 2,
            "profile.managed_default_content_settings.notifications": 2,
            "profile.managed_default_content_settings.media_stream": 2,
        }
        options.add_experimental_option("prefs", prefs)
        
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, 15)
        self.initialized = False
    
    def inicializar(self):
        """Navega a la página de OSIPTEL con reconexión robusta"""
        while True:
            try:
                print("Navegando a OSIPTEL...")
                self.driver.get(self.url)
                
                # Esperar a que cargue el select de tipo de documento
                self.wait.until(
                    EC.presence_of_element_located((By.ID, "IdTipoDoc"))
                )
                
                print("Página cargada correctamente")
                self.initialized = True
                return True
                
            except Exception as e:
                print(f"Error de conexión: {str(e)[:50]}")
                print("Reintentando en 5 segundos...")
                time.sleep(5)
    
    def consultar_lineas(self, ruc):
        """Consulta la cantidad de líneas para un RUC"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not self.initialized:
                    self.inicializar()
                
                # 1. Limpieza visual (si los elementos existen)
                try:
                    self.driver.execute_script("""
                        var tabla = document.getElementById('GridConsulta');
                        if(tabla) tabla.innerHTML = ''; 
                        var info = document.getElementById('GridConsulta_info');
                        if(info) info.innerHTML = '';
                    """)
                except:
                    pass

                # Esperar a que los inputs existan (Vital para modo eager)
                try:
                     self.wait.until(EC.presence_of_element_located((By.ID, "NumeroDocumento")))
                     self.wait.until(EC.presence_of_element_located((By.ID, "IdTipoDoc")))
                except:
                    # Si no aparecen rápido, refrescar
                    self.driver.refresh()
                    continue

                # Seleccionar RUC
                self.driver.execute_script("document.getElementById('IdTipoDoc').value = '2';")
                
                # Input RUC
                self.driver.execute_script(f"document.getElementById('NumeroDocumento').value = '{ruc}';")
                
                # Click Buscar
                self.driver.execute_script("document.getElementById('btnBuscar').click();")
                
                # Manejo de ALERTA inmediata tras buscar (ej: "Error del servidor")
                try:
                    WebDriverWait(self.driver, 1).until(EC.alert_is_present())
                    alert = self.driver.switch_to.alert
                    print(f"    [alert] Alerta al buscar: {alert.text}")
                    alert.accept()
                    raise Exception("Alerta bloqueante al buscar")
                except:
                    pass
                
                # Esperar a que DESAPAREZCA el "Procesando"
                try:
                    WebDriverWait(self.driver, 3).until(
                        EC.visibility_of_element_located((By.ID, "GridConsulta_processing"))
                    )
                    WebDriverWait(self.driver, 20).until(
                        EC.invisibility_of_element_located((By.ID, "GridConsulta_processing"))
                    )
                except:
                    # Si nunca apareció "Procesando", puede que haya sido instantáneo o falló el click
                    pass

                # Espera resultados
                try:
                    WebDriverWait(self.driver, 10).until(
                        lambda d: (d.find_elements(By.ID, "GridConsulta_info") and d.find_element(By.ID, "GridConsulta_info").text.strip() != "") or 
                                  "No se encontraron resultados" in d.page_source or
                                  "no se pudo procesar" in d.page_source.lower()
                    )
                except:
                    print(f"    [WARN] Timeout o datos vacíos para {ruc}. Reiniciando...")
                    self.driver.refresh()
                    continue
                
                # Verificar info
                try:
                    info_element = self.driver.find_element(By.ID, "GridConsulta_info")
                    info_text = info_element.text.strip()
                    
                    if not info_text:
                        # Si está vacío, es el JS de limpieza que pusimos => NO CARGÓ NADA NUEVO
                        raise Exception("La tabla sigue vacía, no cargó resultados nuevos")

                    match = re.search(r'de\s+(\d+)\s+totales', info_text, re.IGNORECASE)
                    if match:
                        return match.group(1)
                except Exception as e:
                    if "no cargó resultados nuevos" in str(e):
                        print(f"    [ERROR] {str(e)}. Reintentando...")
                        self.driver.refresh()
                        continue
                    pass

                html = self.driver.page_source
                
                # ... resto de validaciones ...
                
                # Detectar errores explícitos
                if "no se pudo procesar" in html.lower() or "inténtelo más tarde" in html.lower():
                    print("    [RATE LIMIT] Esperando 10 segundos...")
                    time.sleep(10)
                    self.inicializar()
                    continue
                
                # Verificar si no hay resultados EXPLÍCITAMENTE
                if "No se encontraron resultados" in html:
                    return "0"
                    
                # Si llegamos aquí y no hay "totales" ni "No se encontraron", es un fallo silencioso
                # Probablemente el error 500 o connection closed del AJAX
                print(f"    [ERROR] Fallo silencioso (posible error 500). Reintentando {attempt+1}/{max_retries}...")
                self.driver.refresh()
                time.sleep(3)
                continue
                
            except Exception as e:
                print(f"Error RUC {ruc}: {str(e)[:40]}")
                try:
                    self.inicializar()
                except:
                    pass
        
        return None

    def close(self):
        """Cierra el navegador"""
        try:
            self.driver.quit()
        except:
            pass
