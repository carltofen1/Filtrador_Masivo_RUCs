@echo off
echo ============================================
echo Creando ejecutable del Filtrador de RUCs
echo ============================================

REM Limpiar builds anteriores
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

REM Crear el ejecutable con PyInstaller
pyinstaller --noconfirm --onedir --console ^
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
echo ============================================
echo Ejecutable creado en: dist\launcher\
echo ============================================
pause
