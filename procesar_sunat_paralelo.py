import time
from modules.sheets_manager import SheetsManager
from modules.sunat_scraper import SunatScraper
import config
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Lock y cola compartida para acumular todos los updates
sheets_lock = Lock()
global_updates = []

def procesar_worker(worker_id, rucs_asignados, sheets):
    """
    Procesa un subconjunto de RUCs asignados a este worker
    """
    global global_updates
    sunat = SunatScraper()
    processed = 0
    errors = 0
    
    print(f"\n[Worker {worker_id}] Iniciado - Procesará {len(rucs_asignados)} RUCs")
    
    try:
        for idx, ruc_data in enumerate(rucs_asignados, 1):
            ruc = ruc_data['ruc']
            row = ruc_data['row']
            
            print(f"[Worker {worker_id}] {idx}/{len(rucs_asignados)}: RUC {ruc}")
            
            try:
                sunat_data = sunat.consultar_ruc(ruc)
                
                if not sunat_data:
                    with sheets_lock:
                        global_updates.append({
                            'row': row,
                            'data_ad': [row - 1, ruc, '', ''],  # A:D (sin tocar E=Teléfonos)
                            'data_fk': ['', '', '', '', '', 'Error - SUNAT']  # F:K
                        })
                    errors += 1
                else:
                    estado_final = sunat_data.get('estado_contribuyente', 'DESCONOCIDO')
                    
                    # DATOS SEPARADOS: A:D y F:K (NUNCA tocar E=Teléfonos)
                    data_ad = [
                        row - 1,
                        ruc,
                        sunat_data.get('razon_social', ''),
                        sunat_data.get('representante_legal', '')
                    ]
                    data_fk = [
                        sunat_data.get('documento_identidad', ''),
                        sunat_data.get('departamento', ''),
                        sunat_data.get('provincia', ''),
                        sunat_data.get('distrito', ''),
                        sunat_data.get('direccion', ''),
                        estado_final
                    ]
                    
                    with sheets_lock:
                        global_updates.append({'row': row, 'data_ad': data_ad, 'data_fk': data_fk})
                    
                    processed += 1
                
                # Guardar cada 100 registros GLOBALES (todos los workers juntos)
                with sheets_lock:
                    if len(global_updates) >= 100:
                        print(f"\n*** Guardando {len(global_updates)} registros en batch ***")
                        sheets.update_row_batch(global_updates)
                        global_updates = []
                        time.sleep(1)
                
            except Exception as e:
                print(f"[Worker {worker_id}] Error RUC {ruc}: {str(e)[:50]}")
                with sheets_lock:
                    global_updates.append({
                        'row': row,
                        'data_ad': [row - 1, ruc, '', ''],
                        'data_fk': ['', '', '', '', '', f'Error: {str(e)[:30]}']
                    })
                errors += 1
        
        print(f"[Worker {worker_id}] Finalizado - Procesados: {processed}, Errores: {errors}")
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
        
        # Eliminar RUCs duplicados antes de procesar
        sheets.eliminar_rucs_duplicados()
        
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
        print("Se guardarán en Sheets cada 100 registros acumulados")
        
        start_time = time.time()
        
        # Ejecutar workers en paralelo
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for worker_id in range(5):
                if workers_rucs[worker_id]:  # Solo si tiene RUCs asignados
                    future = executor.submit(procesar_worker, worker_id, workers_rucs[worker_id], sheets)
                    futures.append(future)
                    time.sleep(2)  # Delay entre workers
            
            # Esperar a que todos terminen
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
            sheets.update_row_batch(global_updates)
        
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
