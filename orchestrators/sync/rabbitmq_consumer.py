"""Consume RabbitMQ messages and index into Elasticsearch."""

from __future__ import annotations

import argparse
import asyncio
import traceback

# Custom Elasticsearch log handler
from logging import INFO, Handler, LogRecord

from elasticsearch import AsyncElasticsearch, Elasticsearch

from knowledgebase.client import build_client
from knowledgebase.progress import mark_chunk_complete
from settings import (
    CONGRESS_API_KEY,
    ELASTIC_API_KEY,
    ELASTIC_API_URL,
    RABBITMQ_PREFETCH,
    RABBITMQ_URL,
)
from src.data_collection.queueing.consumer_core import fetch_and_parse
from src.data_collection.queueing.rabbitmq import connect, consume_json
from src.data_collection.queueing.specs import SPECS
from src.data_collection.specialized.common import ensure_index, index_missing_records
from src.data_collection.queueing.rabbitmq import (
    parse_date_chunk_key,
)


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
            import datetime

            log_entry["timestamp"] = datetime.datetime.utcnow().isoformat()
            # Use the synchronous Elasticsearch client for logging
            try:
                # Use localhost and default API key for logging
                es_sync = Elasticsearch(ELASTIC_API_URL, api_key=ELASTIC_API_KEY)
                es_sync.index(index=self.index_name, document=log_entry)
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
    es_handler = ElasticsearchLogHandler(es_client, "logs-congress-ingest")
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    es_handler.setFormatter(formatter)
    logger.addHandler(es_handler)
    # Add console handler for terminal output
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def _resolve_targets(raw: str) -> set[str]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts or "all" in parts:
        return set(SPECS.keys())
    unknown = [part for part in parts if part not in SPECS]
    if unknown:
        raise RuntimeError(f"Unknown targets: {', '.join(sorted(unknown))}")
    return set(parts)


