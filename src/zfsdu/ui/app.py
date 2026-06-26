from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import DataTable, Footer, Header, Input, Static

from zfsdu.errors import ZFSDUError
from zfsdu.formatters import format_bytes, format_percent
from zfsdu.models import (
    DatasetType,
    SizeMode,
    SortDirection,
    SortMetric,
    ZFSEntry,
    Column,
)
from zfsdu.tree import DatasetIndex
from zfsdu.zfs import ZFSClient


@dataclass(slots=True)
class UIConfig:
    root: str | None
    dataset_types: set[DatasetType]
    include_snapshots: bool
    include_bookmarks: bool
    hide_legacy_mountpoints: bool
    size_mode: SizeMode
    sort_metric: SortMetric
    sort_direction: SortDirection


_BROWSER_BINDINGS = [
    binding
    for binding in Binding.make_bindings(DataTable.BINDINGS)
    if binding.key not in {"enter", "left", "right"}
]

_COLUMNS: list[Column] = [
    Column(
        key="name",
        label_full="Name",
        sort_metric=SortMetric.NAME,
        sort_direction=None,
    ),
    Column(
        key="used_bytes",
        label_full="Used Bytes",
        label_short="Used",
        sort_metric=SortMetric.USED_BYTES,
        default_sort_direction=SortDirection.DESC,
        sort_direction=None,
    ),
    Column(
        key="referenced_bytes",
        label_full="Referenced Bytes",
        label_short="Refer",
        sort_metric=SortMetric.REFERENCED_BYTES,
        default_sort_direction=SortDirection.DESC,
        sort_direction=None,
    ),
    Column(
        key="snapshot_used_bytes",
        label_full="Snapshot Used Bytes",
        label_short="Snapshot Used",
        sort_metric=SortMetric.SNAPSHOT_USED_BYTES,
        default_sort_direction=SortDirection.DESC,
        sort_direction=None,
    ),
    Column(
        key="snapshot_count",
        label_full="Snapshot Count",
        label_short="Snapshots",
        sort_metric=SortMetric.SNAPSHOT_COUNT,
        default_sort_direction=SortDirection.DESC,
        sort_direction=None,
    ),
    Column(
        key="share",
        label_full="Share of Parent",
        label_short="Share",
        # sort_metric=SortMetric.SHARE,
        sort_metric=None, #TODO How to sort by share?
        default_sort_direction=SortDirection.DESC,
        sort_direction=None,
    ),
    Column(
        key="type",
        label_full="Dataset Type",
        label_short="Type",
        sort_metric=SortMetric.TYPE,
        sort_direction=None,
    )
]


class DatasetTable(DataTable):
    BINDINGS = [
        Binding("right,enter", "enter_dataset", "Open", show=False),
        Binding("left", "leave_dataset", "Up", show=False),
        *_BROWSER_BINDINGS,
    ]

    class EnterDataset(Message):
        def __init__(self, table: DatasetTable) -> None:
            super().__init__()
            self.table = table

    class LeaveDataset(Message):
        def __init__(self, table: DatasetTable) -> None:
            super().__init__()
            self.table = table

    def action_enter_dataset(self) -> None:
        self.post_message(self.EnterDataset(self))

    def action_leave_dataset(self) -> None:
        self.post_message(self.LeaveDataset(self))


