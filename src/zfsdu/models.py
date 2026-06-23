from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DatasetType(StrEnum):
    FILESYSTEM = "filesystem"
    VOLUME = "volume"
    SNAPSHOT = "snapshot"
    BOOKMARK = "bookmark"


class SortMetric(StrEnum):
    USED = "used"
    REFER = "refer"
    SNAPSHOT = "snapshot"
    NAME = "name"


class SizeMode(StrEnum):
    IEC = "iec"
    DECIMAL = "decimal"
    RAW = "raw"


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

    @property
    def is_snapshot(self) -> bool:
        return self.dataset_type is DatasetType.SNAPSHOT

    @property
    def is_bookmark(self) -> bool:
        return self.dataset_type is DatasetType.BOOKMARK

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


