"""RabbitMQ helpers for publishing and consuming JSON messages."""

from __future__ import annotations

import json
import asyncio
from typing import Any, Awaitable, Callable
import aio_pika
from aio_pika.exceptions import QueueEmpty
import logging
from aiormq.exceptions import ChannelInvalidStateError


async def connect(url: str) -> aio_pika.abc.AbstractRobustConnection:
    return await aio_pika.connect_robust(url)


def parse_date_chunk_key(chunk_key: str):
    """Parse date-based chunk key (fromDate:toDate) and return meta."""
    # Chunk keys are constructed as "{fromDateTime}:{toDateTime}" where
    # the timestamps themselves contain colons (e.g. "2023-01-01T00:00:00Z:2023-01-08T00:00:00Z").
    # Split on the boundary between the two ISO timestamps by looking for the
    # terminating "Z:" sequence (or falling back to the last colon if needed).
    if not isinstance(chunk_key, str):
        raise ValueError("chunk_key must be a string")
    # Prefer splitting on the last occurrence of 'Z:' which separates the two
    # timestamps when they are formatted with a trailing 'Z'. This avoids
    # accidentally splitting inside the time portion.
    if "Z:" in chunk_key:
        pre, post = chunk_key.rsplit("Z:", 1)
        from_date = pre + "Z"
        to_date = post
        return {"fromDateTime": from_date, "toDateTime": to_date}
    # Fallback: if there is exactly one top-level separator (unlikely), split
    # on the last colon to reduce chance of breaking time components.
    if chunk_key.count(":") >= 1:
        pre, post = chunk_key.rsplit(":", 1)
        return {"fromDateTime": pre, "toDateTime": post}
    raise ValueError(f"Unable to parse date chunk_key: {chunk_key}")


async def publish_json(
    channel: aio_pika.abc.AbstractChannel,
    queue_name: str,
    payload: dict[str, Any],
) -> None:
    message = aio_pika.Message(
        body=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
    )
    await channel.default_exchange.publish(message, routing_key=queue_name)


async def consume_json(
    channel: aio_pika.abc.AbstractChannel,
    queue_name: str,
    handler: Callable[[dict], Awaitable[None]],
    *,
    prefetch_count: int = 100,
    max_messages: int | None = None,
) -> None:
    await channel.set_qos(prefetch_count=prefetch_count)
    queue = await channel.declare_queue(queue_name, durable=True)
    logger = logging.getLogger("rabbitmq.consume_json")
    logger.info(
        f"Started consuming from queue: {queue_name} with prefetch_count: {prefetch_count}"
    )
    remaining = max_messages
    while True:
        try:
            try:
                message = await queue.get(timeout=1)
            except QueueEmpty:
                logger.info("Queue is empty; sleeping briefly and retrying.")
                await asyncio.sleep(2)
                continue
            if message is None:
                logger.info("Received None message; sleeping briefly and retrying.")
                await asyncio.sleep(2)
                continue
            payload = message.body
            try:
                async with message.process():
                    try:
                        data = json.loads(payload)
                    except Exception:
                        logger.error(
                            "JSON decode error: %s\nPayload: %s",
                            Exception,
                            payload,
                        )
                        # Acknowledge malformed payloads to avoid retry loops
                        try:
                            await message.ack()
                        except Exception:
                            pass
                        continue
                    # Meta enrichment should be handled by the consumer handler.
                    # Avoid attempting to parse/modify `chunk_key` here to keep
                    # message handling centralized and avoid brittle string
                    # splitting logic.
                    try:
                        await handler(data)
                    except Exception:
                        logger.error(
                            f"Exception processing message:\nPayload: {payload}\nTraceback:",
                            exc_info=True,
                        )
                        # Decide whether to requeue based on redelivery flag to avoid infinite loops
                        redelivered = False
                        try:
                            redelivered = bool(
                                getattr(message, "redelivered", False)
                                or getattr(message, "is_redelivered", False)
                            )
                        except Exception:
                            redelivered = False
                        try:
                            # If this message was already redelivered once, do not requeue again
                            await message.nack(requeue=not redelivered)
                            logger.info(
                                "Message nacked (requeue=%s) after handler exception",
                                (not redelivered),
                            )
                        except Exception as nack_err:
                            logger.error(
                                f"Failed to nack message after handler exception: {nack_err}",
                                exc_info=True,
                            )
                        # move to next message
                        continue
                    # Decrement counter and exit if we've processed the requested number
                    if remaining is not None:
                        remaining -= 1
                        if remaining <= 0:
                            logger.info(
                                "Processed max_messages; exiting consumer loop."
                            )
                            return
            except ChannelInvalidStateError:
                logger.error("ChannelInvalidStateError processing message:")
                logger.error(f"Payload: {payload}")
                try:
                    await message.nack(requeue=True)
                except Exception as nack_err:
                    logger.error(
                        f"Failed to nack message after ChannelInvalidStateError: {nack_err}"
                    )
                continue
        except Exception as exc:
            logger.error(f"Queue/channel error: {exc}", exc_info=True)
            break
