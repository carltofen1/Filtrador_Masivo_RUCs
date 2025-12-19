@echo off
title Creando EXE...
cd /d "%~dp0"

echo Limpiando build anterior...
rmdir /s /q dist 2>nul
rmdir /s /q build 2>nul
del /q *.spec 2>nul

echo Creando ejecutable...
pyinstaller --onefile --name "Filtrador_RUCs" --console launcher.py

echo.
echo Listo! El EXE esta en la carpeta dist\
pause
