from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Dict, Optional
import time
import re

class SunatScraper:
    def __init__(self):
        self.driver = None
        self.wait = None
        self.url_base = "https://e-consultaruc.sunat.gob.pe/cl-ti-itmrconsruc/jcrS00Alias"
        
    def _init_driver(self):
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--blink-settings=imagesEnabled=false')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            prefs = {
                'profile.managed_default_content_settings.images': 2,
                'profile.default_content_setting_values.notifications': 2,
                'profile.managed_default_content_settings.stylesheets': 2,
            }
            chrome_options.add_experimental_option('prefs', prefs)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Ejecutar script para ocultar webdriver
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            self.wait = WebDriverWait(self.driver, 10)
            print("Navegador Chrome inicializado (modo headless)")
    
    def consultar_ruc(self, ruc: str) -> Optional[Dict]:
        ruc = ruc.strip()
        if not ruc.isdigit() or len(ruc) != 11:
            print(f"RUC inválido: {ruc}")
            return None
        
        # Intentar hasta 2 veces si falla el representante legal
        for intento in range(2):
            try:
                self._init_driver()
                
                if intento == 0:
                    print(f"Consultando RUC: {ruc}")
                else:
                    print(f"Reintentando consulta completa del RUC: {ruc}")
                
                # Siempre recargar la página para resetear el estado
                self.driver.get(self.url_base)
                time.sleep(0.5)
                
                try:
                    tab_ruc = self.wait.until(
                        EC.element_to_be_clickable((By.ID, "btnPorRuc"))
                    )
                    tab_ruc.click()
                except:
                    print("No se pudo cambiar a pestaña RUC")
                
                try:
                    input_ruc = self.wait.until(
                        EC.presence_of_element_located((By.ID, "txtRuc"))
                    )
                    input_ruc.clear()
                    input_ruc.send_keys(ruc)
                except Exception as e:
                    print(f"Error ingresando RUC: {e}")
                    if intento == 1:
                        return None
                    continue
                
                captcha_visible = False
                try:
                    txt_codigo = self.driver.find_element(By.ID, "txtCodigo")
                    if txt_codigo.is_displayed():
                        captcha_visible = True
                        print("CAPTCHA detectado. Por favor resuelve el CAPTCHA en el navegador...")
                        print("Presiona ENTER aquí cuando hayas terminado...")
                        input()
                except:
                    pass
                
                try:
                    btn_buscar = self.driver.find_element(By.ID, "btnAceptar")
                    btn_buscar.click()
                    
                    # Esperar a que aparezcan los resultados en lugar de sleep fijo
                    self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "h4.list-group-item-heading"))
                    )
                except Exception as e:
                    print(f"Error al buscar: {e}")
                    if intento == 1:
                        return None
                    continue
                
                resultado = self._extraer_datos_pagina(ruc)
                
                if resultado:
                    # Verificar si falta el representante legal (y no es porque no tiene)
                    if not resultado.get('representante_legal') and not resultado.get('sin_representante') and intento == 0:
                        print("Falta representante legal, reintentando consulta completa...")
                        time.sleep(1)
                        continue
                    
                    print(f"Datos extraídos: {resultado['razon_social']}")
                    return resultado
                else:
                    print(f"No se pudieron extraer datos")
                    if intento == 1:
                        return None
                    continue
                
            except Exception as e:
                print(f"Error consultando RUC {ruc}: {str(e)}")
                if intento == 1:
                    return None
                continue
        
        return None
    
    def _extraer_datos_pagina(self, ruc: str) -> Optional[Dict]:
        try:
            resultado = {
                'ruc': ruc,
                'razon_social': '',
                'representante_legal': '',
                'documento_identidad': '',
                'departamento': '',
                'provincia': '',
                'distrito': '',
                'direccion': ''
            }
            
            try:
                h4_elements = self.driver.find_elements(By.CSS_SELECTOR, "h4.list-group-item-heading")
                target_h4 = None
                
                for h4 in h4_elements:
                    if h4.text.strip().startswith(ruc):
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
                        
                print(f"Razón Social: {resultado['razon_social']}")
            except Exception as e:
                print(f"No se pudo extraer Razón Social: {e}")
            
            try:
                domicilio_divs = self.driver.find_elements(By.CLASS_NAME, "list-group-item")
                
                for div in domicilio_divs:
                    if "Domicilio Fiscal:" in div.text:
                        p_element = div.find_element(By.CSS_SELECTOR, "p.list-group-item-text")
                        direccion_completa = p_element.text.strip()
                        
                        departamentos = [
                            "AMAZONAS", "ANCASH", "APURIMAC", "AREQUIPA", "AYACUCHO", "CAJAMARCA", 
                            "CALLAO", "CUSCO", "HUANCAVELICA", "HUANUCO", "ICA", "JUNIN", "LA LIBERTAD", 
                            "LAMBAYEQUE", "LIMA", "LORETO", "MADRE DE DIOS", "MOQUEGUA", "PASCO", 
                            "PIURA", "PUNO", "SAN MARTIN", "TACNA", "TUMBES", "UCAYALI",
                            "CALLAO (PROVINCIA CONSTITUCIONAL)"
                        ]
                        
                        partes = [p.strip() for p in direccion_completa.split(' - ')]
                        
                        if len(partes) >= 3:
                            resultado['distrito'] = partes[-1]
                            resultado['provincia'] = partes[-2]
                            
                            resto = ' - '.join(partes[:-2]).strip()
                            
                            depto_encontrado = False
                            resto_upper = resto.upper()
                            
                            departamentos.sort(key=len, reverse=True)
                            
                            for depto in departamentos:
                                if resto_upper.endswith(depto):
                                    resultado['departamento'] = depto
                                    
                                    direccion_final = resto[:-(len(depto))].strip()
                                    
                                    while direccion_final.endswith('-') or direccion_final.endswith(' '):
                                        direccion_final = direccion_final[:-1]
                                    
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
                        
                        print(f"Dirección: {resultado['direccion']}")
                        print(f"Distrito: {resultado['distrito']}")
                        print(f"Provincia: {resultado['provincia']}")
                        print(f"Departamento: {resultado['departamento']}")
                        break
                
            except Exception as e:
                print(f"No se pudo extraer Dirección: {e}")
            
            try:
                estado_divs = self.driver.find_elements(By.CLASS_NAME, "list-group-item")
                
                for div in estado_divs:
                    if "Estado del Contribuyente:" in div.text:
                        p_element = div.find_element(By.CSS_SELECTOR, "p.list-group-item-text")
                        estado_contribuyente = p_element.text.strip().upper()
                        resultado['estado_contribuyente'] = estado_contribuyente
                        print(f"Estado: {estado_contribuyente}")
                        break
                        
            except Exception as e:
                print(f"No se pudo extraer Estado: {e}")
                resultado['estado_contribuyente'] = 'DESCONOCIDO'

            try:
                print("Buscando representante legal...")
                
                # Verificar si existe el botón de representantes legales
                try:
                    btn_rep_legal = self.wait.until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btnInfRepLeg"))
                    )
                except:
                    # Si no existe el botón, esta empresa no tiene representantes
                    print("Esta empresa no tiene representantes legales registrados")
                    resultado['sin_representante'] = True
                    return resultado
                
                btn_rep_legal.click()
                time.sleep(0.5)
                
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
                        
                        print(f"Representante Legal: {resultado['representante_legal']}")
                        print(f"Documento: {resultado['documento_identidad']}")
                        break
                
            except Exception as e:
                print(f"No se pudo extraer Representante Legal: {e}")
            
            return resultado
            
        except Exception as e:
            print(f"Error extrayendo datos: {e}")
            return None
    
    def close(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.wait = None
            print("Navegador cerrado")
