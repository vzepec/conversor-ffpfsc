#!/usr/bin/env bash
# Lanza el Conversor FFPFSC usando el entorno virtual del proyecto.
APP_DIR="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
export PYTHONPATH="$APP_DIR/src${PYTHONPATH:+:$PYTHONPATH}"
exec "$APP_DIR/.venv/bin/python" -m ffpfsc_converter "$@"
