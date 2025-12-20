@echo off
title Creando EXE...
cd /d "%~dp0"

echo Limpiando build anterior...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
del /q *.spec 2>nul

echo Creando ejecutable...
pyinstaller --onefile --name "Filtrador_RUCs" --console launcher.py
if errorlevel 1 goto :error

echo.
echo Copiando carpeta modules...
mkdir dist\modules
for %%f in (modules\*.py) do copy /Y "%%f" dist\modules\ >nul

echo Copiando carpeta whatsapp-bot-node (sin node_modules)...
mkdir dist\whatsapp-bot-node
mkdir dist\whatsapp-bot-node\commands
copy /Y whatsapp-bot-node\*.js dist\whatsapp-bot-node\ >nul
copy /Y whatsapp-bot-node\*.json dist\whatsapp-bot-node\ >nul
copy /Y whatsapp-bot-node\*.py dist\whatsapp-bot-node\ >nul
copy /Y whatsapp-bot-node\commands\*.js dist\whatsapp-bot-node\commands\ >nul

echo Copiando archivos...
copy /Y config.py dist\ >nul
copy /Y credentials.json dist\ >nul
copy /Y .env dist\ >nul
copy /Y requirements.txt dist\ >nul
copy /Y procesar_*.py dist\ >nul

echo.
echo ========================================
echo VERIFICACION:
dir dist /b
echo.
echo NOTA: node_modules se instalara
echo automaticamente en la primera ejecucion
echo ========================================
pause
goto :end

:error
echo ERROR durante el proceso!
pause

:end
