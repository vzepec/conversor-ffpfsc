@echo off
rem Instala el Conversor FFPFSC en Windows.
rem Ejecuta instalar.ps1 sin cambiar la politica de ejecucion del sistema.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1" %*
pause
