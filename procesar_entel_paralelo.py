import time
from modules.sheets_manager import SheetsManager
from modules.entel_scraper import EntelScraper
import config
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# Lock para mensajes de consola solamente
print_lock = Lock()

def save_updates_to_sheets(worker_sheets, updates, worker_id, max_retries=3):
    """
    Guarda un batch de actualizaciones con reintentos.
    Cada worker usa su propia conexión a Sheets.
    FIX DEFINITIVO: Solo escribe E (Teléfono) y L (Estado Entel) individualmente.
    NUNCA toca las columnas F-K (datos de SUNAT).
    """
    for attempt in range(max_retries):
        try:
            batch_data = []
            for update in updates:
                row = update['row']
                telefono = update['telefono']
                estado = update['estado']
                
                # SOLO escribir columnas específicas, NUNCA rangos continuos
                # Columna E = Teléfono
                batch_data.append({
                    'range': f"E{row}", 
                    'values': [[telefono]]
                })
                # Columna L = Estado Entel
                batch_data.append({
                    'range': f"L{row}", 
                    'values': [[estado]]
                })
            
            # Usar value_input_option RAW para evitar interpretación
            worker_sheets.worksheet.batch_update(batch_data, value_input_option='RAW')
            with print_lock:
                print(f"    [W{worker_id}] Batch guardado ({len(updates)} registros)")
            return True
            
        except Exception as e:
            with print_lock:
                print(f"    [W{worker_id}] ERROR batch intento {attempt+1}/{max_retries}: {str(e)[:60]}")
            if attempt < max_retries - 1:
                time.sleep(5)  # Más delay entre reintentos
            else:
                # Fallback: guardar uno por uno
                with print_lock:
                    print(f"    [W{worker_id}] Guardando uno por uno...")
                saved = 0
                for update in updates:
                    try:
                        telefono = update['telefono']
                        estado = update['estado']
                        row = update['row']
                        
                        # Solo escribir E y L individualmente
                        worker_sheets.worksheet.update(f"E{row}", [[telefono]], value_input_option='RAW')
                        worker_sheets.worksheet.update(f"L{row}", [[estado]], value_input_option='RAW')
                        saved += 1
                        time.sleep(0.5)  # Más delay
                    except Exception as ex:
                        with print_lock:
                            print(f"    [W{worker_id}] Error guardando fila {update['row']}: {str(ex)[:30]}")
                with print_lock:
                    print(f"    [W{worker_id}] Guardados {saved}/{len(updates)} uno por uno")
                return saved > 0
    return False


def procesar_worker(worker_id, rucs_asignados):
    """
    Procesa un subconjunto de RUCs.
    CADA WORKER TIENE SU PROPIA CONEXION A SHEETS.
    """
    # Crear conexión propia a Sheets para este worker
    worker_sheets = SheetsManager()
    
    entel = EntelScraper()
    processed = 0
    found = 0
    local_updates = []  # Updates locales de este worker
    
    with print_lock:
        print(f"\n[Worker {worker_id}] Iniciado - {len(rucs_asignados)} RUCs - Conexion propia a Sheets")
    
    try:
        # Hacer login
        if not entel.login():
            with print_lock:
                print(f"[Worker {worker_id}] Error: No se pudo iniciar sesion")
            return {'worker_id': worker_id, 'processed': 0, 'found': 0}
        
        for idx, ruc_data in enumerate(rucs_asignados, 1):
            ruc = ruc_data['ruc']
            row = ruc_data['row']
            
            with print_lock:
                print(f"[W{worker_id}] {idx}/{len(rucs_asignados)}: RUC {ruc}")
            
            try:
                telefono = entel.buscar_telefono(ruc)
                
                # VALIDACION: asegurar que telefono tenga contenido real
                telefono_limpio = telefono.strip() if telefono else ''
                tiene_digitos = any(c.isdigit() for c in telefono_limpio) if telefono_limpio else False
                
                if telefono_limpio and tiene_digitos:
                    found += 1
                    local_updates.append({'row': row, 'telefono': telefono_limpio, 'estado': 'OK'})
                else:
                    local_updates.append({'row': row, 'telefono': '', 'estado': 'SIN REGISTRO'})
                
                processed += 1
                
                # Guardar cada 10 registros (reducido para evitar rate limiting)
                if len(local_updates) >= 10:
                    save_updates_to_sheets(worker_sheets, local_updates, worker_id)
                    local_updates = []
                    time.sleep(2)  # Más delay entre batches
                
            except Exception as e:
                with print_lock:
                    print(f"[W{worker_id}] Error RUC {ruc}: {str(e)[:50]}")
                local_updates.append({'row': row, 'telefono': '', 'estado': 'ERROR'})
        
        # Guardar restantes de este worker
        if local_updates:
            save_updates_to_sheets(worker_sheets, local_updates, worker_id)
        
        with print_lock:
            print(f"[Worker {worker_id}] Finalizado - Encontrados: {found}/{processed}")
        return {'worker_id': worker_id, 'processed': processed, 'found': found}
        
    finally:
        entel.close()

