"""List all RabbitMQ queues using aio_pika and HTTP API authentication from settings.py."""

import os
import sys
import aio_pika
import asyncio
import requests

# Load RabbitMQ URL and credentials from settings.py
try:
    from settings import RABBITMQ_URL
except ImportError:
    RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")


def parse_rabbitmq_url(url):
    # Example: amqp://user:pass@host:port/vhost
    import re

    m = re.match(r"amqp://([^:]+):([^@]+)@([^:/]+)(?::(\d+))?(/.*)?", url)
    if not m:
        raise ValueError(f"Could not parse RabbitMQ URL: {url}")
    user, password, host, port, vhost = m.groups()
    port = port or "15672"  # default management port
    vhost = vhost[1:] if vhost else "%2F"  # remove leading /, default to /
    return user, password, host, port, vhost


async def list_queues_aio_pika():
    # This method requires queue names, not listing all queues
    # Use HTTP API for listing all queues
    pass


def list_queues_http():
    user, password, host, port, vhost = parse_rabbitmq_url(RABBITMQ_URL)
    # RabbitMQ management API endpoint
    url = f"http://{host}:15672/api/queues"
    try:
        resp = requests.get(url, auth=(user, password))
        resp.raise_for_status()
        queues = resp.json()
        print(f"Found {len(queues)} queues:")
        for q in queues:
            print(
                f"- {q['name']} (vhost: {q['vhost']}) messages: {q.get('messages', '?')}"
            )
    except Exception as e:
        print(f"Error listing queues: {e}")


if __name__ == "__main__":
    # Only HTTP API can list all queues
    list_queues_http()
