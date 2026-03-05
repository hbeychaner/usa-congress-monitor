"""Script to generate new progress tracking chunks for the latest congress and endpoints."""

import asyncio
from knowledgebase.client import build_client
from knowledgebase.progress import (
    ensure_tracking_index,
    upsert_chunk_progress,
    chunk_exists,
)
from src.data_collection.client import CDGClient
from src.data_collection.endpoints.congress import (
    gather_congresses,
)

from settings import ELASTIC_API_URL, ELASTIC_API_KEY, CONGRESS_API_KEY


async def main():
    """
    Main chunk generator for progress tracking.
    All endpoint-specific logic (meta fields, chunk key) is spec-driven via SPECS.
    Meta is constructed for each chunk using spec.meta_fields for consistency.
    """
    es = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    await ensure_tracking_index(es)
    cdg_client = CDGClient(api_key=CONGRESS_API_KEY)
    # Get all congresses
    congresses = gather_congresses(cdg_client)
    bill_types = ["HR", "S", "HJRES", "SJRES", "HCONRES", "SCONRES", "HRES", "SRES"]
    amendment_types = ["HAMDT", "SAMDT", "SUAMDT"]
    chambers = ["house", "senate", "joint"]
    report_types = ["hrpt", "srpt", "hprt", "sprt"]
    communication_types = ["ec", "pm", "sd"]
    house_vote_sessions = ["1", "2"]

    # Example years and volumeNumbers for demonstration; in production, fetch these dynamically
    years = list(range(1973, 2025))
    volume_numbers = list(range(93, 120))

    from src.data_collection.queueing.specs import SPECS

    for congress in congresses:
        congress_num = int(congress["number"])
        # Bill chunks
        for bill_type in bill_types:
            chunk_key = f"{congress_num}:{bill_type}"
            meta = {
                field: value
                for field, value in zip(
                    SPECS["bill"].meta_fields,
                    [congress_num, None, None, None, congress_num, bill_type],
                )
                if value is not None
            }
            if not await chunk_exists(es, "bill", chunk_key):
                await upsert_chunk_progress(es, "bill", chunk_key, "pending", meta)
        # Amendment chunks
        for amend_type in amendment_types:
            chunk_key = f"{congress_num}:{amend_type}"
            meta = {
                field: value
                for field, value in zip(
                    SPECS["amendment"].meta_fields,
                    [congress_num, None, None, None, congress_num, amend_type],
                )
                if value is not None
            }
            if not await chunk_exists(es, "amendment", chunk_key):
                await upsert_chunk_progress(es, "amendment", chunk_key, "pending", meta)
        # Bound Congressional Record chunks
        for year in years:
            chunk_key = f"{year}"
            meta = {
                field: year for field in SPECS["bound-congressional-record"].meta_fields
            }
            if not await chunk_exists(es, "bound-congressional-record", chunk_key):
                await upsert_chunk_progress(
                    es, "bound-congressional-record", chunk_key, "pending", meta
                )
        # Committee chunks
        for chamber in chambers:
            chunk_key = f"{congress_num}:{chamber}"
            meta = {
                field: value
                for field, value in zip(
                    SPECS["committee"].meta_fields,
                    [congress_num, None, None, None, congress_num, chamber],
                )
                if value is not None
            }
            if not await chunk_exists(es, "committee", chunk_key):
                await upsert_chunk_progress(es, "committee", chunk_key, "pending", meta)
            # Committee Meeting
            if not await chunk_exists(es, "committee-meeting", chunk_key):
                await upsert_chunk_progress(
                    es, "committee-meeting", chunk_key, "pending", meta
                )
            # Committee Print
            if not await chunk_exists(es, "committee-print", chunk_key):
                await upsert_chunk_progress(
                    es, "committee-print", chunk_key, "pending", meta
                )
            # Hearing
            if not await chunk_exists(es, "hearing", chunk_key):
                await upsert_chunk_progress(es, "hearing", chunk_key, "pending", meta)
        # Committee Report
        for report_type in report_types:
            chunk_key = f"{congress_num}:{report_type}"
            meta = {
                field: value
                for field, value in zip(
                    SPECS["committee-report"].meta_fields,
                    [congress_num, None, None, None, congress_num, report_type],
                )
                if value is not None
            }
            if not await chunk_exists(es, "committee-report", chunk_key):
                await upsert_chunk_progress(
                    es, "committee-report", chunk_key, "pending", meta
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
        # Daily Congressional Record (by volumeNumber)
        for volume in volume_numbers:
            chunk_key = f"{volume}"
            if not await chunk_exists(es, "daily-congressional-record", chunk_key):
                await upsert_chunk_progress(
                    es, "daily-congressional-record", chunk_key, "pending"
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
            await upsert_chunk_progress(es, "house-requirement", chunk_key, "pending")
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
