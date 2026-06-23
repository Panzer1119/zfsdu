from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import DatasetType, SortMetric, ZFSEntry


@dataclass(slots=True)
class DatasetIndex:
    entries: dict[str, ZFSEntry]
    children: dict[str | None, list[str]]

    @classmethod
    def build(cls, entries: list[ZFSEntry]) -> DatasetIndex:
        by_name = {entry.name: entry for entry in entries}
        children: dict[str | None, list[str]] = defaultdict(list)

        for entry in entries:
            parent = entry.parent_name
            if parent and parent not in by_name and not entry.is_snapshot and not entry.is_bookmark:
                parent = None
            children[parent].append(entry.name)

        return cls(entries=by_name, children=dict(children))

    def top_level(self, root: str | None) -> list[str]:
        if root:
            return [root] if root in self.entries else []
        return self.children.get(None, [])

    def children_of(
        self,
        parent_name: str,
        *,
        include_snapshots: bool,
        include_bookmarks: bool,
        allowed_types: set[DatasetType],
        sort_metric: SortMetric,
    ) -> list[str]:
        names = []
        for child_name in self.children.get(parent_name, []):
            entry = self.entries[child_name]
            if not include_snapshots and entry.is_snapshot:
                continue
            if not include_bookmarks and entry.is_bookmark:
                continue
            if entry.dataset_type not in allowed_types:
                continue
            names.append(child_name)

        return sorted(names, key=lambda name: self._sort_key(self.entries[name], sort_metric))

    def has_children(self, name: str) -> bool:
        return name in self.children

    def search(self, query: str, root: str | None) -> list[str]:
        needle = query.lower().strip()
        if not needle:
            return []

        matches: list[str] = []
        for name in self.entries:
            if root:
                root_prefix = f"{root}/"
                root_snapshot_prefix = f"{root}@"
                if not (
                    name == root
                    or name.startswith(root_prefix)
                    or name.startswith(root_snapshot_prefix)
                ):
                    continue
            if needle in name.lower():
                matches.append(name)
        matches.sort()
        return matches

    @staticmethod
    def _sort_key(entry: ZFSEntry, metric: SortMetric) -> tuple:
        if metric is SortMetric.NAME:
            return (entry.short_name.lower(),)
        if metric is SortMetric.REFERENCED_BYTES:
            return (-entry.refer, entry.short_name.lower())
        if metric is SortMetric.SNAPSHOT_USED_BYTES:
            return (-entry.used_by_snapshots, entry.short_name.lower())
        return (-entry.used, entry.short_name.lower())


