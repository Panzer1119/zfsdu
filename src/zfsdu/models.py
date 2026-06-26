from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DatasetType(StrEnum):
    FILESYSTEM = "filesystem"
    VOLUME = "volume"
    SNAPSHOT = "snapshot"
    BOOKMARK = "bookmark"


class SortMetric(StrEnum):
    NAME = "name"
    USED_BYTES = "used_bytes"
    REFERENCED_BYTES = "referenced_bytes"
    SNAPSHOT_USED_BYTES = "snapshot_used_bytes"
    SNAPSHOT_COUNT = "snapshot_count"
    SHARE = "share"
    TYPE = "type"


class SortDirection(StrEnum):
    ASC = "asc"
    DESC = "desc"


class SizeMode(StrEnum):
    IEC = "iec"
    DECIMAL = "decimal"
    RAW = "raw"


@dataclass(slots=True, frozen=False)
class Column:
    """Uniquely identifies a column in the DataTable."""
    key: str
    label_full: str
    label_short: str | None = None
    sort_metric: SortMetric | None = None
    default_sort_direction: SortDirection = SortDirection.ASC
    sort_direction: SortDirection | None = None
    hidden: bool = False

    @property
    def is_sortable(self) -> bool:
        return self.sort_metric is not None

    @property
    def is_sorted_by(self) -> bool:
        return self.is_sortable and self.sort_direction is not None

    @property
    def get_label(self, short: bool = True) -> str:
        label: str = self.label_short if short and self.label_short is not None else self.label_full
        if self.is_sorted_by:
            direction_symbol = "▲" if self.sort_direction is SortDirection.ASC else "▼"
            return f"{label} {direction_symbol}"
        #return label
        return f"{label}  "


@dataclass(slots=True, frozen=True)
class ZFSEntry:
    name: str
    dataset_type: DatasetType
    used: int
    refer: int
    used_by_snapshots: int = 0
    used_by_dataset: int = 0
    used_by_children: int = 0
    used_by_refreservation: int = 0
    creation: int = 0
    mountpoint: str = "-"
    origin: str = "-"
    snapshot_count: int = 0 #TODO How do we calculate this, if this is read-only?

    @property
    def is_snapshot(self) -> bool:
        return self.dataset_type is DatasetType.SNAPSHOT

    @property
    def is_bookmark(self) -> bool:
        return self.dataset_type is DatasetType.BOOKMARK

    @property
    def is_normal(self) -> bool:
        return self.dataset_type in {DatasetType.FILESYSTEM, DatasetType.VOLUME}

    @property
    def order(self) -> int:
        """Return an integer representing the order of the dataset type for sorting purposes."""
        if self.dataset_type is DatasetType.FILESYSTEM:
            return 0
        if self.dataset_type is DatasetType.VOLUME:
            return 1
        if self.dataset_type is DatasetType.SNAPSHOT:
            return 2
        if self.dataset_type is DatasetType.BOOKMARK:
            return 3
        return 4

    @property
    def parent_name(self) -> str | None:
        if self.is_snapshot:
            return self.name.split("@", 1)[0]
        if self.is_bookmark:
            return self.name.split("#", 1)[0]
        if "/" not in self.name:
            return None
        return self.name.rsplit("/", 1)[0]

    @property
    def short_name(self) -> str:
        if self.is_snapshot:
            return "@" + self.name.split("@", 1)[1]
        if self.is_bookmark:
            return "#" + self.name.split("#", 1)[1]
        if "/" not in self.name:
            return self.name
        return self.name.rsplit("/", 1)[1]

    @property
    def origin_dataset_name(self) -> str | None:
        if self.origin in {"-", "", "none"}:
            return None
        if "@" not in self.origin:
            return None
        return self.origin.split("@", 1)[0]


