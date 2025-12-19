@echo off
echo ============================================
echo Creando ejecutable del Filtrador de RUCs
echo ============================================

REM Limpiar builds anteriores
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Crear el ejecutable con PyInstaller
REM Incluimos todas las dependencias necesarias para que funcione en otra PC
pyinstaller --noconfirm --onedir --console ^
    --add-data "credentials.json;." ^
    --add-data ".env;." ^
    --add-data "config.py;." ^
    --add-data "procesar_sunat_paralelo.py;." ^
    --add-data "procesar_entel_paralelo.py;." ^
    --add-data "procesar_segmentacion_paralelo.py;." ^
    --add-data "procesar_osiptel_paralelo.py;." ^
    --add-data "whatsapp_bot.py;." ^
    --add-data "modules;modules" ^
    --hidden-import=selenium ^
    --hidden-import=selenium.webdriver ^
    --hidden-import=selenium.webdriver.chrome ^
    --hidden-import=selenium.webdriver.chrome.service ^
    --hidden-import=selenium.webdriver.chrome.options ^
    --hidden-import=selenium.webdriver.common.by ^
    --hidden-import=selenium.webdriver.common.keys ^
    --hidden-import=selenium.webdriver.support.ui ^
    --hidden-import=selenium.webdriver.support.expected_conditions ^
    --hidden-import=webdriver_manager ^
    --hidden-import=webdriver_manager.chrome ^
    --hidden-import=undetected_chromedriver ^
    --hidden-import=openpyxl ^
    --hidden-import=pandas ^
    --hidden-import=gspread ^
    --hidden-import=google.oauth2.service_account ^
    --hidden-import=dotenv ^
    --hidden-import=python-dotenv ^
    --hidden-import=colorama ^
    --hidden-import=tqdm ^
    --hidden-import=requests ^
    --hidden-import=urllib3 ^
    --hidden-import=certifi ^
    --collect-all selenium ^
    --collect-all webdriver_manager ^
    --collect-all undetected_chromedriver ^
    --collect-all certifi ^
    launcher.py

echo.
echo ============================================
echo Ejecutable creado en: dist\launcher\
echo ============================================
pause
