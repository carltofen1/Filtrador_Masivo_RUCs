import time
from modules.sheets_manager import SheetsManager
from modules.claro_scraper import ClaroScraper
import config

def get_rucs_con_sunat(sheets):
    try:
        all_values = sheets.worksheet.get_all_values()
        
        rucs = []
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) <= config.COLUMNS['ESTADO']:
                continue
            
            ruc = row[config.COLUMNS['RUC']].strip() if len(row) > config.COLUMNS['RUC'] else ''
            telefonos = row[config.COLUMNS['TELEFONOS']].strip() if len(row) > config.COLUMNS['TELEFONOS'] else ''
            estado = row[config.COLUMNS['ESTADO']].strip() if len(row) > config.COLUMNS['ESTADO'] else ''
            
            if ruc and estado == 'SUNAT OK' and not telefonos:
                rucs.append({
                    'ruc': ruc,
                    'row': idx,
                    'data_actual': row
                })
        
        print(f"Se encontraron {len(rucs)} RUCs listos para Claro")
        return rucs
        
    except Exception as e:
        print(f"Error al obtener RUCs: {str(e)}")
        return []

def main():
    print("=" * 60)
    print("PROCESADOR DE CLARO")
    print("=" * 60)
    
    print("\nConectando a Google Sheets...")
    sheets = SheetsManager()
    
    print("\nInicializando scraper de Claro...")
    claro = ClaroScraper()
    
    try:
        print("\nObteniendo RUCs con datos de SUNAT...")
        rucs_to_process = get_rucs_con_sunat(sheets)
        
        if not rucs_to_process:
            print("\nNo hay RUCs para procesar")
            print("   Asegúrate de haber ejecutado 'python procesar_sunat.py' primero")
            return
        
        total_rucs = len(rucs_to_process)
        print(f"\nSe encontraron {total_rucs} RUCs listos para Claro")
        
        if total_rucs > 5:
            print("\n" + "!" * 30)
            print(f"ATENCION: Tienes {total_rucs} RUCs pendientes")
            print("!" * 30)
            respuesta = input("\n¿Quieres procesar TODOS o solo los primeros 5 (TEST)? (todos/test): ").lower()
            
            if respuesta == 'test':
                rucs_to_process = rucs_to_process[:5]
                total_rucs = 5
                print(f"\nModo TEST: Se procesarán solo los primeros {total_rucs} RUCs")
            else:
                print(f"\nSe procesarán TODOS los {total_rucs} RUCs")
        
        print("\nIniciando sesión en Claro...")
        if not claro.login():
            print("No se pudo iniciar sesión en Claro")
            return
        
        batch_updates = []
        processed = 0
        errors = 0
        
        for idx, ruc_data in enumerate(rucs_to_process, 1):
            ruc = ruc_data['ruc']
            row = ruc_data['row']
            data_actual = ruc_data['data_actual']
            
            print(f"\n{'=' * 60}")
            print(f"Procesando {idx}/{total_rucs}: RUC {ruc}")
            print(f"{'=' * 60}")
            
            try:
                print("Consultando plataforma Claro...")
                claro_data = claro.buscar_por_ruc(ruc)
                
                if not claro_data:
                    print(f"No se pudo obtener datos de Claro para {ruc}")
                    errors += 1
                    continue
                
                row_data = data_actual[:config.COLUMNS['TELEFONOS']]
                row_data.append(claro_data.get('telefonos', ''))
                
                for col_idx in range(config.COLUMNS['TELEFONOS'] + 1, config.COLUMNS['ESTADO']):
                    if col_idx < len(data_actual):
                        row_data.append(data_actual[col_idx])
                    else:
                        row_data.append('')
                
                row_data.append('Completado')
                
                batch_updates.append({
                    'row': row,
                    'data': row_data
                })
                
                processed += 1
                print(f"Teléfonos de Claro agregados para RUC {ruc}")
                
                if len(batch_updates) >= config.BATCH_SIZE:
                    print(f"\nGuardando batch de {len(batch_updates)} registros...")
                    sheets.update_row_batch(batch_updates)
                    batch_updates = []
                    time.sleep(config.DELAY_BETWEEN_BATCHES)
                
            except Exception as e:
                print(f"Error procesando RUC {ruc}: {str(e)}")
                errors += 1
                continue
        
        if batch_updates:
            print(f"\nGuardando últimos {len(batch_updates)} registros...")
            sheets.update_row_batch(batch_updates)
        
        print("\n" + "=" * 60)
        print("RESUMEN DEL PROCESO - CLARO")
        print("=" * 60)
        print(f"Total procesados: {processed}/{total_rucs}")
        print(f"Errores: {errors}")
        if total_rucs > 0:
            print(f"Tasa de éxito: {(processed/total_rucs)*100:.2f}%")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nProceso interrumpido por el usuario")
        
    except Exception as e:
        print(f"\nError fatal: {str(e)}")
        
    finally:
        print("\nCerrando conexiones...")
        claro.close()
        print("Proceso finalizado")

if __name__ == "__main__":
    main()
