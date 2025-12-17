import time
from modules.sheets_manager import SheetsManager
from modules.segmentacion_scraper import SegmentacionScraper
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
    segmentacion = SegmentacionScraper(headless=True)
    processed = 0
    found = 0
    
    print(f"\n[Worker {worker_id}] Iniciado - Procesara {len(rucs_asignados)} RUCs")
    
    try:
        # Hacer login
        if not segmentacion.login():
            print(f"[Worker {worker_id}] Error: No se pudo iniciar sesion")
            return {'worker_id': worker_id, 'processed': 0, 'found': 0}
        
        for idx, ruc_data in enumerate(rucs_asignados, 1):
            ruc = ruc_data['ruc']
            row = ruc_data['row']
            
            try:
                tipo_cliente = segmentacion.buscar_tipo_cliente(ruc)
                
                # Mostrar resultado
                print(f"[W{worker_id}] {idx}/{len(rucs_asignados)}: {ruc} => {tipo_cliente or 'Sin Segmento'}")
                
                with sheets_lock:
                    if tipo_cliente and tipo_cliente not in ['Sin Segmento', 'Sin Datos']:
                        found += 1
                    global_updates.append({
                        'row': row, 
                        'segmento': tipo_cliente or 'Sin Segmento'
                    })
                
                processed += 1
                
                # Guardar cada 100 registros GLOBALES
                with sheets_lock:
                    if len(global_updates) >= 100:
                        print(f"\n*** Guardando {len(global_updates)} registros en batch ***")
                        batch_data = []
                        for update in global_updates:
                            # Columna N para SEGMENTO (índice 13)
                            batch_data.append({
                                'range': f"N{update['row']}", 
                                'values': [[update['segmento']]]
                            })
                        sheets.worksheet.batch_update(batch_data)
                        global_updates = []
                        time.sleep(1)
                
            except Exception as e:
                print(f"[Worker {worker_id}] Error RUC {ruc}: {str(e)[:50]}")
                with sheets_lock:
                    global_updates.append({
                        'row': row, 
                        'segmento': 'ERROR'
                    })
        
        print(f"[Worker {worker_id}] Finalizado - Encontrados: {found}/{processed}")
        return {'worker_id': worker_id, 'processed': processed, 'found': found}
        
    finally:
        segmentacion.close()

def main():
    print("=" * 60)
    print("PROCESADOR DE SEGMENTACION - MODO PARALELO (5 WORKERS)")
    print("=" * 60)
    
    print("\nConectando a Google Sheets...")
    sheets = SheetsManager()
    
    try:
        # Eliminar RUCs duplicados antes de procesar
        sheets.eliminar_rucs_duplicados()
        
        print("\nObteniendo RUCs sin segmentacion...")
        all_values = sheets.worksheet.get_all_values()
        
        print(f"Total filas en sheet: {len(all_values)}")
        
        rucs_sin_segmentacion = []
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > config.COLUMNS['RUC']:
                ruc_raw = row[config.COLUMNS['RUC']].strip() if len(row) > config.COLUMNS['RUC'] else ''
                
                # Columna N (índice 13) para SEGMENTO
                segmento = row[13].strip() if len(row) > 13 else ''
                
                # Limpieza agresiva del RUC
                solo_digitos = ''.join(c for c in ruc_raw if c.isdigit())
                ruc = solo_digitos[:11] if len(solo_digitos) >= 11 else solo_digitos
                
                if ruc and len(ruc) == 11:
                    if not segmento:
                        rucs_sin_segmentacion.append({
                            'ruc': ruc,
                            'row': idx
                        })
        
        if not rucs_sin_segmentacion:
            print("\nNo hay RUCs sin segmentacion para procesar")
            return
        
        total_rucs = len(rucs_sin_segmentacion)
        print(f"\nSe encontraron {total_rucs} RUCs sin segmentacion")
        print(f"Se procesaran con 5 workers en paralelo")
        
        # Dividir RUCs entre 5 workers
        num_workers = 5
        workers_rucs = [[] for _ in range(num_workers)]
        
        for idx, ruc_data in enumerate(rucs_sin_segmentacion):
            worker_id = idx % num_workers
            workers_rucs[worker_id].append(ruc_data)
        
        print("\nDistribucion de RUCs por worker:")
        for i in range(num_workers):
            print(f"  Worker {i}: {len(workers_rucs[i])} RUCs")
        
        print("\n" + "=" * 60)
        print("EJECUTANDO EN MODO HEADLESS (5 workers en segundo plano)")
        print("=" * 60)
        input("\nPresiona ENTER para comenzar...")
        
        start_time = time.time()
        
        # Ejecutar workers en paralelo
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                if workers_rucs[worker_id]:
                    future = executor.submit(procesar_worker, worker_id, workers_rucs[worker_id], sheets)
                    futures.append(future)
                    time.sleep(3)  # Delay entre cada worker
            
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
                    'range': f"N{update['row']}", 
                    'values': [[update['segmento']]]
                })
            sheets.worksheet.batch_update(batch_data)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Resumen final
        total_processed = sum(r['processed'] for r in results)
        total_found = sum(r['found'] for r in results)
        
        print("\n" + "=" * 60)
        print("RESUMEN DEL PROCESO - SEGMENTACION PARALELO")
        print("=" * 60)
        print(f"Total procesados: {total_processed}/{total_rucs}")
        print(f"Tipos de cliente encontrados: {total_found}")
        if total_processed > 0:
            print(f"Tasa de exito: {(total_found/total_processed)*100:.2f}%")
        print(f"Tiempo total: {total_time/60:.2f} minutos ({total_time/3600:.2f} horas)")
        if total_rucs > 0:
            print(f"Velocidad: {total_time/total_rucs:.2f} segundos por RUC")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nProceso interrumpido por el usuario")
        
    except Exception as e:
        print(f"\nError fatal: {str(e)}")

if __name__ == "__main__":
    main()
