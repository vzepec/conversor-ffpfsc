# Instala el Conversor FFPFSC en Windows y crea los accesos directos.
#
# Uso:  doble clic en instalar.bat                  instalación normal
#       powershell -ExecutionPolicy Bypass -File instalar.ps1 -Dev
#                                                   además instala pytest y ruff
param([switch]$Dev)
$ErrorActionPreference = "Stop"

$AppDir = $PSScriptRoot
$Venv = Join-Path $AppDir ".venv"
$VenvPython = Join-Path $Venv "Scripts\python.exe"
$VenvPythonw = Join-Path $Venv "Scripts\pythonw.exe"
$PythonUrl = "https://www.python.org/downloads/windows/"

Write-Host "== Conversor FFPFSC: instalación =="

# Preferir el lanzador "py" de python.org; si no existe, usar "python" del PATH.
if (Get-Command py -ErrorAction SilentlyContinue) {
    $PyExe = "py"; $PyArgs = @("-3")
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PyExe = "python"; $PyArgs = @()
} else {
    throw "No se encontró Python. Instala Python 3.10 o superior desde $PythonUrl " +
          "marcando 'Add python.exe to PATH'."
}

& $PyExe @PyArgs -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) { throw "Se necesita Python 3.10 o superior ($PythonUrl)." }

& $PyExe @PyArgs -c "import tkinter"
if ($LASTEXITCODE -ne 0) {
    throw "Falta tkinter. Vuelve a ejecutar el instalador de Python y marca 'tcl/tk and IDLE'."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creando entorno virtual en .venv ..."
    & $PyExe @PyArgs -m venv $Venv
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual." }
}

Write-Host "Instalando MkPFS y dependencias (puede tardar unos minutos) ..."
& $VenvPython -m pip install -q --upgrade pip
$Target = if ($Dev) { "${AppDir}[dev]" } else { $AppDir }
& $VenvPython -m pip install -q --upgrade -e $Target
if ($LASTEXITCODE -ne 0) { throw "Falló la instalación de dependencias." }

# Accesos directos en el Escritorio y en el menú Inicio. Se puede arrastrar un
# juego sobre el acceso directo para abrir la app con ese juego en la cola.
$Shell = New-Object -ComObject WScript.Shell
$Folders = @([Environment]::GetFolderPath("Desktop"), [Environment]::GetFolderPath("Programs"))
foreach ($Folder in $Folders) {
    $Link = $Shell.CreateShortcut((Join-Path $Folder "Conversor FFPFSC.lnk"))
    $Link.TargetPath = $VenvPythonw
    $Link.Arguments = "-m ffpfsc_converter"
    $Link.WorkingDirectory = $AppDir
    $Link.IconLocation = "$(Join-Path $AppDir 'assets\icon.ico'),0"
    $Link.Description = "Convierte juegos de PS5 a .ffpfsc"
    $Link.Save()
}

$MkpfsVersion = & $VenvPython -m mkpfs -h | Select-Object -First 1
Write-Host "MkPFS: $MkpfsVersion"
Write-Host "Listo. Abre 'Conversor FFPFSC' desde el Escritorio o el menú Inicio."
