"""Central consumer core: fetch + parse helpers for queue consumers.

Design:
- Provide a single synchronous `fetch_and_parse` helper that can be called
  from async consumers via `asyncio.to_thread` to avoid blocking the event loop.
- Keep logic simple: call `fetch_page` (from specs), coerce via Pydantic
  `spec.response_model` when available, and always return plain `dict` records.
"""

from __future__ import annotations

from typing import Any, List, Tuple

from pydantic import BaseModel

from src.data_collection.queueing.specs import fetch_page


def _coerce_record(item: Any) -> dict:
    # If item is a Pydantic model, convert to dict; otherwise assume it's a dict
    try:
        if isinstance(item, BaseModel):
            return item.model_dump()
    except Exception:
        pass
    return dict(item) if isinstance(item, dict) else {"value": item}


def parse_response(spec, raw_resp: dict) -> List[dict]:
    """Coerce API response to a list of plain dict records according to spec.

    - If `spec.response_model` is present, attempt to `model_validate` the whole
      response and extract the `spec.api_data_key` attribute.
    - Otherwise, read the list from `raw_resp[spec.api_data_key]`.
    - Ensure returned records are plain `dict` objects.
    """
    if spec.response_model is not None:
        try:
            parsed = spec.response_model.model_validate(raw_resp)
            # The response_model may expose the list as an attribute
            records = getattr(parsed, spec.api_data_key, None)
            if records is None:
                # Try model_dump to find key
                dumped = parsed.model_dump()
                records = dumped.get(spec.api_data_key, [])
        except Exception:
            records = raw_resp.get(spec.api_data_key, []) or []
    else:
        records = raw_resp.get(spec.api_data_key, []) or []

    coerced = []
    for r in records:
        coerced.append(_coerce_record(r))
    return coerced


def fetch_and_parse(
    target: str, client: Any, offset: int, limit: int, meta: dict | None, spec
) -> Tuple[dict, List[dict]]:
    """Fetch a page using `fetch_page` and return (raw_response, records).

    This is synchronous and safe to call inside `asyncio.to_thread`.
    """
    # Import here to avoid circular imports at module import time

    raw = fetch_page(target, client, offset=offset, limit=limit, meta=meta)
    records = parse_response(spec, raw)
    return raw, records
