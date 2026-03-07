"""Validate that a single page response from each SPECS endpoint coerces into the declared response model.

This script makes one API call per spec (safe defaults for meta: congress=117, year=2023, type='HR', chamber='house', report_type='hrpt', session=2)
and attempts to validate the returned JSON using the spec.response_model when present.

Run: python tools/validate_responses.py
"""

from __future__ import annotations

import sys
import traceback
from typing import Any

from src.data_collection.queueing import specs
from src.data_collection.client import client

# sensible defaults for meta fields
DEFAULT_META = {
    "congress": 117,
    "year": 2023,
    "type": "HR",
    "chamber": "house",
    "report_type": "hrpt",
    "session": 2,
}

FAILS = []

for key, spec in specs.SPECS.items():
    print(f"\n=== Testing endpoint: {key} ({spec.endpoint}) ===")
    # build meta based on declared meta_fields
    meta = {}
    for f in spec.meta_fields:
        if f in DEFAULT_META:
            meta[f] = DEFAULT_META[f]
        else:
            # set pagination defaults
            if f == "offset":
                meta["offset"] = 0
            if f == "page":
                meta["page"] = 1
            if f == "page_size":
                meta["page_size"] = 1
            if f == "total_pages":
                meta["total_pages"] = 1
    # Special-case: congress endpoint wants offset==congress when limit==1
    offset = 0
    limit = 1
    if spec.endpoint == "congress":
        offset = int(meta.get("congress", 117))
        limit = 1
        api_meta = None
    else:
        offset = int(meta.get("offset", 0))
        limit = int(meta.get("limit", 1) or 1)
        api_meta = meta

    try:
        if spec.endpoint == "law":
            # fetch_law_page requires congress param
            raw = specs.fetch_law_page(client, congress=int(meta.get("congress", 117)), offset=offset, limit=limit)
        else:
            raw = specs.fetch_page(spec.endpoint, client, offset=offset, limit=limit, meta=api_meta)
    except Exception as e:
        print(f"Failed to fetch {spec.endpoint}: {e}")
        traceback.print_exc()
        FAILS.append((key, f"fetch_error: {e}"))
        continue

    # quick structural checks
    if not isinstance(raw, dict):
        print(f"Response for {key} is not a dict: {type(raw)}")
        FAILS.append((key, "not_dict"))
        continue

    # verify api_data_key exists
    api_key = spec.api_data_key
    if api_key not in raw:
        print(f"Response missing api_data_key '{api_key}'. Keys: {list(raw.keys())}")
        FAILS.append((key, "missing_api_data_key"))
        continue

    items = raw.get(api_key)
    if not isinstance(items, list):
        print(f"Data under '{api_key}' is not a list (type={type(items)}).")
        FAILS.append((key, "data_not_list"))
        # continue trying to coerce anyway

    # Try to coerce using response_model when available
    if spec.response_model is not None:
        try:
            model_inst = spec.response_model.model_validate(raw)
            print(f"Coercion into {spec.response_model.__name__} succeeded.")
        except Exception as e:
            print(f"Coercion into {spec.response_model.__name__} FAILED: {e}")
            traceback.print_exc()
            FAILS.append((key, f"coercion_error: {e}"))
            continue
    else:
        print("No response_model declared; skipping model coercion.")

    # If we had items and an id_func, attempt to call id_func on first item
    try:
        if isinstance(items, list) and len(items) > 0 and spec.id_func:
            try:
                _id = spec.id_func(items[0])
            except Exception:
                # id_func may expect dict with different shapes; try forcing dict()
                _id = spec.id_func(dict(items[0]) if hasattr(items[0], "items") else items[0])
            print(f"id_func produced id: {_id}")
    except Exception as e:
        print(f"id_func failed for {key}: {e}")
        traceback.print_exc()
        FAILS.append((key, f"id_func_error: {e}"))

if FAILS:
    print("\nSUMMARY: Some endpoints failed validation:")
    for k, reason in FAILS:
        print(f" - {k}: {reason}")
    sys.exit(2)

print("\nSUMMARY: All endpoints validated successfully.")
sys.exit(0)
