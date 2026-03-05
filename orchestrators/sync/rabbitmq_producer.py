"""Produce Congress API pages into RabbitMQ for async indexing."""

from __future__ import annotations

import argparse
import asyncio
from math import ceil
from time import monotonic
from tqdm import tqdm

from settings import (
    CONGRESS_API_KEY,
    ELASTIC_API_KEY,
    ELASTIC_API_URL,
    RABBITMQ_API_WORKERS,
    RABBITMQ_PAGE_SIZE,
    RABBITMQ_RATE_LIMIT_PER_HOUR,
    RABBITMQ_URL,
)
from src.data_collection.client import CDGClient
from src.data_collection.queueing.rabbitmq import connect, publish_json
from src.data_collection.endpoints.congress import get_current_congress
from src.data_collection.queueing.specs import SPECS, fetch_law_page, fetch_page
from src.data_collection.utils import resolve_pagination
from src.utils.logger import get_logger
from knowledgebase.client import build_client

logger = get_logger(__name__)


class _RateLimiter:
    def __init__(self, max_per_hour: int) -> None:
        self._interval = 3600 / max_per_hour if max_per_hour > 0 else 0
        self._next_time = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        if self._interval <= 0:
            return
        async with self._lock:
            now = monotonic()
            if now < self._next_time:
                await asyncio.sleep(self._next_time - now)
            self._next_time = max(self._next_time, now) + self._interval


async def run(
    target: str,
    congress: int | None = None,
    *,
    rate_limit_per_hour: int | None = None,
    api_workers: int | None = None,
    limiter: _RateLimiter | None = None,
) -> None:
    if not CONGRESS_API_KEY:
        raise RuntimeError("CONGRESS_API_KEY not set")
    if not ELASTIC_API_URL or not ELASTIC_API_KEY:
        raise RuntimeError("ELASTIC_API_URL and ELASTIC_API_KEY are required")

    cdg_client = CDGClient(api_key=CONGRESS_API_KEY)
    es_client = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)

    spec = SPECS.get(target)
    if spec is None:
        raise RuntimeError(f"Unknown target: {target}")
    law_congress: int | None = None
    if target == "law":
        if congress is None:
            current = await asyncio.to_thread(get_current_congress, cdg_client)
            congress = int(current.get("congress", {}).get("number", 0))
        if not congress:
            raise RuntimeError("Unable to resolve congress for law producer")
        law_congress = congress

    # Use per-endpoint queue name
    queue_name = f"{target}_queue"
    conn = await connect(RABBITMQ_URL)
    channel = await conn.channel()
    await channel.declare_queue(queue_name, durable=True)

    # Always start from offset 0 for full ingest, ignore previous progress
    resume_offset = 0

    limiter = limiter or _RateLimiter(
        rate_limit_per_hour or RABBITMQ_RATE_LIMIT_PER_HOUR
    )
    worker_count = max(1, api_workers or RABBITMQ_API_WORKERS)
    start_time = monotonic()
    last_log = start_time
    pages_published = 0

    async def _fetch(offset: int, limit: int) -> dict:
        await limiter.wait()
        if target == "law":
            assert law_congress is not None
            return await asyncio.to_thread(
                fetch_law_page,
                cdg_client,
                congress=law_congress,
                offset=offset,
                limit=limit,
            )
        return await asyncio.to_thread(
            fetch_page,
            target,
            cdg_client,
            offset=offset,
            limit=limit,
        )

    # First page to get totals and page size.
    response = await _fetch(resume_offset, RABBITMQ_PAGE_SIZE)
    # Use correct attribute name: api_data_key
    records = response.get(spec.api_data_key, [])
    if not records:
        await conn.close()
        await es_client.close()
        return

    meta = resolve_pagination(
        response,
        records_len=len(records),
        offset=resume_offset,
        page_size=RABBITMQ_PAGE_SIZE,
    )
    pagination = response.get("pagination")
    # Robustly handle missing total
    total = getattr(meta, "total", None)
    if not total:
        # Try to use count if available
        total = pagination["count"] if pagination and "count" in pagination else None
    effective_page_size = (
        getattr(meta, "page_size", None) or len(records) or RABBITMQ_PAGE_SIZE
    )
    if total:
        total_pages = ceil(int(total) / effective_page_size)
    else:
        total_pages = None  # Unknown
    page_index = (
        int(resume_offset / (effective_page_size or 1)) if effective_page_size else 0
    )

    # Progress bar for API fetching and publishing
    if total_pages:
        pbar = tqdm(total=total_pages, desc=f"{target} pages", unit="page")
    else:
        pbar = tqdm(desc=f"{target} pages", unit="page")

    async def publish_page(
        offset: int, page_no: int, records_payload: list[dict], meta: dict
    ) -> None:
        # Use spec.chunk_key_func for chunk key
        chunk_key = spec.chunk_key_func(meta, law_congress)
        payload = {
            "endpoint": target,
            "chunk_key": chunk_key,
            "meta": meta,
            "records": records_payload,
        }
        await publish_json(channel, queue_name, payload)
        nonlocal pages_published, last_log
        pages_published += 1

    page_index += 1
    # Compose meta for chunk_key generation using spec.meta_fields
    meta = {field: (law_congress if field == "congress" and law_congress is not None else locals().get(field)) for field in spec.meta_fields}
    await publish_page(resume_offset, page_index, records, meta)
    pbar.update(1)

    step = effective_page_size
    remaining_pages = max(0, total_pages - page_index) if total_pages else 0

    if remaining_pages > 0:
        queue: asyncio.Queue[tuple[int, int]] = asyncio.Queue()
        for i in range(1, remaining_pages + 1):
            next_offset = resume_offset + step * i
            next_page = page_index + i
            queue.put_nowait((next_offset, next_page))

        async def worker() -> None:
            while True:
                try:
                    offset, page_no = queue.get_nowait()
                except asyncio.QueueEmpty:
                    return
                # Compose meta for this chunk using spec.meta_fields
                chunk_meta = {field: (law_congress if field == "congress" and law_congress is not None else locals().get(field)) for field in spec.meta_fields}
                response = await _fetch(offset, effective_page_size)
                records = response.get(spec.api_data_key, [])
                if records:
                    await publish_page(offset, page_no, records, chunk_meta)
                pbar.update(1)
                queue.task_done()

        # Actually start the worker tasks
        tasks = [asyncio.create_task(worker()) for _ in range(worker_count)]
        await queue.join()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    pbar.close()
    await conn.close()
    await es_client.close()


