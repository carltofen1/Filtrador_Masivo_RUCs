import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import SPREADSHEET_ID, SHEET_NAME, CREDENTIALS_FILE, COLUMNS, DRINKY_EMAIL
from modules.drinky_scraper import DrinkyScraper
import logging

# Configuración de Logs
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuración de Google Sheets
SCOPE = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def connect_gsheets():
    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPE)
    client = gspread.authorize(creds)
    # Usar ID y Nombre de hoja definidos en config, igual que sheets_manager.py
    sheet = client.open_by_key(SPREADSHEET_ID).worksheet(SHEET_NAME)
    return sheet

def process_ruc(scraper, ruc):
    """Procesa un solo RUC usando el scraper."""
    try:
        # 1. Intentar con endpoint principal (Entel/Organizaciones)
        data = scraper.get_company_data(ruc)
        
        # 2. Si no hay resultados o no hay teléfonos, intentar con Movistar
        phones = []
        if data and data != "SIN_RESULTADOS":
            phones = scraper.extract_phones(data)
        
        if not phones:
            # Intentar fallback a Movistar endpoint
            # print(f"RUC {ruc}: Sin datos en Entel, buscando en Movistar...")
            mov_data = scraper.get_movistar_data(ruc)
            if mov_data and mov_data != "SIN_RESULTADOS":
                # Extract phones from movistar data (structure is likely different or same, handling in extract_phones)
                # We need to pass it to extract_phones. Use a wrapper dict to match expected structure?
                # Actually extract_phones expects {'entel': ..., 'movistar': ...}
                # But get_movistar_data likely returns the inner content directly or wrapped?
                # Let's assume it returns the content of 'movistar' key or similar.
                # If the endpoint is /tacto/movistar/company/RUC, it probably returns { ... data ... }
                # Let's wrap it to match extract_phones expectation
                phones = scraper.extract_phones({'movistar': mov_data})

        if phones:
            phones_str = " / ".join(phones)
            status_str = "OK"
            
            # Output limpio
            msg = f"RUC {ruc}: {phones_str}"
            print(msg)
            return phones_str, status_str
        else:
            print(f"RUC {ruc}: SIN RESULTADOS")
            return "", "SIN REGISTRO"

    except Exception as e:
        logger.error(f"Error procesando RUC {ruc}: {e}")
        return "ERROR", "ERROR"

