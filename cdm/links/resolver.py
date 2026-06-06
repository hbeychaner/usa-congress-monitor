"""Cross-entity link resolution.

Given a record from any resource, this module resolves known foreign-key
references to other stored entities (bills ↔ amendments, members ↔ committees,
etc.) so the CDM can materialise enriched views.
"""

from __future__ import annotations

from typing import Any, Optional


def resolve_bill_ref(record: dict) -> Optional[str]:
    """Return the canonical bill id from a record that contains a bill reference."""
    bill = record.get("bill") or record.get("latestAction", {}).get("bill")
    if not bill:
        return None
    congress = bill.get("congress")
    bill_type = bill.get("type", "").lower()
    number = bill.get("number")
    if congress and bill_type and number:
        return f"{congress}-{bill_type}{number}"
    return None


def resolve_member_ref(record: dict) -> Optional[str]:
    """Return the bioguide id for a member reference if present."""
    sponsor = record.get("sponsors", [{}])[0] if record.get("sponsors") else {}
    return sponsor.get("bioguideId") or record.get("bioguideId")
