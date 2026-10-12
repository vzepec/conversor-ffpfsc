"""Textos del avance y del resultado de la compresión LZ4 en la PS5 (exfat2ampr).

Funciones puras para la fila del panel de transferencias, el aviso del
escritorio y el registro.
"""
from __future__ import annotations

from ffpfsc_converter.domain.lz4 import Lz4JobState, Lz4Status
from ffpfsc_converter.formatting import format_size
from ffpfsc_converter.ui.explorer.lz4_presenters import CHECK_ERROR_CODES, check_error_text
from ffpfsc_converter.ui.explorer.transfer_presenters import TransferProgress
from ffpfsc_converter.ui.job_presenters import RowStatus

ROW_SUBTITLE = "LZ4 en la PS5"
WAITING_TEXT = "Esperando a ShadowMountPlus"
CHECKING_TEXT = "Comprobando el destino…"
STARTING_TEXT = "Iniciando…"
RESUMING_TEXT = "Reanudando…"
CANCELLING_TEXT = "Cancelando…"
RESUME_TEXT = "Reanudar"

_PHASES = {
    "starting": "Iniciando", "waiting": WAITING_TEXT, "mount": "Montando la imagen",
    "cleanup": "Borrando la conversión anterior", "scan": "Analizando el juego",
    "fakelib": "Instalando libSceAmpr", "index": "Escribiendo el índice AMPR",
    "pack": "Comprimiendo (LZ4)", "copy": "Copiando archivos sueltos",
    "verify": "Verificando cada bloque", "remove": "Borrando el original",
    "unmount": "Liberando la imagen",
}
_RESULT_CODES = {
    "dest_create": "No se pudo crear la carpeta de destino.",
    "dest_exists": "Ya hay una conversión en el destino; activa «Reemplazar la conversión "
                   "anterior» para sobrescribirla.",
    "dest_is_source": "El destino es la propia carpeta del juego: elige otra unidad.",
    "dest_unavailable": "La unidad de destino ya no está disponible.",
    "fakelib_failed": "No se pudo instalar libSceAmpr.sprx en el juego convertido.",
    "index_failed": "No se pudo escribir el índice AMPR.",
    "manifest_mismatch": "El juego cambió desde la pausa: no se puede reanudar; vuelve a "
                         "empezar.",
    "nothing_to_resume": "No hay nada que reanudar.",
    "scan_failed": "No se pudo leer el juego de origen.",
    "pack_failed": "Falló la compresión (el detalle está en el registro de exfat2ampr).",
    "copy_failed": "Falló la copia de los archivos sueltos.",
    "verify_failed": "La verificación encontró bloques dañados.",
    "smp_busy": "Cierra el juego o la aplicación abiertos en la PS5.",
    "paused_user": "Se puede reanudar donde quedó.",
    "paused_game": "Se abrió un juego: la conversión se reanuda sola al salir de él.",
    "paused_dest": "Se desconectó el destino: conéctalo y reanuda.",
    "paused_source": "Se desconectó el origen: conéctalo y reanuda.",
    "paused_full": "El destino se llenó: libera espacio y reanuda.",
    "done_fakelib": "El fakelib del juego estaba desactivado en ShadowMountPlus: se cambió a "
                    "«Emuladores».",
}


def job_name(status: Lz4Status) -> str:
    """Nombra la conversión que informa exfat2ampr (para su fila).

    Args:
        status (Lz4Status): Estado leído.

    Returns:
        str: Nombre del juego, su Title ID o ``"exfat2ampr"`` si no se conoce.
    """
    return status.title or status.title_id or "exfat2ampr"


def phase_text(phase: str) -> str:
    """Traduce la fase interna de exfat2ampr.

    Args:
        phase (str): Por ejemplo ``"pack"``.

    Returns:
        str: Nombre en español (la fase tal cual si es desconocida; vacío si no hay).
    """
    return _PHASES.get(phase, phase)


def row_subtitle(status: Lz4Status) -> str:
    """Describe la fase en curso bajo el nombre de la fila (la espera ya la dice la píldora).

    Args:
        status (Lz4Status): Estado leído.

    Returns:
        str: Por ejemplo ``"LZ4 en la PS5 · Comprimiendo (LZ4)"``.
    """
    phase = phase_text(status.phase)
    if not phase or status.waiting or not status.is_active:
        return ROW_SUBTITLE
    return f"{ROW_SUBTITLE} · {phase}"