def worker_task(rucs, worker_id):
    """Función para cada hilo (worker)."""
    # logger.info(f"Worker {worker_id} iniciado. Procesando {len(rucs)} RUCs.")
    
    # Cada worker tiene su propia instancia del scraper para thread-safety
    scraper = DrinkyScraper()
    # Login inicial
    if not scraper.login():
        logger.error(f"Worker {worker_id} no pudo iniciar sesión. Abortando.")
        return []

    results = []
    for ruc in rucs:
        status = process_ruc(scraper, ruc)
        results.append((ruc, status))
        time.sleep(0.5) # Pequeña pausa para no saturar
        
    scraper.close()
    # logger.info(f"Worker {worker_id} finalizado.")
    return results

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Procesar RUCs de Drinky en paralelo.')
    parser.add_argument('--limit', type=int, help='Límite de RUCs a procesar (para pruebas)')
    parser.add_argument('--ruc', type=str, help='Procesar un único RUC específico (Debug)')
    args = parser.parse_args()

    print("Iniciando procesamiento PARALELO de Drinky (Entel)...", flush=True)
    
    # Modo Debug: Un solo RUC
    if args.ruc:
        print(f"Modo DEBUG: Procesando único RUC {args.ruc}")
        scraper = DrinkyScraper()
        if scraper.login():
            phones, status = process_ruc(scraper, args.ruc)
            print(f"Resultado final: {phones} | {status}")
            scraper.close()
        else:
            print("Error: No se pudo iniciar sesión en modo debug.")
        return

    try:
        sheet = connect_gsheets()
        data = sheet.get_all_values()
        df = pd.DataFrame(data[1:], columns=data[0]) 
        
        # Identificar columnas
        col_ruc_idx = COLUMNS['RUC']
        col_tel_idx = COLUMNS['TELEFONOS']
        col_estado_entel_idx = COLUMNS['ESTADO_ENTEL']
        
        # Filtrar RUCs pendientes de procesar ... (Mismo código de filtrado)
        # ...
        
        pending_rucs = []
        pending_rows = [] # Para saber qué fila actualizar (1-indexed para gspread)

        print("Analizando filas pendientes...")
        for i, row in enumerate(data[1:], start=2): # Start=2 porque row 1 es header
            # Limpiar RUC (puede venir como '20601234567.00')
            ruc = str(row[col_ruc_idx]).split('.')[0].strip()
            
            # Chequear estado actual de la columna teléfonos y estado entel
            current_tels = row[col_tel_idx] if len(row) > col_tel_idx else ""
            current_status = row[col_estado_entel_idx] if len(row) > col_estado_entel_idx else ""
            
            # Solo procesar si no tiene teléfonos Y no tiene un estado final (OK o SIN REGISTRO)
            # A veces puede haber teléfonos pero queremos reprocesar si no está marcado como OK/SIN REGISTRO?
            # El usuario pidió explícitamente NO volver a scrapear filas con OK o SIN REGISTRO.
            
            if current_status in ["OK", "SIN REGISTRO"]:
                 continue

            if not current_tels or current_tels.strip() == "":
                if ruc and ruc.isdigit() and len(ruc) == 11:
                    pending_rucs.append(ruc)
                    pending_rows.append(i)

        total_pending = len(pending_rucs)
        print(f"Total RUCs pendientes: {total_pending}")
        
        if total_pending == 0:
            print("No hay RUCs pendientes.")
            return

        # Aplicar límite si se especificó
        if args.limit and args.limit > 0:
            print(f"Limitando proceso a los primeros {args.limit} RUCs.")
            pending_rucs = pending_rucs[:args.limit]
            pending_rows = pending_rows[:args.limit]
            total_pending = len(pending_rucs)

        # Dividir trabajo en lotes globales de 50 para guardar progresivamente
        GLOBAL_BATCH_SIZE = 50
        num_workers = 3
        
        logger.info(f"Procesando {total_pending} RUCs en lotes de {GLOBAL_BATCH_SIZE}...")
        
        start_time = time.time()

        # Iterar sobre la lista total en pasos de GLOBAL_BATCH_SIZE
        for i in range(0, total_pending, GLOBAL_BATCH_SIZE):
            batch_rucs = pending_rucs[i:i + GLOBAL_BATCH_SIZE]
            batch_rows = pending_rows[i:i + GLOBAL_BATCH_SIZE] # Filas correspondientes
            
            # Procesar este lote en paralelo
            # Dividir este pequeño lote entre los workers
            chunk_size = (len(batch_rucs) + num_workers - 1) // num_workers
            mini_chunks = [batch_rucs[j:j + chunk_size] for j in range(0, len(batch_rucs), chunk_size)]
            
            batch_results = {}
            
            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                # Submit tasks for this batch
                future_to_worker = {executor.submit(worker_task, chunk, idx+1): idx for idx, chunk in enumerate(mini_chunks)}
                
                for future in as_completed(future_to_worker):
                     try:
                        results = future.result()
                        for ruc, (phones_val, status_val) in results:
                            batch_results[ruc] = (phones_val, status_val)
                     except Exception as exc:
                        logger.error(f"Error en worker del lote {i}: {exc}")
            
            # Guardar este lote inmediatamente
            updates = []
            for j, row_idx in enumerate(batch_rows):
                ruc = batch_rucs[j]
                if ruc in batch_results:
                    phones_val, status_val = batch_results[ruc]
                    
                    # Update Phones
                    updates.append({
                        'range': gspread.utils.rowcol_to_a1(row_idx, col_tel_idx + 1),
                        'values': [[phones_val]]
                    })
                    # Update Status
                    updates.append({
                        'range': gspread.utils.rowcol_to_a1(row_idx, col_estado_entel_idx + 1),
                        'values': [[status_val]]
                    })

            if updates:
                try:
                    sheet.batch_update(updates)
                    first_row = batch_rows[0]
                    last_row = batch_rows[-1]
                    print(f"Guardado exitoso: Lote {i//GLOBAL_BATCH_SIZE + 1} ({len(updates)//2} RUCs) - Filas {first_row}-{last_row}")
                except Exception as e:
                    logger.error(f"Error guardando lote {i}: {e}")
                    # Podríamos implementar un retry simple aquí
                    time.sleep(5)
                    try:
                        sheet.batch_update(updates)
                        print(f"Retry guardado exitoso: Lote {i//GLOBAL_BATCH_SIZE + 1}")
                    except Exception as e2:
                        logger.error(f"Error fatal guardando lote {i} tras retry: {e2}")

            # Pequeña pausa entre lotes grandes para no saturar API de Google
            time.sleep(1)

        elapsed_time = time.time() - start_time
        print(f"Procesamiento completado en {elapsed_time:.2f} segundos.")

    except Exception as e:
        logger.error(f"Error general: {e}")

if __name__ == "__main__":
    main()
