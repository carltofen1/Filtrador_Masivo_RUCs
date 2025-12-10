import gspread
from google.oauth2.service_account import Credentials
from typing import List, Dict, Any
import time
import config

class SheetsManager:
    def __init__(self):
        self.scope = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        self.creds = Credentials.from_service_account_file(
            config.CREDENTIALS_FILE, 
            scopes=self.scope
        )
        self.client = gspread.authorize(self.creds)
        self.spreadsheet = self.client.open_by_key(config.SPREADSHEET_ID)
        self.worksheet = self.spreadsheet.worksheet(config.SHEET_NAME)
        
    def get_rucs(self, start_row: int = 2) -> List[Dict[str, Any]]:
        try:
            all_values = self.worksheet.get_all_values()
            
            rucs = []
            for idx, row in enumerate(all_values[start_row - 1:], start=start_row):
                if len(row) <= config.COLUMNS['RUC']:
                    continue
                
                ruc_raw = row[config.COLUMNS['RUC']].strip() if len(row) > config.COLUMNS['RUC'] else ''
                estado = row[config.COLUMNS['ESTADO']].strip().upper() if len(row) > config.COLUMNS['ESTADO'] else ''
                
                # Limpieza agresiva: extraer SOLO dígitos
                solo_digitos = ''.join(c for c in ruc_raw if c.isdigit())
                
                # Tomar solo los primeros 11 dígitos (un RUC válido tiene 11)
                ruc = solo_digitos[:11] if len(solo_digitos) >= 11 else solo_digitos
                
                # Validar: debe ser exactamente 11 dígitos
                if ruc and len(ruc) == 11:
                    if not estado or estado == 'PENDIENTE':
                        rucs.append({
                            'ruc': ruc,
                            'row': idx,
                            'estado_actual': estado
                        })
            
            print(f"Se encontraron {len(rucs)} RUCs pendientes para procesar")
            return rucs
            
        except Exception as e:
            print(f"Error al obtener RUCs: {str(e)}")
            return []
    
    def update_row_batch(self, updates: List[Dict[str, Any]]):
        try:
            batch_data = []
            for update in updates:
                row = update['row']
                data = update['data']
                
                range_name = f'A{row}:K{row}'
                batch_data.append({
                    'range': range_name,
                    'values': [data]
                })
            
            self.worksheet.batch_update(batch_data)
            print(f"Actualizadas {len(updates)} filas en batch")
            
        except Exception as e:
            print(f"Error en batch update: {str(e)}")
    
    def get_next_id(self) -> int:
        try:
            id_column = self.worksheet.col_values(config.COLUMNS['ID_REGISTRO'] + 1)
            ids = [int(id_val) for id_val in id_column[1:] if id_val.isdigit()]
            return max(ids) + 1 if ids else 1
            
        except Exception as e:
            print(f"Error al obtener siguiente ID: {str(e)}")
            return 1
    
    def initialize_headers(self):
        try:
            headers = [
                'ID REGISTRO',
                'RUC',
                'Razón Social',
                'Representante Legal',
                'Teléfonos',
                'Documento Identidad',
                'DEPARTAMENTO',
                'PROVINCIA',
                'DISTRITO',
                'DIRECCION',
                'ESTADO'
            ]
            
            first_row = self.worksheet.row_values(1)
            if not first_row or first_row[0] != 'ID REGISTRO':
                self.worksheet.update('A1:K1', [headers])
                print("Headers inicializados")
            else:
                print("Headers ya existen")
                
        except Exception as e:
            print(f"Error al inicializar headers: {str(e)}")
