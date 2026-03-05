"""Consume RabbitMQ messages and index into Elasticsearch."""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import traceback

from elasticsearch import AsyncElasticsearch

from knowledgebase.client import build_client
from knowledgebase.progress import mark_chunk_complete
from settings import (
    ELASTIC_API_KEY,
    ELASTIC_API_URL,
    RABBITMQ_PREFETCH,
    RABBITMQ_URL,
)
from src.data_collection.queueing.rabbitmq import connect, consume_json
from src.data_collection.queueing.specs import SPECS
from src.data_collection.specialized.common import ensure_index, index_missing_records

# Custom Elasticsearch log handler
from logging import Handler, LogRecord, INFO


class ElasticsearchLogHandler(Handler):
    def __init__(self, es_client, index_name):
        super().__init__()
        self.es_client = es_client
        self.index_name = index_name

    def emit(self, record: LogRecord):
        try:
            log_entry = {
                "level": record.levelname,
                "message": self.format(record),
                "module": record.module,
                "funcName": record.funcName,
                "time": record.created,
            }
            # Use synchronous index for logging
            import datetime

            log_entry["timestamp"] = datetime.datetime.utcnow().isoformat()
            try:
                self.es_client.index(index=self.index_name, document=log_entry)
            except Exception:
                pass
        except Exception:
            pass


def get_es_logger(es_client):
    import logging

    logger = logging.getLogger("congress_ingest")
    logger.setLevel(INFO)
    # Remove other handlers
    logger.handlers = []
    handler = ElasticsearchLogHandler(es_client, "logs-congress-ingest")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


def _resolve_targets(raw: str) -> set[str]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts or "all" in parts:
        return set(SPECS.keys())
    unknown = [part for part in parts if part not in SPECS]
    if unknown:
        raise RuntimeError(f"Unknown targets: {', '.join(sorted(unknown))}")
    return set(parts)


