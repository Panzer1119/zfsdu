from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import Footer, Header, Input, Static, Tree

from zfsdu.errors import ZFSDUError
from zfsdu.formatters import format_bytes, format_percent
from zfsdu.models import DatasetType, SizeMode, SortMetric, ZFSEntry
from zfsdu.tree import DatasetIndex
from zfsdu.zfs import ZFSClient


@dataclass(slots=True)
class UIConfig:
    root: str | None
    dataset_types: set[DatasetType]
    include_snapshots: bool
    size_mode: SizeMode
    sort_metric: SortMetric


class ZFSDUApp(App[None]):
    TITLE = "zfsdu"
    CSS_PATH = "zfsdu.tcss"
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "cycle_sort", "Sort"),
        Binding("m", "cycle_size", "Size"),
        Binding("t", "toggle_snapshots", "Snapshots"),
        Binding("/", "search", "Search"),
    ]

    def __init__(self, *, zfs_client: ZFSClient, config: UIConfig) -> None:
        super().__init__()
        self.zfs_client = zfs_client
        self.config = config
        self.index: DatasetIndex | None = None
        self.name_to_node: dict[str, Tree.Node] = {}
        self._search_results: list[str] = []
        self._search_cursor = 0
        self._last_search_query = ""

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            yield Tree("datasets", id="tree")
            yield Static("Loading...", id="details")
        yield Input(placeholder="Search datasets...", id="search-box", classes="hidden")
        yield Static(
            "Press / to search, s to sort, m to change size mode, t to toggle snapshots",
            id="status",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_data()

    def action_refresh(self) -> None:
        self._load_data()

    def action_cycle_sort(self) -> None:
        order = [SortMetric.USED, SortMetric.REFER, SortMetric.SNAPSHOT, SortMetric.NAME]
        idx = (order.index(self.config.sort_metric) + 1) % len(order)
        self.config.sort_metric = order[idx]
        self._render_tree()
        self._set_status(f"Sort: {self.config.sort_metric.value}")

    def action_cycle_size(self) -> None:
        order = [SizeMode.IEC, SizeMode.DECIMAL, SizeMode.RAW]
        idx = (order.index(self.config.size_mode) + 1) % len(order)
        self.config.size_mode = order[idx]
        self._render_tree()
        self._refresh_details()
        self._set_status(f"Size mode: {self.config.size_mode.value}")

    def action_toggle_snapshots(self) -> None:
        self.config.include_snapshots = not self.config.include_snapshots
        self._render_tree()
        state = "shown" if self.config.include_snapshots else "hidden"
        self._set_status(f"Snapshots {state}")

    def action_search(self) -> None:
        input_widget = self.query_one("#search-box", Input)
        input_widget.remove_class("hidden")
        input_widget.focus()

    def _load_data(self) -> None:
        self._set_status("Loading ZFS metadata...")
        try:
            entries = self.zfs_client.list_entries(self.config.dataset_types, self.config.root)
        except ZFSDUError as exc:
            self._set_status(f"Error: {exc}")
            return
        self.index = DatasetIndex.build(entries)
        self._render_tree()
        self._set_status(f"Loaded {len(entries)} ZFS entries")

    def _render_tree(self) -> None:
        tree = self.query_one("#tree", Tree)
        tree.clear()
        tree.root.set_label("datasets")
        tree.root.expand()
        self.name_to_node.clear()

        if not self.index:
            return

        for top_name in self.index.top_level(self.config.root):
            self._add_subtree(tree.root, top_name)

        if self.name_to_node:
            first = next(iter(self.name_to_node.values()))
            tree.select_node(first)
            self._refresh_details(first.data)

    def _add_subtree(self, parent: Tree.Node, name: str) -> None:
        if not self.index:
            return
        entry = self.index.entries[name]

        children = self.index.children_of(
            name,
            include_snapshots=self.config.include_snapshots,
            allowed_types=self.config.dataset_types,
            sort_metric=self.config.sort_metric,
        )
        node = parent.add(self._node_label(entry), data=name, allow_expand=bool(children))
        self.name_to_node[name] = node
        for child_name in children:
            self._add_subtree(node, child_name)

    def _node_label(self, entry: ZFSEntry) -> str:
        return (
            f"{entry.short_name}  [dim]used:[/] {format_bytes(entry.used, self.config.size_mode)}"
            f"  [dim]refer:[/] {format_bytes(entry.refer, self.config.size_mode)}"
        )

    @on(Tree.NodeSelected)
    def on_tree_selected(self, event: Tree.NodeSelected) -> None:
        name = event.node.data
        if isinstance(name, str):
            self._refresh_details(name)

    @on(Input.Submitted, "#search-box")
    def on_search_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        event.input.add_class("hidden")
        event.input.value = ""
        self.query_one("#tree", Tree).focus()

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

        node = self.name_to_node.get(name)
        if not node:
            self._set_status("Match is currently filtered out")
            return

        self._expand_ancestors(node)
        tree = self.query_one("#tree", Tree)
        tree.select_node(node)
        self._refresh_details(name)
        self._set_status(f"Match {self._search_cursor}/{len(self._search_results)}: {name}")

    def _expand_ancestors(self, node: Tree.Node) -> None:
        parent = node.parent
        while parent is not None:
            parent.expand()
            parent = parent.parent

    def _refresh_details(self, name: str | None = None) -> None:
        details = self.query_one("#details", Static)
        if not self.index or not name:
            details.update("No dataset selected")
            return

        entry = self.index.entries[name]
        parent = self.index.entries.get(entry.parent_name or "")
        parent_used = parent.used if parent else 0

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
            f"mountpoint:        {entry.mountpoint}",
        ]
        if parent:
            rows.append(f"share of parent:   {format_percent(entry.used, parent_used)}")

        details.update("\n".join(rows))

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)



