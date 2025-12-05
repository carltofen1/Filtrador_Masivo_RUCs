import time
from modules.sheets_manager import SheetsManager
from modules.entel_scraper import EntelScraper
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
    entel = EntelScraper()
    processed = 0
    found = 0
    
    print(f"\n[Worker {worker_id}] Iniciado - Procesara {len(rucs_asignados)} RUCs")
    
    try:
        # Hacer login
        if not entel.login():
            print(f"[Worker {worker_id}] Error: No se pudo iniciar sesion")
            return {'worker_id': worker_id, 'processed': 0, 'found': 0}
        
        for idx, ruc_data in enumerate(rucs_asignados, 1):
            ruc = ruc_data['ruc']
            row = ruc_data['row']
            
            print(f"[Worker {worker_id}] {idx}/{len(rucs_asignados)}: RUC {ruc}")
            
            try:
                telefono = entel.buscar_telefono(ruc)
                
                with sheets_lock:
                    if telefono:
                        found += 1
                        global_updates.append({'row': row, 'telefono': telefono, 'estado': 'OK'})
                    else:
                        global_updates.append({'row': row, 'telefono': '', 'estado': 'SIN REGISTRO'})
                
                processed += 1
                
                # Guardar cada 100 registros GLOBALES (todos los workers juntos)
                with sheets_lock:
                    if len(global_updates) >= 100:
                        print(f"\n*** Guardando {len(global_updates)} registros en batch ***")
                        batch_data = []
                        for update in global_updates:
                            batch_data.append({'range': f"E{update['row']}", 'values': [[update['telefono']]]})
                            batch_data.append({'range': f"L{update['row']}", 'values': [[update['estado']]]})
                        sheets.worksheet.batch_update(batch_data)
                        global_updates = []
                        time.sleep(1)
                
            except Exception as e:
                print(f"[Worker {worker_id}] Error RUC {ruc}: {str(e)[:50]}")
                with sheets_lock:
                    global_updates.append({'row': row, 'telefono': '', 'estado': 'ERROR'})
        
        print(f"[Worker {worker_id}] Finalizado - Encontrados: {found}/{processed}")
        return {'worker_id': worker_id, 'processed': processed, 'found': found}
        
    finally:
        entel.close()

def main():
    print("=" * 60)
    print("PROCESADOR DE TELEFONOS ENTEL - MODO PARALELO (5 WORKERS)")
    print("=" * 60)
    
    print("\nConectando a Google Sheets...")
    sheets = SheetsManager()
    
    try:
        print("\nObteniendo RUCs sin telefono...")
        all_values = sheets.worksheet.get_all_values()
        
        print(f"Total filas en sheet: {len(all_values)}")
        
        rucs_sin_telefono = []
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > config.COLUMNS['RUC']:
                ruc = row[config.COLUMNS['RUC']].strip() if len(row) > config.COLUMNS['RUC'] else ''
                telefono = row[config.COLUMNS['TELEFONOS']].strip() if len(row) > config.COLUMNS['TELEFONOS'] else ''
                estado_entel = row[config.COLUMNS['ESTADO_ENTEL']].strip() if len(row) > config.COLUMNS['ESTADO_ENTEL'] else ''
                
                if ruc and ruc.isdigit() and len(ruc) == 11:
                    if not telefono and not estado_entel:
                        rucs_sin_telefono.append({
                            'ruc': ruc,
                            'row': idx
                        })
        
        if not rucs_sin_telefono:
            print("\nNo hay RUCs sin telefono para procesar")
            return
        
        total_rucs = len(rucs_sin_telefono)
        print(f"\nSe encontraron {total_rucs} RUCs sin telefono")
        print(f"Se procesaran con 5 workers en paralelo")
        
        # Dividir RUCs entre 5 workers usando modulo 5
        workers_rucs = [[] for _ in range(5)]
        
        for idx, ruc_data in enumerate(rucs_sin_telefono):
            worker_id = idx % 5
            workers_rucs[worker_id].append(ruc_data)
        
        print("\nDistribucion de RUCs por worker:")
        for i in range(5):
            print(f"  Worker {i}: {len(workers_rucs[i])} RUCs")
        
        print("\n" + "=" * 60)
        print("IMPORTANTE: Se abriran 5 navegadores.")
        print("Si alguno pide CAPTCHA, resuelvelo manualmente.")
        print("=" * 60)
        input("\nPresiona ENTER para comenzar...")
        
        start_time = time.time()
        
        # Ejecutar workers en paralelo
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for worker_id in range(5):
                if workers_rucs[worker_id]:
                    future = executor.submit(procesar_worker, worker_id, workers_rucs[worker_id], sheets)
                    futures.append(future)
                    time.sleep(2)  # Delay entre cada worker para no saturar
            
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
                batch_data.append({'range': f"E{update['row']}", 'values': [[update['telefono']]]})
                batch_data.append({'range': f"L{update['row']}", 'values': [[update['estado']]]})
            sheets.worksheet.batch_update(batch_data)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Resumen final
        total_processed = sum(r['processed'] for r in results)
        total_found = sum(r['found'] for r in results)
        
        print("\n" + "=" * 60)
        print("RESUMEN DEL PROCESO - ENTEL PARALELO")
        print("=" * 60)
        print(f"Total procesados: {total_processed}/{total_rucs}")
        print(f"Telefonos encontrados: {total_found}")
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
