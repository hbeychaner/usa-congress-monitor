"""
Recovery script: For each target (bill, member, law, amendment),
fetch all records from the API, check if their ID exists in ES,
and bulk index only missing records.
"""

from __future__ import annotations
import asyncio
from settings import CONGRESS_API_KEY, ELASTIC_API_URL, ELASTIC_API_KEY
from src.data_collection.client import CDGClient
from knowledgebase.client import build_client
from src.data_collection.queueing.specs import SPECS, fetch_page, fetch_law_page
from src.data_collection.specialized.common import ensure_index, existing_ids


async def recover_target(target: str, es_client, cdg_client, law_congress=None):
    spec = SPECS[target]
    index_name = spec.index_name
    await ensure_index(es_client, index_name, spec.mapping)
    print(f"Scanning existing IDs for {target}...")
    existing = await existing_ids(es_client, index_name)
    print(f"Found {len(existing)} existing IDs in ES for {target}.")
    print(f"Fetching all records from API for {target}...")
    offset = 0
    page_size = 100  # reduced for API stability
    missing_records = []
    max_attempts = 5
    while True:
        attempt = 0
        while attempt < max_attempts:
            try:
                if target == "law":
                    if law_congress is None:
                        print("Skipping law: congress not specified.")
                        return
                    page = await asyncio.to_thread(
                        fetch_law_page,
                        cdg_client,
                        congress=law_congress,
                        offset=offset,
                        limit=page_size,
                    )
                else:
                    page = await asyncio.to_thread(
                        fetch_page, target, cdg_client, offset=offset, limit=page_size
                    )
                records = page.get(spec.data_key, [])
                break  # success, exit retry loop
            except Exception as e:
                wait_time = 2**attempt * 0.5
                print(
                    f"Error fetching page at offset {offset} (attempt {attempt + 1}/{max_attempts}): {e}"
                )
                await asyncio.sleep(wait_time)
                attempt += 1
        else:
            print(
                f"Failed to fetch page at offset {offset} after {max_attempts} attempts. Skipping."
            )
            break
        for record in records:
            record_id = spec.id_builder(record)
            if str(record_id) not in existing:
                missing_records.append(record)
        offset += page_size
        await asyncio.sleep(0.5)  # rate limit between requests
        if len(records) < page_size:
            break
    print(f"Found {len(missing_records)} missing records for {target}.")
    if missing_records:
        from knowledgebase.indexing import index_records

        print(f"Indexing missing records for {target}...")
        indexed, errors = await index_records(
            es_client, index_name, missing_records, spec.id_builder, chunk_size=200
        )
        print(f"Indexed {indexed} records for {target}. Errors: {len(errors)}")
    else:
        print(f"No missing records to index for {target}.")


async def main():
    cdg_client = CDGClient(api_key=CONGRESS_API_KEY)
    es_client = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    # For law, get current congress
    law_congress = None
    if "law" in SPECS:
        from src.data_collection.endpoints.congress import get_current_congress

        current = await asyncio.to_thread(get_current_congress, cdg_client)
        law_congress = int(current.get("congress", {}).get("number", 0))
    for target in SPECS:
        await recover_target(target, es_client, cdg_client, law_congress=law_congress)
    await es_client.close()


if __name__ == "__main__":
    asyncio.run(main())
