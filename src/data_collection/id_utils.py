"""Utilities for building deterministic canonical record identifiers.

This module provides helpers to parse Congress.gov API URLs into
stable ids and to derive a canonical identifier for various record
structures (Pydantic models, mappings, or arbitrary objects).
"""

from __future__ import annotations

from typing import Mapping, TypeAlias
from pydantic import BaseModel
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

# JSON-like alias used for mapping values in canonical id builders.
Json: TypeAlias = Mapping[str, object] | str | int | float | bool | None


def _normalize_segment(seg: str) -> str:
    """Normalize a path segment for use in canonical ids.

    Numeric segments are returned unchanged. Non-numeric segments are
    stripped and lowercased to produce stable, comparable tokens.

    Args:
        seg: The URL path segment to normalize.

    Returns:
        A normalized string representation of the segment.
    """
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


def canonical_id(record: BaseModel | Mapping[str, Json] | object) -> str:
    """Return a deterministic canonical id for `record`.

    Precedence:
      1) `record.build_id()` if implemented on the object
      2) explicit id fields found in mapping keys
      3) composite bill/amendment keys using congress/type/number
      4) parsed URL fallback using `parse_url_to_id`
      5) stable hash fallback when nothing else applies

    The function accepts Pydantic models (via `model_dump()`), plain
    mappings, or arbitrary objects (via `vars()`). Always returns a
    non-empty `str`.
    """
    # Prefer an object's own `build_id()` when available (works for
    # Pydantic models and any object mixin). Call this first before
    # converting the record to a mapping so model helpers are preserved.
    try:
        builder = getattr(record, "build_id", None)
        if callable(builder):
            try:
                bid = builder()
            except TypeError:
                try:
                    bid = builder(record)
                except Exception:
                    logger.exception("Error calling build_id with record arg")
                    bid = None
            if bid:
                return str(bid)
    except Exception as exc:
        logger.exception("Unexpected error invoking build_id: %s", exc)

    # handle pydantic BaseModel or dict-like
    mapping: Mapping[str, object] | dict | None = None
    if isinstance(record, BaseModel):
        try:
            mapping = record.model_dump()
        except Exception as exc:
            logger.exception("Failed to dump BaseModel to mapping: %s", exc)
            mapping = None
    if mapping is None and isinstance(record, Mapping):
        mapping = record
    if mapping is None:
        try:
            mapping = vars(record)
        except Exception as exc:
            logger.exception("Failed to convert record to vars(): %s", exc)
            mapping = {}

    for key in ("bioguide_id", "bioguide", "id", "identifier", "guid"):
        val = (
            mapping.get(key)
            if isinstance(mapping, Mapping) or isinstance(mapping, dict)
            else None
        )
        if val:
            # people ids use person: prefix
            if key.startswith("bioguide"):
                return f"person:{val}"
            return f"id:{val}"

    # 2) composite bill key
    if (
        isinstance(mapping, Mapping)
        and mapping.get("congress")
        and mapping.get("type")
        and mapping.get("number")
    ):
        congress = str(mapping.get("congress"))
        bill_type = str(mapping.get("type")).lower()
        number = str(mapping.get("number"))
        return f"bill:{congress}:{bill_type}:{number}"

    # amendments may be indicated by 'amendmentNumber' or path
    if (
        isinstance(mapping, Mapping)
        and mapping.get("congress")
        and mapping.get("number")
        and mapping.get("purpose")
    ):
        # best-effort amendment id
        congress = str(mapping.get("congress"))
        a_type = str(mapping.get("type", "amendment")).lower()
        number = str(mapping.get("number"))
        return f"amendment:{congress}:{a_type}:{number}"

    # 3) url-based fallback
    url = (
        mapping.get("url")
        if isinstance(mapping, Mapping)
        else getattr(record, "url", None)
    )
    if url:
        try:
            return parse_url_to_id(str(url))
        except Exception:
            logger.exception("Failed to parse URL to id fallback: %s", url)

    # ultimate fallback: stringified mapping hash
    return f"record:{abs(hash(str(mapping))) % (10**12)}"
