"""
Queue specs and fetchers for RabbitMQ sync pipelines.

All endpoint-specific logic (chunk key format, meta fields, data key, id function, etc.) is centralized in the SPECS dictionary.
This ensures all ingest, progress, and indexing code can be spec-driven and maintainable.
Legacy chunk key parsing utilities are deprecated and removed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from pydantic import BaseModel

from knowledgebase.ids import (
    amendment_id,
    bill_id,
    bound_congressional_record_id,
    committee_id,
    committee_meeting_id,
    committee_report_id,
    crs_report_id,
    daily_congressional_record_id,
    hearing_id,
    house_requirement_id,
    house_vote_id,
    law_id,
    member_id,
    nomination_id,
    summary_id,
    treaty_id,
)
from knowledgebase.indices import (
    AMENDMENTS_MAPPING,
    BILLS_MAPPING,
    BOUND_CONGRESSIONAL_RECORDS_MAPPING,
    COMMITTEE_MEETINGS_MAPPING,
    COMMITTEE_REPORTS_MAPPING,
    COMMITTEES_MAPPING,
    CONGRESSES_MAPPING,
    CRS_REPORTS_MAPPING,
    DAILY_CONGRESSIONAL_RECORDS_MAPPING,
    HEARINGS_MAPPING,
    HOUSE_REQUIREMENTS_MAPPING,
    HOUSE_VOTES_MAPPING,
    LAWS_MAPPING,
    MEMBERS_MAPPING,
    NOMINATIONS_MAPPING,
    SUMMARIES_MAPPING,
    TREATIES_MAPPING,
)
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.amendments import get_amendments_metadata_paginated
from src.data_collection.endpoints.bills import get_bills_metadata
from src.data_collection.endpoints.committee_artifacts import (
    get_committee_meetings,
    get_committee_reports,
    get_committee_reports_by_congress,
    get_committee_reports_by_congress_and_type,
    get_committee_prints,
)
from src.data_collection.endpoints.committees import get_committees
from src.data_collection.endpoints.congress import gather_congresses, get_congress
from src.data_collection.endpoints.hearings import get_hearings
from src.data_collection.endpoints.laws import get_laws
from src.data_collection.endpoints.members import get_members_list
from src.data_collection.endpoints.nominations import get_nominations
from src.data_collection.endpoints.other import (
    get_crs_reports,
    get_house_requirements,
    get_house_roll_call_votes,
    get_summaries,
    get_treaties,
)
from src.data_collection.endpoints.communications import (
    get_house_communications,
    get_senate_communications,
)
from src.data_collection.endpoints.records import (
    get_bound_congressional_records,
    get_daily_congressional_records,
)
from src.models import meta_models


@dataclass(frozen=True)
class QueueSpec:
    endpoint: str  # API endpoint name (e.g., "bill")
    es_index: str  # Elasticsearch index name (e.g., "congress-bills")
    api_data_key: str  # Key in API response for records (e.g., "bills")
    id_func: Callable[[dict], Any]  # Function to build unique record ID
    es_mapping: dict  # Elasticsearch index mapping
    chunk_key_format: str  # Description of chunk key format (e.g., "congress:type")
    description: str  # Short description of what this spec represents
    chunk_key_func: Callable[
        [dict, int | None], str
    ]  # Function to build chunk key from meta and law_congress
    meta_fields: list[str]  # List of meta fields to include in payload
    # Optional: explicit list of allowed API param names (query/path) for this endpoint.
    # If None, `meta_fields` will be used as the allowed set.
    allowed_params: list[str] | None = None
    # Optional mapping from chunk/meta keys to API parameter names (e.g., "report_type" -> "reportType").
    param_mapping: dict[str, str] | None = None
    # Optional Pydantic models to coerce meta and parse responses
    meta_model: type[BaseModel] | None = None
    response_model: type[BaseModel] | None = None


SPECS: dict[str, QueueSpec] = {
    # Congresses (by congress number)
    "congress": QueueSpec(
        endpoint="congress",
        es_index="congress-congresses",
        api_data_key="congresses",
        id_func=lambda x: str(x.get("number", "")),
        es_mapping=CONGRESSES_MAPPING,
        chunk_key_format="congress (e.g., 117)",
        description="Congress metadata by congress number",
        chunk_key_func=lambda meta, law_congress=None: str(
            meta.get("congress", law_congress or "")
        ),
        meta_fields=["congress"],
        meta_model=meta_models.CongressMeta,
        response_model=meta_models.CongressListResponse,
    ),
    # Bills by congress and bill type
    "bill": QueueSpec(
        endpoint="bill",
        es_index="congress-bills",
        api_data_key="bills",
        id_func=bill_id,
        es_mapping=BILLS_MAPPING,
        chunk_key_format="congress:type (e.g., 117:HR)",
        description="Bills by congress and bill type",
        chunk_key_func=lambda meta, law_congress=None: (
            f"{meta.get('congress', law_congress or '')}:{meta.get('type', '')}"
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress", "type"],
        meta_model=meta_models.BillMeta,
        response_model=meta_models.BillListResponse,
    ),
    # Members by congress
    "member": QueueSpec(
        endpoint="member",
        es_index="congress-members",
        api_data_key="members",
        id_func=member_id,
        es_mapping=MEMBERS_MAPPING,
        chunk_key_format="congress (e.g., 117)",
        description="Members by congress",
        chunk_key_func=lambda meta, law_congress=None: str(
            meta.get("congress", law_congress or "")
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.MemberListResponse,
    ),
    # Laws by congress
    "law": QueueSpec(
        endpoint="law",
        es_index="congress-laws",
        api_data_key="bills",
        id_func=law_id,
        es_mapping=LAWS_MAPPING,
        chunk_key_format="congress (e.g., 117)",
        description="Laws by congress",
        chunk_key_func=lambda meta, law_congress=None: str(
            meta.get("congress", law_congress or "")
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.BillListResponse,
    ),
    # Amendments by congress and amendment type
    "amendment": QueueSpec(
        endpoint="amendment",
        es_index="congress-amendments",
        api_data_key="amendments",
        id_func=amendment_id,
        es_mapping=AMENDMENTS_MAPPING,
        chunk_key_format="congress:type (e.g., 117:SAMDT)",
        description="Amendments by congress and amendment type",
        chunk_key_func=lambda meta, law_congress=None: (
            f"{meta.get('congress', law_congress or '')}:{meta.get('type', '')}"
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress", "type"],
        meta_model=meta_models.AmendmentMeta,
        response_model=meta_models.AmendmentsResponse,
    ),
    # Committees by congress and chamber
    "committee": QueueSpec(
        endpoint="committee",
        es_index="congress-committees",
        api_data_key="committees",
        id_func=committee_id,
        es_mapping=COMMITTEES_MAPPING,
        chunk_key_format="congress:chamber (e.g., 117:house)",
        description="Committees by congress and chamber",
        chunk_key_func=lambda meta, law_congress=None: (
            f"{meta.get('congress', law_congress or '')}:{meta.get('chamber', '')}"
        ),
        meta_fields=[
            "offset",
            "page",
            "page_size",
            "total_pages",
            "congress",
            "chamber",
        ],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.CommitteeListResponse,
    ),
    # Committee meetings by congress and chamber
    "committee-meeting": QueueSpec(
        endpoint="committee-meeting",
        es_index="congress-committee-meetings",
        api_data_key="committeeMeetings",
        id_func=committee_meeting_id,
        es_mapping=COMMITTEE_MEETINGS_MAPPING,
        chunk_key_format="congress:chamber (e.g., 117:house)",
        description="Committee meetings by congress and chamber",
        chunk_key_func=lambda meta, law_congress=None: (
            f"{meta.get('congress', law_congress or '')}:{meta.get('chamber', '')}"
        ),
        meta_fields=[
            "offset",
            "page",
            "page_size",
            "total_pages",
            "congress",
            "chamber",
        ],
        meta_model=meta_models.CommitteeMeetingMeta,
        response_model=meta_models.CommitteeMeetingsResponse,
    ),
    # Committee prints by congress and chamber (optional ingestion)
    "committee-print": QueueSpec(
        endpoint="committee-print",
        es_index="congress-committee-prints",
        api_data_key="committeePrints",
        id_func=lambda x: str(x.get("jacketNumber") or x.get("jacket_number") or ""),
        es_mapping=COMMITTEE_MEETINGS_MAPPING,
        chunk_key_format="congress:chamber (e.g., 117:house)",
        description="Committee prints by congress and chamber",
        chunk_key_func=lambda meta, law_congress=None: (
            f"{meta.get('congress', law_congress or '')}:{meta.get('chamber', '')}"
        ),
        meta_fields=[
            "offset",
            "page",
            "page_size",
            "total_pages",
            "congress",
            "chamber",
        ],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.CommitteePrintsResponse,
    ),
    # Committee reports by congress and report type
    "committee-report": QueueSpec(
        endpoint="committee-report",
        es_index="congress-committee-reports",
        api_data_key="reports",
        id_func=committee_report_id,
        es_mapping=COMMITTEE_REPORTS_MAPPING,
        chunk_key_format="congress:report_type (e.g., 117:hrpt)",
        description="Committee reports by congress and report type",
        chunk_key_func=lambda meta, law_congress=None: (
            f"{meta.get('congress', law_congress or '')}:{meta.get('report_type', '')}"
        ),
        meta_fields=[
            "offset",
            "page",
            "page_size",
            "total_pages",
            "congress",
            "report_type",
        ],
        # map internal snake_case to API camelCase param
        param_mapping={"report_type": "reportType"},
        meta_model=meta_models.CommitteeReportMeta,
        response_model=meta_models.CommitteeReportsResponse,
    ),
    # Hearings by congress and chamber
    "hearing": QueueSpec(
        endpoint="hearing",
        es_index="congress-hearings",
        api_data_key="hearings",
        id_func=hearing_id,
        es_mapping=HEARINGS_MAPPING,
        chunk_key_format="congress:chamber (e.g., 117:house)",
        description="Hearings by congress and chamber",
        chunk_key_func=lambda meta, law_congress=None: (
            f"{meta.get('congress', law_congress or '')}:{meta.get('chamber', '')}"
        ),
        meta_fields=[
            "offset",
            "page",
            "page_size",
            "total_pages",
            "congress",
            "chamber",
        ],
        meta_model=meta_models.HearingMeta,
        response_model=meta_models.HearingsResponse,
    ),
    # Nominations by congress
    "nomination": QueueSpec(
        endpoint="nomination",
        es_index="congress-nominations",
        api_data_key="nominations",
        id_func=nomination_id,
        es_mapping=NOMINATIONS_MAPPING,
        chunk_key_format="congress (e.g., 117)",
        description="Nominations by congress",
        chunk_key_func=lambda meta, law_congress=None: str(
            meta.get("congress", law_congress or "")
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.NominationListResponse,
    ),
    # Bound Congressional Record by year
    "bound-congressional-record": QueueSpec(
        endpoint="bound-congressional-record",
        es_index="congress-bound-congressional-records",
        api_data_key="boundCongressionalRecord",
        id_func=bound_congressional_record_id,
        es_mapping=BOUND_CONGRESSIONAL_RECORDS_MAPPING,
        chunk_key_format="year (e.g., 1990)",
        description="Bound Congressional Record by year",
        chunk_key_func=lambda meta, law_congress=None: str(meta.get("year", "")),
        meta_fields=["offset", "page", "page_size", "total_pages", "year"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.BoundCongressionalRecordResponse,
    ),
    # Daily Congressional Record by volumeNumber
    "daily-congressional-record": QueueSpec(
        endpoint="daily-congressional-record",
        es_index="congress-daily-congressional-records",
        api_data_key="dailyCongressionalRecord",
        id_func=daily_congressional_record_id,
        es_mapping=DAILY_CONGRESSIONAL_RECORDS_MAPPING,
        chunk_key_format="congress (e.g., 117)",
        description="Daily Congressional Record by congress (paginated)",
        chunk_key_func=lambda meta, law_congress=None: str(
            meta.get("congress", law_congress or "")
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.DailyCongressionalRecordResponse,
    ),
    # CRS Reports by year
    "crsreport": QueueSpec(
        endpoint="crsreport",
        es_index="congress-crs-reports",
        api_data_key="CRSReports",
        id_func=crs_report_id,
        es_mapping=CRS_REPORTS_MAPPING,
        chunk_key_format="year (e.g., 2023)",
        description="CRS Reports by year",
        chunk_key_func=lambda meta, law_congress=None: str(meta.get("year", "")),
        meta_fields=["offset", "page", "page_size", "total_pages", "year"],
        meta_model=meta_models.CRSReportMeta,
        response_model=meta_models.CRSReportsResponse,
    ),
    # House communications (paginated)
    "house-communication": QueueSpec(
        endpoint="house-communication",
        es_index="congress-house-communications",
        api_data_key="houseCommunications",
        id_func=lambda x: f"{x.get('congress', '')}-{x.get('number', '')}",
        es_mapping=MEMBERS_MAPPING,
        chunk_key_format="congress (e.g., 117)",
        description="House communications by congress",
        chunk_key_func=lambda meta, law_congress=None: str(
            meta.get("congress", law_congress or "")
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.HouseCommunicationsResponse,
    ),
    # Senate communications (paginated)
    "senate-communication": QueueSpec(
        endpoint="senate-communication",
        es_index="congress-senate-communications",
        api_data_key="senateCommunications",
        id_func=lambda x: f"{x.get('congress', '')}-{x.get('number', '')}",
        es_mapping=MEMBERS_MAPPING,
        chunk_key_format="congress (e.g., 117)",
        description="Senate communications by congress",
        chunk_key_func=lambda meta, law_congress=None: str(
            meta.get("congress", law_congress or "")
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.SenateCommunicationsResponse,
    ),
    # Summaries by congress and bill type
    "summaries": QueueSpec(
        endpoint="summaries",
        es_index="congress-summaries",
        api_data_key="summaries",
        id_func=summary_id,
        es_mapping=SUMMARIES_MAPPING,
        chunk_key_format="congress:type (e.g., 117:HR)",
        description="Bill summaries by congress and bill type",
        chunk_key_func=lambda meta, law_congress=None: (
            f"{meta.get('congress', law_congress or '')}:{meta.get('type', '')}"
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress", "type"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.SummariesResponse,
    ),
    # Treaties by congress
    "treaty": QueueSpec(
        endpoint="treaty",
        es_index="congress-treaties",
        api_data_key="treaties",
        id_func=treaty_id,
        es_mapping=TREATIES_MAPPING,
        chunk_key_format="congress (e.g., 117)",
        description="Treaties by congress",
        chunk_key_func=lambda meta, law_congress=None: str(
            meta.get("congress", law_congress or "")
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.TreatyListResponse,
    ),
    # House requirements by congress
    "house-requirement": QueueSpec(
        endpoint="house-requirement",
        es_index="congress-house-requirements",
        api_data_key="houseRequirements",
        id_func=house_requirement_id,
        es_mapping=HOUSE_REQUIREMENTS_MAPPING,
        chunk_key_format="congress (e.g., 117)",
        description="House requirements by congress",
        chunk_key_func=lambda meta, law_congress=None: str(
            meta.get("congress", law_congress or "")
        ),
        meta_fields=["offset", "page", "page_size", "total_pages", "congress"],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.HouseRequirementsResponse,
    ),
    # House votes by congress and session
    "house-vote": QueueSpec(
        endpoint="house-vote",
        es_index="congress-house-votes",
        api_data_key="houseRollCallVotes",
        id_func=house_vote_id,
        es_mapping=HOUSE_VOTES_MAPPING,
        chunk_key_format="congress:session (e.g., 118:2)",
        description="House roll call votes by congress and session",
        chunk_key_func=lambda meta, law_congress=None: (
            f"{meta.get('congress', law_congress or '')}:{meta.get('session', '')}"
        ),
        meta_fields=[
            "offset",
            "page",
            "page_size",
            "total_pages",
            "congress",
            "session",
        ],
        meta_model=meta_models.GenericChunkMeta,
        response_model=meta_models.HouseVotesResponse,
    ),
}


def fetch_page(
    target: str, client: CDGClient, *, offset: int, limit: int, meta: dict | None = None
) -> dict:
    if target == "bill":
        return get_bills_metadata(client, offset=offset, limit=limit)
    if target == "member":
        return get_members_list(client, offset=offset, limit=limit)
    if target == "law":
        # Default congress: resolved in producer.
        raise RuntimeError("Law fetch requires congress; use fetch_law_page")
    if target == "amendment":
        return get_amendments_metadata_paginated(client, offset=offset, limit=limit)
    if target == "committee":
        return get_committees(client, offset=offset, limit=limit)
    if target == "committee-meeting":
        return get_committee_meetings(client, offset=offset, limit=limit)
    if target == "committee-report":
        # Route according to meta: congress + report_type -> specific endpoint
        if (
            meta
            and meta.get("congress")
            and (meta.get("report_type") or meta.get("reportType"))
        ):
            # accept either internal snake_case or API camelCase param
            rpt = meta.get("report_type") or meta.get("reportType")
            return get_committee_reports_by_congress_and_type(
                client,
                congress=int(meta.get("congress") or 0),
                reportType=str(rpt or ""),
                offset=offset,
                limit=limit,
            )
        if meta and meta.get("congress"):
            return get_committee_reports_by_congress(
                client,
                congress=int(meta.get("congress") or 0),
                offset=offset,
                limit=limit,
            )
        return get_committee_reports(client, offset=offset, limit=limit)

    if target == "hearing":
        return get_hearings(client, offset=offset, limit=limit)
    if target == "nomination":
        return get_nominations(client, offset=offset, limit=limit)
    if target == "bound-congressional-record":
        return get_bound_congressional_records(client, offset=offset, limit=limit)
    if target == "daily-congressional-record":
        return get_daily_congressional_records(client, offset=offset, limit=limit)
    if target == "crsreport":
        return get_crs_reports(client, offset=offset, limit=limit)
    if target == "committee-print":
        return get_committee_prints(client, offset=offset, limit=limit)
    if target == "house-communication":
        return get_house_communications(client, offset=offset, limit=limit)
    if target == "senate-communication":
        return get_senate_communications(client, offset=offset, limit=limit)
    if target == "summaries":
        return get_summaries(client, offset=offset, limit=limit)
    if target == "treaty":
        return get_treaties(client, offset=offset, limit=limit)
    if target == "house-requirement":
        return get_house_requirements(client, offset=offset, limit=limit)
    if target == "house-vote":
        return get_house_roll_call_votes(client, offset=offset, limit=limit)
    if target == "congress":
        if limit == 1:
            # Offset is the congress id (1-based)
            congress_number = offset
            return {
                "congresses": [get_congress(client, congress=congress_number)],
                "pagination": {
                    "count": 1,
                    "offset": offset,
                    "page_size": limit,
                },
            }
        # Otherwise, batch fetch
        all_congresses = gather_congresses(client)
        paged = all_congresses[offset : offset + limit]
        return {
            "congresses": paged,
            "pagination": {
                "count": len(all_congresses),
                "offset": offset,
                "page_size": limit,
            },
        }
    raise ValueError(f"Unknown target: {target}")


def _snake_to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


def normalize_meta_for_api(meta: dict | None, spec: QueueSpec) -> dict:
    """Normalize meta keys to the API parameter names using `spec.param_mapping` or camelCase conversion."""
    if not meta:
        return {}
    mapping = spec.param_mapping or {}
    api_meta: dict = {}
    for k, v in meta.items():
        if k in mapping:
            api_meta[mapping[k]] = v
        elif "_" in k:
            api_meta[_snake_to_camel(k)] = v
        else:
            api_meta[k] = v
    return api_meta


def prepare_api_meta(
    spec: QueueSpec, meta: dict | None
) -> tuple[dict, object | None, dict]:
    """Prepare API meta parameters for a spec.

    Returns (api_meta, meta_obj, filtered_meta) where `meta_obj` is the
    validated Pydantic model instance when `spec.meta_model` is provided
    and validation succeeds, otherwise None. `filtered_meta` contains the
    raw meta filtered to allowed fields and is useful for legacy paths.
    """
    if not meta:
        return {}, None, {}
    api_meta: dict = {}
    meta_obj = None
    filtered_meta: dict = {}
    # Attempt Pydantic coercion when a meta_model is present
    if spec.meta_model is not None:
        try:
            meta_obj = spec.meta_model.model_validate(meta)
            api_meta_all = meta_obj.model_dump(by_alias=True, exclude_none=True)
            allowed_args = spec.allowed_params or list(spec.meta_fields)
            # Build allowed API arg names, including both snake_case and alias/camelCase
            allowed_api_args = set()
            for a in allowed_args:
                allowed_api_args.add(a)
                if spec.param_mapping and a in spec.param_mapping:
                    allowed_api_args.add(spec.param_mapping[a])
                elif "_" in a:
                    allowed_api_args.add(_snake_to_camel(a))
            api_meta = {k: v for k, v in api_meta_all.items() if k in allowed_api_args}
            return api_meta, meta_obj, filtered_meta
        except Exception:
            pass
    # Legacy fallback: filter raw meta and normalize
    allowed_args = spec.allowed_params or list(spec.meta_fields)
    filtered_meta = {k: v for k, v in (meta or {}).items() if k in allowed_args}
    try:
        api_meta = normalize_meta_for_api(filtered_meta, spec)
    except Exception:
        api_meta = dict(filtered_meta)
    return api_meta, meta_obj, filtered_meta


def resolve_pagination_for_consumer(
    endpoint: str,
    spec: QueueSpec,
    meta: dict | None,
    meta_obj: object | None,
    filtered_meta: dict,
) -> tuple[int, int]:
    """Resolve offset and limit for a consumer run.

    Prefers values from `meta_obj` when available, otherwise falls back
    to `filtered_meta` or raw `meta` via `resolve_offset_limit`.
    """
    if endpoint == "congress":
        offset = int((meta or {}).get("congress", 0))
        return offset, 1
    if meta_obj is not None:
        try:
            offset = int(getattr(meta_obj, "offset", 0) or 0)
            limit = int(getattr(meta_obj, "limit", 250) or 250)
            return offset, limit
        except Exception:
            pass
    # Fallback to existing utility
    from src.data_collection.utils import resolve_offset_limit as _resolve

    offset, limit = _resolve(
        filtered_meta or meta or {}, default_offset=0, default_limit=250
    )
    return offset, limit


def fetch_law_page(
    client: CDGClient, *, congress: int, offset: int, limit: int
) -> dict:
    return get_laws(client, congress=congress, offset=offset, limit=limit)
