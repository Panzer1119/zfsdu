from __future__ import annotations

from .models import SizeMode

_IEC_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB")
_DEC_UNITS = ("B", "KB", "MB", "GB", "TB", "PB", "EB")


def format_bytes(value: int, mode: SizeMode) -> str:
    if mode is SizeMode.RAW:
        return str(value)

    if mode is SizeMode.IEC:
        return _format_scaled(value, 1024, _IEC_UNITS)
    return _format_scaled(value, 1000, _DEC_UNITS)


def format_percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "-"
    return f"{(numerator / denominator) * 100:0.1f}%"


def _format_scaled(value: int, base: int, units: tuple[str, ...]) -> str:
    value = max(0, value)
    if value < base:
        return f"{value} B"

    scaled = float(value)
    for unit in units[1:]:
        scaled /= base
        if scaled < base:
            return f"{scaled:0.1f} {unit}"
    return f"{scaled:0.1f} {units[-1]}"