class ZFSDUApp(App[None]):
    TITLE = "zfsdu"
    CSS_PATH = "zfsdu.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("left", "leave_dataset", "Up"),
        Binding("right,enter", "enter_dataset", "Open"),
        Binding("s", "cycle_sort_next", "Sort"),
        Binding("shift+s", "cycle_sort_previous", "Sort (prev)"),
        Binding("i", "toggle_sort_direction", "Reverse"),
        Binding("m", "cycle_size", "Size"),
        Binding("t", "toggle_snapshots", "Snapshots"),
        Binding("b", "toggle_bookmarks", "Bookmarks"),
        Binding("d", "toggle_default_properties", "Defaults"),
        Binding("/", "search", "Search"),
    ]

    def __init__(self, *, zfs_client: ZFSClient, config: UIConfig) -> None:
        super().__init__()
        self.zfs_client = zfs_client
        self.config = config
        self.index: DatasetIndex | None = None
        self._current_directory = config.root
        self._selected_name: str | None = None
        self._visible_names: list[str] = []
        self._search_results: list[str] = []
        self._search_cursor = 0
        self._last_search_query = ""
        self._show_default_properties = False
        self._zfs_get_all_cache: dict[str, list[tuple[str, str, str]]] = {}
        self._zfs_get_all_error_cache: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="browser"):
                yield Static(id="path")
                yield DatasetTable(id="entries")
            yield Static("Loading...", id="details")
        yield Input(placeholder="Search datasets...", id="search-box", classes="hidden")
        yield Static(
            "Use ←/→ to leave or enter datasets, / to search, s to sort, "
            "m to change size mode, t to toggle snapshots, d to toggle default properties",
            id="status",
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#entries", DatasetTable)
        table.cursor_type = "row"
        table.zebra_stripes = True
        columns: list[tuple[str, str]] = [(column.get_label, column.key) for column in _COLUMNS]
        table.add_columns(*columns)
        self._load_data()
        table.focus()

    def _update_columns(self) -> None:
        """Update column headers to show which column is sorted and in what direction."""
        table = self.query_one("#entries", DatasetTable)
        for column in _COLUMNS:
            if column.sort_metric == self.config.sort_metric:
                column.sort_direction = self.config.sort_direction
            else:
                column.sort_direction = None
            table_column = table.columns.get(column.key)
            if not table_column:
                continue
            table_column.label = column.get_label

    def action_refresh(self) -> None:
        self._load_data()

    def action_enter_dataset(self) -> None:
        if not self.index:
            return
        if not self._selected_name:
            self._set_status("No dataset selected")
            return

        entry = self.index.entries[self._selected_name]
        if entry.is_snapshot:
            #TODO What if bookmarks are visible?
            self._set_status("Snapshots cannot be opened")
            return

        if entry.is_bookmark:
            self._set_status("Bookmarks cannot be opened")
            return

        if self.index and not self.index.has_children(entry.name):
            #TODO What if it has children, but snapshots are hidden?
            self._set_status("Already at top level")
            return

        self._current_directory = entry.name
        self._render_browser()
        count = len(self._visible_names)
        if count:
            self._set_status(f"Opened {entry.name} ({count} entries)")
        else:
            self._set_status(f"Opened {entry.name} (empty)")

    def action_leave_dataset(self) -> None:
        if not self.index:
            return
        if self._current_directory is None:
            self._set_status("Already at top level")
            return
        if self.config.root and self._current_directory == self.config.root:
            self._set_status("Already at scan root")
            return

        previous = self._current_directory
        self._current_directory = self.index.entries[previous].parent_name
        self._render_browser(select_name=previous)
        location = self._current_directory or "top level"
        self._set_status(f"Browsing {location}")

    def action_cycle_sort_next(self) -> None:
        self.cycle_sort(cycle_next=True)

    def action_cycle_sort_previous(self) -> None:
        self.cycle_sort(cycle_next=False)

    def cycle_sort(self, cycle_next: bool = True) -> None:
        order: list[SortMetric] = []
        for column in _COLUMNS:
            if column.is_sortable and column.sort_metric is not None:
                order.append(column.sort_metric)
        if cycle_next:
            idx = (order.index(self.config.sort_metric) + 1) % len(order)
        else:
            idx = (order.index(self.config.sort_metric) - 1) % len(order)
        self.config.sort_metric = order[idx]
        self.config.sort_direction = SortDirection.ASC  # Reset to ASC when changing metric
        for column in _COLUMNS:
            if column.sort_metric == self.config.sort_metric and column.default_sort_direction is not None:
                self.config.sort_direction = column.default_sort_direction
        self._render_browser(select_name=self._selected_name)
        direction_label = "↓" if self.config.sort_direction is SortDirection.DESC else "↑"
        self._set_status(f"Sort: {self.config.sort_metric.value} ({direction_label})")

    def action_toggle_sort_direction(self) -> None:
        is_desc = self.config.sort_direction is SortDirection.DESC
        self.config.sort_direction = SortDirection.ASC if is_desc else SortDirection.DESC
        self._render_browser(select_name=self._selected_name)
        direction_label = "↓" if self.config.sort_direction is SortDirection.DESC else "↑"
        self._set_status(f"Sort direction: {self.config.sort_direction.value} {direction_label}")

    def action_cycle_size(self) -> None:
        order = [SizeMode.IEC, SizeMode.DECIMAL, SizeMode.RAW]
        idx = (order.index(self.config.size_mode) + 1) % len(order)
        self.config.size_mode = order[idx]
        self._render_browser(select_name=self._selected_name)
        self._refresh_details()
        self._set_status(f"Size mode: {self.config.size_mode.value}")

    def action_toggle_snapshots(self) -> None:
        self.config.include_snapshots = not self.config.include_snapshots
        self._render_browser(select_name=self._selected_name)
        state = "shown" if self.config.include_snapshots else "hidden"
        self._set_status(f"Snapshots {state}")

    def action_toggle_bookmarks(self) -> None:
        self.config.include_bookmarks = not self.config.include_bookmarks
        self._render_browser(select_name=self._selected_name)
        state = "shown" if self.config.include_bookmarks else "hidden"
        self._set_status(f"Bookmarks {state}")

    def action_toggle_default_properties(self) -> None:
        self._show_default_properties = not self._show_default_properties
        self._refresh_details()
        state = "shown" if self._show_default_properties else "hidden"
        self._set_status(f"Default properties {state}")

    def action_search(self) -> None:
        input_widget = self.query_one("#search-box", Input)
        input_widget.remove_class("hidden")
        input_widget.focus()

    def _load_data(self) -> None:
        self._set_status("Loading ZFS metadata...")
        previous_directory = self._current_directory
        previous_selection = self._selected_name
        try:
            entries = self.zfs_client.list_entries(self.config.dataset_types, self.config.root)
        except ZFSDUError as exc:
            self._set_status(f"Error: {exc}")
            return
        self.index = DatasetIndex.build(entries)
        self._zfs_get_all_cache.clear()
        self._zfs_get_all_error_cache.clear()
        self._search_results.clear()
        self._search_cursor = 0
        self._last_search_query = ""
        self._current_directory = self._restore_directory(previous_directory)
        self._render_browser(select_name=previous_selection)
        self._set_status(f"Loaded {len(entries)} ZFS entries")

    def _restore_directory(self, previous_directory: str | None) -> str | None:
        if not self.index:
            return self.config.root
        if previous_directory and previous_directory in self.index.entries:
            return previous_directory
        if self.config.root and self.config.root in self.index.entries:
            return self.config.root
        return None

    def _render_browser(self, *, select_name: str | None = None) -> None:
        if not self.index:
            return

        table = self.query_one("#entries", DatasetTable)
        table.clear(columns=False)
        self._visible_names = self._visible_children(self._current_directory)

        for name in self._visible_names:
            entry = self.index.entries[name]
            table.add_row(
                self._row_name(entry),
                format_bytes(entry.used, self.config.size_mode),
                format_bytes(entry.refer, self.config.size_mode),
                format_bytes(entry.used_by_snapshots, self.config.size_mode),
                entry.snapshot_count,
                self._share_of_parent(entry),
                entry.dataset_type.value,
                key=name,
            )

        self._update_path()
        self._update_columns()

        if self._visible_names:
            if select_name is not None and select_name in self._visible_names:
                row = self._visible_names.index(select_name)
            else:
                row = 0
            self._selected_name = self._visible_names[row]
            table.move_cursor(row=row, column=0)
        else:
            self._selected_name = None

        self._refresh_details()

    def _snapshot_count(self, parent_name: str | None) -> int:
        if not self.index or parent_name is None:
            return 0
        return len(
            self.index.children_of(
                parent_name,
                include_snapshots=True,
                include_bookmarks=False,
                allowed_types={DatasetType.SNAPSHOT},
                sort_metric=self.config.sort_metric,
                sort_direction=self.config.sort_direction,
            )
        )

    def _bookmark_count(self, parent_name: str | None) -> int:
        if not self.index or parent_name is None:
            return 0
        return len(
            self.index.children_of(
                parent_name,
                include_snapshots=False,
                include_bookmarks=True,
                allowed_types={DatasetType.BOOKMARK},
                sort_metric=self.config.sort_metric,
                sort_direction=self.config.sort_direction,
            )
        )

    def _visible_children(self, parent_name: str | None) -> list[str]:
        if not self.index:
            return []
        if parent_name is None:
            return [
                name for name in self.index.top_level(self.config.root) if self._is_visible(name)
            ]
        names = self.index.children_of(
            parent_name,
            include_snapshots=self.config.include_snapshots,
            include_bookmarks=self.config.include_bookmarks,
            allowed_types=self.config.dataset_types,
            sort_metric=self.config.sort_metric,
            sort_direction=self.config.sort_direction,
        )
        return [name for name in names if self._is_visible(name)]

    def _is_visible(self, name: str) -> bool:
        if not self.index:
            return False
        entry = self.index.entries[name]
        if entry.dataset_type not in self.config.dataset_types:
            return False
        if entry.is_snapshot and not self.config.include_snapshots:
            return False
        if entry.is_bookmark and not self.config.include_bookmarks:
            return False
        if self.config.hide_legacy_mountpoints and entry.mountpoint == "legacy":
            return False
        return True

    def _row_name(self, entry: ZFSEntry) -> str:
        if entry.is_snapshot:
            return f"  {entry.short_name}"
        if entry.is_bookmark:
            return f"  {entry.short_name}"
        if self.index and not self.index.has_children(entry.name):
            #TODO What if it has children, but snapshots are hidden?
            return f"  {entry.short_name}"
        return f"▸ {entry.short_name}"

    def _share_of_parent(self, entry: ZFSEntry) -> str:
        if not self.index:
            return "-"
        parent_name = entry.parent_name
        if not parent_name:
            return "-"
        parent = self.index.entries.get(parent_name)
        if not parent or parent.used <= 0:
            return "-"
        return format_percent(entry.used, parent.used)

    def _update_path(self) -> None:
        root_label = self.config.root or "all datasets"
        current_label = self._current_directory or "top level"
        count = len(self._visible_names)
        noun = "entry" if count == 1 else "entries"
        direction_symbol = "↓" if self.config.sort_direction is SortDirection.DESC else "↑"
        sort_info = f"[dim]sort:[/] {self.config.sort_metric.value} {direction_symbol}"
        self.query_one("#path", Static).update(
            f"[b]Browsing:[/] {current_label}  [dim]root:[/] {root_label}\n"
            f"[dim]items:[/] {count} {noun}  {sort_info}"
        )

    @on(DatasetTable.EnterDataset)
    def on_enter_dataset(self) -> None:
        self.action_enter_dataset()

    @on(DatasetTable.LeaveDataset)
    def on_leave_dataset(self) -> None:
        self.action_leave_dataset()

    @on(DataTable.RowHighlighted, "#entries")
    def on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if 0 <= event.cursor_row < len(self._visible_names):
            self._selected_name = self._visible_names[event.cursor_row]
            self._refresh_details()

    @on(Input.Submitted, "#search-box")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        event.input.add_class("hidden")
        event.input.value = ""
        self.query_one("#entries", DatasetTable).focus()

        if not query:
            self._set_status("Search canceled")
            return
        self._jump_to_search(query)

    def _jump_to_search(self, query: str) -> None:
        if not self.index:
            return

        normalized_query = query.lower()
        if normalized_query != self._last_search_query:
            self._search_results = self.index.search(query, self.config.root)
            self._search_cursor = 0
            self._last_search_query = normalized_query

        if not self._search_results:
            self._set_status(f"No match for '{query}'")
            return

        if self._search_cursor >= len(self._search_results):
            self._search_cursor = 0

        name = self._search_results[self._search_cursor]
        self._search_cursor += 1

        if not self._is_visible(name):
            self._set_status("Match is currently filtered out")
            return

        self._current_directory, select_name = self._search_location(name)
        self._render_browser(select_name=select_name)
        self._set_status(f"Match {self._search_cursor}/{len(self._search_results)}: {name}")

    def _search_location(self, name: str) -> tuple[str | None, str | None]:
        if not self.index:
            return (self.config.root, None)
        if self.config.root and name == self.config.root:
            return (self.config.root, None)
        return (self.index.entries[name].parent_name, name)

    def _refresh_details(self, name: str | None = None) -> None:
        details = self.query_one("#details", Static)
        if not self.index:
            details.update("No dataset selected")
            return

        target_name = name or self._selected_name or self._current_directory
        if not target_name:
            details.update("No dataset selected")
            return

        entry = self.index.entries[target_name]
        parent = self.index.entries.get(entry.parent_name or "")
        parent_used = parent.used if parent else 0
        snapshot_count = self._snapshot_count(entry.name)
        bookmark_count = self._bookmark_count(entry.name)
        if entry.is_bookmark:
            extra = ""
        elif entry.is_snapshot:
            extra = f"bookmarks:         {bookmark_count}"
        else:
            extra = f"snapshots:         {snapshot_count}"
        visible_children = len(self._visible_children(entry.name))
        total_children = len(self.index.children.get(entry.name, []))

        rows = [
            f"[b]{entry.name}[/b]",
            "",
            f"type:              {entry.dataset_type.value}",
            f"used:              {format_bytes(entry.used, self.config.size_mode)}",
            f"referenced:        {format_bytes(entry.refer, self.config.size_mode)}",
            f"used by snapshots: {format_bytes(entry.used_by_snapshots, self.config.size_mode)}",
            f"used by dataset:   {format_bytes(entry.used_by_dataset, self.config.size_mode)}",
            f"used by children:  {format_bytes(entry.used_by_children, self.config.size_mode)}",
            "refreservation:    "
            f"{format_bytes(entry.used_by_refreservation, self.config.size_mode)}",
            extra,
            f"children shown:    {visible_children}",
            f"children total:    {total_children}",
            f"mountpoint:        {entry.mountpoint}",
        ]
        if parent:
            rows.append(f"share of parent:   {format_percent(entry.used, parent_used)}")

        rows.extend(["", "[b]zfs get all[/b]"])
        rows.extend(self._get_all_rows(entry.name))

        details.update("\n".join(rows))

    def _get_all_rows(self, dataset_name: str) -> list[str]:
        if dataset_name in self._zfs_get_all_error_cache:
            return [f"[dim]Unable to load properties:[/] {self._zfs_get_all_error_cache[dataset_name]}"]

        properties = self._zfs_get_all_cache.get(dataset_name)
        if properties is None:
            try:
                properties = self.zfs_client.get_all_properties(dataset_name)
            except ZFSDUError as exc:
                self._zfs_get_all_error_cache[dataset_name] = str(exc)
                return [f"[dim]Unable to load properties:[/] {exc}"]
            self._zfs_get_all_cache[dataset_name] = properties

        visible_properties = sorted(properties, key=lambda row: row[0].lower())
        if not self._show_default_properties:
            visible_properties = [row for row in visible_properties if row[2].lower() != "default"]

        if not visible_properties:
            return ["[dim]No properties to display with current filters[/]"]

        property_width = max((len(name) for name, _, _ in visible_properties), default=8)
        property_width = min(max(property_width, 8), 36)
        value_width = max((len(value) for _, value, _ in visible_properties), default=5)
        value_width = min(max(value_width, 5), 64)
        source_width = max((len(source) for _, _, source in visible_properties), default=6)
        source_width = min(max(source_width, 6), 20)

        rows = [
            f"{'property':<{property_width}}  {'value':<{value_width}}  {'source':<{source_width}}",
            f"{'-' * property_width}  {'-' * value_width}  {'-' * source_width}",
        ]
        rows.extend(
            f"{property_name:<{property_width}}  {value:<{value_width}}  {source:<{source_width}}"
            for property_name, value, source in visible_properties
        )
        return rows

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)



