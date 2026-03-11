from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


def _normalize_segment(seg: str) -> str:
    if seg.isdigit():
        return seg
    return seg.strip().lower()


def parse_url_to_id(url: str) -> str:
    """Turn an API URL into a deterministic id like 'bill:110:hconres:10'.

    Strips query params and scheme, removes leading API version segments
    like 'v3', and returns resource:parts... with segments normalized.
    """
    if not url:
        return "url:"
    p = urlparse(url)
    path = p.path or ""
    # split and drop empty
    parts = [seg for seg in path.split("/") if seg]
    # drop a leading API version token like 'v3'
    if parts and parts[0].lower().startswith("v") and parts[0][1:].isdigit():
        parts = parts[1:]
    if not parts:
        return f"url:{p.netloc}"
    resource = parts[0].lower()
    rest = parts[1:]
    norm_parts = [_normalize_segment(s) for s in rest]
    if norm_parts:
        return f"{resource}:{':'.join(norm_parts)}"
    return f"{resource}"


def canonical_id(record: Any) -> str:
    """Return a deterministic canonical id for a record.

    Precedence:
      1) explicit id fields (bioguide_id, id, identifier)
      2) composite keys (bill: congress+type+number)
      3) parsed URL fallback (resource:path segments)

    Accepts dicts or objects with attributes.
    """
    # handle pydantic BaseModel or dict-like
    mapping = None
    if hasattr(record, "model_dump"):
        try:
            mapping = record.model_dump()
        except Exception:
            mapping = None
    if mapping is None and isinstance(record, dict):
        mapping = record
    if mapping is None:
        # last resort: try vars()
        try:
            mapping = vars(record)
        except Exception:
            mapping = {}

    # 1) explicit id fields
    for key in ("bioguide_id", "bioguide", "id", "identifier", "guid"):
        val = mapping.get(key) if isinstance(mapping, dict) else None
        if val:
            # people ids use person: prefix
            if key.startswith("bioguide"):
                return f"person:{val}"
            return f"id:{val}"

    # 2) composite bill key
    if mapping.get("congress") and mapping.get("type") and mapping.get("number"):
        congress = str(mapping.get("congress"))
        bill_type = str(mapping.get("type")).lower()
        number = str(mapping.get("number"))
        return f"bill:{congress}:{bill_type}:{number}"

    # amendments may be indicated by 'amendmentNumber' or path
    if mapping.get("congress") and mapping.get("number") and mapping.get("purpose"):
        # best-effort amendment id
        congress = str(mapping.get("congress"))
        a_type = str(mapping.get("type", "amendment")).lower()
        number = str(mapping.get("number"))
        return f"amendment:{congress}:{a_type}:{number}"

    # 3) url-based fallback
    url = (
        mapping.get("url")
        if isinstance(mapping, dict)
        else getattr(record, "url", None)
    )
    if url:
        try:
            return parse_url_to_id(str(url))
        except Exception:
            pass

    # ultimate fallback: stringified mapping hash
    return f"record:{abs(hash(str(mapping))) % (10**12)}"
