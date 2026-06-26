from zfsdu.models import DatasetType
from zfsdu.zfs import ZFSClient


def test_parse_row() -> None:
    line = "tank/home\tfilesystem\t1024\t512\t256\t128\t64\t0\t1700000000\t/tank/home"
    entry = ZFSClient._parse_row(line)

    assert entry.name == "tank/home"
    assert entry.dataset_type is DatasetType.FILESYSTEM
    assert entry.used == 1024
    assert entry.used_by_snapshots == 256


def test_parse_row_handles_dash_values() -> None:
    line = "tank/home@s0\tsnapshot\t-\t-\t-\t-\t-\t-\t1700000000\t-"
    entry = ZFSClient._parse_row(line)

    assert entry.dataset_type is DatasetType.SNAPSHOT
    assert entry.used == 0
    assert entry.refer == 0


def test_parse_get_all_row() -> None:
    line = "tank/home\trecordsize\t131072\tlocal"
    property_name, value, source = ZFSClient._parse_get_all_row(line)

    assert property_name == "recordsize"
    assert value == "131072"
    assert source == "local"


