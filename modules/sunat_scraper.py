import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException,
    WebDriverException, NoSuchElementException
)
from typing import Dict, Optional, List
import sys
import time
import re
import threading

# Evita que los íconos (⚠ ✗ →) tumben el programa en consolas sin UTF-8:
# si un carácter no se puede mostrar, se imprime "?" en vez de lanzar UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors='replace')
    except Exception:
        pass


_UC_INIT_LOCK = threading.Lock()

# uc.Chrome.__del__ vuelve a llamar quit() al recolectar el objeto y en Windows imprime
# "OSError: [WinError 6] Controlador no válido". Ya cerramos explícitamente en close().
uc.Chrome.__del__ = lambda self: None
_CHROME_PATHS = None


def _chrome_paths() -> Dict[str, str]:
    """
    Rutas de Chrome y de su chromedriver vía Selenium Manager.
    Usa el Chrome instalado si existe; si no, descarga "Chrome for Testing"
    con su chromedriver de la misma versión (así nunca hay desfase de versiones).
    """
    global _CHROME_PATHS
    if _CHROME_PATHS is None:
        from selenium.webdriver.common.selenium_manager import SeleniumManager
        _CHROME_PATHS = SeleniumManager().binary_paths(['--browser', 'chrome'])
    return _CHROME_PATHS


class SunatBloqueadoError(Exception):
    """SUNAT respondió con un challenge/bloqueo anti-bots (Cloudflare) en vez de la página."""


