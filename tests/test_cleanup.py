from __future__ import annotations

import os
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

from cdm.utils.archive_sweeper import OrphanArchiveSweeper
from cdm.utils.retrain_cleanup import RetrainCleanup

PREFIX = "govinfo_bulk:"


def _make_dir(root: Path, name: str, *, age_days: float = 0, payload: bytes = b"x" * 10) -> Path:
    directory = root / name
    directory.mkdir(parents=True)
    (directory / "file.xml").write_bytes(payload)
    stamp = time.time() - age_days * 86400
    os.utime(directory, (stamp, stamp))
    return directory


def test_sweeper_removes_only_old_unknown_prefixed_dirs(tmp_path: Path) -> None:
    known = _make_dir(tmp_path, f"{PREFIX}known", age_days=5)
    orphan = _make_dir(tmp_path, f"{PREFIX}orphan", age_days=5, payload=b"y" * 100)
    fresh = _make_dir(tmp_path, f"{PREFIX}fresh", age_days=0)
    other = _make_dir(tmp_path, "unrelated", age_days=5)
    (tmp_path / "coverage-report.json").write_text("{}")

    report = OrphanArchiveSweeper(tmp_path, PREFIX).sweep({known.name})

    assert report.directories_removed == 1
    assert report.bytes_freed == 100
    assert not orphan.exists()
    assert known.exists() and fresh.exists() and other.exists()
    assert (tmp_path / "coverage-report.json").exists()


def test_sweeper_missing_root_is_noop(tmp_path: Path) -> None:
    report = OrphanArchiveSweeper(tmp_path / "absent", PREFIX).sweep(set())
    assert report.directories_removed == 0


class FakeClient:
    def __init__(self, versions: list[str]) -> None:
        self.versions = versions
        self.deleted: list[str] = []

    def search(self, **_: Any) -> dict[str, Any]:
        buckets = [{"key": version} for version in self.versions]
        return {"aggregations": {"v": {"buckets": buckets}}}

    def delete_by_query(self, *, query: dict[str, Any], **_: Any) -> None:
        self.deleted = query["terms"]["model_version"]


def test_retrain_cleanup_keeps_newest_indexed_versions(tmp_path: Path) -> None:
    for name in ("v1", "v2", "v3"):
        _make_dir(tmp_path, name, age_days=1)
    stray_old = _make_dir(tmp_path, "stray-old", age_days=3)
    stray_new = _make_dir(tmp_path, "stray-new", age_days=0)

    client = FakeClient(["v3", "v2", "v1"])
    report = RetrainCleanup(client, "analysis", tmp_path, keep_versions=2).run()

    assert client.deleted == ["v1"]
    assert report.stale_versions == ["v1"]
    assert not (tmp_path / "v1").exists()
    assert not stray_old.exists()
    assert (tmp_path / "v2").exists() and (tmp_path / "v3").exists()
    assert stray_new.exists()
    assert report.model_dirs_removed == 2
    assert isinstance(report.bytes_freed, int)
    assert report.summary()


def test_retrain_cleanup_without_stale_versions_skips_delete(tmp_path: Path) -> None:
    client = FakeClient(["v1"])
    RetrainCleanup(client, "analysis", tmp_path, min_orphan_age=timedelta(days=1)).run()
    assert client.deleted == []
