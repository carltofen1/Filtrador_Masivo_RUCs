"""
Procesador de SUNAT por Razón Social → RUC (PARALELO + RÁPIDO)
5 workers en paralelo, solo extrae RUC de la lista (sin click en detalle).
"""
import time
from modules.sheets_manager import SheetsManager
from modules.sunat_scraper import SunatScraper
import config
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import re

sheets_lock = Lock()
global_updates = []

def limpiar_razon_social(texto: str) -> str:
    """Limpia caracteres rotos sin destruir el texto."""
    texto = texto.replace('\ufffd', '')
    texto = texto.replace('ï¿½', '')
    texto = re.sub(r'[^\w\s.&\-/]', '', texto, flags=re.UNICODE)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto

def guardar_batch(sheets):
    """Guarda los updates acumulados en Google Sheets."""
    global global_updates
    if not global_updates:
        return
    
    updates_to_save = list(global_updates)
    global_updates = []
    
    try:
        sheets.worksheet.batch_update(updates_to_save, value_input_option='RAW')
        print(f"\n  💾 GUARDADOS {len(updates_to_save)} RUCs en Sheets ✓\n")
    except Exception as e:
        print(f"\n  ❌ ERROR guardando: {e}")
        try:
            time.sleep(2)
            sheets.worksheet.batch_update(updates_to_save, value_input_option='RAW')
            print(f"\n  💾 GUARDADOS {len(updates_to_save)} en reintento ✓\n")
        except Exception as e2:
            print(f"\n  ❌❌ FALLÓ reintento: {e2}")
            global_updates = updates_to_save + global_updates

def procesar_worker(worker_id, razones_asignadas, sheets):
    global global_updates
    scraper = SunatScraper(headless=False)
    encontrados = 0
    errors = 0
    
    print(f"\n[Worker {worker_id}] Iniciado - {len(razones_asignadas)} razones sociales")
    
    try:
        for idx, item in enumerate(razones_asignadas, 1):
            razon = item['razon_social']
            row = item['row']
            
            razon_limpia = limpiar_razon_social(razon)
            
            if len(razon_limpia) < 2:
                errors += 1
                continue
            
            print(f"[W{worker_id}] {idx}/{len(razones_asignadas)}: {razon_limpia}")
            
            try:
                resultados = scraper.consultar_por_razon_social(razon_limpia, max_resultados=1)
                
                if resultados:
                    mejor = resultados[0]
                    ruc = mejor.get('ruc', '')
                    razon_oficial = mejor.get('razon_social', razon)
                    
                    if ruc:
                        with sheets_lock:
                            global_updates.append({
                                'range': f'B{row}:C{row}',
                                'values': [[ruc, razon_oficial]]
                            })
                        encontrados += 1
                        print(f"  ✓ {ruc} - {razon_oficial}")
                    else:
                        errors += 1
                else:
                    errors += 1
                
                with sheets_lock:
                    if len(global_updates) >= 30:
                        guardar_batch(sheets)
                        
            except Exception as e:
                print(f"  ✗ Error: {str(e)[:50]}")
                errors += 1
        
        print(f"[Worker {worker_id}] DONE - Encontrados: {encontrados}, Errores: {errors}")
        return {'worker_id': worker_id, 'encontrados': encontrados, 'errors': errors}
        
    finally:
        scraper.close()


def main():
    print("=" * 60)
    print("PROCESADOR SUNAT - RAZÓN SOCIAL → RUC")
    print("5 WORKERS EN PARALELO (MODO RÁPIDO)")
    print("=" * 60)
    
    print("\nConectando a Google Sheets...")
    sheets = SheetsManager()
    
    try:
        sheets.initialize_headers()
        
        print("\nObteniendo Razones Sociales a procesar...")
        all_values = sheets.worksheet.get_all_values()
        
        razones_pendientes = []
        col_razon = config.COLUMNS['RAZON_SOCIAL']
        col_ruc = config.COLUMNS['RUC']
        
        for idx, row in enumerate(all_values[1:], start=2):
            razon_social = row[col_razon].strip() if len(row) > col_razon else ''
            ruc = row[col_ruc].strip() if len(row) > col_ruc else ''
            
            if razon_social and not ruc:
                razones_pendientes.append({
                    'razon_social': razon_social,
                    'row': idx
                })
        
        if not razones_pendientes:
            print("\nNo hay Razones Sociales pendientes.")
            return
        
        total = len(razones_pendientes)
        print(f"\n{total} Razones Sociales pendientes")
        
        NUM_WORKERS = 5
        workers_data = [[] for _ in range(NUM_WORKERS)]
        for idx, item in enumerate(razones_pendientes):
            workers_data[idx % NUM_WORKERS].append(item)
        
        print(f"\nDistribución por worker:")
        for i in range(NUM_WORKERS):
            print(f"  Worker {i}: {len(workers_data[i])} razones sociales")
        
        print(f"\nIniciando {NUM_WORKERS} workers en paralelo...")
        start_time = time.time()
        
        global global_updates
        
        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = []
            for wid in range(NUM_WORKERS):
                if workers_data[wid]:
                    future = executor.submit(procesar_worker, wid, workers_data[wid], sheets)
                    futures.append(future)
                    time.sleep(2)
            
            results = []
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"\nError en worker: {str(e)}")
        
        with sheets_lock:
            if global_updates:
                guardar_batch(sheets)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        total_encontrados = sum(r['encontrados'] for r in results)
        total_errors = sum(r['errors'] for r in results)
        
        print("\n" + "=" * 60)
        print("RESUMEN")
        print("=" * 60)
        print(f"Total: {total}")
        print(f"RUCs encontrados: {total_encontrados}")
        print(f"Sin resultado: {total_errors}")
        if total > 0:
            print(f"Tasa éxito: {(total_encontrados/total)*100:.1f}%")
        print(f"Tiempo: {total_time/60:.1f} min ({total_time/3600:.1f} horas)")
        print("=" * 60)
        
    except KeyboardInterrupt:
        print("\n\nInterrumpido - guardando...")
        with sheets_lock:
            if global_updates:
                guardar_batch(sheets)
    
    except Exception as e:
        print(f"\nError fatal: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
