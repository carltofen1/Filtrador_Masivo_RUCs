@echo off
title Creando EXE...
cd /d "%~dp0"
echo Creando ejecutable...
pyinstaller --onefile --name "Filtrador_RUCs" --console launcher.py
echo.
echo Listo! El EXE esta en la carpeta dist\
pause
