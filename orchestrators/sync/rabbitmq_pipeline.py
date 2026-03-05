"""Run RabbitMQ producer and consumer together."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from orchestrators.sync.rabbitmq_consumer import run as run_consumer
from orchestrators.sync.rabbitmq_producer import run as run_producer
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def run_pipeline(
    target: str,
    *,
    congress: int | None = None,
    rate_limit_per_hour: int | None = None,
    api_workers: int | None = None,
    stop_after_producer: bool = False,
    grace_seconds: float = 5.0,
) -> None:
    consumer_task = asyncio.create_task(run_consumer(target))
    try:
        await run_producer(
            target,
            congress,
            rate_limit_per_hour=rate_limit_per_hour,
            api_workers=api_workers,
        )
        if stop_after_producer:
            if grace_seconds > 0:
                await asyncio.sleep(grace_seconds)
            consumer_task.cancel()
            try:
                await consumer_task
            except asyncio.CancelledError:
                logger.info("Consumer cancelled after producer finished.")
        else:
            await consumer_task
    finally:
        if not consumer_task.done():
            consumer_task.cancel()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RabbitMQ producer and consumer together."
    )
    parser.add_argument("target", help="Target sync (bill, member, law, amendment)")
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
    parser.add_argument(
        "--stop-after-producer",
        action="store_true",
        help="Stop the consumer after the producer finishes.",
    )
    parser.add_argument(
        "--grace-seconds",
        type=float,
        default=5.0,
        help="Seconds to wait before stopping the consumer (when enabled).",
    )
    args = parser.parse_args()

    asyncio.run(
        run_pipeline(
            args.target,
            congress=args.congress,
            rate_limit_per_hour=args.rate_limit_per_hour,
            api_workers=args.api_workers,
            stop_after_producer=args.stop_after_producer,
            grace_seconds=args.grace_seconds,
        )
    )


if __name__ == "__main__":
    main()
