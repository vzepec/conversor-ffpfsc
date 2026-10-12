"""Mensajes en español de la compresión LZ4 remota (exfat2ampr).

exfat2ampr responde con códigos estables en inglés; aquí se traducen a frases
cortas y sin jerga, listas para mostrar. El detalle técnico (código, puerto,
respuesta en inglés) va al registro de la app, no a estos textos.
"""
from __future__ import annotations

PAIR_BLOCKED_TEXT = ("Demasiados códigos incorrectos. Espera un minuto y vuelve a cargar "
                     "exfat2ampr en la PS5 para ver el código nuevo.")
NO_DESTINATION_TEXT = "No hay ninguna unidad de la PS5 donde guardar el juego."
NETWORK_ERROR_TEXT = "exfat2ampr no responde. Comprueba que la PS5 siga encendida."
ELF_SEND_ERROR_TEXT = ("No se pudo iniciar exfat2ampr. Carga etaHEN (o elfldr) en la PS5 e "
                       "inténtalo de nuevo.")
LAUNCH_TIMEOUT_TEXT = "exfat2ampr no arrancó en la PS5. Inténtalo de nuevo."
SOURCE_MISSING_TEXT = "No se puede comprimir eso. Elige la carpeta del juego o su imagen."
CONNECTION_LOST_TEXT = ("Se perdió la conexión. La compresión sigue en la PS5: vuelve a "
                        "conectarte para ver cómo termina.")
_CANNOT_RESUME = "No se puede reanudar. Vuelve a empezar la compresión."
_UNKNOWN_TEXT = "exfat2ampr no pudo hacerlo. Los detalles están en Registros."

_ENGINE_ERRORS = {
    "queue_full": "Hay demasiadas compresiones en espera. Inténtalo más tarde.",
    "dest_unavailable": "La unidad de destino no está disponible. Elige otra.",
    "bad_path": "No se puede usar la ubicación de ese juego.",
    "bad_name": "No se puede usar ese nombre de carpeta.",
    "nothing_to_retry": "No hay nada que reintentar.",
    "busy": "La PS5 está ocupada con otra compresión. Espera a que termine.",
    "cannot resume": _CANNOT_RESUME,
    "cannot_resume": _CANNOT_RESUME,
    "blocked": PAIR_BLOCKED_TEXT,
    "bad_response": "Respuesta inesperada de exfat2ampr. Usa la versión 1.45.",
}


def engine_error_text(code: str) -> str:
    """Traduce el código de error de exfat2ampr a un mensaje para el usuario.

    Args:
        code (str): Código que dio exfat2ampr (``queue_full``, ``dest_unavailable``…).

    Returns:
        str: Mensaje corto en español neutro (uno genérico si el código es desconocido).
    """
    return _ENGINE_ERRORS.get(code.strip().lower(), _UNKNOWN_TEXT)
