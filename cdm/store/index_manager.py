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

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from elasticsearch import NotFoundError

from cdm.store.opensearch import index_name, read_alias, write_alias

# Path relative to repo root; walks up from this file's location.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAPPINGS_YAML = _REPO_ROOT / "documentation" / "opensearch_mappings.yaml"

INDEX_PREFIX = "congress"
MAPPING_VERSION = "2026-09-01.1"


def _prefixed(name: str) -> str:
    """Return the full OpenSearch index name: ``congress-{name}``."""
    return index_name(name)


@lru_cache(maxsize=1)
def load_definitions() -> dict[str, dict]:
    """Parse the mappings YAML and return ``{name: {settings, mappings}}`` dict.

    Top-level YAML keys that start with ``#`` (comments) or are clearly not
    index definitions are silently ignored. Cached because callers such as
    per-document mapping validation invoke this on every indexed record.
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

    @staticmethod
    def _versioned_mapping(definition: dict) -> dict:
        versioned = deepcopy(definition)
        mappings = versioned.setdefault("mappings", {})
        metadata = mappings.setdefault("_meta", {})
        metadata["mapping_version"] = MAPPING_VERSION
        return versioned

    @staticmethod
    def _normalize_mapping(value: Any) -> Any:
        if isinstance(value, dict):
            normalized = {
                key: IndexManager._normalize_mapping(item)
                for key, item in value.items()
            }
            if normalized.get("type") == "object" and "properties" in normalized:
                normalized.pop("type")
            return normalized
        if isinstance(value, list):
            return [IndexManager._normalize_mapping(item) for item in value]
        if value in {True, False}:
            return str(value).lower()
        return value

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
                self.ensure_aliases(name)
                return
            raise RuntimeError(f"Index {idx!r} already exists.")

        versioned = self._versioned_mapping(defn)
        body: dict = {
            key: versioned[key]
            for key in ("settings", "mappings")
            if key in versioned
        }

        self.client.indices.create(index=idx, body=body)
        self.ensure_aliases(name)
        print(f"  created {idx}")

    def create_versioned(self, name: str, version: int = 2) -> str:
        """Create a versioned staging index without changing live aliases."""
        if name not in self.definitions:
            raise KeyError(f"Unknown index definition: {name}")
        if version < 1:
            raise ValueError("Index version must be positive")

        idx = f"{_prefixed(name)}-v{version}"
        defn = self.definitions[name]
        versioned = self._versioned_mapping(defn)
        body = {
            key: versioned[key]
            for key in ("settings", "mappings")
            if key in versioned
        }
        if self.dry_run:
            print(f"[dry-run] would create staging index {idx!r}")
            return idx
        if self.client.indices.exists(index=idx):
            return idx
        self.client.indices.create(index=idx, body=body)
        print(f"  created staging index {idx}")
        return idx

    def reindex_to_versioned(self, name: str, version: int = 2) -> dict:
        """Copy a live index into versioned staging using OpenSearch reindex."""
        if name not in self.definitions:
            raise KeyError(f"Unknown index definition: {name}")
        if version < 1:
            raise ValueError("Index version must be positive")

        source = _prefixed(name)
        target = f"{source}-v{version}"
        if self.dry_run:
            print(f"[dry-run] would reindex {source!r} into {target!r}")
            return {"source": source, "target": target, "dry_run": True}

        self.create_versioned(name, version)
        result = self.client.reindex(
            body={"source": {"index": source}, "dest": {"index": target}},
            wait_for_completion=True,
            refresh=True,
            requests_per_second=-1,
        )
        if result.get("failures"):
            raise RuntimeError(
                f"Reindex from {source!r} to {target!r} reported failures: "
                f"{result['failures'][:3]}"
            )
        print(f"  reindexed {source} -> {target} ({result.get('created', 0)} created)")
        return result

    def validate_versioned(self, name: str, version: int = 2) -> dict:
        """Validate a versioned index without changing the cluster."""
        if name not in self.definitions:
            raise KeyError(f"Unknown index definition: {name}")
        if version < 1:
            raise ValueError("Index version must be positive")

        source = _prefixed(name)
        target = f"{source}-v{version}"
        if not self.client.indices.exists(index=target):
            raise RuntimeError(f"Staging index {target!r} does not exist")

        metadata = self.client.indices.get(index=target).get(target, {})
        expected_mapping = self._versioned_mapping(self.definitions[name]).get(
            "mappings", {}
        )
        actual_mapping = metadata.get("mappings", {})
        normalized_mapping = self._normalize_mapping(actual_mapping)
        normalized_expected_mapping = self._normalize_mapping(expected_mapping)
        mapping_version = actual_mapping.get("_meta", {}).get("mapping_version")
        source_count = self.client.count(index=source).get("count", 0)
        target_count = self.client.count(index=target).get("count", 0)
        aliases = sorted(
            self.client.indices
            .get_alias(index=target)
            .get(target, {})
            .get("aliases", {})
        )
        sample = self.client.search(
            index=target,
            body={"size": 3, "query": {"match_all": {}}},
        )
        sample_ids = [hit.get("_id") for hit in sample.get("hits", {}).get("hits", [])]
        sample_id_mismatches = [
            hit.get("_id")
            for hit in sample.get("hits", {}).get("hits", [])
            if hit.get("_id") != hit.get("_source", {}).get("id")
        ]
        result = {
            "source": source,
            "target": target,
            "source_count": source_count,
            "target_count": target_count,
            "mapping_match": normalized_mapping == normalized_expected_mapping,
            "mapping_version": mapping_version,
            "aliases": aliases,
            "sample_ids": sample_ids,
            "sample_id_mismatches": sample_id_mismatches,
        }
        result["valid"] = (
            source_count == target_count
            and result["mapping_match"]
            and mapping_version == MAPPING_VERSION
            and not aliases
            and not sample_id_mismatches
        )
        return result

    def ensure_write_alias(self, name: str) -> None:
        """Ensure the bulk-write alias points at the logical index."""
        self._ensure_alias(name, write_alias(name))

    def ensure_read_alias(self, name: str) -> None:
        """Ensure the read alias points at the logical index."""
        self._ensure_alias(name, read_alias(name))

    def _ensure_alias(self, name: str, alias: str) -> None:
        idx = _prefixed(name)
        if self.dry_run:
            print(f"[dry-run] would point {alias!r} to {idx!r}")
            return
        try:
            current = self.client.indices.get_alias(name=alias)
        except NotFoundError:
            current = {}
        actions = [
            {"remove": {"index": current_index, "alias": alias}}
            for current_index in current
            if current_index != idx
        ]
        actions.append({"add": {"index": idx, "alias": alias}})
        self.client.indices.update_aliases(body={"actions": actions})

    def ensure_aliases(self, name: str) -> None:
        """Ensure both read and write aliases point at the logical index."""
        idx = _prefixed(name)
        aliases = (read_alias(name), write_alias(name))
        if self.dry_run:
            for alias in aliases:
                print(f"[dry-run] would point {alias!r} to {idx!r}")
            return
        actions = []
        for alias in aliases:
            try:
                current = self.client.indices.get_alias(name=alias)
            except NotFoundError:
                current = {}
            actions.extend(
                {"remove": {"index": current_index, "alias": alias}}
                for current_index in current
                if current_index != idx
            )
            actions.append({"add": {"index": idx, "alias": alias}})
        self.client.indices.update_aliases(body={"actions": actions})

    def switch_aliases_to_versioned(self, name: str, version: int = 2) -> dict:
        """Atomically move read and write aliases to a validated staging index."""
        result = self.validate_versioned(name, version)
        if not result["valid"]:
            raise RuntimeError(f"Staging validation failed: {result}")
        source = _prefixed(name)
        target = result["target"]
        actions = [
            {"remove": {"index": source, "alias": read_alias(name)}},
            {"remove": {"index": source, "alias": write_alias(name)}},
            {"add": {"index": target, "alias": read_alias(name)}},
            {"add": {"index": target, "alias": write_alias(name)}},
        ]
        if self.dry_run:
            print(f"[dry-run] would switch aliases from {source!r} to {target!r}")
            return {"source": source, "target": target, "actions": actions}
        self.client.indices.update_aliases(body={"actions": actions})
        return {"source": source, "target": target, "actions": actions}

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

        self.client.indices.put_mapping(
            index=idx,
            body=self._versioned_mapping(defn)["mappings"],
        )
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
                    stats
                    .get("indices", {})
                    .get(idx, {})
                    .get("total", {})
                    .get("docs", {})
                    .get("count", 0)
                )
            rows.append({
                "name": name,
                "full_name": idx,
                "exists": exists,
                "doc_count": doc_count,
            })
        return rows

    def audit(self) -> dict:
        """Inspect declared and physical indices without changing the cluster.

        The result is intended for migration review and deletion manifests. It
        includes declared targets, physical indices outside the mapping file,
        aliases, document counts, and live mappings.
        """
        declared = set(self.index_names())
        physical = self.client.indices.get(index=f"{INDEX_PREFIX}-*")
        aliases = self.client.indices.get_alias(index=f"{INDEX_PREFIX}-*")
        targets = []
        for name in self.index_names():
            idx = _prefixed(name)
            metadata = physical.get(idx, {})
            exists = idx in physical
            count = self.client.count(index=idx).get("count", 0) if exists else 0
            targets.append({
                "name": name,
                "full_name": idx,
                "exists": exists,
                "doc_count": count,
                "aliases": sorted(aliases.get(idx, {}).get("aliases", {})),
                "mapping": metadata.get("mappings", {}),
                "settings": metadata.get("settings", {}),
            })
        staging = sorted(
            name
            for name in physical
            if name.startswith(f"{INDEX_PREFIX}-")
            and name.rsplit("-v", 1)[-1].isdigit()
        )
        unexpected = sorted(
            set(physical) - {row["full_name"] for row in targets} - set(staging)
        )
        return {
            "declared_count": len(declared),
            "targets": targets,
            "staging_indices": staging,
            "unexpected_physical_indices": unexpected,
        }
