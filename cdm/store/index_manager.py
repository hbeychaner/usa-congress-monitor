"""OpenSearch index lifecycle management.

Loads index definitions from ``documentation/opensearch_mappings.yaml`` and
provides helpers to create, update, or delete indices against a live cluster.

Typical usage
─────────────
    from cdm.store.index_manager import IndexManager

    mgr = IndexManager(client)
    mgr.create_all()           # create every index (skips existing)
    mgr.create("legislation")  # create one index
    mgr.update("legislation")  # PUT updated mapping onto existing index
    mgr.delete("legislation")  # ⚠ destructive – asks for confirmation
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from cdm.store.opensearch import index_name, write_alias

# Path relative to repo root; walks up from this file's location.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAPPINGS_YAML = _REPO_ROOT / "documentation" / "opensearch_mappings.yaml"

INDEX_PREFIX = "congress"


def _prefixed(name: str) -> str:
    """Return the full OpenSearch index name: ``congress-{name}``."""
    return index_name(name)


def load_definitions() -> dict[str, dict]:
    """Parse the mappings YAML and return ``{name: {settings, mappings}}`` dict.

    Top-level YAML keys that start with ``#`` (comments) or are clearly not
    index definitions are silently ignored.
    """
    raw = yaml.safe_load(_MAPPINGS_YAML.read_text())
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


class IndexManager:
    """Manages OpenSearch index lifecycle against a live cluster.

    Parameters
    ----------
    client:
        An ``elasticsearch.Elasticsearch`` client instance pointed at the
        OpenSearch cluster (OpenSearch is compatible with the ES 8 client via
        the ``compatibility_mode`` header).
    dry_run:
        When ``True``, log what *would* happen but make no API calls.
    """

    def __init__(self, client: Any, *, dry_run: bool = False) -> None:
        self.client = client
        self.dry_run = dry_run
        self._defs: dict[str, dict] | None = None

    # ── definition loading ────────────────────────────────────────────────

    @property
    def definitions(self) -> dict[str, dict]:
        if self._defs is None:
            self._defs = load_definitions()
        return self._defs

    def index_names(self) -> list[str]:
        """Return logical index names (without prefix) defined in the YAML."""
        return list(self.definitions.keys())

    # ── individual index operations ───────────────────────────────────────

    def create(self, name: str, *, exists_ok: bool = True) -> None:
        """Create the index *name* with its settings and mappings.

        Parameters
        ----------
        name:
            Logical index name as defined in the YAML (e.g. ``"legislation"``).
        exists_ok:
            If ``True`` (default), silently skip already-existing indices.
        """
        idx = _prefixed(name)
        defn = self.definitions[name]

        if self.dry_run:
            print(f"[dry-run] would create index {idx!r}")
            return

        if self.client.indices.exists(index=idx):
            if exists_ok:
                self.ensure_write_alias(name)
                return
            raise RuntimeError(f"Index {idx!r} already exists.")

        body: dict = {}
        if "settings" in defn:
            body["settings"] = defn["settings"]
        if "mappings" in defn:
            body["mappings"] = defn["mappings"]

        self.client.indices.create(index=idx, body=body)
        self.ensure_write_alias(name)
        print(f"  created {idx}")

    def ensure_write_alias(self, name: str) -> None:
        """Ensure the bulk-write alias points at the logical index."""
        idx = _prefixed(name)
        if self.dry_run:
            print(f"[dry-run] would point {write_alias(name)!r} to {idx!r}")
            return
        self.client.indices.put_alias(index=idx, name=write_alias(name))

    def update(self, name: str) -> None:
        """Push an updated mapping onto an existing index *name*.

        Settings (shards/replicas) are not changed; only ``mappings`` is sent.
        Use this after adding new fields to the YAML.
        """
        idx = _prefixed(name)
        defn = self.definitions[name]

        if "mappings" not in defn:
            print(f"  no mappings to update for {idx}")
            return

        if self.dry_run:
            print(f"[dry-run] would update mappings on {idx!r}")
            return

        self.client.indices.put_mapping(index=idx, body=defn["mappings"])
        print(f"  updated {idx}")

    def delete(self, name: str, *, confirm: bool = False) -> None:
        """Delete index *name*.  Requires ``confirm=True`` to prevent accidents."""
        if not confirm:
            raise ValueError(
                f"Pass confirm=True to delete index {_prefixed(name)!r}. "
                "This is destructive and cannot be undone."
            )
        idx = _prefixed(name)
        if self.dry_run:
            print(f"[dry-run] would delete index {idx!r}")
            return
        self.client.indices.delete(index=idx, ignore_unavailable=True)
        print(f"  deleted {idx}")

    # ── bulk operations ───────────────────────────────────────────────────

    def create_all(self, *, exists_ok: bool = True) -> None:
        """Create every index defined in the YAML (skips existing by default)."""
        for name in self.index_names():
            self.create(name, exists_ok=exists_ok)

    def update_all(self) -> None:
        """Push updated mappings onto every existing index."""
        for name in self.index_names():
            self.update(name)

    # ── status helpers ────────────────────────────────────────────────────

    def status(self) -> list[dict]:
        """Return a list of ``{name, full_name, exists, doc_count}`` dicts."""
        rows = []
        for name in self.index_names():
            idx = _prefixed(name)
            exists = bool(self.client.indices.exists(index=idx))
            doc_count = 0
            if exists:
                stats = self.client.indices.stats(index=idx)
                doc_count = (
                    stats.get("indices", {})
                    .get(idx, {})
                    .get("total", {})
                    .get("docs", {})
                    .get("count", 0)
                )
            rows.append(
                {
                    "name": name,
                    "full_name": idx,
                    "exists": exists,
                    "doc_count": doc_count,
                }
            )
        return rows
