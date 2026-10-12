"""Mensajes en español de la compresión LZ4 remota (exfat2ampr).

exfat2ampr responde con códigos estables en inglés; aquí se traducen a textos
listos para mostrar.
"""
from __future__ import annotations

from ffpfsc_converter.config import E2A_HTTP_PORT, ELF_LOADER_PORT

PAIR_BLOCKED_TEXT = (
    "Demasiados intentos con un código incorrecto: espera un minuto. El código cambió: "
    "vuelve a cargar exfat2ampr en la PS5 para ver el nuevo en la notificación."
)
NO_DESTINATION_TEXT = (
    "Ninguna unidad de la PS5 admite escritura: no hay dónde guardar el juego convertido."
)

_ENGINE_ERRORS: dict[str, str] = {
    "queue_full": "exfat2ampr tiene la cola llena. Espera a que termine alguna conversión "
                  "e inténtalo de nuevo.",
    "dest_unavailable": "La unidad de destino ya no está disponible o no admite escritura. "
                        "Elige otra.",
    "bad_path": "exfat2ampr no aceptó la ruta del juego.",
    "bad_name": "exfat2ampr no aceptó el nombre de la carpeta de salida.",
    "nothing_to_retry": "No hay ninguna conversión para reintentar.",
    "busy": "exfat2ampr está ocupado con una conversión. Espera a que termine.",
    "cannot resume": "No se puede reanudar esta conversión: falta el juego de origen o el "
                     "punto de reanudación ya no es válido.",
    "cannot_resume": "No se puede reanudar esta conversión: falta el juego de origen o el "
                     "punto de reanudación ya no es válido.",
    "blocked": PAIR_BLOCKED_TEXT,
    "bad_response": "exfat2ampr dio una respuesta que no se entiende. Comprueba que sea una "
                    "versión compatible.",
}


def engine_error_text(code: str, fallback: str) -> str:
    """Traduce el código de error de exfat2ampr a un mensaje para el usuario.

    Args:
        code (str): Código que dio exfat2ampr (``queue_full``, ``dest_unavailable``…).
        fallback (str): Detalle en inglés que acompaña al código, para los códigos desconocidos.

    Returns:
        str: Mensaje en español neutro.
    """
    known = _ENGINE_ERRORS.get(code.strip().lower())
    if known:
        return known
    detail = fallback.strip() or code.strip() or "motivo desconocido"
    return f"exfat2ampr rechazó la orden ({detail})."


def network_error_text(host: str) -> str:
    """Explica que exfat2ampr no responde en la consola.

    Args:
        host (str): Dirección de la PS5.

    Returns:
        str: Mensaje en español neutro.
    """
    return (f"No se pudo hablar con exfat2ampr en {host}:{E2A_HTTP_PORT}. "
            "Comprueba que la PS5 siga encendida y que exfat2ampr esté cargado.")


def elf_send_error_text(host: str) -> str:
    """Explica que no se pudo enviar exfat2ampr al cargador de ELF.

    Args:
        host (str): Dirección de la PS5.

    Returns:
        str: Mensaje en español neutro.
    """
    return (f"No se pudo enviar exfat2ampr a {host}:{ELF_LOADER_PORT}. "
            f"¿Está activo etaHEN con su cargador de ELF escuchando en el puerto "
            f"{ELF_LOADER_PORT}?")


def launch_timeout_text(host: str) -> str:
    """Explica que exfat2ampr no arrancó tras enviarlo al cargador de ELF.

    Args:
        host (str): Dirección de la PS5.

    Returns:
        str: Mensaje en español neutro.
    """
    return (f"Se envió exfat2ampr a {host}, pero no empezó a responder. ¿El cargador de ELF "
            f"escucha en el puerto {ELF_LOADER_PORT}? Carga exfat2ampr a mano e inténtalo "
            "de nuevo.")


def source_missing_text(path: str) -> str:
    """Explica que exfat2ampr no reconoce la ruta elegida como un juego.

    Args:
        path (str): Carpeta o imagen elegida en la PS5.

    Returns:
        str: Mensaje en español neutro.
    """
    return (f"exfat2ampr no reconoce {path} como un juego que pueda convertir. Elige la "
            "carpeta del juego o una imagen .exfat/.ffpkg de una carpeta de juegos.")


def connection_lost_text(host: str) -> str:
    """Explica que se dejó de recibir el avance de la conversión.

    La conversión sigue en la PS5: exfat2ampr no depende de esta app.

    Args:
        host (str): Dirección de la PS5.

    Returns:
        str: Mensaje en español neutro.
    """
    return (f"Se perdió la conexión con exfat2ampr en {host}. La conversión sigue en la PS5; "
            "vuelve a conectarte para ver cómo termina.")
