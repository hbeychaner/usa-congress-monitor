"""Load bill and member list data into Elasticsearch."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, Iterable

from elasticsearch import AsyncElasticsearch
from elasticsearch.helpers import async_bulk

from settings import ELASTIC_API_KEY, ELASTIC_API_URL, ES_LOCAL_API_KEY, ES_LOCAL_URL
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_BILLS_INDEX = "congress-bills"
DEFAULT_MEMBERS_INDEX = "congress-members"

BILLS_MAPPING = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            "congress": {"type": "integer"},
            "type": {"type": "keyword"},
            "number": {"type": "keyword"},
            "title": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "originChamber": {"type": "keyword"},
            "originChamberCode": {"type": "keyword"},
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "updateDateIncludingText": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
            "url": {"type": "keyword"},
            "latestAction": {
                "properties": {
                    "actionDate": {
                        "type": "date",
                        "format": "strict_date_optional_time||yyyy-MM-dd",
                    },
                    "text": {
                        "type": "text",
                        "fields": {"keyword": {"type": "keyword"}},
                    },
                }
            },
        },
    },
}

MEMBERS_MAPPING = {
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword"},
            "bioguideId": {"type": "keyword"},
            "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "fullName": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "partyName": {"type": "keyword"},
            "party": {"type": "keyword"},
            "state": {"type": "keyword"},
            "district": {"type": "integer"},
            "url": {"type": "keyword"},
            "depiction": {
                "properties": {
                    "imageUrl": {"type": "keyword"},
                    "attribution": {"type": "text"},
                }
            },
            "updateDate": {
                "type": "date",
                "format": "strict_date_optional_time||yyyy-MM-dd",
            },
        },
    },
}


def build_client(url: str | None, api_key: str | None) -> AsyncElasticsearch:
    """Create an Elasticsearch client using API key auth."""
    if not url:
        raise ValueError("ELASTIC_API_URL is required.")
    if not api_key:
        raise ValueError("ELASTIC_API_KEY is required.")
    return AsyncElasticsearch(url, api_key=api_key, request_timeout=60)


async def ensure_index(
    client: AsyncElasticsearch, index_name: str, mapping: dict[str, Any]
) -> None:
    """Create the index if it does not exist."""
    if await client.indices.exists(index=index_name):
        return
    await client.indices.create(
        index=index_name,
        settings=mapping.get("settings", {}),
        mappings=mapping.get("mappings", {}),
    )


def load_json(path: Path) -> list[dict[str, Any]]:
    """Load JSON list data from a file."""
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected list data in {path}")
    return data


def bill_id(record: dict[str, Any]) -> str:
    """Build a stable bill document id."""
    congress = record.get("congress")
    bill_type = str(record.get("type", "")).lower()
    number = record.get("number")
    return f"bill-{congress}-{bill_type}-{number}"


def member_id(record: dict[str, Any]) -> str:
    """Build a stable member document id."""
    return str(record.get("bioguideId") or record.get("bioguide_id") or "")


def build_actions(
    index_name: str, records: Iterable[dict[str, Any]], id_builder
) -> list[dict[str, Any]]:
    """Prepare bulk actions for Elasticsearch."""
    actions: list[dict[str, Any]] = []
    for record in records:
        record_id = id_builder(record)
        if not record_id:
            continue
        record["id"] = record_id
        actions.append(
            {
                "_op_type": "index",
                "_index": index_name,
                "_id": record_id,
                "_source": record,
            }
        )
    return actions


async def load_index(
    client: AsyncElasticsearch,
    index_name: str,
    records: list[dict[str, Any]],
    id_builder,
) -> int:
    """Load data into Elasticsearch using bulk indexing."""
    actions = build_actions(index_name, records, id_builder)
    if not actions:
        return 0
    success, _ = await async_bulk(
        client, actions, chunk_size=500, request_timeout=120
    )
    return success


async def run(data_dir: Path, bills_index: str, members_index: str) -> None:
    """Load bill and member list data into Elasticsearch."""
    url = ELASTIC_API_URL or ES_LOCAL_URL
    api_key = ELASTIC_API_KEY or ES_LOCAL_API_KEY

    client = build_client(url, api_key)

    await ensure_index(client, bills_index, BILLS_MAPPING)
    await ensure_index(client, members_index, MEMBERS_MAPPING)

    bills_path = data_dir / "bill" / "list.json"
    members_path = data_dir / "member" / "list.json"

    bills = load_json(bills_path)
    members = load_json(members_path)

    bills_loaded = await load_index(client, bills_index, bills, bill_id)
    members_loaded = await load_index(client, members_index, members, member_id)

    logger.info("Loaded %s bill records into %s", bills_loaded, bills_index)
    logger.info("Loaded %s member records into %s", members_loaded, members_index)
    await client.close()


def main() -> None:
    """CLI entrypoint."""
    repo_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("daily_output_7d"),
        help="Directory containing daily output folders.",
    )
    parser.add_argument(
        "--bills-index",
        default=DEFAULT_BILLS_INDEX,
        help="Elasticsearch index name for bills.",
    )
    parser.add_argument(
        "--members-index",
        default=DEFAULT_MEMBERS_INDEX,
        help="Elasticsearch index name for members.",
    )
    args = parser.parse_args()
    data_dir = args.data_dir
    if not data_dir.is_absolute():
        data_dir = repo_root / data_dir

    asyncio.run(run(data_dir, args.bills_index, args.members_index))


if __name__ == "__main__":
    main()
