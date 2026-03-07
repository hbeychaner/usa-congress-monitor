"""Script to generate new progress tracking chunks for the latest congress and endpoints."""

import asyncio
from datetime import datetime, timedelta
from knowledgebase.client import build_client
from knowledgebase.progress import (
    ensure_tracking_index,
    upsert_chunk_progress,
    chunk_exists,
)
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.congress import gather_congresses
from src.data_collection.queueing.specs import SPECS
from settings import ELASTIC_API_URL, ELASTIC_API_KEY, CONGRESS_API_KEY


async def main():
    """
    Main chunk generator for progress tracking.
    All endpoint-specific logic (meta fields, chunk key) is spec-driven via SPECS.
    Meta is constructed for each chunk using spec.meta_fields for consistency.
    """
    # Endpoints supporting date/time chunking (from swagger.yaml)
    date_based_endpoints = [
        "bill",
        "amendment",
        "summaries",
        "congressional-record",
        "daily-congressional-record",
        "bound-congressional-record",
        "house-communication",
        "senate-communication",
        "committee-report",
        "committee-meeting",
        "committee-print",
        "hearing",
        "nomination",
        "crsreport",
        "treaty",
    ]

    date_windows = []
    today = datetime.utcnow()
    start_date = today.replace(year=today.year - 75, month=1, day=1)
    window_size = 180
    while start_date < today:
        end_date = start_date + timedelta(days=window_size)
        date_windows.append(
            (
                start_date.strftime("%Y-%m-%dT00:00:00Z"),
                end_date.strftime("%Y-%m-%dT00:00:00Z"),
            )
        )
        start_date = end_date

    es = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    await ensure_tracking_index(es)

    def _sanitize_meta(m: dict) -> dict:
        """Return a copy of meta only containing keys with non-None values."""
        if not isinstance(m, dict):
            return {}
        return {k: v for k, v in m.items() if v is not None}

    # Generate date-based chunks for all endpoints supporting date/time
    for endpoint in date_based_endpoints:
        for from_date, to_date in date_windows:
            chunk_key = f"{from_date}:{to_date}"
            meta = {
                "fromDateTime": from_date,
                "toDateTime": to_date,
            }
            if not await chunk_exists(es, endpoint, chunk_key):
                await upsert_chunk_progress(es, endpoint, chunk_key, "pending", _sanitize_meta(meta))

    cdg_client = CDGClient(api_key=CONGRESS_API_KEY)
    # Get all congresses
    congresses = gather_congresses(cdg_client)
    bill_types = ["HR", "S", "HJRES", "SJRES", "HCONRES", "SCONRES", "HRES", "SRES"]
    chambers = ["house", "senate"]  # Only 'house' and 'senate' are valid in API
    report_types = ["hrpt", "srpt"]  # Only 'hrpt' and 'srpt' are valid in API
    communication_types = ["ec", "pm"]  # Only 'ec' and 'pm' are valid in API
    house_vote_sessions = ["1", "2"]  # Sessions are '1' and '2'

    # Example years for demonstration; in production, fetch these dynamically
    years = list(range(1951, 2027))
    # For volumes, do not specify explicit numbers; fetch or enumerate dynamically as needed

    date_windows = []
    today = datetime.utcnow()
    start_date = today.replace(year=today.year - 2, month=1, day=1)
    window_size = 7  # days
    while start_date < today:
        end_date = start_date + timedelta(days=window_size)
        date_windows.append(
            (
                start_date.strftime("%Y-%m-%dT00:00:00Z"),
                end_date.strftime("%Y-%m-%dT00:00:00Z"),
            )
        )
        start_date = end_date

    # Per-congress chunking for endpoints that require it
    for congress in congresses:
        congress_num = int(congress["number"])
        # Bound Congressional Record chunks (by year)
        for year in years:
            chunk_key = f"{year}"
            meta = {
                field: year for field in SPECS["bound-congressional-record"].meta_fields
            }
            if not await chunk_exists(es, "bound-congressional-record", chunk_key):
                await upsert_chunk_progress(
                    es, "bound-congressional-record", chunk_key, "pending", _sanitize_meta(meta)
                )
        # Committee chunks
        for chamber in chambers:
            chunk_key = f"{congress_num}:{chamber}"
            base_meta = {"congress": congress_num, "chamber": chamber}
            meta = {field: base_meta[field] for field in SPECS["committee"].meta_fields if field in base_meta}
            if not await chunk_exists(es, "committee", chunk_key):
                await upsert_chunk_progress(es, "committee", chunk_key, "pending", _sanitize_meta(meta))
            if not await chunk_exists(es, "committee-meeting", chunk_key):
                await upsert_chunk_progress(
                    es, "committee-meeting", chunk_key, "pending", _sanitize_meta(meta)
                )
            if not await chunk_exists(es, "committee-print", chunk_key):
                await upsert_chunk_progress(
                    es, "committee-print", chunk_key, "pending", _sanitize_meta(meta)
                )
            if not await chunk_exists(es, "hearing", chunk_key):
                await upsert_chunk_progress(es, "hearing", chunk_key, "pending", _sanitize_meta(meta))
        # Committee Report
        for report_type in report_types:
            chunk_key = f"{congress_num}:{report_type}"
            base_meta = {"congress": congress_num, "report_type": report_type}
            meta = {field: base_meta[field] for field in SPECS["committee-report"].meta_fields if field in base_meta}
            if not await chunk_exists(es, "committee-report", chunk_key):
                await upsert_chunk_progress(
                    es, "committee-report", chunk_key, "pending", _sanitize_meta(meta)
                )
        # Congress
        chunk_key = f"{congress_num}"
        meta = {field: congress_num for field in SPECS["congress"].meta_fields}
        if not await chunk_exists(es, "congress", chunk_key):
            await upsert_chunk_progress(es, "congress", chunk_key, "pending", _sanitize_meta(meta))
        # CRS Report (by year)
        for year in years:
            chunk_key = f"{year}"
            meta = {field: year for field in SPECS["crsreport"].meta_fields}
            if not await chunk_exists(es, "crsreport", chunk_key):
                await upsert_chunk_progress(es, "crsreport", chunk_key, "pending", _sanitize_meta(meta))
        # Daily Congressional Record (paginated by congress)
        # Create a single paginated chunk per congress instead of enumerating volumes
        chunk_key = f"{congress_num}"
        meta = {field: congress_num for field in SPECS["daily-congressional-record"].meta_fields if field == "congress"}
        if not await chunk_exists(es, "daily-congressional-record", chunk_key):
            await upsert_chunk_progress(
                es, "daily-congressional-record", chunk_key, "pending", _sanitize_meta(meta)
            )
        # House Communication
        for comm_type in communication_types:
            chunk_key = f"{congress_num}:{comm_type}"
            if not await chunk_exists(es, "house-communication", chunk_key):
                await upsert_chunk_progress(
                    es, "house-communication", chunk_key, "pending"
                )
        # House Requirement
        chunk_key = f"{congress_num}"
        if not await chunk_exists(es, "house-requirement", chunk_key):
            meta = {field: congress_num for field in SPECS["house-requirement"].meta_fields if field == "congress"}
            await upsert_chunk_progress(es, "house-requirement", chunk_key, "pending", _sanitize_meta(meta))
        # House Roll Call Vote
        for session in house_vote_sessions:
            chunk_key = f"{congress_num}:{session}"
            if not await chunk_exists(es, "house-vote", chunk_key):
                await upsert_chunk_progress(es, "house-vote", chunk_key, "pending")
        # Member
        if not await chunk_exists(es, "member", chunk_key):
            await upsert_chunk_progress(es, "member", chunk_key, "pending")
        # Nomination
        if not await chunk_exists(es, "nomination", chunk_key):
            await upsert_chunk_progress(es, "nomination", chunk_key, "pending")
        # Senate Communication
        for comm_type in communication_types:
            chunk_key = f"{congress_num}:{comm_type}"
            if not await chunk_exists(es, "senate-communication", chunk_key):
                await upsert_chunk_progress(
                    es, "senate-communication", chunk_key, "pending"
                )
        # Treaty
        if not await chunk_exists(es, "treaty", chunk_key):
            await upsert_chunk_progress(es, "treaty", chunk_key, "pending")
        # Bound Congressional Record chunks
        for year in years:
            chunk_key = f"{year}"
            meta = {
                field: year for field in SPECS["bound-congressional-record"].meta_fields
            }
            if not await chunk_exists(es, "bound-congressional-record", chunk_key):
                await upsert_chunk_progress(
                    es, "bound-congressional-record", chunk_key, "pending", _sanitize_meta(meta)
                )
        # Committee chunks
        for chamber in chambers:
            chunk_key = f"{congress_num}:{chamber}"
            base_meta = {"congress": congress_num, "chamber": chamber}
            meta = {field: base_meta[field] for field in SPECS["committee"].meta_fields if field in base_meta}
            if not await chunk_exists(es, "committee", chunk_key):
                await upsert_chunk_progress(es, "committee", chunk_key, "pending", _sanitize_meta(meta))
            # Committee Meeting
            if not await chunk_exists(es, "committee-meeting", chunk_key):
                await upsert_chunk_progress(
                    es, "committee-meeting", chunk_key, "pending", _sanitize_meta(meta)
                )
            # Committee Print
            if not await chunk_exists(es, "committee-print", chunk_key):
                await upsert_chunk_progress(
                    es, "committee-print", chunk_key, "pending", _sanitize_meta(meta)
                )
            # Hearing
            if not await chunk_exists(es, "hearing", chunk_key):
                await upsert_chunk_progress(es, "hearing", chunk_key, "pending", _sanitize_meta(meta))
        # Committee Report
        for report_type in report_types:
            chunk_key = f"{congress_num}:{report_type}"
            base_meta = {"congress": congress_num, "report_type": report_type}
            meta = {field: base_meta[field] for field in SPECS["committee-report"].meta_fields if field in base_meta}
            if not await chunk_exists(es, "committee-report", chunk_key):
                await upsert_chunk_progress(
                    es, "committee-report", chunk_key, "pending", _sanitize_meta(meta)
                )
        # Congress
        chunk_key = f"{congress_num}"
        meta = {field: congress_num for field in SPECS["congress"].meta_fields}
        if not await chunk_exists(es, "congress", chunk_key):
            await upsert_chunk_progress(es, "congress", chunk_key, "pending", meta)
        # CRS Report (by year)
        for year in years:
            chunk_key = f"{year}"
            meta = {field: year for field in SPECS["crsreport"].meta_fields}
            if not await chunk_exists(es, "crsreport", chunk_key):
                await upsert_chunk_progress(es, "crsreport", chunk_key, "pending", meta)
        # Daily Congressional Record (paginated by congress)
        # House Communication
        for comm_type in communication_types:
            chunk_key = f"{congress_num}:{comm_type}"
            if not await chunk_exists(es, "house-communication", chunk_key):
                await upsert_chunk_progress(
                    es, "house-communication", chunk_key, "pending"
                )
        # House Requirement
        chunk_key = f"{congress_num}"
        if not await chunk_exists(es, "house-requirement", chunk_key):
            meta = {field: congress_num for field in SPECS["house-requirement"].meta_fields if field == "congress"}
            await upsert_chunk_progress(es, "house-requirement", chunk_key, "pending", _sanitize_meta(meta))
        # House Roll Call Vote
        for session in house_vote_sessions:
            chunk_key = f"{congress_num}:{session}"
            if not await chunk_exists(es, "house-vote", chunk_key):
                await upsert_chunk_progress(es, "house-vote", chunk_key, "pending")
        # Member
        if not await chunk_exists(es, "member", chunk_key):
            await upsert_chunk_progress(es, "member", chunk_key, "pending")
        # Nomination
        if not await chunk_exists(es, "nomination", chunk_key):
            await upsert_chunk_progress(es, "nomination", chunk_key, "pending")
        # Senate Communication
        for comm_type in communication_types:
            chunk_key = f"{congress_num}:{comm_type}"
            if not await chunk_exists(es, "senate-communication", chunk_key):
                await upsert_chunk_progress(
                    es, "senate-communication", chunk_key, "pending"
                )
        # Summaries
        for bill_type in bill_types:
            chunk_key = f"{congress_num}:{bill_type}"
            if not await chunk_exists(es, "summaries", chunk_key):
                await upsert_chunk_progress(es, "summaries", chunk_key, "pending")
        # Treaty
        if not await chunk_exists(es, "treaty", chunk_key):
            await upsert_chunk_progress(es, "treaty", chunk_key, "pending")
    await es.close()
    print("Chunk generation complete for all congresses.")


if __name__ == "__main__":
    asyncio.run(main())
