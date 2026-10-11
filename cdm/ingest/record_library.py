"""Durable per-label record archives that survive job retention."""

from __future__ import annotations

from pathlib import Path

from cdm.ingest.archive import LatestRecordArchive


class RecordLibrary:
    """Archives outside the job directories, so retention never prunes them."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def archive(self, label: str) -> LatestRecordArchive:
        return LatestRecordArchive(self._root / label, 0)
