"""Test meta -> API param inference and fetch a single page per spec.

For each spec this prints:
 - spec key
 - prepared API params (from `prepare_api_meta`)
 - chunk key (from `chunk_key_func`)
 - whether fetch_page returned the expected `api_data_key` and list

Run: python tools/test_meta_inference.py
"""
from __future__ import annotations

import sys
import traceback
from typing import Any

from src.data_collection.queueing import specs
from src.data_collection.client import client

DEFAULT_META = {
    "congress": 117,
    "year": 2023,
    "type": "HR",
    "chamber": "house",
    "report_type": "hrpt",
    "session": 2,
}

fails = []

for key, spec in specs.SPECS.items():
    print(f"\n--- {key} ---")
    # Build sample meta only with declared fields
    sample_meta = {}
    for f in spec.meta_fields:
        if f in DEFAULT_META:
            sample_meta[f] = DEFAULT_META[f]
        else:
            if f == "offset":
                sample_meta["offset"] = 0
            if f == "page":
                sample_meta["page"] = 1
            if f == "page_size":
                sample_meta["page_size"] = 1
            if f == "total_pages":
                sample_meta["total_pages"] = 1
    # Prepare api_meta
    api_meta, meta_obj, filtered_meta = specs.prepare_api_meta(spec, sample_meta)
    chunk_key = spec.chunk_key_func(sample_meta, None)
    print("prepared api_meta:", api_meta)
    print("filtered_meta:", filtered_meta)
    print("meta_obj:", type(meta_obj).__name__ if meta_obj else None)
    print("chunk_key:", chunk_key)

    # Determine offset/limit for fetch
    if spec.endpoint == "congress":
        offset = int(sample_meta.get("congress", 117))
        limit = 1
    else:
        offset = int(sample_meta.get("offset", 0))
        limit = 1

    try:
        if spec.endpoint == "law":
            raw = specs.fetch_law_page(client, congress=int(sample_meta.get("congress", 117)), offset=offset, limit=limit)
        else:
            raw = specs.fetch_page(spec.endpoint, client, offset=offset, limit=limit, meta=api_meta)
    except Exception as e:
        print("fetch failed:", e)
        traceback.print_exc()
        fails.append((key, f"fetch_error: {e}"))
        continue

    api_key = spec.api_data_key
    if not isinstance(raw, dict):
        print("fetch returned non-dict", type(raw))
        fails.append((key, "not_dict"))
        continue
    if api_key not in raw:
        print(f"missing api_data_key '{api_key}' in response; keys: {list(raw.keys())}")
        fails.append((key, "missing_api_data_key"))
        continue
    items = raw.get(api_key)
    print(f"fetched {len(items) if isinstance(items, list) else 'N/A'} items for key '{api_key}'")

if fails:
    print("\nFailures:")
    for k, r in fails:
        print(k, r)
    sys.exit(2)

print('\nAll meta->API inference tests passed.')
sys.exit(0)
