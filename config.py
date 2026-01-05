import os
import sys
from dotenv import load_dotenv

def get_resource_path(relative_path):
    """Obtiene la ruta correcta para archivos bundled con PyInstaller"""
    if getattr(sys, 'frozen', False):
        # Ejecutando como ejecutable PyInstaller
        # Los archivos están junto al .exe, no dentro del bundle temporal
        base_path = os.path.dirname(sys.executable)
    else:
        # Ejecutando como script normal
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

# Cargar .env desde la ubicación correcta
env_path = get_resource_path('.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv()  # Fallback

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '')
SHEET_NAME = os.getenv('SHEET_NAME', 'Datos_Filtrados')
CREDENTIALS_FILE = get_resource_path('credentials.json')

CLARO_USERNAME = os.getenv('CLARO_USERNAME', '')
CLARO_PASSWORD = os.getenv('CLARO_PASSWORD', '')
CLARO_URL = os.getenv('CLARO_URL', '')

ENTEL_USERNAME = os.getenv('ENTEL_USERNAME', 'ventas.admin2@entelempresa.pe')
ENTEL_PASSWORD = os.getenv('ENTEL_PASSWORD', 'Interconexion123.')
ENTEL_URL = 'https://entel.insolutions.pe/entelid-portal/Account/Login'

# Segmentación (Salesforce/Claro)
SEGMENTACION_URL = 'https://transforma.my.site.com/s/login/'
SEGMENTACION_USERNAME = os.getenv('SEGMENTACION_USERNAME', 'usuario1h&gsolucionesdenegocios@claro.comunidad.com')
SEGMENTACION_PASSWORD = os.getenv('SEGMENTACION_PASSWORD', 'Hgsoluciones2025+')

# Portal Factibilidad Claro (Cobertura)
FACTIBILIDAD_URL = 'https://172.19.90.243/portalfactibilidad/public/'
FACTIBILIDAD_USERNAME = os.getenv('FACTIBILIDAD_USERNAME', 'D99957628')
FACTIBILIDAD_PASSWORD = os.getenv('FACTIBILIDAD_PASSWORD', 'Europa1234*')

# WhatsApp Bot
WHATSAPP_SESSION_PATH = os.getenv('WHATSAPP_SESSION_PATH', './whatsapp_session')

BATCH_SIZE = int(os.getenv('BATCH_SIZE', 5))
DELAY_BETWEEN_BATCHES = float(os.getenv('DELAY_BETWEEN_BATCHES', 0.2))

COLUMNS = {
    'ID_REGISTRO': 0,
    'RUC': 1,
    'RAZON_SOCIAL': 2,
    'REPRESENTANTE_LEGAL': 3,
    'TELEFONOS': 4,
    'DOCUMENTO_IDENTIDAD': 5,
    'DEPARTAMENTO': 6,
    'PROVINCIA': 7,
    'DISTRITO': 8,
    'DIRECCION': 9,
    'ESTADO': 10,
    'ESTADO_ENTEL': 11
}

STATUS = {
    'PENDING': 'Pendiente',
    'PROCESSING': 'Procesando',
    'COMPLETED': 'Completado',
    'ERROR': 'Error'
}
