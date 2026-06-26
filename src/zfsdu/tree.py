from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .models import DatasetType, SortMetric, SortDirection, ZFSEntry


@dataclass(slots=True)
class DatasetIndex:
    entries: dict[str, ZFSEntry]
    children: dict[str | None, list[str]]
    parents: dict[str, str | None]

    @classmethod
    def build(cls, entries: list[ZFSEntry]) -> DatasetIndex:
        by_name = {entry.name: entry for entry in entries}
        children: dict[str | None, list[str]] = defaultdict(list)
        parents: dict[str, str | None] = {}

        for entry in entries:
            parent = entry.parent_name
            if parent and parent not in by_name and not entry.is_snapshot and not entry.is_bookmark:
                parent = None
            children[parent].append(entry.name)
            parents[entry.name] = parent

        return cls(entries=by_name, children=dict(children), parents=parents)

    @classmethod
    def build_by_origin(cls, entries: list[ZFSEntry], root: str | None) -> DatasetIndex:
        filesystems = [entry for entry in entries if entry.dataset_type is DatasetType.FILESYSTEM]
        if root:
            root_prefix = f"{root}/"
            filesystems = [
                entry for entry in filesystems if entry.name == root or entry.name.startswith(root_prefix)
            ]

        by_name = {entry.name: entry for entry in filesystems}
        children: dict[str | None, list[str]] = defaultdict(list)
        parents: dict[str, str | None] = {}

        for entry in filesystems:
            parent: str | None = None
            if root and entry.name == root:
                parent = None
            else:
                origin_parent = entry.origin_dataset_name
                if origin_parent and origin_parent in by_name:
                    parent = origin_parent

            children[parent].append(entry.name)
            parents[entry.name] = parent

        return cls(entries=by_name, children=dict(children), parents=parents)

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
        sort_direction: SortDirection = SortDirection.ASC,
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

        reverse = sort_direction is SortDirection.DESC

        # Pre-sort by names
        names_sorted = sorted(names, key=lambda name: self.entries[name].short_name.lower())

        # Sort by the specified metric and direction
        names_sorted = sorted(
            names_sorted, key=lambda name: self._sort_key(self.entries[name], sort_metric), reverse=reverse
        )

        if sort_metric is SortMetric.TYPE:
            return names_sorted

        # And if not already done, sort by dataset type order
        return sorted(names_sorted, key=lambda name: self.entries[name].order)

    def has_children(self, name: str) -> bool:
        return name in self.children

    def parent_of(self, name: str) -> str | None:
        return self.parents.get(name)

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
            return (entry.short_name.lower(), )
        if metric is SortMetric.USED_BYTES:
            return (entry.used, )
        if metric is SortMetric.REFERENCED_BYTES:
            return (entry.refer, )
        if metric is SortMetric.SNAPSHOT_USED_BYTES:
            return (entry.used_by_snapshots, )
        if metric is SortMetric.SNAPSHOT_COUNT:
            return (entry.snapshot_count, )
        #TODO How to sort by share?
        # if metric is SortMetric.SHARE:
        #     return (entry.share, )
        if metric is SortMetric.TYPE:
            # return (entry.dataset_type, )
            return (entry.order, )
        return (entry.short_name.lower(),)


