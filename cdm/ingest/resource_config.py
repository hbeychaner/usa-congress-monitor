"""Per-resource configuration describing how each Congress.gov resource is scoped.

``RESOURCE_CONFIGS`` is the single source of truth for:
- which query params control date filtering
- whether a congress number is required on the list URL
- whether the resource has an item endpoint at all (list_only)
- sensible defaults for fetch_items (off for very large resources)

The pipeline and CLI use this catalog to automatically configure each
IngestRunner without the caller needing to know per-resource quirks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

from cdm.ingest.runner import Resource


Scope = Literal["date_window", "congress_scoped", "static"]


@dataclass
class ResourceConfig:
    resource: Resource
    # How the list endpoint is scoped/filtered
    scope: Scope
    # Query param names for date filtering (None if not supported)
    from_date_param: Optional[str] = None
    to_date_param: Optional[str] = None
    # Whether the list URL path requires a {congress} segment
    requires_congress: bool = False
    # Whether this resource has no item endpoint (list phase only)
    list_only: bool = False
    # Whether to fetch items by default (False for very large resources)
    fetch_items_default: bool = True
    # Human-readable note for the CLI --help output
    notes: str = ""


# ---------------------------------------------------------------------------
# Catalog — one entry per Resource enum value
# ---------------------------------------------------------------------------

RESOURCE_CONFIGS: Dict[Resource, ResourceConfig] = {
    r: c
    for r, c in [
        (
            Resource.AMENDMENT,
            ResourceConfig(
                resource=Resource.AMENDMENT,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
        (
            Resource.BILL,
            ResourceConfig(
                resource=Resource.BILL,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                # Bills are very numerous; default to list-only for bulk runs
                fetch_items_default=False,
                notes="Use --items to fetch full bill detail; very large dataset",
            ),
        ),
        (
            Resource.BOUND_CONGRESSIONAL_RECORD,
            ResourceConfig(
                resource=Resource.BOUND_CONGRESSIONAL_RECORD,
                scope="static",
                # 93k records going back 200 years; API ignores date filters
                fetch_items_default=False,
                notes="Static; list-only (93k total records, API ignores date filters)",
            ),
        ),
        (
            Resource.COMMITTEE,
            ResourceConfig(
                resource=Resource.COMMITTEE,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
        (
            Resource.COMMITTEE_MEETING,
            ResourceConfig(
                resource=Resource.COMMITTEE_MEETING,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
        (
            Resource.COMMITTEE_PRINT,
            ResourceConfig(
                resource=Resource.COMMITTEE_PRINT,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
        (
            Resource.COMMITTEE_REPORT,
            ResourceConfig(
                resource=Resource.COMMITTEE_REPORT,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
        (
            Resource.CONGRESS,
            ResourceConfig(
                resource=Resource.CONGRESS,
                scope="static",
                fetch_items_default=True,
                notes="Static list of all 119 congresses; no date filter",
            ),
        ),
        (
            Resource.CRSREPORT,
            ResourceConfig(
                resource=Resource.CRSREPORT,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
        (
            Resource.DAILY_CONGRESSIONAL_RECORD,
            ResourceConfig(
                resource=Resource.DAILY_CONGRESSIONAL_RECORD,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                # ~200 issues/year; each item is a full CR document (large payload)
                fetch_items_default=False,
                notes="List-only by default; use --resources daily_congressional_record --items to fetch full text",
            ),
        ),
        (
            Resource.HEARING,
            ResourceConfig(
                resource=Resource.HEARING,
                scope="congress_scoped",
                requires_congress=False,  # congress optional on list URL
                fetch_items_default=True,
            ),
        ),
        (
            Resource.HOUSE_COMMUNICATION,
            ResourceConfig(
                resource=Resource.HOUSE_COMMUNICATION,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
        (
            Resource.HOUSE_REQUIREMENT,
            ResourceConfig(
                resource=Resource.HOUSE_REQUIREMENT,
                scope="static",
                fetch_items_default=False,
                notes="Reference data; list-only by default (3k rows, rarely changes)",
            ),
        ),
        (
            Resource.HOUSE_VOTE,
            ResourceConfig(
                resource=Resource.HOUSE_VOTE,
                scope="congress_scoped",
                requires_congress=True,
                fetch_items_default=True,
                notes="Requires congress number; optionally scoped by session",
            ),
        ),
        (
            Resource.LAW,
            ResourceConfig(
                resource=Resource.LAW,
                scope="congress_scoped",
                requires_congress=True,
                list_only=True,
                fetch_items_default=False,
                notes="Item endpoint returns 5xx; use bill ingest for full records",
            ),
        ),
        (
            Resource.MEMBER,
            ResourceConfig(
                resource=Resource.MEMBER,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                # Members are numerous; fetch items selectively
                fetch_items_default=False,
                notes="Use --items to fetch full member bio; large dataset",
            ),
        ),
        (
            Resource.NOMINATION,
            ResourceConfig(
                resource=Resource.NOMINATION,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
        (
            Resource.SENATE_COMMUNICATION,
            ResourceConfig(
                resource=Resource.SENATE_COMMUNICATION,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
        (
            Resource.SUMMARIES,
            ResourceConfig(
                resource=Resource.SUMMARIES,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                list_only=True,
                fetch_items_default=False,
                notes="No item endpoint; summaries are embedded in list",
            ),
        ),
        (
            Resource.TREATY,
            ResourceConfig(
                resource=Resource.TREATY,
                scope="date_window",
                from_date_param="fromDateTime",
                to_date_param="toDateTime",
                fetch_items_default=True,
            ),
        ),
    ]
}


def get_config(resource: Resource) -> ResourceConfig:
    """Return the ResourceConfig for *resource*, raising KeyError if missing."""
    return RESOURCE_CONFIGS[resource]


def date_windowed() -> List[ResourceConfig]:
    return [c for c in RESOURCE_CONFIGS.values() if c.scope == "date_window"]


def congress_scoped() -> List[ResourceConfig]:
    return [c for c in RESOURCE_CONFIGS.values() if c.scope == "congress_scoped"]


def static_resources() -> List[ResourceConfig]:
    return [c for c in RESOURCE_CONFIGS.values() if c.scope == "static"]
