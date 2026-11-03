from __future__ import annotations

import os
import time
from pathlib import Path

from cdm.utils.archive_sweeper import OrphanArchiveSweeper


def _make_dir(
    root: Path, name: str, *, age_days: float = 0, payload: bytes = b"x" * 10
) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "file.xml").write_bytes(payload)
    stamp = time.time() - age_days * 86400
    os.utime(directory, (stamp, stamp))
    return directory


def test_sweeper_removes_only_old_unknown_prefixed_dirs(tmp_path: Path) -> None:
    prefix = "govinfo_bulk:"
    known = _make_dir(tmp_path, f"{prefix}known", age_days=5)
    orphan = _make_dir(tmp_path, f"{prefix}orphan", age_days=5, payload=b"y" * 100)
    fresh = _make_dir(tmp_path, f"{prefix}fresh", age_days=0)
    other = _make_dir(tmp_path, "unrelated", age_days=5)
    (tmp_path / "coverage-report.json").write_text("{}")

    report = OrphanArchiveSweeper(tmp_path, prefix).sweep({known.name})

    assert report.directories_removed == 1
    assert report.bytes_freed == 100
    assert not orphan.exists()
    assert known.exists() and fresh.exists() and other.exists()
    assert (tmp_path / "coverage-report.json").exists()


def test_sweeper_missing_root_is_noop(tmp_path: Path) -> None:
    report = OrphanArchiveSweeper(tmp_path / "absent", "govinfo_bulk:").sweep(set())
    assert report.directories_removed == 0
