@echo off
rem Lanza el Conversor FFPFSC en Windows con el entorno virtual del proyecto,
rem sin ventana de consola. Acepta rutas de juegos como argumentos.
set "PYTHONPATH=%~dp0src;%PYTHONPATH%"
start "" "%~dp0.venv\Scripts\pythonw.exe" -m ffpfsc_converter %*
