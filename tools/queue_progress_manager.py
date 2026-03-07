"""Script to manage Congress ingest progress: queue incomplete chunks for processing."""

import asyncio
import json

import aio_pika

from knowledgebase.client import build_client
from knowledgebase.progress import (
    ensure_tracking_index,
    get_incomplete_chunks,
    upsert_chunk_progress,
)

from settings import ELASTIC_API_URL, ELASTIC_API_KEY, RABBITMQ_URL


async def queue_chunk(chunk: dict, rabbitmq_url: str, queue_name: str):
    try:
        from src.data_collection.queueing.specs import SPECS

        endpoint = chunk["endpoint"]
        spec = SPECS.get(endpoint)
        # Construct meta using spec.meta_fields if spec is not None
        if spec is not None and hasattr(spec, "meta_fields"):
            meta = {
                field: chunk.get("meta", {}).get(field, chunk.get(field))
                for field in spec.meta_fields
            }
        else:
            meta = chunk.get("meta", {})
        conn = await aio_pika.connect_robust(rabbitmq_url)
        channel = await conn.channel()
        await channel.declare_queue(queue_name, durable=True)
        # Validate meta: require at least one non-None value
        def _has_valid_meta(m: dict) -> bool:
            if not isinstance(m, dict):
                return False
            return any(v is not None for v in m.values())

        if not _has_valid_meta(meta):
            print(f"Skipping publish: chunk {chunk['chunk_key']} for endpoint {endpoint} has empty meta.")
            await conn.close()
            return

        payload = {
            "endpoint": endpoint,
            "chunk_key": chunk["chunk_key"],
            "meta": meta,
        }
        message = aio_pika.Message(
            body=json.dumps(payload).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await channel.default_exchange.publish(message, routing_key=queue_name)
        print(f"Published to queue: {queue_name}")
        await conn.close()
    except Exception as e:
        print(f"Error publishing to RabbitMQ queue '{queue_name}': {e}")


async def main():
    """
    Main progress manager for ingest queueing.
    All endpoint-specific logic (meta fields, chunk key) is spec-driven via SPECS.
    Meta is constructed for each chunk using spec.meta_fields for consistency.
    """
    es = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    await ensure_tracking_index(es)
    incomplete = await get_incomplete_chunks(es)
    print(f"Found {len(incomplete)} incomplete chunks.")
    for chunk in incomplete:
        endpoint = chunk["endpoint"]
        queue_name = f"{endpoint}_queue"
        print(f"Queueing: {endpoint} {chunk['chunk_key']} -> {queue_name}")
        await queue_chunk(chunk, RABBITMQ_URL, queue_name)
        await upsert_chunk_progress(
            es, endpoint, chunk["chunk_key"], "in_progress", chunk.get("meta")
        )
    await es.close()


if __name__ == "__main__":
    asyncio.run(main())
