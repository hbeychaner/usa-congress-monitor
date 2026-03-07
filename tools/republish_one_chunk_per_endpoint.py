#!/usr/bin/env python3
"""Republish one `in_progress` chunk per endpoint to RabbitMQ for quick validation."""
import asyncio
import json
from elasticsearch import Elasticsearch
from settings import ELASTIC_API_URL, ELASTIC_API_KEY, RABBITMQ_URL
import aio_pika


async def publish(payloads: list[dict]):
    conn = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await conn.channel()
    for p in payloads:
        qname = f"{p['endpoint']}_queue"
        await channel.declare_queue(qname, durable=True)
        msg = aio_pika.Message(
            body=json.dumps(p).encode("utf-8"),
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await channel.default_exchange.publish(msg, routing_key=qname)
        print("Published", p["endpoint"], p.get("chunk_key"))
    await conn.close()


def main():
    es = Elasticsearch(ELASTIC_API_URL, api_key=ELASTIC_API_KEY)
    idx = "congress-progress-tracking"
    from src.data_collection.queueing.specs import SPECS

    payloads = []
    for endpoint in SPECS.keys():
        q = {
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"endpoint": endpoint}},
                        {"term": {"status": "in_progress"}},
                    ]
                }
            },
            "size": 1,
        }
        try:
            res = es.search(index=idx, body=q)
            hits = res.get("hits", {}).get("hits", [])
            if not hits:
                print("No in_progress chunk for", endpoint)
                continue
            doc = hits[0]["_source"]
            chunk_key = doc.get("chunk_key")
            meta = doc.get("meta") or {}
            # Build a simple fallback meta when progress doc lacks meta
            if not meta and chunk_key:
                pagination_keys = {"offset", "page", "page_size", "total_pages"}
                spec = SPECS.get(endpoint)
                try:
                    if "Z:" in chunk_key:
                        # date range chunk_key like '1951-01-01T00:00:00Z:1951-06-30T00:00:00Z'
                        a, b = chunk_key.split("Z:")
                        from_dt = a + "Z"
                        to_dt = b if b.endswith("Z") else b + "Z"
                        meta = {"fromDateTime": from_dt, "toDateTime": to_dt}
                    elif ":" in chunk_key and spec is not None:
                        parts = chunk_key.split(":")
                        identifying_fields = [f for f in spec.meta_fields if f not in pagination_keys]
                        meta = {}
                        for i, part in enumerate(parts[: len(identifying_fields)]):
                            key = identifying_fields[i]
                            # coerce numbers for common fields
                            if part.isdigit() and key in ("congress", "year"):
                                meta[key] = int(part)
                            else:
                                meta[key] = part
                    elif chunk_key.isdigit() and spec is not None:
                        # single numeric chunk_key -> likely congress or year
                        if "congress" in spec.meta_fields:
                            meta = {"congress": int(chunk_key)}
                        elif "year" in spec.meta_fields:
                            meta = {"year": int(chunk_key)}
                except Exception:
                    meta = meta or {}

            payloads.append({"endpoint": endpoint, "chunk_key": chunk_key, "meta": meta})
        except Exception as e:
            print("Error fetching chunk for", endpoint, e)
    if not payloads:
        print("No payloads to publish")
        return
    asyncio.run(publish(payloads))


if __name__ == "__main__":
    main()
