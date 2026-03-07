import pytest
import sys

from src.data_collection.queueing import specs
from src.data_collection.client import client as cdg_client


@pytest.mark.integration
def test_meta_inference_and_fetch():
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

        api_meta, meta_obj, filtered_meta = specs.prepare_api_meta(spec, sample_meta)
        chunk_key = spec.chunk_key_func(sample_meta, None)

        # Basic chunk_key checks
        assert isinstance(chunk_key, str) and chunk_key.strip(), (
            f"Empty chunk_key for spec {key}"
        )
        fmt = (spec.chunk_key_format or "").lower()
        # If format includes a separator, expect it in the generated key
        if ":" in fmt:
            assert ":" in chunk_key, f"Expected ':' in chunk_key for {key}: {chunk_key}"
        # endpoint-specific expectations
        if spec.endpoint == "congress":
            assert chunk_key == str(sample_meta.get("congress", "")), (
                f"Congress chunk_key mismatch for {key}: {chunk_key}"
            )
        if "year" in fmt:
            assert chunk_key == str(sample_meta.get("year", "")), (
                f"Year chunk_key mismatch for {key}: {chunk_key}"
            )
        if "type" in spec.meta_fields and sample_meta.get("type"):
            assert sample_meta.get("type").upper() in chunk_key.upper(), (
                f"Type missing from chunk_key for {key}: {chunk_key}"
            )
        if "chamber" in spec.meta_fields and sample_meta.get("chamber"):
            assert sample_meta.get("chamber").lower() in chunk_key.lower(), (
                f"Chamber missing from chunk_key for {key}: {chunk_key}"
            )

        # Determine offset/limit
        if spec.endpoint == "congress":
            offset = int(sample_meta.get("congress", 117))
            limit = 1
        else:
            offset = int(sample_meta.get("offset", 0))
            limit = 1

        try:
            if spec.endpoint == "law":
                raw = specs.fetch_law_page(
                    cdg_client,
                    congress=int(sample_meta.get("congress", 117)),
                    offset=offset,
                    limit=limit,
                )
            else:
                raw = specs.fetch_page(
                    spec.endpoint, cdg_client, offset=offset, limit=limit, meta=api_meta
                )
        except Exception as e:
            fails.append((key, f"fetch_error: {e}"))
            continue

        api_key = spec.api_data_key
        if not isinstance(raw, dict) or api_key not in raw:
            fails.append((key, "missing_api_data_key_or_not_dict"))
            continue

        items = raw.get(api_key)
        # verify id_func works for the first item when present
        if isinstance(items, list) and len(items) > 0 and spec.id_func:
            first = items[0]
            # Some endpoints (e.g., congress) nest the domain object inside a wrapper
            if isinstance(first, dict) and "congress" in first and key == "congress":
                candidate = first.get("congress")
            else:
                candidate = first
            try:
                _id = spec.id_func(candidate)
            except Exception:
                _id = spec.id_func(dict(candidate) if hasattr(candidate, "items") else candidate)
            assert _id, f"id_func returned empty id for spec {key}"

        print(
            f"fetched {len(items) if isinstance(items, list) else 'N/A'} items for key '{api_key}'"
        )

    assert not fails, f"Meta inference failures: {fails}"
