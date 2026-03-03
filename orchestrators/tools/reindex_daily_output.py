"""Reindex daily_output data into knowledgebase indices."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from knowledgebase.client import build_client
from knowledgebase.indexing import index_records
from knowledgebase.indices import build_default_specs
from knowledgebase.ids import (
    amendment_id,
    bill_id,
    bound_congressional_record_id,
    committee_id,
    committee_meeting_id,
    committee_print_id,
    committee_report_id,
    congress_id,
    congressional_record_id,
    crs_report_id,
    daily_congressional_record_id,
    hearing_id,
    house_communication_id,
    house_requirement_id,
    house_vote_id,
    law_id,
    member_id,
    nomination_id,
    senate_communication_id,
    summary_id,
    treaty_id,
)
from knowledgebase.setup import KnowledgebaseSetup
from settings import ELASTIC_API_KEY, ELASTIC_API_URL, ES_LOCAL_API_KEY, ES_LOCAL_URL
from src.utils.logger import get_logger

logger = get_logger(__name__)

IndexFunc = Callable[[dict[str, Any]], str]

INDEX_BUILDERS: dict[str, IndexFunc] = {
    "amendment": amendment_id,
    "bill": bill_id,
    "bound-congressional-record": bound_congressional_record_id,
    "committee": committee_id,
    "committee-meeting": committee_meeting_id,
    "committee-print": committee_print_id,
    "committee-report": committee_report_id,
    "congress": congress_id,
    "congressional-record": congressional_record_id,
    "crsreport": crs_report_id,
    "daily-congressional-record": daily_congressional_record_id,
    "hearing": hearing_id,
    "house-communication": house_communication_id,
    "house-requirement": house_requirement_id,
    "house-vote": house_vote_id,
    "law": law_id,
    "member": member_id,
    "nomination": nomination_id,
    "senate-communication": senate_communication_id,
    "summaries": summary_id,
    "treaty": treaty_id,
}


def load_json(path: Path) -> list[dict[str, Any]]:
    """Load list data from JSON."""
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected list data in {path}")
    return data


def normalize_dates(records: list[dict[str, Any]]) -> None:
    """Normalize updateDate fields to ISO 8601 with 'T' separator."""
    for record in records:
        value = record.get("updateDate")
        if isinstance(value, str) and "T" not in value and " " in value:
            record["updateDate"] = value.replace(" ", "T", 1)


def ensure_indices(client) -> None:
    """Create all knowledgebase indices if missing."""
    setup = KnowledgebaseSetup(client)
    setup.ensure_indices(build_default_specs())


def resolve_index_name(folder: str, records: list[dict[str, Any]]) -> str:
    """Resolve the index name from recordType."""
    for record in records:
        record_type = record.get("recordType")
        if record_type:
            return str(record_type)
    raise ValueError(f"Missing recordType for folder: {folder}")


def main(data_dir: str | Path = "daily_output_7d") -> None:
    """Reindex data from daily output files."""
    url = ELASTIC_API_URL or ES_LOCAL_URL
    api_key = ELASTIC_API_KEY or ES_LOCAL_API_KEY
    client = build_client(url, api_key)
    ensure_indices(client)

    base = Path(data_dir)
    if not base.is_absolute():
        base = Path(__file__).resolve().parents[1] / base
    total_indexed = 0
    for folder, id_builder in INDEX_BUILDERS.items():
        list_path = base / folder / "list.json"
        records = load_json(list_path)
        if not records:
            logger.info("No records for %s", folder)
            continue
        normalize_dates(records)
        for record in records:
            id_builder(record)
        index_name = resolve_index_name(folder, records)
        indexed, errors = index_records(client, index_name, records, id_builder)
        total_indexed += indexed
        if errors:
            logger.warning(
                "%s errors indexing %s (showing first 3)",
                len(errors),
                index_name,
            )
            for error in errors[:3]:
                logger.warning("Index error: %s", error)
        logger.info("Indexed %s records into %s", indexed, index_name)

    logger.info("Total indexed records: %s", total_indexed)


if __name__ == "__main__":
    main()
