"""Scan and optionally fix progress chunks with empty or invalid `meta`.

Usage:
  python tools/fix_invalid_meta_chunks.py        # report only
  python tools/fix_invalid_meta_chunks.py --fix  # attempt to auto-fix
  python tools/fix_invalid_meta_chunks.py --fix --yes  # auto-fix without prompt

The script uses `settings.py` for ES connection and the repository SPECS to
interpret expected meta fields. Fixing is conservative and only fills meta
when it can be reasonably inferred from the `chunk_key` (date ranges,
congress:chamber pairs, single-number keys for congress/year).
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
from typing import Any

from knowledgebase.client import build_client
from knowledgebase.progress import TRACKING_INDEX
from settings import ELASTIC_API_URL, ELASTIC_API_KEY

from src.data_collection.queueing.specs import SPECS
from src.data_collection.queueing.rabbitmq import parse_date_chunk_key


def _has_valid_meta(m: Any) -> bool:
    if not isinstance(m, dict):
        return False
    return any(v is not None for v in m.values())


def _infer_meta_from_chunk(endpoint: str, chunk_key: str) -> dict:
    """Conservative meta inference from chunk_key for common patterns."""
    meta: dict = {}
    if not chunk_key:
        return meta
    # Date-range window format: '<iso>Z:<iso>Z' (we rely on parse_date_chunk_key)
    if ":" in chunk_key and chunk_key.count(":") >= 2:
        # likely an ISO timestamp pair containing colons
        try:
            date_meta = parse_date_chunk_key(chunk_key)
            meta.update(date_meta)
            return meta
        except Exception:
            pass
    # Simple 'congress' (numeric) or 'year'
    if chunk_key.isdigit():
        # guess congress/year
        meta["congress"] = int(chunk_key)
        return meta
    # 'congress:chamber' or 'congress:type' or 'congress:session'
    if ":" in chunk_key:
        left, right = chunk_key.split(":", 1)
        # try parse left as int (congress)
        if left.isdigit():
            meta["congress"] = int(left)
            # heuristics for right value name
            # store right under one of likely fields if matches known values
            if right in ("house", "senate"):
                meta["chamber"] = right
            elif right.isdigit():
                meta["session"] = int(right)
            else:
                # default to 'type' or 'report_type'
                meta["type"] = right
            return meta
    return meta


async def main(fix: bool, assume_yes: bool) -> None:
    es = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    # Query all docs (up to 10000)
    resp = await es.search(index=TRACKING_INDEX, query={"match_all": {}}, size=10000)
    hits = resp.get("hits", {}).get("hits", [])
    bad = []
    for hit in hits:
        src = hit.get("_source", {})
        endpoint = src.get("endpoint")
        chunk_key = src.get("chunk_key")
        meta = src.get("meta")
        if _has_valid_meta(meta):
            # still check whether required fields per spec are missing
            spec = SPECS.get(endpoint)
            if spec:
                missing = [
                    f
                    for f in spec.meta_fields
                    if f not in (meta or {}) or (meta or {}).get(f) is None
                ]
                if missing:
                    bad.append((hit, "missing_required_fields", missing))
            continue
        # invalid/empty meta
        bad.append((hit, "invalid_meta", None))

    if not bad:
        print("No chunks with invalid or missing meta found.")
        await es.close()
        return

    print(f"Found {len(bad)} chunks with invalid/missing meta:")
    for hit, reason, extra in bad:
        src = hit.get("_source", {})
        endpoint = src.get("endpoint")
        chunk_key = src.get("chunk_key")
        print(f"- {endpoint}:{chunk_key} -> {reason} {extra or ''}")

    if not fix:
        print("Run this script with --fix to attempt conservative auto-fixes.")
        await es.close()
        return

    if not assume_yes:
        ans = input("Proceed with auto-fixing the above chunks? [y/N]: ")
        if ans.lower() not in ("y", "yes"):
            print("Aborting.")
            await es.close()
            return

    # Attempt fixes
    for hit, reason, extra in bad:
        doc_id = hit.get("_id")
        src = hit.get("_source", {})
        endpoint = src.get("endpoint")
        chunk_key = src.get("chunk_key")
        status = src.get("status")
        meta = src.get("meta") or {}
        inferred = _infer_meta_from_chunk(endpoint, chunk_key)
        if not inferred:
            print(f"Could not infer meta for {endpoint}:{chunk_key}; skipping.")
            continue
        # Only include fields expected by spec
        spec = SPECS.get(endpoint)
        if spec:
            allowed = set(spec.meta_fields)
            new_meta = {k: v for k, v in inferred.items() if k in allowed}
        else:
            new_meta = inferred
        # merge existing meta values if present
        merged = dict(meta or {})
        merged.update(new_meta)
        # Upsert doc
        body = {
            "endpoint": endpoint,
            "chunk_key": chunk_key,
            "status": status or "pending",
            "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "meta": merged,
        }
        await es.index(index=TRACKING_INDEX, id=doc_id, document=body)
        print(f"Patched meta for {endpoint}:{chunk_key} -> {new_meta}")

    await es.close()
    print("Auto-fix complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fix", action="store_true", help="Attempt conservative auto-fixes"
    )
    parser.add_argument("--yes", action="store_true", help="Assume yes for fixes")
    args = parser.parse_args()
    asyncio.run(main(args.fix, args.yes))
