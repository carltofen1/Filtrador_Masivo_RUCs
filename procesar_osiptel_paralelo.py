import time
from modules.sheets_manager import SheetsManager
from modules.osiptel_scraper import OsiptelScraper
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
    osiptel = OsiptelScraper(headless=True)
    processed = 0
    found = 0
    
    print(f"\n[Worker {worker_id}] Iniciado - Procesara {len(rucs_asignados)} RUCs")
    
    try:
        # Inicializar
        if not osiptel.inicializar():
            print(f"[Worker {worker_id}] Error: No se pudo inicializar")
            return {'worker_id': worker_id, 'processed': 0, 'found': 0}
        
        for idx, ruc_data in enumerate(rucs_asignados, 1):
            ruc = ruc_data['ruc']
            row = ruc_data['row']
            
            print(f"[Worker {worker_id}] {idx}/{len(rucs_asignados)}: RUC {ruc}")
            
            try:
                start_req = time.time()
                cantidad = osiptel.consultar_lineas(ruc)
                duration = time.time() - start_req
                
                # Mostrar resultado en terminal
                print(f"    => {cantidad or '0'} líneas ({duration:.2f}s)")
                
                with sheets_lock:
                    if cantidad and cantidad != "0":
                        found += 1
                    global_updates.append({
                        'row': row, 
                        'cantidad': cantidad or '0'
                    })
                
                processed += 1
                
                # Sin esperas artificiales, directo al siguiente
                time.sleep(0.01)
                
                # Guardar cada 100 registros GLOBALES
                with sheets_lock:
                    if len(global_updates) >= 100:
                        print(f"\n*** Guardando {len(global_updates)} registros en batch ***")
                        batch_data = []
                        for update in global_updates:
                            # Columna M para cantidad de líneas (índice 12)
                            batch_data.append({
                                'range': f"M{update['row']}", 
                                'values': [[update['cantidad']]]
                            })
                        sheets.worksheet.batch_update(batch_data)
                        global_updates = []
                        time.sleep(1)
                
            except Exception as e:
                print(f"[Worker {worker_id}] Error RUC {ruc}: {str(e)[:50]}")
                with sheets_lock:
                    global_updates.append({
                        'row': row, 
                        'cantidad': 'ERROR'
                    })
        
        print(f"[Worker {worker_id}] Finalizado - Con líneas: {found}/{processed}")
        return {'worker_id': worker_id, 'processed': processed, 'found': found}
        
    finally:
        osiptel.close()

def main():
    print("=" * 60)
    print("PROCESADOR DE OSIPTEL - CANTIDAD DE LINEAS (1 WORKER)")
    print("=" * 60)
    
    print("\nConectando a Google Sheets...")
    sheets = SheetsManager()
    
    try:
        print("\nObteniendo RUCs sin cantidad de lineas...")
        all_values = sheets.worksheet.get_all_values()
        
        print(f"Total filas en sheet: {len(all_values)}")
        
        rucs_sin_lineas = []
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > config.COLUMNS['RUC']:
                ruc_raw = row[config.COLUMNS['RUC']].strip() if len(row) > config.COLUMNS['RUC'] else ''
                
                # Columna M (índice 12) para cantidad de líneas
                cantidad = row[12].strip() if len(row) > 12 else ''
                
                # Limpieza agresiva del RUC
                solo_digitos = ''.join(c for c in ruc_raw if c.isdigit())
                ruc = solo_digitos[:11] if len(solo_digitos) >= 11 else solo_digitos
                
                if ruc and len(ruc) == 11:
                    if not cantidad:
                        rucs_sin_lineas.append({
                            'ruc': ruc,
                            'row': idx
                        })
        
        if not rucs_sin_lineas:
            print("\nNo hay RUCs sin cantidad de lineas para procesar")
            return
        
        total_rucs = len(rucs_sin_lineas)
        print(f"\nSe encontraron {total_rucs} RUCs sin cantidad de lineas")
        print(f"Se procesara con 5 workers")
        
        # 1 worker para máxima estabilidad
        num_workers = 1
        workers_rucs = [[] for _ in range(num_workers)]
        
        for idx, ruc_data in enumerate(rucs_sin_lineas):
            worker_id = idx % num_workers
            workers_rucs[worker_id].append(ruc_data)
        
        print("\nDistribucion de RUCs por worker:")
        for i in range(num_workers):
            print(f"  Worker {i}: {len(workers_rucs[i])} RUCs")
        
        print("\n" + "=" * 60)
        input("\nPresiona ENTER para comenzar...")
        
        start_time = time.time()
        
        # Ejecutar workers en paralelo
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                if workers_rucs[worker_id]:
                    future = executor.submit(procesar_worker, worker_id, workers_rucs[worker_id], sheets)
                    futures.append(future)
                    time.sleep(2)  # Delay entre cada worker
            
            results = []
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    print(f"\nError en worker: {str(e)}")
        
        # Guardar registros restantes
        if global_updates:
            print(f"\n*** Guardando ultimos {len(global_updates)} registros ***")
            batch_data = []
            for update in global_updates:
                batch_data.append({
                    'range': f"M{update['row']}", 
                    'values': [[update['cantidad']]]
                })
            sheets.worksheet.batch_update(batch_data)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Resumen final
        total_processed = sum(r['processed'] for r in results)
        total_found = sum(r['found'] for r in results)
        
        print("\n" + "=" * 60)
        print("RESUMEN DEL PROCESO - OSIPTEL")
        print("=" * 60)
        print(f"Total procesados: {total_processed}/{total_rucs}")
        print(f"RUCs con líneas: {total_found}")
        if total_processed > 0:
            print(f"Tasa con líneas: {(total_found/total_processed)*100:.2f}%")
        print(f"Tiempo total: {total_time/60:.2f} minutos")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nProceso interrumpido por el usuario")
        
    except Exception as e:
        print(f"\nError fatal: {str(e)}")

if __name__ == "__main__":
    main()
