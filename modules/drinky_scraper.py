import requests
import time
import json
import logging
from config import DRINKY_URL, DRINKY_EMAIL, DRINKY_PASSWORD

# Configure logging
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DrinkyScraper:
    def __init__(self):
        self.base_url = DRINKY_URL
        self.email = DRINKY_EMAIL
        self.password = DRINKY_PASSWORD
        self.token = None
        self.session = requests.Session()
        
        # Headers based on HAR analysis
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'es-419,es;q=0.9,en;q=0.8',
            'Origin': 'https://cms.drinkyn.com',
            'Referer': 'https://cms.drinkyn.com/',
        })

    def login(self):
        """Authenticates with the Drinky API."""
        try:
            url = f"{self.base_url}/auth/login"
            payload = {
                "email": self.email,
                "password": self.password
            }
            
            logger.info(f"Attempting login to {url} with {self.email}")
            response = self.session.post(url, json=payload, timeout=30)
            
            if response.status_code in [200, 201]:
                data = response.json()
                self.token = data.get('token')
                if self.token:
                    # Update session headers with the token
                    self.session.headers.update({'Authorization': f'Bearer {self.token}'})
                    logger.info("Login successful. Token acquired.")
                    return True
                else:
                    logger.error("Login response did not contain a token.")
            else:
                logger.error(f"Login failed with status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                
        except Exception as e:
            logger.error(f"Login exception: {str(e)}")
            
        return False

    def get_company_data(self, ruc):
        """Fetches company data for a given RUC."""
        if not self.token:
            if not self.login():
                return None

        try:
            url = f"{self.base_url}/tacto/company/{ruc}"
            logger.info(f"Fetching data for RUC: {ruc}")
            
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 401:
                logger.warning("Token expired or invalid. Retrying login...")
                if self.login():
                    return self.get_company_data(ruc) # Retry once
            elif response.status_code == 404:
                logger.info(f"RUC {ruc} not found.")
                return "SIN_RESULTADOS"
            else:
                logger.error(f"Error fetching RUC {ruc}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error processing RUC {ruc}: {str(e)}")
            
        return None

    def get_movistar_data(self, ruc):
        """Fetches Movistar data for a given RUC (fallback)."""
        if not self.token:
             if not self.login():
                 return None
                 
        try:
            # Correct endpoint found in HAR: /tacto/movistar/{ruc}
            url = f"{self.base_url}/tacto/movistar/{ruc}"
            logger.info(f"Fetching Movistar data for RUC: {ruc}")
            
            response = self.session.get(url, timeout=30)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return "SIN_RESULTADOS"
            else:
                 logger.error(f"Error fetching Movistar RUC {ruc}: {response.status_code}")
                 
        except Exception as e:
            logger.error(f"Error processing Movistar RUC {ruc}: {str(e)}")
            
        return None

    def extract_phones(self, data):
        """Extracts phone numbers from the API response."""
        phones = []
        
        # 1. Extract from 'entel' (Organizaciones)
        if 'entel' in data and data['entel']:
            entel_data = data['entel']
            # From 'contactos'
            contactos = entel_data.get('contactos') or []
            for contacto in contactos:
                phone = contacto.get('telefono')
                if phone and len(phone) > 6:
                    clean_phone = ''.join(filter(str.isdigit, phone))
                    if clean_phone: phones.append(clean_phone)
            # From 'lineasOtras'
            lineas = entel_data.get('lineasOtras') or []
            for linea in lineas:
                phone = linea.get('telefono')
                if phone:
                    clean_phone = ''.join(filter(str.isdigit, str(phone)))
                    if clean_phone: phones.append(clean_phone)

        # 2. Extract from 'movistar' logic
        # Check for 'movistar' key (if passed wrapped) OR 'movistar_data' (if passed raw from get_movistar_data)
        
        # If passed wrapped as {'movistar': data}
        movistar_data = None
        if 'movistar' in data:
            # The data might be the response itself which contains 'movistar_data'
            # Or if we wrapped it in procesar_drinky_paralelo as {'movistar': mov_data}
            # Let's inspect what mov_data structure is.
            # From HAR: response contains "movistar_data": { ... }
            raw_mov = data['movistar']
            if isinstance(raw_mov, dict):
                 movistar_data = raw_mov.get('movistar_data') or raw_mov # Handle if it's nested or direct
        
        # Also check if data ITSELF is the movistar response (contains movistar_data)
        if 'movistar_data' in data:
            movistar_data = data['movistar_data']

        if movistar_data:
            # Extract from 'productos' -> 'products' -> 'codeProduct'
            productos = movistar_data.get('productos') or {}
            products_list = productos.get('products') or []
            for prod in products_list:
                phone = prod.get('codeProduct')
                # serviceType "Movil" check? HAR showed "serviceType":"Movil"
                if phone and prod.get('serviceType') == 'Movil':
                     clean_phone = ''.join(filter(str.isdigit, str(phone)))
                     if clean_phone: phones.append(clean_phone)
            
            # Extract from 'contactos' if exists
            contactos = movistar_data.get('contactos') or []
            for contacto in contactos:
                phone = contacto.get('telefono')
                if phone:
                    clean_phone = ''.join(filter(str.isdigit, str(phone)))
                    if clean_phone: phones.append(clean_phone)
                     
        # Remove duplicates while preserving order
        seen = set()
        unique_phones = []
        for p in phones:
            if p not in seen:
                seen.add(p)
                unique_phones.append(p)
        
        # Return only the top 2
        return unique_phones[:2]

    def close(self):
        self.session.close()
