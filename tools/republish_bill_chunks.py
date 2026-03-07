#!/usr/bin/env python3
"""Republish in_progress `bill` chunks to RabbitMQ (test a limited batch)."""
import asyncio
import json
from elasticsearch import Elasticsearch
from settings import ELASTIC_API_URL, ELASTIC_API_KEY, RABBITMQ_URL
import aio_pika

BATCH_SIZE = 1

async def publish_chunks(chunks):
    conn = await aio_pika.connect_robust(RABBITMQ_URL)
    channel = await conn.channel()
    await channel.declare_queue('bill_queue', durable=True)
    for c in chunks:
        payload = {'endpoint': 'bill', 'chunk_key': c['chunk_key'], 'meta': c.get('meta', {})}
        msg = aio_pika.Message(
            body=json.dumps(payload).encode('utf-8'),
            content_type='application/json',
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await channel.default_exchange.publish(msg, routing_key='bill_queue')
        print('Published', c['chunk_key'])
    await conn.close()

def main():
    es = Elasticsearch(ELASTIC_API_URL, api_key=ELASTIC_API_KEY)
    idx = 'congress-progress-tracking'
    q = {"query": {"bool": {"filter": [{"term": {"endpoint": "bill"}}, {"term": {"status": "in_progress"}}]}} , "size": 500}
    res = es.search(index=idx, body=q)
    hits = res['hits']['hits']
    print('Found', len(hits), 'in_progress bill chunks; will publish up to', BATCH_SIZE)
    chunk_list = [h['_source'] for h in hits][:BATCH_SIZE]
    asyncio.run(publish_chunks(chunk_list))

if __name__ == '__main__':
    main()
