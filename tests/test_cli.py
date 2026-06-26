from __future__ import annotations

import logging
from pathlib import Path

from zfsdu.cli import build_parser, configure_logging


def test_parser_accepts_log_file() -> None:
    parser = build_parser()
    args = parser.parse_args(["--log-file", "zfsdu.log"])

    assert args.log_file == "zfsdu.log"


def test_parser_accepts_hide_legacy_mountpoints_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["--hide-legacy-mountpoints"])

    assert args.hide_legacy_mountpoints is True


def test_parser_accepts_docker_origin_tree_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["--docker-origin-tree", "tank/docker"])

    assert args.docker_origin_tree is True
    assert args.root == "tank/docker"


def test_configure_logging_writes_to_file(tmp_path: Path) -> None:
    log_file = tmp_path / "zfsdu.log"

    configure_logging("INFO", str(log_file))
    logging.getLogger("zfsdu.tests").info("hello log")

    assert log_file.exists()
    assert "hello log" in log_file.read_text(encoding="utf-8")

