"""Adaptador a MkPFS: todo el conocimiento sobre su CLI y su API interna.

Si MkPFS cambia, este subpaquete es lo único que debería tocarse. El resto de
la aplicación importa desde aquí y no desde los módulos internos.
"""
from ffpfsc_converter.infrastructure.mkpfs_adapter.command import build_pack_command
from ffpfsc_converter.infrastructure.mkpfs_adapter.metadata import (
    read_exfat_member,
    read_metadata,
)
from ffpfsc_converter.infrastructure.mkpfs_adapter.output import parse_progress, split_lines
from ffpfsc_converter.infrastructure.mkpfs_adapter.process import PackProcess

__all__ = [
    "PackProcess",
    "build_pack_command",
    "parse_progress",
    "read_exfat_member",
    "read_metadata",
    "split_lines",
]
