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
                    # Estados de SUNAT que indican que ya fue procesado
                    estados_sunat_procesados = [
                        'ACTIVO', 'ACTIVA', 
                        'BAJA DE OFICIO', 'BAJA DEFINITIVA', 'BAJA PROVISIONAL',
                        'SUSPENSIÓN TEMPORAL', 'SUSPENSION TEMPORAL',
                        'NO HABIDO', 'NO HALLADO',
                        'ERROR - SUNAT', 'ERROR', 'SIN REGISTRO',
                        'DESCONOCIDO'
                    ]
                    
                    # Solo saltar si tiene un estado SUNAT válido (no "OK" de Entel)
                    ya_procesado = any(estado.startswith(e) or estado == e for e in estados_sunat_procesados)
                    
                    if not ya_procesado:
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
        """
        Actualiza filas en batch. 
        IMPORTANTE: Usa rangos separados A:D y F:K para NUNCA sobrescribir columna E (Teléfonos).
        """
        try:
            batch_data = []
            for update in updates:
                row = update['row']
                
                # NUEVO FORMATO: data_ad y data_fk (separados para preservar Teléfonos)
                if 'data_ad' in update and 'data_fk' in update:
                    # Rango A:D (ID, RUC, Razón Social, Representante)
                    batch_data.append({
                        'range': f'A{row}:D{row}',
                        'values': [update['data_ad']]
                    })
                    # Rango F:K (Doc Identidad, Depto, Prov, Distrito, Dirección, Estado)
                    batch_data.append({
                        'range': f'F{row}:K{row}',
                        'values': [update['data_fk']]
                    })
                # FORMATO LEGACY (compatibilidad hacia atrás, pero ya no debería usarse)
                elif 'data' in update:
                    data = update['data']
                    batch_data.append({
                        'range': f'A{row}:K{row}',
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
    
    def eliminar_rucs_duplicados(self) -> int:
        """
        Elimina RUCs duplicados del sheet, manteniendo solo la primera ocurrencia.
        Retorna la cantidad de duplicados eliminados.
        ULTRA-RÁPIDO: Reconstruye la hoja sin duplicados en segundos.
        """
        try:
            print("\nVerificando RUCs duplicados...")
            all_values = self.worksheet.get_all_values()
            
            if len(all_values) <= 1:
                print("   No hay datos para verificar")
                return 0
            
            headers = all_values[0]
            datos = all_values[1:]
            total_original = len(datos)
            
            # Filtrar duplicados en memoria (ultra-rápido)
            ruc_col = config.COLUMNS['RUC']
            rucs_vistos = set()
            datos_unicos = []
            
            for row in datos:
                if len(row) > ruc_col:
                    ruc_raw = row[ruc_col].strip()
                    solo_digitos = ''.join(c for c in ruc_raw if c.isdigit())
                    ruc = solo_digitos[:11] if len(solo_digitos) >= 11 else solo_digitos
                    
                    if ruc and len(ruc) == 11:
                        if ruc not in rucs_vistos:
                            rucs_vistos.add(ruc)
                            datos_unicos.append(row)
                    else:
                        # Mantener filas sin RUC válido
                        datos_unicos.append(row)
                else:
                    datos_unicos.append(row)
            
            duplicados_eliminados = total_original - len(datos_unicos)
            
            if duplicados_eliminados == 0:
                print("   No se encontraron RUCs duplicados")
                return 0
            
            print(f"   Se encontraron {duplicados_eliminados} RUCs duplicados")
            print(f"   Reconstruyendo hoja sin duplicados...")
            
            # Reconstruir la hoja completa (solo 2-3 llamadas API)
            # 1. Limpiar todo el contenido excepto headers
            self.worksheet.batch_clear([f'A2:Z{total_original + 1}'])
            
            # 2. Escribir datos únicos en lotes grandes
            if datos_unicos:
                # Dividir en lotes de 5000 filas para evitar límites de API
                batch_size = 5000
                for i in range(0, len(datos_unicos), batch_size):
                    batch = datos_unicos[i:i + batch_size]
                    start_row = i + 2  # +2 porque fila 1 son headers
                    end_row = start_row + len(batch) - 1
                    
                    # Determinar el rango de columnas necesario
                    max_cols = max(len(row) for row in batch) if batch else 1
                    end_col = chr(ord('A') + min(max_cols - 1, 25))  # Máximo Z
                    
                    range_name = f'A{start_row}:{end_col}{end_row}'
                    self.worksheet.update(range_name, batch, value_input_option='RAW')
                    
                    print(f"   Escritas filas {start_row} a {end_row}")
            
            print(f"   ✓ Eliminados {duplicados_eliminados} RUCs duplicados en segundos")
            print(f"   Total de registros: {total_original} → {len(datos_unicos)}")
            return duplicados_eliminados
            
        except Exception as e:
            print(f"   Error al eliminar duplicados: {str(e)}")
            return 0