def main():
    print("=" * 60)
    print("PROCESADOR DE TELEFONOS ENTEL - MODO PARALELO (5 WORKERS)")
    print("CADA WORKER CON SU PROPIA CONEXION A SHEETS")
    print("=" * 60)
    
    print("\nConectando a Google Sheets (lectura inicial)...")
    sheets = SheetsManager()
    
    try:
        print("\nObteniendo RUCs sin telefono...")
        all_values = sheets.worksheet.get_all_values()
        
        print(f"Total filas en sheet: {len(all_values)}")
        
        rucs_sin_telefono = []
        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) > config.COLUMNS['RUC']:
                ruc_raw = row[config.COLUMNS['RUC']].strip() if len(row) > config.COLUMNS['RUC'] else ''
                telefono = row[config.COLUMNS['TELEFONOS']].strip() if len(row) > config.COLUMNS['TELEFONOS'] else ''
                estado_entel = row[config.COLUMNS['ESTADO_ENTEL']].strip() if len(row) > config.COLUMNS['ESTADO_ENTEL'] else ''
                
                # Limpieza agresiva: extraer SOLO dígitos
                solo_digitos = ''.join(c for c in ruc_raw if c.isdigit())
                # Tomar solo los primeros 11 dígitos
                ruc = solo_digitos[:11] if len(solo_digitos) >= 11 else solo_digitos
                
                if ruc and len(ruc) == 11:
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
        print("Cada worker tendra su propia conexion a Google Sheets")
        
        # Dividir RUCs entre 5 workers
        num_workers = 5
        workers_rucs = [[] for _ in range(num_workers)]
        
        for idx, ruc_data in enumerate(rucs_sin_telefono):
            worker_id = idx % num_workers
            workers_rucs[worker_id].append(ruc_data)
        
        print("\nDistribucion de RUCs por worker:")
        for i in range(num_workers):
            print(f"  Worker {i}: {len(workers_rucs[i])} RUCs")
        
        print("\n" + "=" * 60)
        print("IMPORTANTE: Se abriran 5 navegadores.")
        print("Si alguno pide CAPTCHA, resuelvelo manualmente.")
        print("=" * 60)
        input("\nPresiona ENTER para comenzar...")
        
        start_time = time.time()
        
        # Ejecutar workers en paralelo - cada uno crea su propia conexion a Sheets
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = []
            for worker_id in range(num_workers):
                if workers_rucs[worker_id]:
                    # Ya no pasamos 'sheets' - cada worker crea su propia conexion
                    future = executor.submit(procesar_worker, worker_id, workers_rucs[worker_id])
                    futures.append(future)
                    time.sleep(3)  # Delay entre workers
            
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
