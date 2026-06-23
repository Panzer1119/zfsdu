from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Iterable

from .errors import InvalidDatasetError, ZFSCommandError, ZFSUnavailableError
from .models import DatasetType, ZFSEntry

_LOG = logging.getLogger(__name__)

_ZFS_COLUMNS = [
    "name",
    "type",
    "used",
    "refer",
    "usedbysnapshots",
    "usedbydataset",
    "usedbychildren",
    "usedbyrefreservation",
    "creation",
    "mountpoint",
]


class ZFSClient:
    def __init__(self, executable: str = "zfs") -> None:
        self.executable = executable

    def check_available(self) -> None:
        if shutil.which(self.executable) is None:
            raise ZFSUnavailableError("`zfs` command not found in PATH")

    def list_entries(
        self,
        dataset_types: Iterable[DatasetType],
        root: str | None,
    ) -> list[ZFSEntry]:
        type_csv = ",".join(t.value for t in dataset_types)
        cmd = [
            self.executable,
            "list",
            "-H",
            "-p",
            "-r",
            "-t",
            type_csv,
            "-o",
            ",".join(_ZFS_COLUMNS),
        ]
        if root:
            cmd.append(root)

        output = self._run(cmd)
        entries = [self._parse_row(line) for line in output.splitlines() if line.strip()]

        if root and not entries:
            raise InvalidDatasetError(f"Dataset root `{root}` not found or has no visible children")

        return entries

    def _run(self, cmd: list[str]) -> str:
        self.check_available()
        _LOG.debug("Running command: %s", " ".join(cmd))
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise ZFSCommandError(f"Failed to execute command: {exc}") from exc

        if result.returncode != 0:
            stderr = result.stderr.strip() or "unknown error"
            if "dataset does not exist" in stderr:
                raise InvalidDatasetError(stderr)
            raise ZFSCommandError(f"`{' '.join(cmd)}` failed: {stderr}")
        return result.stdout

    @staticmethod
    def _parse_row(line: str) -> ZFSEntry:
        parts = line.rstrip("\n").split("\t")
        if len(parts) != len(_ZFS_COLUMNS):
            raise ZFSCommandError(f"Unexpected zfs output row format: {line}")

        (
            name,
            entry_type,
            used,
            refer,
            by_snap,
            by_dataset,
            by_children,
            by_refres,
            creation,
            mount,
        ) = parts

        return ZFSEntry(
            name=name,
            dataset_type=DatasetType(entry_type),
            used=_parse_zfs_int(used),
            refer=_parse_zfs_int(refer),
            used_by_snapshots=_parse_zfs_int(by_snap),
            used_by_dataset=_parse_zfs_int(by_dataset),
            used_by_children=_parse_zfs_int(by_children),
            used_by_refreservation=_parse_zfs_int(by_refres),
            creation=_parse_zfs_int(creation),
            mountpoint=mount,
        )


def _parse_zfs_int(value: str) -> int:
    if value in {"-", "none", ""}:
        return 0
    return int(value)


