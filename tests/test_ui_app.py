import asyncio
from collections.abc import Iterable

from zfsdu.models import DatasetType, SizeMode, SortMetric, SortDirection, ZFSEntry
from zfsdu.ui.app import UIConfig, ZFSDUApp
from zfsdu.zfs import ZFSClient


class FakeZFSClient(ZFSClient):
    def __init__(self, entries: list[ZFSEntry]) -> None:
        super().__init__(executable="zfs")
        self.entries = entries

    def list_entries(
        self,
        dataset_types: Iterable[DatasetType],
        root: str | None,
    ) -> list[ZFSEntry]:
        return self.entries

    def get_all_properties(self, dataset_name: str) -> list[tuple[str, str, str]]:
        return [
            ("recordsize", "131072", "local"),
            ("aclmode", "discard", "default"),
            ("compression", "zstd", "inherited"),
        ]


def _entry(
    name: str,
    dtype: DatasetType,
    used: int,
    refer: int = 0,
    mountpoint: str = "-",
) -> ZFSEntry:
    return ZFSEntry(name=name, dataset_type=dtype, used=used, refer=refer, mountpoint=mountpoint)


def _make_app(
    *,
    root: str | None = None,
    include_snapshots: bool = False,
    include_bookmarks: bool = False,
    hide_legacy_mountpoints: bool = False,
) -> ZFSDUApp:
    entries = [
        _entry("tank", DatasetType.FILESYSTEM, 100, 90),
        _entry("backup", DatasetType.FILESYSTEM, 40, 35),
        _entry("tank/home", DatasetType.FILESYSTEM, 70, 60),
        _entry("tank/home/docs", DatasetType.FILESYSTEM, 10, 8),
        _entry("tank/home@daily", DatasetType.SNAPSHOT, 5, 5),
    ]
    return ZFSDUApp(
        zfs_client=FakeZFSClient(entries),
        config=UIConfig(
            root=root,
            dataset_types={DatasetType.FILESYSTEM, DatasetType.SNAPSHOT},
            include_snapshots=include_snapshots,
            include_bookmarks=include_bookmarks,
            hide_legacy_mountpoints=hide_legacy_mountpoints,
            size_mode=SizeMode.RAW,
            sort_metric=SortMetric.USED_BYTES,
            sort_direction=SortDirection.DESC,
        ),
    )


def test_arrow_navigation_enters_and_leaves_datasets() -> None:
    async def scenario() -> None:
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.pause()
            assert app._current_directory is None
            assert app._selected_name == "tank"

            await pilot.press("right")
            await pilot.pause()
            assert app._current_directory == "tank"
            assert app._selected_name == "tank/home"

            await pilot.press("right")
            await pilot.pause()
            assert app._current_directory == "tank/home"
            assert app._selected_name == "tank/home/docs"

            await pilot.press("left")
            await pilot.pause()
            assert app._current_directory == "tank"
            assert app._selected_name == "tank/home"

            await pilot.press("left")
            await pilot.pause()
            assert app._current_directory is None
            assert app._selected_name == "tank"

    asyncio.run(scenario())


def test_left_arrow_stays_within_scan_root() -> None:
    async def scenario() -> None:
        app = _make_app(root="tank")

        async with app.run_test() as pilot:
            await pilot.pause()
            assert app._current_directory == "tank"
            assert app._selected_name == "tank/home"

            await pilot.press("left")
            await pilot.pause()
            assert app._current_directory == "tank"
            assert app._selected_name == "tank/home"

    asyncio.run(scenario())


def test_search_opens_matching_parent_directory() -> None:
    async def scenario() -> None:
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.pause()
            app._jump_to_search("docs")
            await pilot.pause()

            assert app._current_directory == "tank/home"
            assert app._selected_name == "tank/home/docs"

    asyncio.run(scenario())


def test_details_include_get_all_properties() -> None:
    async def scenario() -> None:
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.pause()
            assert app._selected_name == "tank"
            assert "tank" in app._zfs_get_all_cache

            rows = app._get_all_rows("tank")
            rendered_rows = "\n".join(rows)
            assert "aclmode" in rendered_rows
            assert "compression" in rendered_rows
            assert "recordsize" in rendered_rows
            assert rendered_rows.index("aclmode") < rendered_rows.index("compression") < rendered_rows.index("recordsize")

            data_rows = rows[2:]
            source_starts = [
                (line.index("default") if "default" in line else line.index("inherited") if "inherited" in line else line.index("local"))
                for line in data_rows
            ]
            assert len(set(source_starts)) == 1

            await pilot.press("d")
            await pilot.pause()

            filtered_rows = "\n".join(app._get_all_rows("tank"))
            assert "aclmode" not in filtered_rows
            assert "compression" in filtered_rows
            assert "recordsize" in filtered_rows

    asyncio.run(scenario())


def test_hide_legacy_mountpoints_filters_matching_datasets() -> None:
    async def scenario() -> None:
        entries = [
            _entry("tank", DatasetType.FILESYSTEM, 100, 90, mountpoint="/tank"),
            _entry("tank/legacy", DatasetType.FILESYSTEM, 40, 30, mountpoint="legacy"),
            _entry("tank/normal", DatasetType.FILESYSTEM, 30, 20, mountpoint="/tank/normal"),
        ]
        app = ZFSDUApp(
            zfs_client=FakeZFSClient(entries),
            config=UIConfig(
                root="tank",
                dataset_types={DatasetType.FILESYSTEM},
                include_snapshots=False,
                include_bookmarks=False,
                hide_legacy_mountpoints=True,
                size_mode=SizeMode.RAW,
                sort_metric=SortMetric.NAME,
                sort_direction=SortDirection.ASC,
            ),
        )

        async with app.run_test() as pilot:
            await pilot.pause()
            assert "tank/legacy" not in app._visible_names
            assert "tank/normal" in app._visible_names

    asyncio.run(scenario())



