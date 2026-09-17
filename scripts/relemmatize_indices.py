"""Recompute ``*_lemma`` fields for already-indexed documents.

The lemmatizer now drops stop words, so lemma values written by older code are
stale. This script scans each index that declares lemma fields, recomputes the
``{field}_lemma`` siblings from the raw text, and bulk-updates only documents
whose lemmas changed.

Usage:
    uv run python scripts/relemmatize_indices.py --dry-run
    uv run python scripts/relemmatize_indices.py
    uv run python scripts/relemmatize_indices.py --indices legislation
"""

from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cdm.store.client import get_opensearch_client
from cdm.store.index_manager import lemma_field_paths, load_definitions
from cdm.store.indexer import _apply_lemmas
from cdm.store.opensearch import read_alias


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--indices",
        nargs="*",
        help="Index definition names to process (default: all with lemma fields)",
    )
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument(
        "--max-docs", type=int, help="Stop after scanning this many docs per index"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many documents would change without writing",
    )
    return parser.parse_args()


def lemma_indices() -> list[str]:
    return [name for name in load_definitions() if lemma_field_paths(name)]


def _root_fields(name: str) -> list[str]:
    return sorted({path[0] for path in lemma_field_paths(name)})


def _changed_roots(name: str, before: dict, after: dict) -> list[str]:
    """Top-level keys whose value changed, including ``{root}_lemma`` siblings."""
    candidates: list[str] = []
    for root in _root_fields(name):
        candidates.extend((root, f"{root}_lemma"))
    return [key for key in candidates if before.get(key) != after.get(key)]


def process_index(
    client, name: str, *, batch_size: int, dry_run: bool, max_docs: int | None = None
) -> tuple[int, int]:
    """Return (scanned, updated) counts for index definition *name*."""
    from elasticsearch.helpers import bulk, scan

    index = read_alias(name)
    roots = _root_fields(name)
    source_fields = roots + [f"{root}*" for root in roots]
    scanned = updated = 0
    actions: list[dict] = []

    def flush() -> int:
        nonlocal actions
        if not actions or dry_run:
            count = len(actions)
            actions = []
            return count
        success, _ = bulk(client, actions, raise_on_error=True)
        actions = []
        return success

    for hit in scan(
        client,
        index=index,
        query={"query": {"match_all": {}}, "_source": source_fields},
    ):
        if max_docs is not None and scanned >= max_docs:
            break
        scanned += 1
        source = hit.get("_source") or {}
        before = deepcopy(source)
        _apply_lemmas(source, name)
        changed = _changed_roots(name, before, source)
        if not changed:
            continue
        updated += 1
        actions.append(
            {
                "_op_type": "update",
                "_index": hit["_index"],
                "_id": hit["_id"],
                "retry_on_conflict": 3,
                "doc": {key: source.get(key) for key in changed},
            }
        )
        if len(actions) >= batch_size:
            flush()
        if scanned % 10_000 == 0:
            print(f"  {name}: scanned={scanned} updated={updated}", flush=True)
    flush()
    return scanned, updated


def main() -> int:
    args = parse_args()
    names = args.indices or lemma_indices()
    unknown = [name for name in names if not lemma_field_paths(name)]
    if unknown:
        print(f"no lemma fields defined for: {', '.join(unknown)}", file=sys.stderr)
        return 1
    client = get_opensearch_client()
    for name in names:
        print(f"{name}: paths={['.'.join(p) for p in lemma_field_paths(name)]}")
        scanned, updated = process_index(
            client,
            name,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
            max_docs=args.max_docs,
        )
        verb = "would update" if args.dry_run else "updated"
        print(f"{name}: scanned={scanned} {verb}={updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