class SunatScraper:
    """
    Scraper optimizado para consultas de RUC en SUNAT.
    
    Mejoras sobre la versión anterior:
    - Reutiliza la sesión del navegador entre consultas
    - Usa WebDriverWait en lugar de time.sleep() fijos
    - Auto-recovery si el driver crashea
    - Extrae datos del DOM en una sola pasada
    - Reintentos inteligentes con backoff
    """
    
    MAX_RETRIES = 3
    WAIT_TIMEOUT = 12  # segundos para WebDriverWait
    PAGE_LOAD_TIMEOUT = 15
    
    # Departamentos del Perú (ordenados por longitud desc para matching correcto)
    DEPARTAMENTOS = sorted([
        "AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO", "CAJAMARCA",
        "CALLAO", "CUSCO", "HUANCAVELICA", "HUANUCO", "ICA", "JUNIN", "LA LIBERTAD",
        "LAMBAYEQUE", "LIMA", "LORETO", "MADRE DE DIOS", "MOQUEGUA", "PASCO",
        "PIURA", "PUNO", "SAN MARTIN", "TACNA", "TUMBES", "UCAYALI",
        "CALLAO (PROVINCIA CONSTITUCIONAL)"
    ], key=len, reverse=True)

    def __init__(self, headless: bool = False):
        # headless=False => Chrome visible pero minimizado: Cloudflare desafía al modo headless
        self.driver = None
        self.wait = None
        self.headless = headless
        self.url_base = "https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/jcrS00Alias"
        self._page_loaded = False  # Track si ya tenemos la página cargada
        self._consecutive_errors = 0
        
    def _init_driver(self):
        """Inicializa Chrome con undetected-chromedriver (evita la detección de Cloudflare)."""
        if self.driver is not None:
            return

        options = uc.ChromeOptions()

        if self.headless:
            options.add_argument('--headless=new')
        else:
            # Ventana real pero fuera de la pantalla: Cloudflare la ve como un Chrome
            # normal y no molesta. (Minimizada no sirve: el teclado no llega a los inputs.)
            options.add_argument('--window-position=-32000,-32000')

        options.add_argument('--window-size=1920,1080')
        options.add_argument('--disable-popup-blocking')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--log-level=3')
        # Sin imágenes ni notificaciones (no afecta la detección)
        options.add_argument('--blink-settings=imagesEnabled=false')
        options.add_experimental_option('prefs', {
            'profile.managed_default_content_settings.images': 2,
            'profile.default_content_setting_values.notifications': 2,
        })

        # uc parchea el chromedriver en disco: con varios workers en paralelo
        # se serializa la creación para que no se pisen entre ellos.
        with _UC_INIT_LOCK:
            rutas = _chrome_paths()
            self.driver = uc.Chrome(
                options=options,
                browser_executable_path=rutas['browser_path'],
                driver_executable_path=rutas['driver_path'],
                use_subprocess=True,
            )

        self.driver.set_page_load_timeout(self.PAGE_LOAD_TIMEOUT)

        self.wait = WebDriverWait(
            self.driver, self.WAIT_TIMEOUT,
            ignored_exceptions=[StaleElementReferenceException]
        )
        self._page_loaded = False
        print("Chrome (undetected) inicializado (headless)" if self.headless else "Chrome (undetected) inicializado")
    
    def _escribir(self, elemento, texto: str):
        """
        Escribe texto en un input. Con el chromedriver parchado por undetected-chromedriver
        send_keys() no genera eventos de teclado, así que se usa CDP Input.insertText
        (equivale a teclear) y, si aun así no quedó, se asigna el valor por JS.
        """
        self.driver.execute_script("arguments[0].value=''; arguments[0].focus();", elemento)
        try:
            self.driver.execute_cdp_cmd('Input.insertText', {'text': texto})
        except WebDriverException:
            pass
        if (elemento.get_attribute('value') or '') != texto:
            self.driver.execute_script(
                "arguments[0].value=arguments[1];"
                "arguments[0].dispatchEvent(new Event('input',{bubbles:true}));"
                "arguments[0].dispatchEvent(new Event('change',{bubbles:true}));",
                elemento, texto
            )

    def _clic(self, elemento):
        """Clic vía JS: en la página de SUNAT los clics nativos de WebDriver no llegan al handler."""
        self.driver.execute_script("arguments[0].click();", elemento)

    def _restart_driver(self):
        """Reinicia el driver por completo (auto-recovery)."""
        print("Reiniciando navegador...")
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass
        self.driver = None
        self.wait = None
        self._page_loaded = False
        self._init_driver()
    
    def _esta_bloqueado(self) -> bool:
        """True si SUNAT está mostrando el challenge/bloqueo de Cloudflare."""
        try:
            titulo = (self.driver.title or '').lower()
            url = self.driver.current_url or ''
        except WebDriverException:
            return False
        if '__cf_chl' in url:
            return True
        if any(t in titulo for t in ('just a moment', 'un momento', 'attention required',
                                     'access denied', 'acceso denegado')):
            return True
        try:
            src = self.driver.page_source[:20000]
        except WebDriverException:
            return False
        # Ojo: toda página normal de SUNAT trae "/cdn-cgi/challenge-platform/scripts/precursor";
        # solo la página del challenge carga "chl_page" / "_cf_chl_opt".
        return 'chl_page' in src or '_cf_chl_opt' in src or 'cf-turnstile-response' in src

    CHALLENGE_TIMEOUT = 20  # segundos que se le da al challenge de Cloudflare para resolverse solo

    def _verificar_bloqueo(self):
        # Con undetected-chromedriver el "Just a moment..." suele pasar solo en unos segundos
        limite = time.time() + self.CHALLENGE_TIMEOUT
        while self._esta_bloqueado() and time.time() < limite:
            time.sleep(1)
        if self._esta_bloqueado():
            raise SunatBloqueadoError(
                "SUNAT está bloqueando el navegador automatizado (Cloudflare). "
                "No es un error de tu PC ni del firewall."
            )

    def _navigate_to_search(self):
        """Navega a la página de búsqueda y asegura que el form esté listo."""
        try:
            self.driver.get(self.url_base)
            self._verificar_bloqueo()

            # Esperar a que el input de RUC esté presente
            try:
                self.wait.until(
                    EC.presence_of_element_located((By.ID, "txtRuc"))
                )
            except TimeoutException:
                self._verificar_bloqueo()
                raise
            
            # Intentar click en pestaña RUC (puede que ya esté seleccionada)
            try:
                tab_ruc = self.driver.find_element(By.ID, "btnPorRuc")
                if tab_ruc.is_displayed():
                    self._clic(tab_ruc)
            except (NoSuchElementException, WebDriverException):
                pass  # Ya está en la pestaña correcta
            
            self._page_loaded = True
            
        except TimeoutException:
            print("Timeout cargando página de SUNAT")
            self._page_loaded = False
            raise
        except WebDriverException as e:
            print(f"Error navegando a SUNAT: {e}")
            self._page_loaded = False
            raise
    
    def consultar_ruc(self, ruc: str) -> Optional[Dict]:
        """
        Consulta un RUC en SUNAT y devuelve los datos extraídos.
        
        Incluye reintentos automáticos con recovery del driver si falla.
        """
        ruc = ruc.strip()
        if not ruc.isdigit() or len(ruc) != 11:
            print(f"RUC inválido: {ruc}")
            return None
        
        last_error = None
        
        for intento in range(self.MAX_RETRIES):
            try:
                self._init_driver()
                
                if intento == 0:
                    print(f"Consultando RUC: {ruc}")
                else:
                    print(f"Reintentando RUC {ruc} (intento {intento + 1}/{self.MAX_RETRIES})")
                
                # Siempre navegar de nuevo para resetear el estado del formulario
                self._navigate_to_search()
                
                # Ingresar RUC en el campo de búsqueda
                input_ruc = self.driver.find_element(By.ID, "txtRuc")
                self._escribir(input_ruc, ruc)
                
                # Verificar CAPTCHA
                self._handle_captcha()
                
                # Buscar
                btn_buscar = self.driver.find_element(By.ID, "btnAceptar")
                self._clic(btn_buscar)
                
                # Esperar resultados
                try:
                    self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h4.list-group-item-heading"))
                    )
                except TimeoutException:
                    self._verificar_bloqueo()
                    raise
                
                # Extraer datos
                resultado = self._extraer_datos(ruc)
                
                if resultado:
                    # Si falta representante legal en empresa, reintentar UNA vez
                    if (not resultado.get('representante_legal') 
                            and not resultado.get('sin_representante') 
                            and intento == 0):
                        print("Falta representante legal, reintentando...")
                        continue
                    
                    print(f"  → {resultado['razon_social']}")
                    self._consecutive_errors = 0
                    return resultado
                else:
                    print("No se pudieron extraer datos")
                    if intento < self.MAX_RETRIES - 1:
                        continue
                    return None
                
            except SunatBloqueadoError:
                # Reintentar no sirve: avisar al procesador para que se detenga
                raise

            except TimeoutException:
                last_error = "Timeout esperando respuesta de SUNAT"
                print(f"  ⚠ {last_error}")
                # Si timeout, probablemente SUNAT está lento - no reiniciar driver
                if intento < self.MAX_RETRIES - 1:
                    self._page_loaded = False
                    time.sleep(1)
                    
            except WebDriverException as e:
                last_error = str(e)[:80]
                print(f"  ⚠ Error del navegador: {last_error}")
                self._consecutive_errors += 1
                # Si el driver crasheó, reiniciarlo
                if self._consecutive_errors >= 2 or intento >= 1:
                    self._restart_driver()
                else:
                    self._page_loaded = False
                    
            except Exception as e:
                last_error = str(e)[:80]
                print(f"  ⚠ Error inesperado: {last_error}")
                if intento < self.MAX_RETRIES - 1:
                    self._restart_driver()
        
        print(f"  ✗ Fallaron todos los intentos para RUC {ruc}: {last_error}")
        return None
    
    def _handle_captcha(self):
        """Detecta y maneja CAPTCHA si aparece."""
        try:
            txt_codigo = self.driver.find_element(By.ID, "txtCodigo")
            if txt_codigo.is_displayed():
                print("⚠ CAPTCHA detectado. Resuelve el CAPTCHA en el navegador...")
                print("  Presiona ENTER aquí cuando hayas terminado...")
                input()
        except NoSuchElementException:
            pass  # No hay CAPTCHA, continuar
    
    def _extraer_datos(self, ruc: str) -> Optional[Dict]:
        """
        Extrae todos los datos de la página de resultados en una sola pasada.
        
        Optimizado: hace un solo find_elements para obtener todos los divs
        y los procesa en memoria, en lugar de múltiples queries al DOM.
        """
        try:
            es_persona_natural = ruc.startswith('10')
            
            resultado = {
                'ruc': ruc,
                'razon_social': '',
                'representante_legal': '',
                'documento_identidad': '',
                'departamento': '',
                'provincia': '',
                'distrito': '',
                'direccion': '',
                'tipo_contribuyente': '',
                'estado_contribuyente': 'DESCONOCIDO',
            }
            
            # --- Razón Social (del h4) ---
            try:
                h4_elements = self.driver.find_elements(By.CSS_SELECTOR, "h4.list-group-item-heading")
                target_h4 = None
                
                for h4 in h4_elements:
                    texto = h4.text.strip()
                    if texto.startswith(ruc):
                        target_h4 = h4
                        break
                
                if not target_h4:
                    for h4 in h4_elements:
                        if ruc in h4.text:
                            target_h4 = h4
                            break
                
                if not target_h4 and h4_elements:
                    target_h4 = h4_elements[0]
                
                if target_h4:
                    texto_completo = target_h4.text.strip()
                    if ' - ' in texto_completo:
                        resultado['razon_social'] = texto_completo.split(' - ', 1)[1].strip()
                    else:
                        resultado['razon_social'] = texto_completo
            except Exception as e:
                print(f"  No se pudo extraer Razón Social: {e}")
            
            # --- Extraer todos los list-group-item de una sola vez ---
            all_divs = self.driver.find_elements(By.CLASS_NAME, "list-group-item")
            
            for div in all_divs:
                try:
                    div_text = div.text
                except StaleElementReferenceException:
                    continue
                
                # Domicilio Fiscal
                if "Domicilio Fiscal:" in div_text:
                    try:
                        p_el = div.find_element(By.CSS_SELECTOR, "p.list-group-item-text")
                        self._parsear_direccion(p_el.text.strip(), resultado)
                    except (NoSuchElementException, StaleElementReferenceException):
                        pass
                
                # Estado del Contribuyente
                elif "Estado del Contribuyente:" in div_text:
                    try:
                        p_el = div.find_element(By.CSS_SELECTOR, "p.list-group-item-text")
                        resultado['estado_contribuyente'] = p_el.text.strip().upper()
                    except (NoSuchElementException, StaleElementReferenceException):
                        pass
                
                # Tipo de Documento (solo para persona natural)
                elif es_persona_natural and "Tipo de Documento:" in div_text:
                    try:
                        p_el = div.find_element(By.CSS_SELECTOR, "p.list-group-item-text")
                        texto_documento = p_el.text.strip()
                        # Formato: "DNI 70450683 - POZSGAI ACOSTA, PATRICK LAZSLO ARJUNA"
                        if ' - ' in texto_documento:
                            partes = texto_documento.split(' - ', 1)
                            resultado['documento_identidad'] = partes[0].strip()
                            resultado['representante_legal'] = partes[1].strip()
                    except (NoSuchElementException, StaleElementReferenceException):
                        pass
                
                # Tipo Contribuyente
                elif "Tipo Contribuyente:" in div_text:
                    try:
                        p_el = div.find_element(By.CSS_SELECTOR, "p.list-group-item-text")
                        resultado['tipo_contribuyente'] = p_el.text.strip()
                    except (NoSuchElementException, StaleElementReferenceException):
                        pass
            
            # Marcar persona natural
            if es_persona_natural:
                resultado['es_persona_natural'] = True
                resultado['sin_representante'] = True
            
            # --- Representante Legal (solo empresas) ---
            if not es_persona_natural:
                self._extraer_representante_legal(resultado)
            
            return resultado
            
        except Exception as e:
            print(f"  Error extrayendo datos: {e}")
            return None
    
    def _parsear_direccion(self, direccion_completa: str, resultado: Dict):
        """Parsea la dirección completa en departamento, provincia, distrito y dirección."""
        partes = [p.strip() for p in direccion_completa.split(' - ')]
        
        if len(partes) >= 3:
            resultado['distrito'] = partes[-1]
            resultado['provincia'] = partes[-2]
            
            resto = ' - '.join(partes[:-2]).strip()
            resto_upper = resto.upper()
            
            depto_encontrado = False
            for depto in self.DEPARTAMENTOS:
                if resto_upper.endswith(depto):
                    resultado['departamento'] = depto
                    direccion_final = resto[:-(len(depto))].strip().rstrip('-').strip()
                    resultado['direccion'] = direccion_final
                    depto_encontrado = True
                    break
            
            if not depto_encontrado:
                if len(partes) >= 4:
                    resultado['departamento'] = partes[-3]
                    resultado['direccion'] = ' - '.join(partes[:-3])
                else:
                    resultado['departamento'] = ''
                    resultado['direccion'] = resto
        else:
            resultado['direccion'] = direccion_completa
    
    def _extraer_representante_legal(self, resultado: Dict):
        """Extrae el representante legal haciendo click en el botón correspondiente."""
        try:
            # Verificar si existe el botón de representantes legales
            try:
                btn_rep_legal = self.wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnInfRepLeg"))
                )
            except TimeoutException:
                # No tiene representantes legales registrados
                resultado['sin_representante'] = True
                return
            
            self._clic(btn_rep_legal)
            
            # Esperar a que aparezca la tabla de representantes
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, "tbody"))
                )
            except TimeoutException:
                resultado['sin_representante'] = True
                return
            
            tbody = self.driver.find_element(By.TAG_NAME, "tbody")
            filas = tbody.find_elements(By.TAG_NAME, "tr")
            
            for fila in filas:
                celdas = fila.find_elements(By.TAG_NAME, "td")
                
                if len(celdas) >= 3:
                    tipo_doc = celdas[0].text.strip()
                    num_doc = celdas[1].text.strip()
                    nombre = celdas[2].text.strip()
                    
                    resultado['representante_legal'] = nombre
                    resultado['documento_identidad'] = f"{tipo_doc} {num_doc}"
                    break  # Solo el primero
                    
        except Exception as e:
            print(f"  No se pudo extraer Representante Legal: {e}")
    
    def consultar_por_razon_social(self, razon_social: str, max_resultados: int = 20) -> List[Dict]:
        """
        Busca en SUNAT por Razón Social y extrae datos de cada resultado.
        
        Args:
            razon_social: Nombre o razón social a buscar
            max_resultados: Máximo de resultados a procesar (default 20)
            
        Returns:
            Lista de diccionarios con datos de cada RUC encontrado
        """
        razon_social = razon_social.strip()
        if not razon_social or len(razon_social) < 2:
            print(f"Razón social muy corta: '{razon_social}'")
            return []
        
        for intento in range(self.MAX_RETRIES):
            try:
                self._init_driver()
                
                if intento == 0:
                    print(f"Buscando Razón Social: {razon_social}")
                else:
                    print(f"Reintentando '{razon_social}' (intento {intento + 1}/{self.MAX_RETRIES})")
                
                # Navegar a la página
                self.driver.get(self.url_base)
                self._verificar_bloqueo()
                self.wait.until(EC.presence_of_element_located((By.ID, "btnPorRazonSocial")))
                
                # Click en pestaña "Por Nomb./Raz.Soc."
                tab_rs = self.driver.find_element(By.ID, "btnPorRazonSocial")
                self._clic(tab_rs)
                
                # Esperar que aparezca el input de razón social
                self.wait.until(EC.presence_of_element_located((By.ID, "txtNombreRazonSocial")))
                
                # Ingresar la razón social
                input_rs = self.driver.find_element(By.ID, "txtNombreRazonSocial")
                self._escribir(input_rs, razon_social)
                
                # Verificar CAPTCHA
                self._handle_captcha()
                
                # Buscar
                btn_buscar = self.driver.find_element(By.ID, "btnAceptar")
                self._clic(btn_buscar)
                
                # Manejar posible alert de SUNAT (caracteres inválidos)
                try:
                    from selenium.webdriver.common.alert import Alert
                    time.sleep(0.3)
                    alert = self.driver.switch_to.alert
                    alert_text = alert.text
                    alert.accept()
                    print(f"  ⚠ SUNAT rechazó la búsqueda: {alert_text[:60]}")
                    return []
                except:
                    pass  # No hay alert, continuar
                
                # Esperar resultados (lista de RUCs)
                try:
                    self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "a.list-group-item.aRucs"))
                    )
                except TimeoutException:
                    print(f"  Sin resultados para '{razon_social}'")
                    return []
                
                # Extraer lista de resultados
                resultados_links = self.driver.find_elements(By.CSS_SELECTOR, "a.list-group-item.aRucs")
                total_encontrados = len(resultados_links)
                print(f"  Encontrados: {total_encontrados} resultados")
                
                # Extraer info básica de cada resultado de la lista
                resultados_basicos = []
                for link in resultados_links[:max_resultados]:
                    try:
                        h4s = link.find_elements(By.TAG_NAME, "h4")
                        ruc_text = h4s[0].text.strip() if len(h4s) > 0 else ''
                        nombre_text = h4s[1].text.strip() if len(h4s) > 1 else ''
                        
                        # Extraer RUC limpio del texto "RUC: 20123456789"
                        ruc = ''
                        if 'RUC:' in ruc_text:
                            ruc = ruc_text.replace('RUC:', '').strip()
                        elif ruc_text:
                            solo_digitos = ''.join(c for c in ruc_text if c.isdigit())
                            if len(solo_digitos) == 11:
                                ruc = solo_digitos
                        
                        # Extraer estado
                        estado = ''
                        try:
                            span_estado = link.find_element(By.CSS_SELECTOR, "p strong span")
                            estado = span_estado.text.strip().upper()
                        except NoSuchElementException:
                            pass
                        
                        if ruc:
                            resultados_basicos.append({
                                'ruc': ruc,
                                'razon_social': nombre_text,
                                'estado_contribuyente': estado
                            })
                    except (StaleElementReferenceException, IndexError):
                        continue
                
                
                print(f"  ✓ {len(resultados_basicos)} RUCs extraídos para '{razon_social}'")
                self._consecutive_errors = 0
                return resultados_basicos
                
            except SunatBloqueadoError:
                raise

            except TimeoutException:
                print(f"  ⚠ Timeout buscando '{razon_social}'")
                if intento < self.MAX_RETRIES - 1:
                    self._page_loaded = False
                    time.sleep(1)
                    
            except WebDriverException as e:
                print(f"  ⚠ Error del navegador: {str(e)[:80]}")
                self._consecutive_errors += 1
                if self._consecutive_errors >= 2:
                    self._restart_driver()
                    
            except Exception as e:
                print(f"  ⚠ Error inesperado: {str(e)[:80]}")
                if intento < self.MAX_RETRIES - 1:
                    self._restart_driver()
        
        print(f"  ✗ Fallaron todos los intentos para '{razon_social}'")
        return []

    def close(self):
        """Cierra el navegador y libera recursos."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None
            self.wait = None
            self._page_loaded = False
            print("Navegador cerrado")
