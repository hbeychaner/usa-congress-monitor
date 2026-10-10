"""Remove superseded topic-model artifacts after a successful retrain."""

from __future__ import annotations

import shutil
import time
from datetime import timedelta
from pathlib import Path

from elasticsearch import Elasticsearch
from pydantic import BaseModel, Field

from cdm.store.embedding_store import EmbeddingStore
from cdm.utils.archive_sweeper import MIN_ORPHAN_AGE

KEEP_MODEL_VERSIONS = 2


class CleanupReport(BaseModel):
    stale_versions: list[str] = Field(default_factory=list)
    model_dirs_removed: int = 0
    embeddings_removed: int = 0
    bytes_freed: int = 0

    def summary(self) -> str:
        return (
            f"removed {len(self.stale_versions)} old model versions, "
            f"{self.model_dirs_removed} model dirs, "
            f"{self.embeddings_removed} stale embeddings, "
            f"{self.bytes_freed / 1e6:.0f} MB"
        )


class RetrainCleanup:
    """Keeps the newest indexed model versions and deletes everything older."""

    def __init__(
        self,
        client: Elasticsearch,
        analysis_index: str,
        model_dir: Path,
        keep_versions: int = KEEP_MODEL_VERSIONS,
        min_orphan_age: timedelta = MIN_ORPHAN_AGE,
        embedding_store: EmbeddingStore | None = None,
        live_doc_ids: set[str] | None = None,
    ) -> None:
        self.client = client
        self.analysis_index = analysis_index
        self.model_dir = model_dir
        self.keep_versions = keep_versions
        self.min_orphan_age = min_orphan_age
        self.embedding_store = embedding_store
        self.live_doc_ids = live_doc_ids

    def _indexed_versions(self) -> list[str]:
        response = self.client.search(
            index=self.analysis_index,
            size=0,
            aggs={"v": {"terms": {"field": "model_version", "size": 100}}},
        )
        return sorted(
            (bucket["key"] for bucket in response["aggregations"]["v"]["buckets"]),
            reverse=True,
        )

    @staticmethod
    def _size(directory: Path) -> int:
        return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())

    def _remove_dir(self, directory: Path, report: CleanupReport) -> None:
        report.bytes_freed += self._size(directory)
        shutil.rmtree(directory, ignore_errors=True)
        report.model_dirs_removed += 1

    def run(self) -> CleanupReport:
        report = CleanupReport()
        if self.embedding_store is not None and self.live_doc_ids is not None:
            pruned = self.embedding_store.prune(self.live_doc_ids)
            report.embeddings_removed = pruned.deleted
        indexed = self._indexed_versions()
        report.stale_versions = indexed[self.keep_versions :]
        if report.stale_versions:
            self.client.delete_by_query(
                index=self.analysis_index,
                query={"terms": {"model_version": report.stale_versions}},
                conflicts="proceed",
                wait_for_completion=False,
            )
        kept = set(indexed[: self.keep_versions])
        if not self.model_dir.is_dir():
            return report
        cutoff = time.time() - self.min_orphan_age.total_seconds()
        for directory in self.model_dir.iterdir():
            if not directory.is_dir() or directory.name in kept:
                continue
            # Unindexed dirs may belong to a run still in progress; only reap old ones.
            if directory.name not in indexed and directory.stat().st_mtime > cutoff:
                continue
            self._remove_dir(directory, report)
        return report
