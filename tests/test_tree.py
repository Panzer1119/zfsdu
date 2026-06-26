from zfsdu.models import DatasetType, SortMetric, SortDirection, ZFSEntry
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
        include_bookmarks=False,
        allowed_types={DatasetType.FILESYSTEM},
        sort_metric=SortMetric.USED_BYTES,
        sort_direction=SortDirection.DESC,
    )
    assert children == ["tank/b", "tank/a"]


def test_children_sort_by_used_ascending() -> None:
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
        include_bookmarks=False,
        allowed_types={DatasetType.FILESYSTEM},
        sort_metric=SortMetric.USED_BYTES,
        sort_direction=SortDirection.ASC,
    )
    assert children == ["tank/a", "tank/b"]


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


def test_build_by_origin_relations() -> None:
    index = DatasetIndex.build_by_origin(
        [
            _entry("tank/docker", DatasetType.FILESYSTEM, 100),
            ZFSEntry(
                name="tank/docker/layer-a",
                dataset_type=DatasetType.FILESYSTEM,
                used=50,
                refer=30,
                origin="tank/docker@snap-root",
            ),
            ZFSEntry(
                name="tank/docker/layer-b",
                dataset_type=DatasetType.FILESYSTEM,
                used=20,
                refer=10,
                origin="tank/docker/layer-a@snap-1",
            ),
            _entry("tank/docker@ignore", DatasetType.SNAPSHOT, 1),
        ],
        root="tank/docker",
    )

    assert index.top_level("tank/docker") == ["tank/docker"]
    assert index.children_of(
        "tank/docker",
        include_snapshots=False,
        include_bookmarks=False,
        allowed_types={DatasetType.FILESYSTEM},
        sort_metric=SortMetric.NAME,
    ) == ["tank/docker/layer-a"]
    assert index.parent_of("tank/docker/layer-b") == "tank/docker/layer-a"


