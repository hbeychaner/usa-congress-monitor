"""Common validator helpers for models."""

from __future__ import annotations

from cdm.models.shared import Chamber, LawType


def convert_law_type(value: str | LawType) -> LawType:
    """Convert raw law type strings into the LawType enum."""
    if isinstance(value, LawType):
        return value
    if value == "Public Law":
        return LawType.PUBLIC
    if value == "Private Law":
        return LawType.PRIVATE
    raise ValueError("Invalid law type")


def normalize_chamber(v: object) -> Chamber | None:
    """Normalize various chamber string forms into `Chamber` enum or None."""
    if v is None:
        return None
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


