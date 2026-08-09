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

from dataclasses import dataclass
from typing import Literal

from cdm.ingest.runner import Resource
from cdm.models.endpoint_spec import ParamLocation

Scope = Literal["date_window", "congress_scoped", "static"]


@dataclass
class ResourceConfig:
    resource: Resource
    # How the list endpoint is scoped/filtered
    scope: Scope
    # Query param names for date filtering (None if not supported)
    from_date_param: str | None = None
    to_date_param: str | None = None
    # Whether this resource has no item endpoint (list phase only)
    list_only: bool = False
    # Whether to fetch items by default (False for very large resources)
    fetch_items_default: bool = True
    # Human-readable note for the CLI --help output
    notes: str = ""

    @property
    def requires_congress(self) -> bool:
        """Whether the registered list spec requires a congress path value."""
        if self.scope != "congress_scoped":
            return False
        return list_spec_requires_congress(self.resource)


# ---------------------------------------------------------------------------
# Catalog — one entry per Resource enum value
# ---------------------------------------------------------------------------

RESOURCE_CONFIGS: dict[Resource, ResourceConfig] = {
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
                scope="static",
                fetch_items_default=True,
                notes="API ignores all date filter params (fromDateTime and fromDate both return full 20k count); fetch once as static",
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
                scope="static",
                fetch_items_default=True,
                notes="API ignores all date filter params (fromDateTime and fromDate both return full 13.8k count); fetch once as static",
            ),
        ),
        (
            Resource.DAILY_CONGRESSIONAL_RECORD,
            ResourceConfig(
                resource=Resource.DAILY_CONGRESSIONAL_RECORD,
                scope="static",
                fetch_items_default=False,
                notes="API ignores fromDateTime/toDateTime — always returns all 5.8k issues; fetch once as static. List-only by default (large PDF payloads per item)",
            ),
        ),
        (
            Resource.HEARING,
            ResourceConfig(
                resource=Resource.HEARING,
                scope="static",
                fetch_items_default=True,
                notes="API ignores fromDateTime/toDateTime — always returns full collection (35k records); fetch once as static",
            ),
        ),
        (
            Resource.HOUSE_COMMUNICATION,
            ResourceConfig(
                resource=Resource.HOUSE_COMMUNICATION,
                scope="static",
                fetch_items_default=True,
                notes="API ignores fromDateTime/toDateTime — always returns full collection; fetch once as static",
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
                fetch_items_default=True,
                notes="Global list; item URLs may include session details",
            ),
        ),
        (
            Resource.LAW,
            ResourceConfig(
                resource=Resource.LAW,
                scope="congress_scoped",
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
                scope="static",
                fetch_items_default=True,
                notes="API ignores fromDateTime/toDateTime — always returns full collection; fetch once as static",
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


def list_spec_requires_congress(resource: Resource) -> bool:
    """Return whether the registered list endpoint requires a congress path value."""
    # Importing the specs package registers every list/item spec. Keep this lazy
    # so importing the configuration catalog does not trigger model registration.
    import cdm.data_collection.specs  # noqa: F401
    from cdm.data_collection.endpoint_registry import get_spec

    list_spec = get_spec(f"{resource.value}_list")
    return any(
        param.location == ParamLocation.PATH
        and param.name == "congress"
        and param.required
        for param in list_spec.param_specs
    )


def effective_scope(config: ResourceConfig) -> Scope:
    """Return the planning scope, correcting stale congress-scope metadata."""
    if config.scope == "congress_scoped" and not config.requires_congress:
        return "static"
    return config.scope


def validate_scope_catalog() -> None:
    """Raise when scope metadata contradicts the configured query fields."""
    for config in RESOURCE_CONFIGS.values():
        has_date_params = bool(config.from_date_param or config.to_date_param)
        if config.scope == "static" and has_date_params:
            raise ValueError(
                f"Static resource {config.resource.value} cannot define date parameters"
            )
        if config.scope == "date_window" and not (
            config.from_date_param and config.to_date_param
        ):
            raise ValueError(
                f"Date-windowed resource {config.resource.value} requires both date parameters"
            )


def date_windowed() -> list[ResourceConfig]:
    return [c for c in RESOURCE_CONFIGS.values() if effective_scope(c) == "date_window"]


def congress_scoped() -> list[ResourceConfig]:
    return [
        c for c in RESOURCE_CONFIGS.values() if effective_scope(c) == "congress_scoped"
    ]


def static_resources() -> list[ResourceConfig]:
    return [c for c in RESOURCE_CONFIGS.values() if effective_scope(c) == "static"]
