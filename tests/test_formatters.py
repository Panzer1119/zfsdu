from zfsdu.formatters import format_bytes, format_percent
from zfsdu.models import SizeMode


def test_format_bytes_iec() -> None:
    assert format_bytes(1024, SizeMode.IEC) == "1.0 KiB"


def test_format_bytes_decimal() -> None:
    assert format_bytes(1000, SizeMode.DECIMAL) == "1.0 KB"


def test_format_bytes_raw() -> None:
    assert format_bytes(1000, SizeMode.RAW) == "1000"


def test_format_percent_handles_zero() -> None:
    assert format_percent(5, 0) == "-"

