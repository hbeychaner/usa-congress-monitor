"""Durable append-only archives for fetched ingest records."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


class JsonlRecordArchive:
    """Write fetched records to per-resource JSONL files as they arrive."""

    def __init__(self, root: Path, attempt: int) -> None:
        self.root = root
        self.attempt = attempt
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()

    def write(self, resource: str, record: dict[str, Any]) -> None:
        with self._locks_guard:
            lock = self._locks.setdefault(resource, threading.Lock())
        path = self.root / resource / f"records-attempt-{self.attempt}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=True, separators=(",", ":")) + "\n"
        with lock, path.open("a", encoding="utf-8", buffering=1) as archive:
            archive.write(line)
            archive.flush()
            os.fsync(archive.fileno())