def row_progress(status: Lz4Status) -> TransferProgress:
    """Prepara el avance de la conversión para la barra de la fila.

    Args:
        status (Lz4Status): Estado leído.

    Returns:
        TransferProgress: Porcentaje y texto como ``"42% · 20.0 GB de 48.0 GB"``.
    """
    percent = float(min(max(status.percent, 0), 100))
    if status.bytes_total <= 0:
        return TransferProgress(percent, f"{percent:.0f}%")
    return TransferProgress(percent, f"{percent:.0f}% · {format_size(status.bytes_done)} de "
                                     f"{format_size(status.bytes_total)}")


def queued_text(position: int) -> str:
    """Describe una conversión recién aceptada por exfat2ampr.

    Args:
        position (int): Lugar en la cola (``0`` = empieza ya).

    Returns:
        str: ``"Iniciando…"`` o ``"En cola de exfat2ampr (N por delante)"``.
    """
    return STARTING_TEXT if position <= 0 else f"En cola de exfat2ampr ({position} por delante)"


def code_text(code: str, message: str) -> str:
    """Traduce el código de resultado o de pausa de exfat2ampr.

    Args:
        code (str): Por ejemplo ``"verify_failed"`` o ``"paused_full"``.
        message (str): Detalle en inglés de exfat2ampr (respaldo para códigos desconocidos).

    Returns:
        str: Explicación en español neutro.
    """
    if code in _RESULT_CODES:
        return _RESULT_CODES[code]
    if code in CHECK_ERROR_CODES:
        return check_error_text(code)
    detail = message.strip() or code.strip() or "motivo desconocido"
    return f"exfat2ampr se detuvo ({detail})."


def result_status(status: Lz4Status) -> RowStatus:
    """Resume cómo terminó la conversión para la píldora de la fila.

    Args:
        status (Lz4Status): Último estado (terminado, con error, cancelado o en pausa).

    Returns:
        RowStatus: Tipo de píldora, texto y detalle.
    """
    if status.state is Lz4JobState.DONE:
        extra = f" {code_text(status.code, '')}" if status.code == "done_fakelib" else ""
        return RowStatus("ok", "✓ Comprimido", f"Quedó en {status.dest}.{extra}".strip())
    if status.state is Lz4JobState.CANCELLED:
        return RowStatus("warn", "Cancelado", "exfat2ampr borró la carpeta a medias; el "
                                              "original sigue intacto.")
    if status.state is Lz4JobState.PAUSED:
        return RowStatus("warn", "En pausa", code_text(status.code or "paused_user", ""))
    return RowStatus("bad", "Error", code_text(status.code, status.message))


def failed_status(message: str) -> RowStatus:
    """Resume un error que impidió seguir la conversión.

    Args:
        message (str): Motivo completo.

    Returns:
        RowStatus: Píldora de error con la primera línea del motivo.
    """
    first = next((line for line in message.splitlines() if line.strip()), "")
    return RowStatus("bad", "Error", first)


def can_resume(status: Lz4Status) -> bool:
    """Indica si se puede ofrecer «Reanudar» tras el resultado.

    Args:
        status (Lz4Status): Último estado.

    Returns:
        bool: ``True`` si quedó en pausa con punto de reanudación y carpeta conocida.
    """
    return status.state is Lz4JobState.PAUSED and status.resumable and bool(status.dest)


def finish_title(status: Lz4Status) -> str:
    """Titula el aviso del escritorio al terminar.

    Args:
        status (Lz4Status): Último estado.

    Returns:
        str: Título corto según el resultado.
    """
    if status.state is Lz4JobState.DONE:
        return "Compresión LZ4 terminada en la PS5"
    if status.state is Lz4JobState.PAUSED:
        return "Compresión LZ4 en pausa"
    return "La compresión LZ4 no terminó"


def cancel_confirmation(dest: str) -> str:
    """Pide confirmar la cancelación, que borra la carpeta en curso.

    Args:
        dest (str): Carpeta de salida en la PS5 (vacía si aún no se conoce).

    Returns:
        str: Pregunta con la ruta exacta que se borrará.
    """
    where = dest or "la carpeta de salida"
    return (f"Si cancelas, exfat2ampr BORRARÁ de la PS5 la carpeta a medias:\n\n{where}\n\n"
            "El juego original no se toca. ¿Cancelar la compresión?")
