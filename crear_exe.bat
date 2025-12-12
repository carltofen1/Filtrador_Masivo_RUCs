@echo off
echo ============================================
echo   CREANDO EJECUTABLE FILTRADOR DE RUCs
echo ============================================
echo.

echo [1/4] Limpiando carpetas anteriores...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist launcher.spec del launcher.spec

echo [2/4] Generando ejecutable con todas las dependencias...
pyinstaller --onedir --console ^
    --hidden-import=selenium ^
    --hidden-import=selenium.webdriver ^
    --hidden-import=selenium.webdriver.chrome.service ^
    --hidden-import=selenium.webdriver.chrome.options ^
    --hidden-import=selenium.webdriver.common.by ^
    --hidden-import=selenium.webdriver.common.keys ^
    --hidden-import=selenium.webdriver.support.ui ^
    --hidden-import=selenium.webdriver.support.expected_conditions ^
    --hidden-import=gspread ^
    --hidden-import=google.oauth2.service_account ^
    --hidden-import=dotenv ^
    --hidden-import=concurrent.futures ^
    --add-data "credentials.json;." ^
    --add-data ".env;." ^
    --add-data "config.py;." ^
    --add-data "procesar_sunat_paralelo.py;." ^
    --add-data "procesar_entel_paralelo.py;." ^
    --add-data "procesar_segmentacion_paralelo.py;." ^
    --add-data "procesar_osiptel_paralelo.py;." ^
    --add-data "modules;modules" ^
    launcher.py

echo.
echo [3/4] Copiando archivos extra a dist/launcher...
copy credentials.json dist\launcher\
copy .env dist\launcher\
copy config.py dist\launcher\
copy procesar_sunat_paralelo.py dist\launcher\
copy procesar_entel_paralelo.py dist\launcher\
copy procesar_segmentacion_paralelo.py dist\launcher\
copy procesar_osiptel_paralelo.py dist\launcher\
xcopy modules dist\launcher\modules\ /E /I /Y

echo.
echo [4/4] Listo!
echo ============================================
echo   EL EJECUTABLE ESTA EN: dist\launcher\launcher.exe
echo   Copia TODA la carpeta dist\launcher a otra PC
echo ============================================
echo.
pause
