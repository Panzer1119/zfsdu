import asyncio
from collections.abc import Iterable

from zfsdu.models import DatasetType, SizeMode, SortMetric, ZFSEntry
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


def _entry(name: str, dtype: DatasetType, used: int, refer: int = 0) -> ZFSEntry:
    return ZFSEntry(name=name, dataset_type=dtype, used=used, refer=refer)


def _make_app(*, root: str | None = None, include_snapshots: bool = False, include_bookmarks: bool = False) -> ZFSDUApp:
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
            size_mode=SizeMode.RAW,
            sort_metric=SortMetric.USED_BYTES,
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



