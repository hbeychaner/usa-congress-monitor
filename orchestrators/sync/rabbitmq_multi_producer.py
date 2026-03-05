"""Run RabbitMQ producers for multiple targets with a shared rate limit."""

from __future__ import annotations

import argparse
import asyncio

from orchestrators.sync.rabbitmq_producer import run_multi
from src.data_collection.queueing.specs import SPECS


def _resolve_targets(raw: str) -> list[str]:
    parts = [part.strip() for part in raw.split(",") if part.strip()]
    if not parts or "all" in parts:
        return sorted(SPECS.keys())
    unknown = [part for part in parts if part not in SPECS]
    if unknown:
        raise RuntimeError(f"Unknown targets: {', '.join(sorted(unknown))}")
    return parts


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RabbitMQ producers for multiple targets."
    )
    parser.add_argument(
        "targets",
        help=("Comma-separated targets (bill, member, law, amendment) or 'all'."),
    )
    parser.add_argument(
        "--congress",
        type=int,
        help="Congress number for law target (defaults to current)",
    )
    parser.add_argument(
        "--rate-limit-per-hour",
        type=int,
        help="Override the API rate limit per hour (shared).",
    )
    parser.add_argument(
        "--api-workers",
        type=int,
        help="Number of parallel API fetch workers per target.",
    )
    args = parser.parse_args()

    targets = _resolve_targets(args.targets)
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
