@echo off
echo ============================================
echo   CREANDO EJECUTABLE FILTRADOR DE RUCs
echo ============================================
echo.

echo [1/3] Generando launcher.exe...
pyinstaller --onefile --console launcher.py

echo.
echo [2/3] Copiando archivos necesarios a dist...
copy credentials.json dist\
copy .env dist\
copy config.py dist\
copy procesar_sunat_paralelo.py dist\
copy procesar_entel_paralelo.py dist\
copy procesar_segmentacion_paralelo.py dist\
xcopy modules dist\modules\ /E /I /Y

echo.
echo [3/3] Listo!
echo ============================================
echo   EL EJECUTABLE ESTA EN: dist\launcher.exe
echo ============================================
echo.
pause
