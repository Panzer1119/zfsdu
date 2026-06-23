from __future__ import annotations

import argparse
import logging
import os
import sys

from .errors import InvalidDatasetError, ZFSCommandError, ZFSUnavailableError
from .models import DatasetType, SizeMode, SortMetric
from .ui.app import UIConfig, ZFSDUApp
from .zfs import ZFSClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zfsdu",
        description="ncdu-inspired interactive explorer for ZFS datasets, volumes, and snapshots",
    )
    parser.add_argument(
        "root",
        nargs="?",
        default=None,
        help="dataset root to browse (for example tank/home)",
    )
    parser.add_argument(
        "--types",
        default="filesystem,volume",
        help="comma-separated dataset types: filesystem,volume,snapshot,all",
    )
    parser.add_argument(
        "--sort",
        choices=[metric.value for metric in SortMetric],
        default=SortMetric.USED.value,
        help="sort metric for tree nodes",
    )

    size_group = parser.add_mutually_exclusive_group()
    size_group.add_argument("-H", "--human", action="store_true", help="show IEC units (default)")
    size_group.add_argument("-D", "--human-decimal", action="store_true", help="show decimal units")
    size_group.add_argument("-p", "--parsable", action="store_true", help="show raw bytes")

    parser.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default="auto",
        help="color output control",
    )
    parser.add_argument(
        "--show-snapshots",
        action="store_true",
        help="include snapshots in the tree by default",
    )
    parser.add_argument(
        "--show-bookmarks",
        action="store_true",
        help="include bookmarks in the tree by default",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="WARNING",
        help="logging verbosity",
    )
    return parser


def parse_types(raw: str) -> set[DatasetType]:
    raw = raw.strip().lower()
    if raw == "all":
        return {DatasetType.FILESYSTEM, DatasetType.VOLUME, DatasetType.SNAPSHOT}

    items = {item.strip() for item in raw.split(",") if item.strip()}
    if not items:
        raise ValueError("--types must not be empty")

    parsed: set[DatasetType] = set()
    for item in items:
        try:
            parsed.add(DatasetType(item))
        except ValueError as exc:
            raise ValueError(f"Unsupported dataset type: {item}") from exc
    return parsed


def select_size_mode(args: argparse.Namespace) -> SizeMode:
    if args.parsable:
        return SizeMode.RAW
    if args.human_decimal:
        return SizeMode.DECIMAL
    return SizeMode.IEC


def configure_color(mode: str) -> None:
    if mode == "never":
        os.environ["NO_COLOR"] = "1"
    elif mode == "always":
        os.environ["FORCE_COLOR"] = "1"


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))
    configure_color(args.color)

    try:
        dataset_types = parse_types(args.types)
    except ValueError as exc:
        parser.error(str(exc))
        return

    include_snapshots = args.show_snapshots or DatasetType.SNAPSHOT in dataset_types
    include_bookmarks = args.show_bookmarks or DatasetType.BOOKMARK in dataset_types

    config = UIConfig(
        root=args.root,
        dataset_types=dataset_types,
        include_snapshots=include_snapshots,
        include_bookmarks=include_bookmarks,
        size_mode=select_size_mode(args),
        sort_metric=SortMetric(args.sort),
    )

    try:
        zfs_client = ZFSClient()
        zfs_client.check_available()
        app = ZFSDUApp(zfs_client=zfs_client, config=config)
        app.run()
    except (ZFSUnavailableError, ZFSCommandError, InvalidDatasetError) as exc:
        print(f"zfsdu: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc




