"""Run specialized sync handlers by name or all."""

from __future__ import annotations

import argparse
from typing import Callable

from elasticsearch import Elasticsearch
from tqdm import tqdm

from knowledgebase.client import build_client
from settings import CONGRESS_API_KEY, ELASTIC_API_KEY, ELASTIC_API_URL
from src.data_collection.client import CDGClient
from src.data_collection.specialized.registry import REGISTRY
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _build_clients() -> tuple[CDGClient, Elasticsearch]:
    if not CONGRESS_API_KEY:
        raise RuntimeError("CONGRESS_API_KEY not set")

    if not ELASTIC_API_URL or not ELASTIC_API_KEY:
        raise RuntimeError("ELASTIC_API_URL and ELASTIC_API_KEY are required")

    cdg_client = CDGClient(api_key=CONGRESS_API_KEY)
    es_client = build_client(ELASTIC_API_URL, ELASTIC_API_KEY)
    return cdg_client, es_client


def run_all() -> None:
    cdg_client, es_client = _build_clients()
    items = list(REGISTRY.items())
    for name, handler in tqdm(items, desc="Sync endpoints", unit="endpoint"):
        logger.info("Running sync for %s", name)
        result = handler(cdg_client, es_client)
        logger.info("%s sync result: %s", name, result)


def run_target(target: str) -> None:
    handler: Callable | None = REGISTRY.get(target)
    if handler is None:
        raise RuntimeError(f"Unknown sync target: {target}")
    cdg_client, es_client = _build_clients()
    with tqdm(total=1, desc=f"Sync {target}", unit="run") as bar:
        result = handler(cdg_client, es_client)
        logger.info("Sync result: %s", result)
        bar.update(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a specialized sync handler.")
    parser.add_argument(
        "target",
        nargs="?",
        default="all",
        help="Which sync to run (or 'all').",
    )
    args = parser.parse_args()

    if args.target == "all":
        run_all()
    else:
        run_target(args.target)


if __name__ == "__main__":
    main()
