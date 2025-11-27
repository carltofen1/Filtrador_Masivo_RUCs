import os
from dotenv import load_dotenv

load_dotenv()

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID', '')
SHEET_NAME = os.getenv('SHEET_NAME', 'Datos_Filtrados')
CREDENTIALS_FILE = 'credentials.json'

CLARO_USERNAME = os.getenv('CLARO_USERNAME', '')
CLARO_PASSWORD = os.getenv('CLARO_PASSWORD', '')
CLARO_URL = os.getenv('CLARO_URL', '')

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
    'ESTADO': 10
}

STATUS = {
    'PENDING': 'Pendiente',
    'PROCESSING': 'Procesando',
    'COMPLETED': 'Completado',
    'ERROR': 'Error'
}
