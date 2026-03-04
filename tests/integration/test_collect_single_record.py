"""Smoke test for collecting one record per endpoint and serializing to JSON."""

from __future__ import annotations

import json
import inspect
from typing import Any, Mapping

from src.models.data_types import CongressDataType
from src.data_collection.endpoints.amendments import get_amendments_metadata_paginated
from src.data_collection.endpoints.bills import get_bills_metadata
from src.data_collection.endpoints.committee_artifacts import (
    get_committee_meetings,
    get_committee_prints,
    get_committee_reports,
)
from src.data_collection.endpoints.committees import get_committees
from src.data_collection.endpoints.communications import (
    get_house_communications,
    get_senate_communications,
)
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
from src.data_collection.endpoints.records import (
    get_bound_congressional_records,
    get_congressional_records,
    get_daily_congressional_records,
)
import pytest

from tests.integration.test_endpoints import get_first_item, get_response_with_retries


def _serialize_one(
    response: Mapping[str, Any], key: CongressDataType
) -> dict[str, Any]:
    item = get_first_item(response, key)
    return dict(item)


def test_collect_single_record_json(client, tmp_path) -> None:
    """Collect one record per endpoint and serialize to JSON."""
    snapshot: dict[str, Any] = {}

    snapshot["members"] = _serialize_one(
        get_response_with_retries(get_members_list, client, limit=1),
        CongressDataType.MEMBERS,
    )
    snapshot["amendments"] = _serialize_one(
        get_response_with_retries(
            get_amendments_metadata_paginated, client, limit=1
        ),
        CongressDataType.AMENDMENTS,
    )
    snapshot["bills"] = _serialize_one(
        get_response_with_retries(get_bills_metadata, client, limit=1),
        CongressDataType.BILLS,
    )
    snapshot["committees"] = _serialize_one(
        get_response_with_retries(get_committees, client, limit=1),
        CongressDataType.COMMITTEES,
    )
    snapshot["committee_reports"] = _serialize_one(
        get_response_with_retries(get_committee_reports, client, limit=1),
        CongressDataType.REPORTS,
    )
    snapshot["committee_prints"] = _serialize_one(
        get_response_with_retries(get_committee_prints, client),
        CongressDataType.COMMITTEE_PRINTS,
    )
    snapshot["committee_meetings"] = _serialize_one(
        get_response_with_retries(get_committee_meetings, client, limit=1),
        CongressDataType.COMMITTEE_MEETINGS,
    )
    snapshot["hearings"] = _serialize_one(
        get_response_with_retries(get_hearings, client, limit=1),
        CongressDataType.HEARINGS,
    )
    snapshot["house_communications"] = _serialize_one(
        get_response_with_retries(get_house_communications, client, limit=1),
        CongressDataType.HOUSE_COMMUNICATIONS,
    )
    snapshot["house_requirements"] = _serialize_one(
        get_response_with_retries(get_house_requirements, client, limit=1),
        CongressDataType.HOUSE_REQUIREMENTS,
    )
    snapshot["house_roll_call_votes"] = _serialize_one(
        get_response_with_retries(get_house_roll_call_votes, client, limit=1),
        CongressDataType.HOUSE_ROLL_CALL_VOTES,
    )
    snapshot["senate_communications"] = _serialize_one(
        get_response_with_retries(get_senate_communications, client, limit=1),
        CongressDataType.SENATE_COMMUNICATIONS,
    )
    snapshot["nominations"] = _serialize_one(
        get_response_with_retries(get_nominations, client, limit=1),
        CongressDataType.NOMINATIONS,
    )
    snapshot["crs_reports"] = _serialize_one(
        get_response_with_retries(get_crs_reports, client, limit=1),
        CongressDataType.CRS_REPORTS,
    )
    snapshot["summaries"] = _serialize_one(
        get_response_with_retries(get_summaries, client, limit=1),
        CongressDataType.SUMMARIES,
    )
    snapshot["treaties"] = _serialize_one(
        get_response_with_retries(get_treaties, client, limit=1),
        CongressDataType.TREATIES,
    )
    snapshot["laws"] = _serialize_one(
        get_response_with_retries(get_laws, client, congress=118, limit=1),
        CongressDataType.LAWS,
    )
    snapshot["bound_congressional_records"] = _serialize_one(
        get_response_with_retries(get_bound_congressional_records, client, limit=1),
        CongressDataType.BOUND_CONGRESSIONAL_RECORD,
    )
    snapshot["daily_congressional_records"] = _serialize_one(
        get_response_with_retries(get_daily_congressional_records, client, limit=1),
        CongressDataType.DAILY_CONGRESSIONAL_RECORD,
    )

    record_response = get_response_with_retries(
        get_congressional_records, client, year=2022, month=6, day=28
    )
    issues = record_response.get("Results", {}).get("Issues", [])
    assert issues, "No congressional record issues returned from API"
    snapshot["congressional_records"] = dict(issues[0])

    output_path = tmp_path / "single_record_snapshot.json"
    output_path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert output_path.exists()


