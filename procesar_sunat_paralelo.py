import time
from modules.sheets_manager import SheetsManager
from modules.sunat_scraper import SunatScraper
import config
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Lock para sincronizar escrituras a Sheets
sheets_lock = Lock()

def procesar_worker(worker_id, rucs_asignados, sheets):
    """
    Procesa un subconjunto de RUCs asignados a este worker
    """
    sunat = SunatScraper()
    batch_updates = []
    processed = 0
    errors = 0
    
    print(f"\n[Worker {worker_id}] Iniciado - Procesará {len(rucs_asignados)} RUCs")
    
    try:
        for idx, ruc_data in enumerate(rucs_asignados, 1):
            ruc = ruc_data['ruc']
            row = ruc_data['row']
            
            print(f"\n[Worker {worker_id}] Procesando {idx}/{len(rucs_asignados)}: RUC {ruc}")
            
            try:
                sunat_data = sunat.consultar_ruc(ruc)
                
                if not sunat_data:
                    print(f"[Worker {worker_id}] No se pudo obtener datos de SUNAT para {ruc}")
                    batch_updates.append({
                        'row': row,
                        'data': [
                            row - 1, ruc, '', '', '', '', '', '', '', '',
                            'Error - SUNAT'
                        ]
                    })
                    errors += 1
                else:
                    estado_final = sunat_data.get('estado_contribuyente', 'DESCONOCIDO')
                    
                    row_data = [
                        row - 1,
                        ruc,
                        sunat_data.get('razon_social', ''),
                        sunat_data.get('representante_legal', ''),
                        '',
                        sunat_data.get('documento_identidad', ''),
                        sunat_data.get('departamento', ''),
                        sunat_data.get('provincia', ''),
                        sunat_data.get('distrito', ''),
                        sunat_data.get('direccion', ''),
                        estado_final
                    ]
                    
                    batch_updates.append({
                        'row': row,
                        'data': row_data
                    })
                    
                    processed += 1
                    print(f"[Worker {worker_id}] Datos preparados para RUC {ruc}")
                
                # Guardar cada 20 registros
                if len(batch_updates) >= 20:
                    with sheets_lock:
                        print(f"\n[Worker {worker_id}] Guardando batch de {len(batch_updates)} registros...")
                        sheets.update_row_batch(batch_updates)
                        batch_updates = []
                        time.sleep(0.2)
                
            except Exception as e:
                print(f"[Worker {worker_id}] Error procesando RUC {ruc}: {str(e)}")
                error_msg = str(e)[:50]
                batch_updates.append({
                    'row': row,
                    'data': [
                        row - 1, ruc, '', '', '', '', '', '', '', '',
                        f'Error: {error_msg}'
                    ]
                })
                errors += 1
        
        # Guardar registros restantes
        if batch_updates:
            with sheets_lock:
                print(f"\n[Worker {worker_id}] Guardando últimos {len(batch_updates)} registros...")
                sheets.update_row_batch(batch_updates)
        
        print(f"\n[Worker {worker_id}] Finalizado - Procesados: {processed}, Errores: {errors}")
        return {'worker_id': worker_id, 'processed': processed, 'errors': errors}
        
    finally:
        sunat.close()

def main():
    print("=" * 60)
    print("PROCESADOR DE SUNAT - MODO PARALELO (5 WORKERS)")
    print("=" * 60)
    
    print("\nConectando a Google Sheets...")
    sheets = SheetsManager()
    
    try:
        sheets.initialize_headers()
        
        print("\nObteniendo RUCs a procesar...")
        rucs_to_process = sheets.get_rucs()
        
        if not rucs_to_process:
            print("\nNo hay RUCs para procesar")
            return
        
        total_rucs = len(rucs_to_process)
        print(f"\nSe encontraron {total_rucs} RUCs pendientes")
        print(f"Se procesarán TODOS los {total_rucs} RUCs con 5 workers en paralelo")
        
        # Dividir RUCs entre 5 workers usando módulo 5
        workers_rucs = [[] for _ in range(5)]
        
        for idx, ruc_data in enumerate(rucs_to_process):
            worker_id = idx % 5
            workers_rucs[worker_id].append(ruc_data)
        
        # Mostrar distribución
        print("\nDistribución de RUCs por worker:")
        for i in range(5):
            print(f"  Worker {i}: {len(workers_rucs[i])} RUCs")
        
        print(f"\nIniciando procesamiento paralelo con 5 workers...")
        print("Cada worker guardará en Sheets cada 20 registros")
        
        start_time = time.time()
        
        # Ejecutar workers en paralelo
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for worker_id in range(5):
                if workers_rucs[worker_id]:  # Solo si tiene RUCs asignados
                    future = executor.submit(procesar_worker, worker_id, workers_rucs[worker_id], sheets)
                    futures.append(future)
            
            # Esperar a que todos terminen
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"\nError en worker: {str(e)}")
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Resumen final
        total_processed = sum(r['processed'] for r in results)
        total_errors = sum(r['errors'] for r in results)
        
        print("\n" + "=" * 60)
        print("RESUMEN DEL PROCESO - SUNAT PARALELO")
        print("=" * 60)
        print(f"Total procesados: {total_processed}/{total_rucs}")
        print(f"Errores: {total_errors}")
        if total_rucs > 0:
            print(f"Tasa de éxito: {(total_processed/total_rucs)*100:.2f}%")
        print(f"Tiempo total: {total_time/60:.2f} minutos ({total_time/3600:.2f} horas)")
        print(f"Velocidad: {total_time/total_rucs:.2f} segundos por RUC")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nProceso interrumpido por el usuario")
        
    except Exception as e:
        print(f"\nError fatal: {str(e)}")

if __name__ == "__main__":
    main()
