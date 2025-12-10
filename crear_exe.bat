@echo off
echo ============================================
echo   CREANDO EJECUTABLE FILTRADOR DE RUCs
echo ============================================
echo.

echo [1/4] Limpiando carpetas anteriores...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist launcher.spec del launcher.spec

echo [2/4] Generando launcher.exe...
pyinstaller --onefile --console launcher.py

echo.
echo [3/4] Copiando archivos necesarios a dist...
copy credentials.json dist\
copy .env dist\
copy config.py dist\
copy procesar_sunat_paralelo.py dist\
copy procesar_entel_paralelo.py dist\
copy procesar_segmentacion_paralelo.py dist\
xcopy modules dist\modules\ /E /I /Y

echo.
echo [4/4] Listo!
echo ============================================
echo   EL EJECUTABLE ESTA EN: dist\launcher.exe
echo ============================================
echo.
pause