@pytest.mark.slow
def test_collect_paginated_snapshots(client, tmp_path) -> None:
    """Collect small paginated snapshots for each endpoint and serialize to JSON."""

    def _take_page(fetcher, key: CongressDataType, **kwargs) -> list[dict[str, Any]]:
        signature = inspect.signature(fetcher)
        call_kwargs = dict(kwargs)
        if "limit" in signature.parameters:
            call_kwargs["limit"] = 5
        response = get_response_with_retries(fetcher, client, **call_kwargs)
        items = response.get(str(key), [])
        return [dict(item) for item in items]

    snapshot: dict[str, Any] = {}
    snapshot["members"] = _take_page(get_members_list, CongressDataType.MEMBERS)
    snapshot["amendments"] = _take_page(
        get_amendments_metadata_paginated, CongressDataType.AMENDMENTS
    )
    snapshot["bills"] = _take_page(get_bills_metadata, CongressDataType.BILLS)
    snapshot["committees"] = _take_page(get_committees, CongressDataType.COMMITTEES)
    snapshot["committee_reports"] = _take_page(
        get_committee_reports, CongressDataType.REPORTS
    )
    snapshot["committee_prints"] = _take_page(
        get_committee_prints, CongressDataType.COMMITTEE_PRINTS
    )
    snapshot["committee_meetings"] = _take_page(
        get_committee_meetings, CongressDataType.COMMITTEE_MEETINGS
    )
    snapshot["hearings"] = _take_page(get_hearings, CongressDataType.HEARINGS)
    snapshot["house_communications"] = _take_page(
        get_house_communications, CongressDataType.HOUSE_COMMUNICATIONS
    )
    snapshot["house_requirements"] = _take_page(
        get_house_requirements, CongressDataType.HOUSE_REQUIREMENTS
    )
    snapshot["house_roll_call_votes"] = _take_page(
        get_house_roll_call_votes, CongressDataType.HOUSE_ROLL_CALL_VOTES
    )
    snapshot["senate_communications"] = _take_page(
        get_senate_communications, CongressDataType.SENATE_COMMUNICATIONS
    )
    snapshot["nominations"] = _take_page(get_nominations, CongressDataType.NOMINATIONS)
    snapshot["crs_reports"] = _take_page(get_crs_reports, CongressDataType.CRS_REPORTS)
    snapshot["summaries"] = _take_page(get_summaries, CongressDataType.SUMMARIES)
    snapshot["treaties"] = _take_page(get_treaties, CongressDataType.TREATIES)
    snapshot["laws"] = _take_page(get_laws, CongressDataType.LAWS, congress=118)
    snapshot["bound_congressional_records"] = _take_page(
        get_bound_congressional_records, CongressDataType.BOUND_CONGRESSIONAL_RECORD
    )
    snapshot["daily_congressional_records"] = _take_page(
        get_daily_congressional_records, CongressDataType.DAILY_CONGRESSIONAL_RECORD
    )

    output_path = tmp_path / "paginated_snapshot.json"
    output_path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert output_path.exists()
