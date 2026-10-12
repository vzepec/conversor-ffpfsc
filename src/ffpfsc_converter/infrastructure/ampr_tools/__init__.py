"""Herramientas de ampr_emu para comprimir en LZ4 (formato AMPR) en el PC.

Los scripts los descarga el instalador en ``third_party/``; aquí solo se arman sus
comandos y se interpreta su salida. Se ejecutan con ``PackProcess`` como MkPFS.
"""
from __future__ import annotations

from ffpfsc_converter.infrastructure.ampr_tools.commands import AmprTools, PackPaths
from ffpfsc_converter.infrastructure.ampr_tools.output import (
    PackSummary,
    packed_file_total,
    parse_pack_progress,
    parse_pack_summary,
)

__all__ = ["AmprTools", "PackPaths", "PackSummary", "packed_file_total",
           "parse_pack_progress", "parse_pack_summary"]