async def run(targets: str) -> None:
    if not ELASTIC_API_URL or not ELASTIC_API_KEY:
        raise RuntimeError("ELASTIC_API_URL and ELASTIC_API_KEY are required")

    endpoint = targets.strip()
    queue_name = f"{endpoint}_queue"
    es_client: AsyncElasticsearch = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    logger = get_es_logger(es_client)
    conn = await connect(RABBITMQ_URL)
    channel = await conn.channel()
    await channel.declare_queue(queue_name, durable=True)

    from src.data_collection.client import CDGClient
    from src.data_collection.queueing.specs import fetch_page

    async def handler(payload: dict) -> None:
        """
        Ingest handler for RabbitMQ consumer.
        All endpoint-specific logic (chunk key, meta fields, data key, id function) is spec-driven via SPECS.
        Assumes meta and chunk_key are constructed according to spec for each endpoint.
        """
        try:
            chunk_key = payload.get("chunk_key")
            meta = payload.get("meta", {})
            logger.info(f"Processing chunk: endpoint={endpoint}, chunk_key={chunk_key}")
            spec = SPECS.get(endpoint)
            if spec is None:
                logger.error(f"No spec found for endpoint: {endpoint}")
                return
            index_name = spec.es_index
            await ensure_index(es_client, index_name, spec.es_mapping)
            # Validate meta fields
            missing_fields = [field for field in spec.meta_fields if field not in meta]
            if missing_fields:
                logger.error(
                    f"Meta missing fields for endpoint={endpoint}: {missing_fields}"
                )
                return
            # Validate chunk key
            expected_chunk_key = spec.chunk_key_func(meta, meta.get("congress"))
            if chunk_key != expected_chunk_key:
                logger.warning(
                    f"Chunk key mismatch for endpoint={endpoint}: expected {expected_chunk_key}, got {chunk_key}"
                )
            client = CDGClient(api_key=str(meta.get("api_key") or ""))
            # Filter meta fields according to endpoint requirements
            # See documentation/original/*Endpoint.md for details
            endpoint_args = {
                "bill": ["congress", "type", "offset", "limit"],
                "summaries": ["congress", "type", "offset", "limit"],
                "member": ["congress", "offset", "limit", "currentMember"],
                "amendment": ["congress", "type", "offset", "limit"],
                "committee": ["congress", "chamber", "offset", "limit"],
                "committee-meeting": ["congress", "chamber", "offset", "limit"],
                "committee-report": ["congress", "report_type", "offset", "limit"],
                "hearing": ["congress", "chamber", "offset", "limit"],
                "nomination": ["congress", "offset", "limit"],
                "bound-congressional-record": ["year", "offset", "limit"],
                "daily-congressional-record": ["volumeNumber", "offset", "limit"],
                "crsreport": ["year", "offset", "limit"],
                "treaty": ["congress", "offset", "limit"],
                "house-requirement": ["congress", "offset", "limit"],
                "house-vote": ["congress", "session", "offset", "limit"],
                "senate-communication": ["congress", "type", "offset", "limit"],
                "house-communication": ["congress", "type", "offset", "limit"],
                "congress": ["congress", "offset", "limit"],
            }
            allowed_args = endpoint_args.get(endpoint, list(meta.keys()))
            filtered_meta = {k: v for k, v in meta.items() if k in allowed_args}
            try:
                records = fetch_page(endpoint, client, **filtered_meta).get(
                    spec.api_data_key, []
                )
                # Mark chunk as in_progress after successful API fetch
                if chunk_key is not None:
                    from knowledgebase.progress import upsert_chunk_progress

                    await upsert_chunk_progress(
                        es_client, endpoint, chunk_key, "in_progress", meta
                    )
                    logger.info(
                        f"Marked chunk as in_progress: endpoint={endpoint}, chunk_key={chunk_key}"
                    )
            except Exception as api_exc:
                logger.error(
                    f"API fetch failed for endpoint={endpoint}, chunk_key={chunk_key}: {api_exc}"
                )
                logger.error(traceback.format_exc())
                # Revert chunk to pending on error
                if chunk_key is not None:
                    from knowledgebase.progress import upsert_chunk_progress

                    await upsert_chunk_progress(
                        es_client, endpoint, chunk_key, "pending", meta
                    )
                    logger.info(
                        f"Reverted chunk to pending: endpoint={endpoint}, chunk_key={chunk_key}"
                    )
                return
            if not records:
                logger.warning(f"No records found in chunk: {chunk_key}")
                return
            for record in records:
                spec.id_func(record)
            await index_missing_records(
                es_client,
                index_name,
                records,
                spec.id_func,
                chunk_size=200,
            )
            logger.info(f"Indexed {len(records)} records for chunk {chunk_key}")
            # Mark chunk as complete
            if chunk_key is not None:
                await mark_chunk_complete(es_client, endpoint, chunk_key, meta)
                logger.info(
                    f"Marked chunk as complete: endpoint={endpoint}, chunk_key={chunk_key}"
                )
            else:
                logger.error(
                    "chunk_key is missing from payload; cannot mark chunk as complete."
                )
        except Exception as e:
            logger.error(
                f"Error processing chunk: endpoint={endpoint}, chunk_key={payload.get('chunk_key')}, error={e}"
            )
            logger.error(traceback.format_exc())

    await consume_json(
        channel,
        queue_name,
        handler,
        prefetch_count=RABBITMQ_PREFETCH,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consume RabbitMQ messages for indexing."
    )
    parser.add_argument(
        "endpoint",
        help="Endpoint to consume (e.g., bill, amendment, committee, etc.) or 'all' for all endpoints.",
    )
    args = parser.parse_args()
    if args.endpoint == "all":
        # List all endpoints from SPECS
        endpoints = list(SPECS.keys())
        procs = []
        for endpoint in endpoints:
            print(f"Launching consumer for endpoint: {endpoint}")
            proc = subprocess.Popen(["python", __file__, endpoint])
            procs.append(proc)
        # Wait for all subprocesses to finish
        for proc in procs:
            proc.wait()
    else:
        asyncio.run(run(args.endpoint))


if __name__ == "__main__":
    main()
