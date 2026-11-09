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
    # Extrae de la página de resultados los h4 y cada recuadro con su primer valor
    _JS_RESULTADOS = (
        "return {"
        " h4: [...document.querySelectorAll('h4.list-group-item-heading')].map(e => e.innerText.trim()),"
        " items: [...document.querySelectorAll('.list-group-item')].map(d => {"
        "   const p = d.querySelector('p.list-group-item-text');"
        "   return {t: d.innerText, p: p ? p.innerText : '', hasP: !!p};"
        " })"
        "};"
    )
    URLS_BLOQUEADAS = [
        '*site24x7*', '*ruxitagentjs*', '*oss.maxcdn.com*', '*192.168.*',
        '*google-analytics.com*', '*googletagmanager.com*',
        '*.woff*', '*.ttf*', '*.png*', '*.jpg*', '*.gif*', '*.ico*',
    ]
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
        self._busqueda_directa_ok = False  # True tras la primera consulta exitosa
        
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
        # Ojo: page_load_strategy='eager' hace que Cloudflare bloquee; no usarlo.

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

        # Scripts de monitoreo/analítica de terceros que la página carga y no hacen falta
        try:
            self.driver.execute_cdp_cmd('Network.enable', {})
            self.driver.execute_cdp_cmd('Network.setBlockedURLs', {'urls': self.URLS_BLOQUEADAS})
        except WebDriverException:
            pass

        self.wait = WebDriverWait(
            self.driver, self.WAIT_TIMEOUT,
            ignored_exceptions=[StaleElementReferenceException]
        )
        self._page_loaded = False
        print("Chrome (undetected) inicializado (headless)" if self.headless else "Chrome (undetected) inicializado")
    
    def _enviar_busqueda_directa(self, ruc: str):
        """
        Envía por POST el mismo formulario que arma la página de búsqueda
        (accion=consPorRuc). El token de reCAPTCHA de SUNAT es un valor aleatorio
        generado en el navegador, así que no hace falta recargar el formulario:
        ahorra una carga de página por RUC.
        """
        pagina_anterior = self.driver.find_element(By.TAG_NAME, 'html')
        self.driver.execute_script(
            "const [url, ruc] = arguments;"
            "let token = ''; while (token.length < 52) token += Math.random().toString(36).substring(2);"
            "const campos = {accion: 'consPorRuc', razSoc: '', nroRuc: ruc, nrodoc: '',"
            "  token: token.substring(0, 52), contexto: 'ti-it', modo: '1', rbtnTipo: '1',"
            "  search1: ruc, tipdoc: '1', search2: '', search3: '', codigo: ''};"
            "const f = document.createElement('form'); f.method = 'post'; f.action = url;"
            "for (const [k, v] of Object.entries(campos)) {"
            "  const i = document.createElement('input'); i.type = 'hidden'; i.name = k; i.value = v;"
            "  f.appendChild(i); }"
            "document.body.appendChild(f); HTMLFormElement.prototype.submit.call(f);",
            self.url_base, ruc
        )
        # Esperar a que la página anterior se vaya (si no, el h4 viejo daría un falso positivo)
        WebDriverWait(self.driver, self.WAIT_TIMEOUT).until(EC.staleness_of(pagina_anterior))
        self._verificar_bloqueo()

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
                
                if intento == 0 and self._busqueda_directa_ok:
                    # Ya estamos en SUNAT: enviar la búsqueda sin recargar el formulario
                    self._enviar_busqueda_directa(ruc)
                else:
                    # Camino clásico: cargar el formulario, escribir el RUC y pulsar Buscar
                    self._busqueda_directa_ok = False
                    self._navigate_to_search()
                    input_ruc = self.driver.find_element(By.ID, "txtRuc")
                    self._escribir(input_ruc, ruc)
                    self._handle_captcha()
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
                    self._busqueda_directa_ok = True
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
        
        Optimizado: una sola llamada JS trae los h4 y todos los recuadros,
        que luego se procesan en memoria.
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
            
            # Una sola llamada al navegador trae todo el DOM relevante
            # (antes eran 2-3 round-trips de WebDriver por cada recuadro).
            dom = self.driver.execute_script(self._JS_RESULTADOS) or {}

            # --- Razón Social (del h4) ---
            h4s = dom.get('h4') or []
            texto_completo = (
                next((t for t in h4s if t.startswith(ruc)), None)
                or next((t for t in h4s if ruc in t), None)
                or (h4s[0] if h4s else '')
            )
            if ' - ' in texto_completo:
                resultado['razon_social'] = texto_completo.split(' - ', 1)[1].strip()
            else:
                resultado['razon_social'] = texto_completo

            # --- Recuadros (list-group-item): etiqueta + primer <p> de valor ---
            for item in dom.get('items') or []:
                div_text, valor = item.get('t') or '', (item.get('p') or '').strip()
                if "Domicilio Fiscal:" in div_text:
                    if item.get('hasP'):
                        self._parsear_direccion(valor, resultado)
                elif "Estado del Contribuyente:" in div_text:
                    if item.get('hasP'):
                        resultado['estado_contribuyente'] = valor.upper()
                elif es_persona_natural and "Tipo de Documento:" in div_text:
                    # Formato: "DNI 70450683 - APELLIDOS, NOMBRES"
                    if ' - ' in valor:
                        partes = valor.split(' - ', 1)
                        resultado['documento_identidad'] = partes[0].strip()
                        resultado['representante_legal'] = partes[1].strip()
                elif "Tipo Contribuyente:" in div_text:
                    if item.get('hasP'):
                        resultado['tipo_contribuyente'] = valor

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
            # La página de resultados ya cargó: si no hay botón, la empresa no tiene
            # representantes registrados (antes se esperaban 12 s inútilmente).
            botones = self.driver.find_elements(By.CSS_SELECTOR, "button.btnInfRepLeg")
            if not botones:
                resultado['sin_representante'] = True
                return

            self._clic(botones[0])

            # Esperar a que aparezca la tabla de representantes
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.TAG_NAME, "tbody"))
                )
            except TimeoutException:
                resultado['sin_representante'] = True
                return

            fila = self.driver.execute_script(
                "const t=document.querySelector('tbody'); if(!t) return null;"
                "for (const tr of t.querySelectorAll('tr')) {"
                "  const c=[...tr.querySelectorAll('td')].map(td=>td.innerText.trim());"
                "  if (c.length>=3) return c; }"
                "return null;"
            )
            if fila:
                resultado['representante_legal'] = fila[2]
                resultado['documento_identidad'] = f"{fila[0]} {fila[1]}"

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
