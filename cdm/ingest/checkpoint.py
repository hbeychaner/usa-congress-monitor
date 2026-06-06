"""Resumable checkpoint management for ingest runs.

Checkpoints are stored as JSON files. Each resource gets one file tracking
the last fully committed offset and item id so a run can resume without
re-fetching already-processed records.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


_DEFAULT_DIR = Path.home() / ".congress_tracker" / "checkpoints"


def _checkpoint_path(resource: str, checkpoint_dir: Optional[Path] = None) -> Path:
    d = checkpoint_dir or _DEFAULT_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{resource}.json"


def load(resource: str, checkpoint_dir: Optional[Path] = None) -> dict:
    """Load checkpoint for *resource*. Returns empty dict if not found."""
    p = _checkpoint_path(resource, checkpoint_dir)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {}


def save(resource: str, state: dict, checkpoint_dir: Optional[Path] = None) -> None:
    """Atomically write *state* as the checkpoint for *resource*."""
    p = _checkpoint_path(resource, checkpoint_dir)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    os.replace(tmp, p)


def clear(resource: str, checkpoint_dir: Optional[Path] = None) -> None:
    """Remove the checkpoint file for *resource*."""
    p = _checkpoint_path(resource, checkpoint_dir)
    p.unlink(missing_ok=True)
