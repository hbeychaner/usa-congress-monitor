"""Common validator helpers for models."""

from __future__ import annotations

from datetime import datetime


# Enums imported lazily inside functions to avoid circular imports
def convert_law_type(value: str):
    """Convert raw law type strings into the LawType enum.

    Import enums lazily to avoid circular imports with model modules.
    """
    from src.models.bills import LawType

    if value == "Public Law":
        return LawType.PUBLIC
    if value == "Private Law":
        return LawType.PRIVATE
    raise ValueError("Invalid law type")


def normalize_chamber(v):
    """Normalize various chamber string forms into `Chamber` enum or None.

    Import `Chamber` lazily to avoid circular imports.
    """
    if v is None:
        return None
    from src.models.people import Chamber

    if isinstance(v, Chamber):
        return v
    raw = str(v).strip().lower()
    if "house" in raw or "represent" in raw or raw in ("h", "hr"):
        return Chamber.HOUSE
    if raw.startswith("sen") or "senate" in raw or raw in ("s",):
        return Chamber.SENATE
    if raw.capitalize() == Chamber.HOUSE.value:
        return Chamber.HOUSE
    if raw.capitalize() == Chamber.SENATE.value:
        return Chamber.SENATE
    return None


def parse_iso_datetime(value: str):
    """Parse a variety of ISO-like datetime strings into a datetime.

    Returns a datetime on success or raises ValueError on failure. This
    helper keeps parsing logic centralized for model validators.
    """
    if value is None:
        raise ValueError("None is not a valid datetime")
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    # try fromisoformat first (Python 3.7+)
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    # common fallback formats
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognized datetime format: {value}")
