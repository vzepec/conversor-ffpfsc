#!/usr/bin/env bash
# Instala el Conversor FFPFSC (MkPFS + interfaz) y crea los accesos directos.
#
# Uso:  ./instalar.sh          instalación normal
#       ./instalar.sh --dev    además instala pytest y ruff
set -euo pipefail
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$APP_DIR/.venv"
EXTRAS=""
[ "${1:-}" = "--dev" ] && EXTRAS="[dev]"

echo "== Conversor FFPFSC: instalación =="

need=()
python3 -c "import tkinter" 2>/dev/null || need+=(python3-tk)
python3 -c "import ensurepip, venv" 2>/dev/null || need+=(python3-venv)
if [ ${#need[@]} -gt 0 ]; then
  echo "Instalando paquetes del sistema: ${need[*]} (pedirá tu contraseña)"
  sudo apt-get install -y "${need[@]}"
fi

[ -x "$VENV/bin/python" ] || python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -q --upgrade pip
"$VENV/bin/python" -m pip install -q --upgrade -e "$APP_DIR$EXTRAS"
chmod +x "$APP_DIR/abrir.sh"
# Componentes de LZ4 (ampr_emu): opcionales; sin internet se avisa y sigue.
"$VENV/bin/python" "$APP_DIR/tools/fetch_third_party.py" || true

DESKTOP_FILE_CONTENT="[Desktop Entry]
Type=Application
Name=Conversor FFPFSC
Comment=Convierte juegos de PS5 a .ffpfsc
Exec=\"$APP_DIR/abrir.sh\" %F
Icon=$APP_DIR/assets/icon.png
StartupWMClass=Conversor-ffpfsc
Terminal=false
Categories=Utility;"

mkdir -p "$HOME/.local/share/applications"
echo "$DESKTOP_FILE_CONTENT" > "$HOME/.local/share/applications/conversor-ffpfsc.desktop"
DESK="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Escritorio")"; mkdir -p "$DESK"
echo "$DESKTOP_FILE_CONTENT" > "$DESK/Conversor FFPFSC.desktop"
chmod +x "$DESK/Conversor FFPFSC.desktop" "$HOME/.local/share/applications/conversor-ffpfsc.desktop"
command -v gio >/dev/null && gio set "$DESK/Conversor FFPFSC.desktop" metadata::trusted true 2>/dev/null || true

echo "MkPFS: $("$VENV/bin/python" -m mkpfs -h 2>&1 | head -1 || true)"
echo "Listo. Abre 'Conversor FFPFSC' desde el Escritorio o el menú."
