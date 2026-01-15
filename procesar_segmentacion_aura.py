"""
Procesador de Segmentación - Versión API Aura (Sin Selenium)
Utiliza ScopedResultsDataProviderController para buscar RUCs directamente via API.
"""
import time
import json
import re
import requests
from urllib.parse import urlencode
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from modules.sheets_manager import SheetsManager
import config

# Lock para acceso thread-safe a sheets
sheets_lock = Lock()
global_updates = []


class AuraSegmentacionAPI:
    """
    Cliente API para consultar segmentación de Salesforce via Aura Framework.
    100% basado en requests HTTP, sin Selenium.
    """
    
    BASE_URL = "https://transforma.my.site.com"
    
    def __init__(self, username=None, password=None):
        self.username = username or config.SEGMENTACION_USERNAME
        self.password = password or config.SEGMENTACION_PASSWORD
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Cache-Control": "max-age=0",
            "Upgrade-Insecure-Requests": "1"
        })
        self.fwuid = None
        self.aura_token = None
        self.logged_in = False
    
    def _extract_tokens_from_html(self, html):
        """Extrae fwuid y aura.token del HTML."""
        # Extraer fwuid
        fwuid_match = re.search(r'"fwuid"\s*:\s*"([^"]+)"', html)
        if fwuid_match:
            self.fwuid = fwuid_match.group(1)
        
        # Buscar token en HTML
        token_match = re.search(r'"token"\s*:\s*"([^"]+)"', html)
        if token_match:
            self.aura_token = token_match.group(1)
        else:
            # Buscar en cookies 
            cookie_name_match = re.search(r'"eikoocnekot"\s*:\s*"([^"]+)"', html)
            if cookie_name_match:
                cookie_name = cookie_name_match.group(1)
                if cookie_name in self.session.cookies:
                    self.aura_token = self.session.cookies[cookie_name]
    
    def login(self):
        """Realiza login via Aura API con manejo completo de redirects."""
        try:
            # Paso 1: Cargar página de login
            print(f"[Login] Cargando página de login...")
            resp_login = self.session.get(f"{self.BASE_URL}/s/login/", timeout=30)
            print(f"[Login] Status: {resp_login.status_code}, Size: {len(resp_login.text)} bytes")
            self._extract_tokens_from_html(resp_login.text)
            
            if not self.fwuid:
                print(f"[Login] Error: No se encontró fwuid en HTML")
                # Guardar HTML para debug
                with open("debug_login_fail.html", "w", encoding="utf-8") as f:
                    f.write(resp_login.text[:5000])
                return False
            
            print(f"[Login] FWUID encontrado: {self.fwuid[:20]}...")
            
            # Paso 2: Enviar credenciales via Aura
            context_json = {
                "mode": "PROD",
                "fwuid": self.fwuid,
                "app": "siteforce:loginApp2",
                "loaded": {"APPLICATION@markup://siteforce:loginApp2": "1343_FXfywJTDy_Pq6QSlM3hWkA"},
                "dn": [], "globals": {}, "uad": False
            }
            
            actions = [{
                "id": "login_action",
                "descriptor": "apex://LightningLoginFormController/ACTION$login",
                "callingDescriptor": "markup://c:loginForm",
                "params": {
                    "username": self.username,
                    "password": self.password,
                    "startUrl": "/s/"
                }
            }]
            
            form_data = {
                "message": json.dumps({"actions": actions}),
                "aura.context": json.dumps(context_json),
                "aura.pageURI": "/s/login/",
                "aura.token": self.aura_token or "undefined"
            }
            
            print("[Login] Enviando credenciales...")
            resp_auth = self.session.post(
                f"{self.BASE_URL}/s/sfsites/aura",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                params={"r": 1, "apex.LightningLoginFormController.login": 1},
                timeout=30
            )
            
            if resp_auth.status_code != 200:
                print(f"[Login] Error HTTP en POST: {resp_auth.status_code}")
                return False
            
            # Paso 3: Seguir redirect de frontdoor
            try:
                data = resp_auth.json()
                actions_resp = data.get("actions", [])
                if not actions_resp:
                    print(f"[Login] Respuesta POST sin actions: {data}")
                
                for action in actions_resp:
                    if action.get("state") == "SUCCESS":
                        redir_url = action.get("returnValue")
                        if redir_url:
                            print(f"[Login] Redireccionando a: {redir_url[:50]}...")
                            # Seguir el frontdoor redirect
                            resp_fd = self.session.get(redir_url, allow_redirects=True, timeout=30)
                            
                            # Buscar redirect JS si la página es pequeña
                            if len(resp_fd.text) < 5000:
                                match = re.search(r'window\.location\.href\s*=\s*[\'"]([^\'"]+)[\'"]', resp_fd.text)
                                if not match:
                                    match = re.search(r'window\.location\s*=\s*[\'"]([^\'"]+)[\'"]', resp_fd.text)
                                if match:
                                    next_url = match.group(1)
                                    if next_url.startswith('/'):
                                        next_url = self.BASE_URL + next_url
                                    print(f"[Login] Siguiendo JS redirect a: {next_url}")
                                    self.session.get(next_url, allow_redirects=True, timeout=30)
                    else:
                        print(f"[Login] Action state no es SUCCESS: {action.get('state')} - Error: {action.get('error')}")
            except Exception as e:
                print(f"[Login] Error en redirects: {e}")
                pass  # Continuar aunque falle el redirect
            
            # Paso 4: Navegar a /s/ para obtener tokens de sesión
            print("[Login] Cargando Home /s/...")
            resp_home = self.session.get(f"{self.BASE_URL}/s/", timeout=30)
            print(f"[Login] Home size: {len(resp_home.text)} bytes")
            self._extract_tokens_from_html(resp_home.text)
            
            # Si aún no tenemos token, buscarlo en cookies dinámicas
            if not self.aura_token:
                print("[Login] Token no encontrado en HTML, buscando en cookies...")
                # Buscar nombre de cookie de token en HTML
                cookie_name_match = re.search(r'"eikoocnekot"\s*:\s*"([^"]+)"', resp_home.text)
                if cookie_name_match:
                    cookie_name = cookie_name_match.group(1)
                    print(f"[Login] Nombre de cookie detectado: {cookie_name}")
                    # Buscar en cookies
                    for cookie in self.session.cookies:
                        if cookie.name == cookie_name:
                            self.aura_token = cookie.value
                            print(f"[Login] Token encontrado en cookie!")
                            break
                    if not self.aura_token:
                        print("[Login] Cookie encontrada pero sin valor o no coincide")
                else:
                    print("[Login] No se encontró nombre de cookie 'eikoocnekot' en HTML")
            
            self.logged_in = bool(self.fwuid and self.aura_token)
            if not self.logged_in:
                print(f"[Login] Fallo final: FWUID={bool(self.fwuid)}, Token={bool(self.aura_token)}")
            
            return self.logged_in
            
        except Exception as e:
            print(f"[Login] Excepción: {e}")
            return False
    
    def search_ruc(self, ruc):
        """
        Busca un RUC usando ScopedResultsDataProviderController.
        Retorna Account ID o None/"SIN_RESULTADOS".
        """
        if not self.logged_in:
            return None
        
        try:
            descriptor = "serviceComponent://ui.search.components.forcesearch.scopedresultsdataprovider.ScopedResultsDataProviderController/ACTION$getItems"
            
            scope_map = {
                "color": "5867E8",
                "icon": f"{self.BASE_URL}/img/icon/t4v35/standard/account_120.png",
                "label": "Cliente", "keyPrefix": "001", "name": "Account",
                "namespace": "forceCommunity", "cacheable": "Y",
                "id": "forceCommunity:Account", "labelPlural": "Clientes"
            }
            
            actions = [{
                "id": "search_ruc",
                "descriptor": descriptor,
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "scopeMap": scope_map,
                    "term": ruc,
                    "pageSize": 5,
                    "currentPage": 1,
                    "sortBy": None,
                    "enableRowActions": True,
                    "context": {"goBackOnCancel": True, "persistedContextParams": {"feeds": {}}},
                    "withSpellCorrection": True
                }
            }]
            
            context_json = {
                "mode": "PROD", "fwuid": self.fwuid, "app": "siteforce:communityApp",
                "loaded": {"APPLICATION@markup://siteforce:communityApp": "1421_mg1QpGWKsu060_sD-hU2fg"},
                "dn": [], "globals": {}, "uad": True
            }
            
            form_data = {
                "message": json.dumps({"actions": actions}),
                "aura.context": json.dumps(context_json),
                "aura.pageURI": f"/s/global-search/{ruc}",
                "aura.token": self.aura_token
            }
            
            response = self.session.post(
                f"{self.BASE_URL}/s/sfsites/aura",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                for action in data.get("actions", []):
                    if action.get("state") == "SUCCESS":
                        results = action.get("returnValue", {}).get("result", [])
                        if results:
                            return results[0].get("recordId")
                        if action.get("returnValue", {}).get("totalSize", 0) == 0:
                            return "SIN_RESULTADOS"
            
            return None
            
        except Exception:
            return None
    
    def get_segmentation_data(self, account_id):
        """
        Obtiene datos de segmentación para un Account ID.
        Retorna dict con Segmento, TipoCliente, etc.
        """
        if not self.logged_in or not account_id:
            return None
        
        try:
            descriptor = "serviceComponent://ui.force.components.controllers.recordGlobalValueProvider.RecordGvpController/ACTION$getRecord"
            
            actions = [{
                "id": "get_seg",
                "descriptor": descriptor,
                "callingDescriptor": "UNKNOWN",
                "params": {
                    "recordId": account_id,
                    "fields": ["Account.PE_Segmento__c", "Account.PE_Tipo_de_Cliente__c", 
                              "Account.PE_Sector__c", "Account.Name"],
                    "optionalFields": [],
                    "layoutTypes": [],
                    "modes": [],
                    "recordTypeId": None
                }
            }]
            
            context_json = {
                "mode": "PROD", "fwuid": self.fwuid, "app": "siteforce:communityApp",
                "loaded": {"APPLICATION@markup://siteforce:communityApp": "1421_mg1QpGWKsu060_sD-hU2fg"},
                "dn": [], "globals": {}, "uad": True
            }
            
            form_data = {
                "message": json.dumps({"actions": actions}),
                "aura.context": json.dumps(context_json),
                "aura.pageURI": f"/s/account/{account_id}",
                "aura.token": self.aura_token
            }
            
            response = self.session.post(
                f"{self.BASE_URL}/s/sfsites/aura",
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"},
                timeout=30
            )
            
            if response.status_code == 200:
                text = response.text
                result = {}
                
                # Extraer valores con regex
                patterns = {
                    "Segmento": r'"PE_Segmento__c"\s*:\s*(?:\{[^}]*"value"\s*:\s*"([^"]+)"|\s*"([^"]+)")',
                    "TipoCliente": r'"PE_Tipo_de_Cliente__c"\s*:\s*(?:\{[^}]*"value"\s*:\s*"([^"]+)"|\s*"([^"]+)")',
                }
                
                for key, pattern in patterns.items():
                    match = re.search(pattern, text)
                    if match:
                        result[key] = match.group(1) or match.group(2)
                
                return result if result else None
            
            return None
            
        except Exception:
            return None
    
    def buscar_segmento(self, ruc):
        """
        Método compatible con el scraper anterior.
        Busca RUC y retorna el segmento.
        """
        account_id = self.search_ruc(ruc)
        
        if account_id == "SIN_RESULTADOS":
            return "Sin Segmento"
        
        if not account_id:
            return None
        
        data = self.get_segmentation_data(account_id)
        if data:
            return data.get("Segmento") or data.get("TipoCliente") or "Sin Datos"
        
        return None


def procesar_worker(worker_id, rucs_asignados, sheets):
    """
    Procesa un subconjunto de RUCs asignados a este worker.
    """
    global global_updates
    api = AuraSegmentacionAPI()
    processed = 0
    found = 0
    
    print(f"[Worker {worker_id}] Iniciado - Procesará {len(rucs_asignados)} RUCs")
    
    try:
        if not api.login():
            print(f"[Worker {worker_id}] Error: No se pudo iniciar sesión")
            return {'worker_id': worker_id, 'processed': 0, 'found': 0}
        
        print(f"[Worker {worker_id}] Login exitoso")
        
        for idx, ruc_data in enumerate(rucs_asignados, 1):
            ruc = ruc_data['ruc']
            row = ruc_data['row']
            
            try:
                segmento = api.buscar_segmento(ruc)
                resultado = segmento if segmento else "ERROR"
                
                print(f"[W{worker_id}] {idx}/{len(rucs_asignados)}: {ruc} => {resultado}")
                
                with sheets_lock:
                    valores_invalidos = ['Sin Datos', 'ERROR_DESCONOCIDO', 'ERROR_REVISION', 
                                        'ERROR_EXCEPCION', 'ERROR_NO_LOGUEADO', 'ERROR_SESION_PERDIDA', 'ERROR']
                    if segmento and segmento not in valores_invalidos:
                        found += 1
                    global_updates.append({'row': row, 'segmento': resultado})
                
                processed += 1
                
                # Guardar cada 100 registros
                with sheets_lock:
                    if len(global_updates) >= 100:
                        print(f"\n*** Guardando {len(global_updates)} registros en batch ***")
                        batch_data = [{'range': f"N{u['row']}", 'values': [[u['segmento']]]} for u in global_updates]
                        sheets.worksheet.batch_update(batch_data)
                        global_updates = []
                        time.sleep(0.5)
                
            except Exception as e:
                print(f"[Worker {worker_id}] Error RUC {ruc}: {str(e)[:50]}")
                with sheets_lock:
                    global_updates.append({'row': row, 'segmento': 'ERROR'})
        
        print(f"[Worker {worker_id}] Finalizado - Encontrados: {found}/{processed}")
        return {'worker_id': worker_id, 'processed': processed, 'found': found}
        
    except Exception as e:
        print(f"[Worker {worker_id}] Error fatal: {e}")
        return {'worker_id': worker_id, 'processed': processed, 'found': found}


def main():
    print("=" * 60)
    print("PROCESADOR DE SEGMENTACIÓN - API AURA (SIN SELENIUM)")
    print("=" * 60)
    
    print("\nConectando a Google Sheets...")
    sheets = SheetsManager()
    
    try:
        print("Obteniendo RUCs sin segmentación...")
        all_values = sheets.worksheet.get_all_values()
        
        print(f"Total filas en sheet: {len(all_values)}")
        
        rucs_sin_segmentacion = []
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > config.COLUMNS['RUC']:
                ruc_raw = row[config.COLUMNS['RUC']].strip() if len(row) > config.COLUMNS['RUC'] else ''
                segmento = row[13].strip() if len(row) > 13 else ''
                
                # Limpieza del RUC
                solo_digitos = ''.join(c for c in ruc_raw if c.isdigit())
                ruc = solo_digitos[:11] if len(solo_digitos) >= 11 else solo_digitos
                
                if ruc and len(ruc) == 11:
                    if not segmento:
                        rucs_sin_segmentacion.append({'ruc': ruc, 'row': idx})
        
        if not rucs_sin_segmentacion:
            print("\nNo hay RUCs sin segmentación para procesar")
            return
        
        total_rucs = len(rucs_sin_segmentacion)
        num_workers = 1
        
        print(f"\nSe encontraron {total_rucs} RUCs sin segmentación")
        print(f"Se procesarán con {num_workers} workers en paralelo")
        
        # Dividir RUCs entre workers
        workers_rucs = [[] for _ in range(num_workers)]
        for idx, ruc_data in enumerate(rucs_sin_segmentacion):
            workers_rucs[idx % num_workers].append(ruc_data)
        
        print("\nDistribución de RUCs por worker:")
        for i in range(num_workers):
            print(f"  Worker {i}: {len(workers_rucs[i])} RUCs")
        
        print("\n" + "=" * 60)
        input("Presiona ENTER para comenzar...")
        print("=" * 60)
        
        start_time = time.time()
        
        # Ejecutar workers en paralelo
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                if workers_rucs[worker_id]:
                    future = executor.submit(procesar_worker, worker_id, workers_rucs[worker_id], sheets)
                    futures.append(future)
                    time.sleep(0.5)  # Delay entre workers
            
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"\nError en worker: {str(e)}")
        
        # Guardar registros restantes
        if global_updates:
            print(f"\n*** Guardando últimos {len(global_updates)} registros ***")
            batch_data = [{'range': f"N{u['row']}", 'values': [[u['segmento']]]} for u in global_updates]
            sheets.worksheet.batch_update(batch_data)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Resumen final
        total_processed = sum(r['processed'] for r in results)
        total_found = sum(r['found'] for r in results)
        
        print("\n" + "=" * 60)
        print("RESUMEN DEL PROCESO - SEGMENTACIÓN API AURA")
        print("=" * 60)
        print(f"Total procesados: {total_processed}/{total_rucs}")
        print(f"Segmentos encontrados: {total_found}")
        if total_processed > 0:
            print(f"Tasa de éxito: {(total_found/total_processed)*100:.2f}%")
        print(f"Tiempo total: {total_time/60:.2f} minutos")
        if total_rucs > 0:
            print(f"Velocidad: {total_time/total_rucs:.2f} segundos por RUC")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nProceso interrumpido por el usuario")
        
    except Exception as e:
        print(f"\nError fatal: {str(e)}")


if __name__ == "__main__":
    main()
