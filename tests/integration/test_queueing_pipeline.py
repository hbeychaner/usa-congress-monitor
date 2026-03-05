import asyncio
import pytest
import aio_pika
import json
from knowledgebase.progress import ensure_tracking_index, upsert_chunk_progress, get_incomplete_chunks
from knowledgebase.client import build_client
from settings import ELASTIC_API_URL, ELASTIC_API_KEY, RABBITMQ_URL
from src.data_collection.queueing.specs import SPECS

@pytest.mark.asyncio
async def test_queue_chunk_and_consume():
    """
    Integration test: queue a chunk, consume it, and verify progress update.
    """
    es = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    await ensure_tracking_index(es)
    endpoint = "member"
    chunk_key = "117"
    meta = {field: 117 for field in SPECS[endpoint].meta_fields}
    await upsert_chunk_progress(es, endpoint, chunk_key, "pending", meta)
    incomplete = await get_incomplete_chunks(es)
    assert any(c["chunk_key"] == chunk_key for c in incomplete)

    # Queue the chunk
    conn = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await conn.channel()
    queue_name = f"{endpoint}_queue"
    queue = await channel.declare_queue(queue_name, durable=True)
    await queue.purge()
    payload = {
        "endpoint": endpoint,
        "chunk_key": chunk_key,
        "meta": meta,
    }
    message = aio_pika.Message(
        body=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await channel.default_exchange.publish(message, routing_key=queue_name)
    await conn.close()

    # Simulate consumer: fetch from queue and check payload
    conn = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await conn.channel()
    queue = await channel.declare_queue(queue_name, durable=True)
    incoming = await queue.get(timeout=5)
    assert incoming is not None
    data = json.loads(incoming.body.decode("utf-8"))
    assert data["endpoint"] == endpoint
    assert data["chunk_key"] == chunk_key
    assert data["meta"] == meta
    await conn.close()

    # Clean up: mark chunk complete
    await upsert_chunk_progress(es, endpoint, chunk_key, "complete", meta)
    await es.close()

@pytest.mark.asyncio
async def test_producer_consumer_integration():
    """
    Integration test: simulate producer queuing and consumer processing for a chunk.
    """
    es = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    await ensure_tracking_index(es)
    endpoint = "member"
    chunk_key = "118"
    meta = {field: 118 for field in SPECS[endpoint].meta_fields}
    await upsert_chunk_progress(es, endpoint, chunk_key, "pending", meta)
    queue_name = f"{endpoint}_queue"

    # Producer: queue chunk
    conn = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await conn.channel()
    queue = await channel.declare_queue(queue_name, durable=True)
    await queue.purge()
    payload = {
        "endpoint": endpoint,
        "chunk_key": chunk_key,
        "meta": meta,
    }
    message = aio_pika.Message(
        body=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await channel.default_exchange.publish(message, routing_key=queue_name)
    await conn.close()

    # Consumer: fetch and process
    conn = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await conn.channel()
    queue = await channel.declare_queue(queue_name, durable=True)
    incoming = await queue.get(timeout=5)
    assert incoming is not None
    data = json.loads(incoming.body.decode("utf-8"))
    assert data["endpoint"] == endpoint
    assert data["chunk_key"] == chunk_key
    assert data["meta"] == meta
    await upsert_chunk_progress(es, endpoint, chunk_key, "complete", meta)
    await conn.close()
    await es.close()
