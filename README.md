# Filtrador Masivo de RUCs

Herramienta para completar un Google Sheet de empresas peruanas a partir de su RUC:
datos de SUNAT, teléfonos (Drinky/Entel), segmentación y un bot de WhatsApp
para consultas puntuales.

## Uso

Ejecuta `dist/launcher.exe` (o `python launcher.py` en desarrollo) y elige en el menú:

| Opción | Script | Qué hace |
|---|---|---|
| 1 | `procesar_sunat_paralelo.py` | Razón social, representante, dirección y estado (5 workers) |
| 2 | `procesar_drinky_paralelo.py` | Teléfonos vía API de Drinky (Entel / Movistar) |
| 3 | `procesar_segmentacion_api.py` | Tipo de cliente (100 % API) |
| 4 | `whatsapp-bot-node/` + `python_server.py` | Bot de WhatsApp (`server.exe` + `bot.exe`) |

Scripts sueltos:
- `procesar_razon_social.py`: busca el RUC a partir de la razón social.
- `test_scraper.py`: prueba rápida de SUNAT con un RUC.

## Configuración

- `.env`: `SPREADSHEET_ID`, `SHEET_NAME`, credenciales de Drinky, Segmentación,
  Factibilidad y tokens de las APIs de DNI.
- `credentials.json`: cuenta de servicio de Google con acceso de **Editor** al Sheet.

Ninguno de los dos se sube a git.

## SUNAT y Cloudflare

`modules/sunat_scraper.py` usa **undetected-chromedriver** con una ventana real ubicada
fuera de la pantalla:

- El modo headless y `page_load_strategy='eager'` hacen que Cloudflare bloquee.
- En la página de SUNAT los eventos nativos de WebDriver no llegan, así que se escribe
  con CDP (`Input.insertText`) y se hace clic por JS.
- Desde el segundo RUC la búsqueda se envía por POST sin recargar el formulario, y se
  bloquean los scripts de monitoreo de terceros (~2,5 s por RUC y por worker).
- Si no hay Chrome instalado, Selenium Manager descarga *Chrome for Testing*.

## Compilar

```bash
python build_dist.py              # todo: server, launcher y bot
python build_dist.py launcher     # solo el launcher
```

Genera `dist/` en modo `--onedir`, que arranca en 1-2 s:
`launcher.exe`, `server.exe`, `bot.exe`, sus carpetas `_*_libs/`, `.env` y `credentials.json`.

## Estructura

```
launcher.py                  menú principal
config.py                    configuración (lee .env)
procesar_*.py                procesadores masivos (Google Sheets)
modules/
  sunat_scraper.py           SUNAT (undetected-chromedriver)
  drinky_scraper.py          API Drinky
  claro_cobertura_scraper.py cobertura Claro (bot)
  dni_scraper.py             APIs de DNI (bot)
  sheets_manager.py          lectura/escritura en batch del Sheet
whatsapp-bot-node/           bot de WhatsApp (Node) + python_server.py
build_dist.py                compilación a dist/
```

## Autor

Desarrollado por Carltofen1 (Patrick Pozsgai).
