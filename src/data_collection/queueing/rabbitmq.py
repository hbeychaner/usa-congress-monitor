"""RabbitMQ helpers for publishing and consuming JSON messages."""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable
import aio_pika
import logging
from aiormq.exceptions import ChannelInvalidStateError


async def connect(url: str) -> aio_pika.abc.AbstractRobustConnection:
    return await aio_pika.connect_robust(url)


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
    handler: Callable[[dict[str, Any]], Awaitable[None]],
    *,
    prefetch_count: int = 100,
    # exit_on_empty removed
) -> None:
    await channel.set_qos(prefetch_count=prefetch_count)
    queue = await channel.declare_queue(queue_name, durable=True)
    logger = logging.getLogger("rabbitmq.consume_json")
    while True:
        try:
            async with queue.iterator() as queue_iter:
                processed = 0
                async for message in queue_iter:
                    payload = message.body
                    try:
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
                                    continue
                                try:
                                    await handler(data)
                                except Exception:
                                    logger.error(
                                        f"Exception processing message {data.get('page', '')}:\nPayload: {payload}\nTraceback:",
                                        exc_info=True,
                                    )
                        except ChannelInvalidStateError:
                            logger.error("ChannelInvalidStateError processing message:")
                            logger.error(f"Payload: {payload}")
                            # Try to nack the message if possible, else skip acking
                            try:
                                await message.nack(requeue=True)
                            except Exception as nack_err:
                                logger.error(
                                    f"Failed to nack message after ChannelInvalidStateError: {nack_err}"
                                )
                            continue
                    except Exception as outer_err:
                        logger.error(
                            f"Unexpected error in consume_json: {outer_err}\nPayload: {payload}",
                            exc_info=True,
                        )
                        continue
                    processed += 1
                if processed == 0:
                    logger.info("No messages processed, breaking loop.")
                    break
        except Exception as exc:
            logger.error("Queue/channel error: %s. Reconnecting in 5s...", exc)
            import asyncio

            await asyncio.sleep(5)
