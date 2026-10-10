"""Remove per-job archive directories that no longer have a ledger entry."""

from __future__ import annotations

import os
import shutil
import time
from datetime import timedelta
from pathlib import Path

from pydantic import BaseModel

MIN_ORPHAN_AGE = timedelta(days=1)


class SweepReport(BaseModel):
    directories_removed: int = 0
    bytes_freed: int = 0


class OrphanArchiveSweeper:
    """Deletes ``<prefix>*`` job directories whose job id is not in the ledger."""

    def __init__(
        self, root: Path, name_prefix: str, min_age: timedelta = MIN_ORPHAN_AGE
    ) -> None:
        self.root = root
        self.name_prefix = name_prefix
        self.min_age = min_age

    @staticmethod
    def _size(directory: Path) -> int:
        total = 0
        for current, _, files in os.walk(directory):
            for name in files:
                try:
                    total += (Path(current) / name).stat().st_size
                except OSError:
                    continue
        return total

    def sweep(self, known_ids: set[str]) -> SweepReport:
        report = SweepReport()
        if not self.root.is_dir():
            return report
        # The age guard keeps directories of jobs created after the id snapshot.
        cutoff = time.time() - self.min_age.total_seconds()
        with os.scandir(self.root) as entries:
            for entry in entries:
                if (
                    not entry.is_dir(follow_symlinks=False)
                    or not entry.name.startswith(self.name_prefix)
                    or entry.name in known_ids
                    or entry.stat().st_mtime > cutoff
                ):
                    continue
                report.bytes_freed += self._size(Path(entry.path))
                shutil.rmtree(entry.path, ignore_errors=True)
                report.directories_removed += 1
        return report
