from zfsdu.models import DatasetType, SortMetric, ZFSEntry
from zfsdu.tree import DatasetIndex


def _entry(name: str, dtype: DatasetType, used: int, refer: int = 0) -> ZFSEntry:
    return ZFSEntry(name=name, dataset_type=dtype, used=used, refer=refer)


def test_build_and_children_sort_by_used() -> None:
    index = DatasetIndex.build(
        [
            _entry("tank", DatasetType.FILESYSTEM, 10),
            _entry("tank/a", DatasetType.FILESYSTEM, 5),
            _entry("tank/b", DatasetType.FILESYSTEM, 8),
        ]
    )

    children = index.children_of(
        "tank",
        include_snapshots=False,
        allowed_types={DatasetType.FILESYSTEM},
        sort_metric=SortMetric.USED,
    )
    assert children == ["tank/b", "tank/a"]


def test_search_respects_root() -> None:
    index = DatasetIndex.build(
        [
            _entry("tank", DatasetType.FILESYSTEM, 10),
            _entry("tank/home", DatasetType.FILESYSTEM, 5),
            _entry("backup/home", DatasetType.FILESYSTEM, 5),
        ]
    )

    results = index.search("home", "tank")
    assert results == ["tank/home"]