async def run(targets: str, once: bool = False) -> None:
    if not ELASTIC_API_URL or not ELASTIC_API_KEY:
        raise RuntimeError("ELASTIC_API_URL and ELASTIC_API_KEY are required")

    endpoint = targets.strip()
    queue_name = f"{endpoint}_queue"
    es_client: AsyncElasticsearch = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    logger = get_es_logger(es_client)
    conn = await connect(RABBITMQ_URL)
    channel = await conn.channel()
    await channel.declare_queue(queue_name, durable=True)

    # Get total number of chunks for this endpoint
    from elasticsearch import Elasticsearch

    from knowledgebase.progress import upsert_chunk_progress
    from src.data_collection.client import CDGClient

    es_sync = Elasticsearch(ELASTIC_API_URL, api_key=ELASTIC_API_KEY)
    progress_index = "congress-progress-tracking"
    total_chunks = es_sync.count(
        index=progress_index,
        body={
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"endpoint": endpoint}},
                        {"term": {"status": "pending"}},
                    ]
                }
            }
        },
    ).get("count", 0)
    from tqdm import tqdm

    pbar = tqdm(total=total_chunks, desc=f"{endpoint} chunks", unit="chunk")

    processed_chunks = 0

    async def handler(payload: dict) -> None:
        """
        Ingest handler for RabbitMQ consumer.
        All endpoint-specific logic (chunk key, meta fields, data key, id function) is spec-driven via SPECS.
        Assumes meta and chunk_key are constructed according to spec for each endpoint.
        """
        try:
            nonlocal processed_chunks, pbar
            chunk_key = payload.get("chunk_key")
            meta = payload.get("meta", {})

            def _has_valid_meta(m: dict) -> bool:
                if not isinstance(m, dict):
                    return False
                # Consider meta valid if at least one value is not None
                return any(v is not None for v in m.values())

            # Enforce that producers include structured `meta` in messages.
            if not _has_valid_meta(meta):
                logger.error(
                    f"[ERROR] Missing or empty meta in payload for endpoint={endpoint}, chunk_key={chunk_key}."
                    " Producer must include structured `meta`."
                )
                # Revert to pending so the chunk can be fixed and requeued.
                if chunk_key is not None:
                    await upsert_chunk_progress(
                        es_client, endpoint, chunk_key, "pending", meta
                    )
                return
            logger.info(
                f"[START] Picked up chunk: endpoint={endpoint}, chunk_key={chunk_key}, meta={meta}"
            )
            # Prefer explicit meta supplied by the producer. Only attempt to
            # extract a date range from `chunk_key` as a safe fallback when the
            # `meta` payload lacks `fromDateTime`/`toDateTime`.
            if endpoint in ["bill", "amendment", "summaries"] and chunk_key:
                if not meta.get("fromDateTime") or not meta.get("toDateTime"):
                    try:
                        date_meta = parse_date_chunk_key(chunk_key)
                        meta.update(date_meta)
                        logger.info(
                            f"[META] Extracted date meta from chunk_key={chunk_key}: {date_meta}"
                        )
                    except Exception:
                        logger.warning(
                            f"[META] Could not parse date range from chunk_key={chunk_key};"
                            " ensure producer includes explicit meta in the message"
                        )
            spec = SPECS.get(endpoint)
            if spec is None:
                logger.error(f"[ERROR] No spec found for endpoint: {endpoint}")
                return
            index_name = spec.es_index
            await ensure_index(es_client, index_name, spec.es_mapping)
            logger.info(f"[INDEX] Ensured ES index: {index_name}")
            # Validate meta fields.
            # `spec.meta_fields` includes pagination keys (offset, page, page_size, total_pages)
            # which are not required to be present on the chunk doc. Allow chunks that
            # provide an explicit date range (`fromDateTime`/`toDateTime`) to proceed;
            # otherwise require at least one identifying field (e.g., `congress`, `type`,
            # `chamber`, `year`) to be present and non-empty.
            pagination_keys = {"offset", "page", "page_size", "total_pages"}
            identifying_fields = [
                f for f in spec.meta_fields if f not in pagination_keys
            ]

            # If the chunk supplies a date range we accept it as a valid identifier
            # for date-based endpoints (bill, amendment, summaries, etc.). Otherwise
            # require at least one identifying field to be present.
            if not (meta.get("fromDateTime") and meta.get("toDateTime")):
                present = [
                    f
                    for f in identifying_fields
                    if f in meta and meta.get(f) is not None
                ]
                if not present:
                    logger.error(
                        f"[ERROR] Meta missing identifying fields for endpoint={endpoint}: expected one of {identifying_fields}, meta={meta}"
                    )
                    return
            client = CDGClient(api_key=str(meta.get("api_key") or CONGRESS_API_KEY))
            # Normalize meta to API params and optionally coerce via Pydantic models.
            from src.data_collection.queueing.specs import (
                prepare_api_meta,
                resolve_pagination_for_consumer,
            )

            api_meta, meta_obj, filtered_meta = prepare_api_meta(spec, meta)
            logger.info(
                f"[META] Resolved meta for endpoint={endpoint}: {meta} -> api_meta={api_meta}"
            )
            max_attempts = 5
            attempt = 0
            backoff_base = 2
            # Resolve pagination values (offset/limit) from validated meta or legacy meta
            offset, limit = resolve_pagination_for_consumer(
                endpoint, spec, meta, meta_obj, filtered_meta
            )
            logger.info(f"[FETCH] Will fetch page: offset={offset}, limit={limit}")
            while attempt < max_attempts:
                try:
                    logger.info(
                        f"[FETCH] Attempt {attempt + 1}/{max_attempts} for chunk_key={chunk_key}"
                    )
                    # Use consumer core to fetch and parse without duplicating logic
                    raw_resp, records = await asyncio.to_thread(
                        fetch_and_parse, endpoint, client, offset, limit, api_meta, spec
                    )
                    logger.info(
                        f"[FETCH] Got {len(records)} records for chunk_key={chunk_key}"
                    )
                    # Mark chunk as in_progress after successful API fetch
                    if chunk_key is not None:
                        await upsert_chunk_progress(
                            es_client, endpoint, chunk_key, "in_progress", meta
                        )
                        logger.info(
                            f"[PROGRESS] Marked chunk as in_progress: endpoint={endpoint}, chunk_key={chunk_key}"
                        )
                    break
                except Exception as api_exc:
                    wait_time = backoff_base**attempt
                    logger.error(
                        f"[ERROR] API fetch failed for endpoint={endpoint}, chunk_key={chunk_key}: {api_exc}"
                    )
                    logger.error(traceback.format_exc())
                    logger.warning(
                        f"[WAIT] Waiting {wait_time}s before retrying due to possible rate limiting (attempt {attempt + 1}/{max_attempts})"
                    )
                    await asyncio.sleep(wait_time)
                    attempt += 1
            else:
                # Revert chunk to pending on error after all attempts
                if chunk_key is not None:
                    await upsert_chunk_progress(
                        es_client, endpoint, chunk_key, "pending", meta
                    )
                    logger.info(
                        f"[PROGRESS] Reverted chunk to pending: endpoint={endpoint}, chunk_key={chunk_key} after {max_attempts} failed attempts"
                    )
                return
            if not records:
                logger.warning(f"[EMPTY] No records found in chunk: {chunk_key}")
                pbar.update(1)
                processed_chunks += 1
                logger.info(
                    f"[PROGRESS] {processed_chunks}/{total_chunks} chunks processed for {endpoint}"
                )
                return
            for record in records:
                spec.id_func(record)
            logger.info(
                f"[INDEX] Indexing {len(records)} records for chunk {chunk_key}"
            )
            await index_missing_records(
                es_client,
                index_name,
                records,
                spec.id_func,
                chunk_size=200,
            )
            logger.info(f"[INDEX] Indexed {len(records)} records for chunk {chunk_key}")
            # Mark chunk as complete
            if chunk_key is not None:
                await mark_chunk_complete(es_client, endpoint, chunk_key, meta)
                logger.info(
                    f"[PROGRESS] Marked chunk as complete: endpoint={endpoint}, chunk_key={chunk_key}"
                )
            else:
                logger.error(
                    "[ERROR] chunk_key is missing from payload; cannot mark chunk as complete."
                )
            pbar.update(1)
            processed_chunks += 1
            logger.info(
                f"[PROGRESS] {processed_chunks}/{total_chunks} chunks processed for {endpoint}"
            )
        except Exception as e:
            logger.error(
                f"[ERROR] Error processing chunk: endpoint={endpoint}, chunk_key={payload.get('chunk_key')}, error={e}"
            )
            logger.error(traceback.format_exc())
            # Revert chunk to pending on any error during ingest or completion marking
            chunk_key = payload.get("chunk_key")
            meta = payload.get("meta", {})
            if chunk_key is not None:
                await upsert_chunk_progress(
                    es_client, endpoint, chunk_key, "pending", meta
                )
                logger.info(
                    f"[PROGRESS] Reverted chunk to pending due to ingest error: endpoint={endpoint}, chunk_key={chunk_key}"
                )

    await consume_json(
        channel,
        queue_name,
        handler,
        prefetch_count=RABBITMQ_PREFETCH,
        max_messages=(1 if once else None),
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Consume RabbitMQ messages for indexing."
    )
    parser.add_argument(
        "endpoint",
        help="Endpoint to consume (e.g., bill, amendment, committee, etc.) or 'all' for all endpoints.",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one message then exit (useful for smoke tests)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Overall timeout in seconds for this consumer run (useful to avoid hangs)",
    )
    args = parser.parse_args()
    if args.endpoint == "all":
        # Process all endpoints sequentially in a single process
        endpoints = list(SPECS.keys())

        async def run_all():
            for endpoint in endpoints:
                print(f"=== Starting endpoint: {endpoint} ===")
                try:
                    if args.timeout:
                        try:
                            await asyncio.wait_for(run(endpoint), timeout=args.timeout)
                        except asyncio.TimeoutError:
                            print(
                                f"!!! Timeout after {args.timeout}s for endpoint {endpoint}"
                            )
                            continue
                    else:
                        await run(endpoint)
                    print(f"=== Finished endpoint: {endpoint} ===")
                except Exception as exc:
                    print(f"!!! Exception in endpoint {endpoint}: {exc}")
                    import traceback

                    traceback.print_exc()

        asyncio.run(run_all())
    else:
        # Run single endpoint with optional timeout
        async def _single():
            return await run(args.endpoint, once=args.once)

        if args.timeout:
            try:
                asyncio.run(asyncio.wait_for(_single(), timeout=args.timeout))
            except asyncio.TimeoutError:
                print(f"!!! Timeout after {args.timeout}s for endpoint {args.endpoint}")
        else:
            asyncio.run(_single())


if __name__ == "__main__":
    main()
