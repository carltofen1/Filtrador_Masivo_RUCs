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
import os
from datetime import datetime

# Archivo de log para debug
LOG_FILE = os.path.join(os.path.dirname(__file__), '..', 'segmentacion_debug.log')

# Contadores globales de errores (para resumen)
ERROR_STATS = {
    'timeout': 0,
    'no_existe': 0,
    'error_click': 0,
    'patron_no_encontrado': 0,
    'exito': 0
}

def log_debug(mensaje, tipo_error=None):
    """Escribe mensaje de debug al archivo log y actualiza contadores"""
    global ERROR_STATS
    if tipo_error and tipo_error in ERROR_STATS:
        ERROR_STATS[tipo_error] += 1
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(f"{datetime.now().strftime('%H:%M:%S')} - {mensaje}\n")

def get_error_stats():
    """Retorna las estadísticas de errores"""
    return ERROR_STATS.copy()

def reset_error_stats():
    """Resetea los contadores de errores"""
    global ERROR_STATS
    for key in ERROR_STATS:
        ERROR_STATS[key] = 0

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
        self.wait = WebDriverWait(self.driver, 8)  # Reducido de 15 a 8 segundos
        self.logged_in = False
        
        # NUEVO: Contadores para recuperación automática
        self.errores_consecutivos = 0
        self.rucs_desde_ultimo_refresh = 0
        self.MAX_ERRORES_ANTES_REFRESH = 3  # Después de 3 errores seguidos, hacer refresh
        self.RUCS_ANTES_REFRESH = 200  # Hacer refresh preventivo cada 200 RUCs
    
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
    
    def refresh_session(self):
        """
        Refresca la sesión haciendo F5 y verificando que el buscador siga disponible.
        Si falla, hace re-login completo.
        """
        try:
            log_debug("Refrescando sesión (F5)...")
            self.driver.refresh()  # F5
            time.sleep(2)
            
            # Verificar si el buscador sigue disponible
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Search...']"))
                )
                log_debug("Refresh exitoso - sesión válida")
                self.errores_consecutivos = 0
                self.rucs_desde_ultimo_refresh = 0
                return True
            except:
                # El buscador no apareció - sesión expirada, hacer re-login
                log_debug("Sesión expirada después del refresh - haciendo re-login...")
                return self.relogin()
                
        except Exception as e:
            log_debug(f"Error en refresh: {str(e)}")
            return self.relogin()
    
    def relogin(self):
        """
        Cierra completamente el navegador y abre uno nuevo para restaurar la sesión.
        Esto libera memoria y asegura un estado completamente limpio.
        """
        try:
            log_debug("Haciendo re-login completo - cerrando navegador y abriendo nuevo...")
            self.logged_in = False
            
            # CERRAR navegador actual completamente
            try:
                self.driver.quit()
            except:
                pass
            
            time.sleep(1)
            
            # CREAR nuevo navegador con las mismas opciones
            options = Options()
            # Si estaba en headless, mantenerlo (aunque no lo recomiendo para Salesforce)
            options.add_argument('--headless=new')  # Mantener headless si estaba activo
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
            self.wait = WebDriverWait(self.driver, 8)
            
            # Hacer login normal
            result = self.login()
            if result:
                log_debug("Re-login exitoso - navegador nuevo funcionando")
                self.errores_consecutivos = 0
                self.rucs_desde_ultimo_refresh = 0
            return result
            
        except Exception as e:
            log_debug(f"Error en re-login: {str(e)}")
            return False
    
    def buscar_tipo_cliente(self, ruc, intento=1):
        """
        VERSIÓN OPTIMIZADA - Busca RUC y extrae segmento de forma rápida.
        Solo marca "Sin Segmento" si aparece el mensaje explícito de no encontrado.
        """
        MAX_INTENTOS = 2  # Reducido para velocidad
        
        try:
            if not self.logged_in:
                # Intentar re-login si no estamos logueados
                if not self.relogin():
                    return "ERROR_NO_LOGUEADO"
            
            # REFRESH PREVENTIVO cada N RUCs para evitar saturación
            self.rucs_desde_ultimo_refresh += 1
            if self.rucs_desde_ultimo_refresh >= self.RUCS_ANTES_REFRESH:
                log_debug(f"Refresh preventivo después de {self.rucs_desde_ultimo_refresh} RUCs")
                self.refresh_session()
            
            # Obtener buscador (ya debería estar disponible)
            search_input = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder='Search...']"))
            )
            
            # Limpiar y escribir RUC - SIN ESPERAS INNECESARIAS
            search_input.send_keys(Keys.CONTROL + "a")
            search_input.send_keys(Keys.DELETE)
            search_input.send_keys(ruc)
            search_input.send_keys(Keys.RETURN)
            
            # Esperar a que cargue (tiempo mínimo necesario)
            time.sleep(0.6)
            
            # ESTRATEGIA RÁPIDA: Buscar el link del cliente
            try:
                cliente_link = WebDriverWait(self.driver, 4).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.outputLookupLink"))
                )
                # ¡ENCONTRADO! Click inmediato
                cliente_link.click()
                
            except:
                # No apareció link - verificar si es "no encontrado"
                if "No se han encontrado resultados" in self.driver.page_source:
                    # ESPERAR 0.75s y verificar que el mensaje SIGUE AHÍ (es fijo, no transitorio)
                    time.sleep(0.75)
                    if "No se han encontrado resultados" in self.driver.page_source:
                        log_debug(f"{ruc} - Sin Segmento (confirmado estable)", 'no_existe')
                        return "Sin Segmento"
                    # El mensaje desapareció = era transitorio, reintentar
                
                # No hay mensaje o era transitorio - reintentar si quedan intentos
                if intento < MAX_INTENTOS:
                    self._volver_inicio_rapido()
                    return self.buscar_tipo_cliente(ruc, intento + 1)
                
                log_debug(f"{ruc} - TIMEOUT sin resultado claro", 'timeout')
                return "ERROR_DESCONOCIDO"
            
            # Click exitoso - EXTRAER SEGMENTO RÁPIDO
            # Esperar que cargue la página del cliente
            time.sleep(0.8)
            
            # Loop rápido para extraer el segmento (máximo 2 segundos)
            for _ in range(4):
                html = self.driver.page_source
                
                # PATRÓN ÚNICO OPTIMIZADO: Buscar PE Tipo de Cliente
                match = re.search(
                    r'PE.?Tipo.?de.?Cliente.{0,500}?<lightning-formatted-text[^>]*>([^<]+)</lightning-formatted-text>',
                    html, re.DOTALL | re.IGNORECASE
                )
                if match:
                    valor = match.group(1).strip()
                    if valor and len(valor) > 1:
                        log_debug(f"{ruc} - OK: {valor}", 'exito')
                        self.errores_consecutivos = 0  # RESETEAR en éxito
                        self._volver_inicio_rapido()
                        return valor
                
                # Patrón alternativo: data-value
                match2 = re.search(
                    r'PE.?Tipo.?de.?Cliente.*?data-value=["\']([^"\']+)["\']',
                    html, re.DOTALL | re.IGNORECASE
                )
                if match2:
                    valor = match2.group(1).strip()
                    if valor and len(valor) > 1:
                        log_debug(f"{ruc} - OK: {valor}", 'exito')
                        self.errores_consecutivos = 0  # RESETEAR en éxito
                        self._volver_inicio_rapido()
                        return valor
                
                time.sleep(0.5)
            
            # No encontró segmento - reintentar o marcar error
            if intento < MAX_INTENTOS:
                self._volver_inicio_rapido()
                return self.buscar_tipo_cliente(ruc, intento + 1)
            
            self._volver_inicio_rapido()
            log_debug(f"{ruc} - Patrón no encontrado", 'patron_no_encontrado')
            return "Sin Datos"
            
        except Exception as e:
            self.errores_consecutivos += 1
            log_debug(f"{ruc} - Excepción #{self.errores_consecutivos}: {str(e)[:50]}")
            
            # Si hay muchos errores consecutivos, la sesión probablemente expiró
            if self.errores_consecutivos >= self.MAX_ERRORES_ANTES_REFRESH:
                log_debug(f"Detectados {self.errores_consecutivos} errores consecutivos - refrescando sesión")
                if self.refresh_session():
                    # Sesión restaurada - reintentar este RUC
                    return self.buscar_tipo_cliente(ruc, intento=1)
                else:
                    return "ERROR_SESION_PERDIDA"
            
            if intento < MAX_INTENTOS:
                try:
                    self._volver_inicio_rapido()
                    return self.buscar_tipo_cliente(ruc, intento + 1)
                except:
                    pass
            return "ERROR_EXCEPCION"
    
    def _volver_inicio_rapido(self):
        """Vuelve al inicio ULTRA RÁPIDO"""
        try:
            # Presionar Escape para cerrar cualquier modal y luego buscar el logo
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            logo = self.driver.find_element(By.CSS_SELECTOR, "a.siteforceContentLogo, .slds-global-header__logo, a[href='/s/']")
            logo.click()
            time.sleep(0.3)
            return
        except:
            pass
        # Fallback: navegación directa
        self.driver.get("https://transforma.my.site.com/s/")
        time.sleep(0.3)
    
    def _volver_inicio(self):
        """Vuelve al inicio de forma inteligente"""
        self._volver_inicio_rapido()
        try:
            WebDriverWait(self.driver, 2).until(
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
