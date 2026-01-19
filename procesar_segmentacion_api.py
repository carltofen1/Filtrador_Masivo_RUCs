"""
Procesador de Segmentación - 100% API (SIN SELENIUM)
Basado en test_segmentacion_aura_v3.py que funciona perfectamente.
Procesa RUCs desde Google Sheets y escribe los resultados.
"""
import requests
import json
import re
from urllib.parse import urlencode, unquote
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

from modules.sheets_manager import SheetsManager
import config

sheets_lock = Lock()
global_updates = []

class AuraSegmentacionAPI:
    """
    Cliente 100% API para Salesforce Aura.
    Basado en V3 que funciona.
    """
    
    BASE_URL = "https://transforma.my.site.com"
    
    def __init__(self, username=None, password=None):
        self.username = username or config.SEGMENTACION_USERNAME
        self.password = password or config.SEGMENTACION_PASSWORD
        self.session = requests.Session()
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'es-419,es;q=0.9,en;q=0.8',
            'Origin': self.BASE_URL,
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })

        self.fwuid = None
        self.aura_token = None
        self.logged_in = False
        
    def _extract_tokens_from_html(self, html, context_source="Unknown"):
        """Extrae fwuid y aura.token del HTML y cookies."""
        
        # FWUID
        fwuid_match = re.search(r'"fwuid"\s*:\s*"([^"]+)"', html)
        if fwuid_match:
            self.fwuid = fwuid_match.group(1)
            
        # Aura Token - primero buscar en HTML
        token_match = re.search(r'aura\.token\s*=\s*"(eyJ[^"]+)"', html)
        if not token_match:
            token_match = re.search(r'"token"\s*:\s*"(eyJ[^"]+)"', html)
        if not token_match:
            token_match = re.search(r'data-aura-token="([^"]+)"', html)
        
        # Si no está en HTML, buscar en cookies (CLAVE!)
        if not token_match:
            jwt_candidates = re.findall(r'"(eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+)"', html)
            if jwt_candidates:
                self.aura_token = jwt_candidates[0]
                return
        
        if token_match:
            self.aura_token = token_match.group(1)
        else:
            # Buscar en cookies
            for cookie in self.session.cookies:
                if cookie.name == "token" or "jwt" in cookie.name.lower() or cookie.value.startswith("eyJ"):
                    self.aura_token = unquote(cookie.value)
                    return
            self.aura_token = "undefined"

    def login(self):
        """Realiza login 100% API."""
        try:
            # 1. GET Login Page
            print("[Login] Cargando página de login...")
            resp = self.session.get(f"{self.BASE_URL}/s/login/", timeout=30)
            self._extract_tokens_from_html(resp.text, "Login Page")
            
            if not self.fwuid:
                print("[Login] Error: No se puede proceder sin fwuid.")
                return False

            # 2. POST Login Credentials
            print("[Login] Enviando credenciales...")
            
            message = {
                "actions": [{
                    "id": "123;a",
                    "descriptor": "apex://applauncher.LoginFormController/ACTION$login",
                    "callingDescriptor": "markup://salesforceIdentity:loginForm2",
                    "params": {
                        "username": self.username,
                        "password": self.password,
                        "startUrl": ""
                    },
                    "version": "60.0" 
                }]
            }
            
            context = {
                "mode": "PROD",
                "fwuid": self.fwuid,
                "app": "siteforce:loginApp2",
                "loaded": {"APPLICATION@markup://siteforce:loginApp2": "REQUIRED"},
                "dn": [], "globals": {}, "uad": True
            }
            
            post_data = {
                'message': json.dumps(message),
                'aura.context': json.dumps(context),
                'aura.pageURI': '/s/login/',
                'aura.token': self.aura_token
            }
            
            post_url = f"{self.BASE_URL}/s/sfsites/aura?r=1&applauncher.LoginForm.login=1"
            headers = {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}
            
            resp_post = self.session.post(post_url, data=urlencode(post_data), headers=headers)
            
            if resp_post.status_code != 200:
                print(f"[Login] Error HTTP: {resp_post.status_code}")
                return False
                
            resp_json = resp_post.json()
            
            # 3. Handle Redirect (Frontdoor)
            events = resp_json.get('events', [])
            redirect_url = None
            for evt in events:
                if evt['descriptor'] == "markup://force:navigateToURL":
                    redirect_url = evt['attributes']['url']
                    break
                elif evt['descriptor'] == "markup://aura:clientRedirect":
                    redirect_url = evt['attributes']['values']['url']
                    break
            
            if not redirect_url:
                match = re.search(r'frontdoor\.jsp\?sid=[^"&]+', json.dumps(resp_json))
                if match:
                    redirect_url = match.group(0)
                    if not redirect_url.startswith("http"):
                        redirect_url = f"{self.BASE_URL}/s/{redirect_url}"

            if not redirect_url:
                print("[Login] No se encontró URL de redirección")
                return False
                
            print("[Login] Siguiendo redirección...")
            
            # 4. Access Frontdoor
            resp_home = self.session.get(redirect_url, allow_redirects=True)
            
            # Si hay redirect JS
            if len(resp_home.text) < 5000 and "window.location" in resp_home.text:
                match = re.search(r'window\.location\.href\s*=\s*[\'"]([^\'"]+)[\'"]', resp_home.text)
                if not match:
                    match = re.search(r'window\.location\s*=\s*[\'"]([^\'"]+)[\'"]', resp_home.text)
                
                if match:
                    new_url = match.group(1)
                    if new_url.startswith('/'):
                        new_url = self.BASE_URL + new_url
                    resp_home = self.session.get(new_url, allow_redirects=True)

            # Extraer tokens de Home
            self._extract_tokens_from_html(resp_home.text, "Home Page")
            
            # Si no encontró tokens, navegar a /s/
            if not self.fwuid or self.aura_token == "undefined":
                resp_home = self.session.get(f"{self.BASE_URL}/s/", timeout=30)
                self._extract_tokens_from_html(resp_home.text, "Home /s/")
            
            if not self.fwuid:
                print("[Login] Error crítico: No se obtuvo fwuid")
                return False
            
            # Buscar token en cookies si aún no lo tenemos
            if self.aura_token == "undefined":
                for cookie in self.session.cookies:
                    if cookie.value.startswith("eyJ"):
                        self.aura_token = unquote(cookie.value)
                        print(f"[Login] Token encontrado en cookie: {cookie.name}")
                        break
            
            self.logged_in = True
            print("[Login] ✅ Login exitoso!")
            return True

        except Exception as e:
            print(f"[Login] Excepción: {e}")
            import traceback
            traceback.print_exc()
            return False

    def search_ruc(self, ruc):
        """Busca un RUC usando ScopedResultsDataProviderController."""
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
                "id": "search_ruc_action",
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
                
                # Fallback regex
                response_text = json.dumps(data)
                account_ids = re.findall(r'"recordId"\s*:\s*"(001[A-Za-z0-9]{15,18})"', response_text)
                if account_ids:
                    return account_ids[0]
            
            return None
        except Exception:
            return None
    
    def get_segmentation_data(self, record_id):
        """Obtiene datos de segmentación para un Account ID."""
        if not self.logged_in or not record_id:
            return None
        
        try:
            # Descriptor largo con todos los campos
            record_descriptor = f"{record_id}.0125A000001RdBjQAK.null.null.null.Name.VIEW.false.null.Name,LastModifiedDate,BillingCity,Parent;2Id,Usuario_transferencia__c,DivisaCuenta__c,GpoEconomico__c,CreatedById,CreatedBy;2Name,BillingPostalCode,reasignacion__c,Sic,CurrencyIsoCode,Consultor_Principal__c,RegionFacturacion__c,ShippingStreet,ShippingPostalCode,CreatedDate,ShippingState,Id,RegionEnvio__c,BillingState,PE_Ejecutivo_Postventa__c,PE_Segmento__c,Usuario_transferencia__r;2Name,LastModifiedBy;2Id,PE_CanalPostVenta__c,Estatus__c,NumberOfEmployees,Parent;2RecordTypeId,fecha_de_transferencia__c,PE_Sector__c,Detalle_de_Servicios__c,CreatedBy;2Id,PE_Fecha_de_proxima_desasignacion__c,Phone,Usuario_transferencia__r;2Id,RecordTypeId,ShippingCountry,ShippingCity,Pais__c,PE_ultima_fecha_de_asignacion__c,ParentId,PE_Tipo_de_Cliente__c,CanalVenta__c,Parent;2Name,LastModifiedBy;2Name,SystemModstamp,BillingCountry,BillingStreet,PE_Tipo_Empresa__c,FacturacionServicios__c,RecordType__c,LastModifiedById,Descripcion__c,PhotoUrl.null"

            message = {
                "actions": [{
                    "id": "214;a", 
                    "descriptor": "serviceComponent://ui.force.components.controllers.recordGlobalValueProvider.RecordGvpController/ACTION$getRecord",
                    "callingDescriptor": "UNKNOWN",
                    "params": {"recordDescriptor": record_descriptor},
                    "version": "60.0"
                }]
            }

            context = {
                "mode": "PROD", "fwuid": self.fwuid, "app": "siteforce:communityApp",
                "loaded": {"APPLICATION@markup://siteforce:communityApp": "REQUIRED"},
                "dn": [], "globals": {}, "uad": True
            }

            post_data = {
                'message': json.dumps(message),
                'aura.context': json.dumps(context),
                'aura.pageURI': f'/s/account/{record_id}/detail', 
                'aura.token': self.aura_token
            }
            
            url = f"{self.BASE_URL}/s/sfsites/aura?r=10&ui.force.components.controllers.recordGlobalValueProvider.RecordGvpController.getRecord=1"
            
            resp = self.session.post(url, data=urlencode(post_data), headers={
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Referer': f"{self.BASE_URL}/s/account/{record_id}/detail"
            })
            
            if resp.status_code != 200:
                return None
            
            data = resp.json()
            
            # Buscar en Global Value Providers
            context_data = data.get("context", {})
            gvps = context_data.get("globalValueProviders", [])
            
            extracted_data = {}

            for gvp in gvps:
                if gvp.get("type") == "$Record":
                    records = gvp.get("values", {}).get("records", {})
                    target_record = records.get(record_id, {})
                    rec_str = json.dumps(target_record)
                    
                    patterns = {
                        "Segmento": r'"PE_Segmento__c"\s*:\s*(?:{\s*"[^"]*"\s*:\s*[^,]*,\s*"value"\s*:\s*"([^"]+)"|"[^"]+")',
                        "TipoCliente": r'"PE_Tipo_de_Cliente__c"\s*:\s*(?:{\s*"[^"]*"\s*:\s*[^,]*,\s*"value"\s*:\s*"([^"]+)"|"[^"]+")',
                    }

                    for key, pattern in patterns.items():
                        match = re.search(pattern, rec_str)
                        if match and match.group(1):
                            extracted_data[key] = match.group(1)

                    if extracted_data:
                        return extracted_data
            
            return None

        except Exception:
            return None

    def buscar_segmento(self, ruc):
        """Método simplificado para buscar segmento de un RUC."""
        account_id = self.search_ruc(ruc)
        if account_id == "SIN_RESULTADOS":
            return "Sin Segmento"
        if not account_id:
            return None
        data = self.get_segmentation_data(account_id)
        if data:
            return data.get("TipoCliente") or data.get("Segmento") or "Sin Datos"
        return None