async def run_multi(
    targets: list[str],
    congress: int | None = None,
    *,
    rate_limit_per_hour: int | None = None,
    api_workers: int | None = None,
) -> None:
    limiter = _RateLimiter(rate_limit_per_hour or RABBITMQ_RATE_LIMIT_PER_HOUR)
    unique_targets = sorted({target.strip() for target in targets if target.strip()})
    if not unique_targets:
        raise RuntimeError("At least one target is required")
    from tqdm import tqdm

    with tqdm(
        total=len(unique_targets), desc="Endpoints", unit="endpoint"
    ) as endpoint_bar:
        for target in unique_targets:
            await run(
                target,
                congress,
                rate_limit_per_hour=rate_limit_per_hour,
                api_workers=api_workers,
                limiter=limiter,
            )
            endpoint_bar.update(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Produce Congress API pages to RabbitMQ."
    )
    parser.add_argument(
        "target",
        help="Target sync (bill, member, law, amendment, comma-separated, or 'all')",
    )
    parser.add_argument(
        "--congress",
        type=int,
        help="Congress number for law target (defaults to current)",
    )
    parser.add_argument(
        "--rate-limit-per-hour",
        type=int,
        help="Override the API rate limit per hour.",
    )
    parser.add_argument(
        "--api-workers",
        type=int,
        help="Number of parallel API fetch workers.",
    )
    args = parser.parse_args()

    # Support 'all' and comma-separated targets
    raw = args.target.strip()
    if raw == "all":
        targets = list(SPECS.keys())
    else:
        targets = [t.strip() for t in raw.split(",") if t.strip()]
    if len(targets) == 1:
        asyncio.run(
            run(
                targets[0],
                args.congress,
                rate_limit_per_hour=args.rate_limit_per_hour,
                api_workers=args.api_workers,
            )
        )
    else:
        asyncio.run(
            run_multi(
                targets,
                args.congress,
                rate_limit_per_hour=args.rate_limit_per_hour,
                api_workers=args.api_workers,
            )
        )


if __name__ == "__main__":
    main()