def worker_task(api, worker_id, rucs, sheets):
    """Procesa un subconjunto de RUCs."""
    global global_updates
    processed = 0
    found = 0
    
    for idx, ruc_data in enumerate(rucs, 1):
        ruc = ruc_data['ruc']
        row = ruc_data['row']
        try:
            segmento = api.buscar_segmento(ruc)
            resultado = segmento if segmento else "ERROR"
            
            print(f"[W{worker_id}] {idx}/{len(rucs)}: {ruc} => {resultado}")
            
            with sheets_lock:
                valores_invalidos = ['Sin Datos', 'ERROR', 'Sin Segmento', 'ERROR_NO_LOGUEADO']
                if segmento and segmento not in valores_invalidos:
                    found += 1
                global_updates.append({'row': row, 'segmento': resultado})
            
            processed += 1
            
            with sheets_lock:
                if len(global_updates) >= 50:
                    print(f"\n*** Guardando {len(global_updates)} updates ***")
                    batch_data = [{'range': f"N{u['row']}", 'values': [[u['segmento']]]} for u in global_updates]
                    sheets.worksheet.batch_update(batch_data)
                    global_updates = []
                    
        except Exception as e:
            print(f"Error {ruc}: {e}")
            
    return {'processed': processed, 'found': found}


def main():
    global global_updates
    print("=" * 60)
    print("PROCESADOR DE SEGMENTACIÓN - 100% API (SIN SELENIUM)")
    print("=" * 60)
    
    sheets = SheetsManager()
    all_values = sheets.worksheet.get_all_values()
    print(f"Total filas: {len(all_values)}")
    
    rucs_sin_segmentacion = []
    for idx, row in enumerate(all_values[1:], start=2):
        if len(row) > config.COLUMNS['RUC']:
            ruc_raw = row[config.COLUMNS['RUC']].strip()
            segmento = row[13].strip() if len(row) > 13 else ''
            solo_digitos = ''.join(c for c in ruc_raw if c.isdigit())
            ruc = solo_digitos[:11] if len(solo_digitos) >= 11 else solo_digitos
            
            if ruc and len(ruc) == 11 and not segmento:
                rucs_sin_segmentacion.append({'ruc': ruc, 'row': idx})
                
    if not rucs_sin_segmentacion:
        print("✅ No hay RUCs pendientes de segmentación.")
        return

    print(f"RUCs a procesar: {len(rucs_sin_segmentacion)}")
    
    # Login
    api = AuraSegmentacionAPI()
    if not api.login():
        print("❌ Login falló. No se puede continuar.")
        return
    
    print("✅ Login exitoso. Iniciando procesamiento...")
    
    # Procesar secuencialmente (la API compartida es thread-safe)
    num_workers = 3
    workers_rucs = [[] for _ in range(num_workers)]
    for idx, ruc_data in enumerate(rucs_sin_segmentacion):
        workers_rucs[idx % num_workers].append(ruc_data)
        
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for i in range(num_workers):
            if workers_rucs[i]:
                futures.append(executor.submit(worker_task, api, i, workers_rucs[i], sheets))
        
        results = [f.result() for f in as_completed(futures)]
    
    # Guardar restantes
    if global_updates:
        print(f"Guardando {len(global_updates)} updates finales...")
        batch_data = [{'range': f"N{u['row']}", 'values': [[u['segmento']]]} for u in global_updates]
        sheets.worksheet.batch_update(batch_data)
    
    total_processed = sum(r['processed'] for r in results)
    total_found = sum(r['found'] for r in results)
    print(f"\n✅ Completado: {total_found}/{total_processed} RUCs con segmento válido")


if __name__ == "__main__":
    main()
