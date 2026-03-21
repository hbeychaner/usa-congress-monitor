"""Shared logging utilities for the repo."""

from __future__ import annotations

import logging
import logging.handlers
import os
import queue
from typing import Optional

_state: dict = {"configured": False, "queue_listener": None}


def configure_logging(level: Optional[str] = None) -> None:
    """Configure root logging once for the application.

    Uses a background `QueueListener` + `QueueHandler` so logging emits
    do not block asyncio event loops or other tight code paths.
    """
    if _state["configured"]:
        return
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()

    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")

    # Console handler for actual output
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    console.setLevel(log_level)

    # Queue-based handler + listener to make logging non-blocking
    q: queue.Queue = queue.Queue(-1)
    qh = logging.handlers.QueueHandler(q)

    root = logging.getLogger()
    root.setLevel(log_level)
    # Attach the queue handler to the root logger
    root.addHandler(qh)

    # Start a listener that will consume the queue in a background thread
    _state["queue_listener"] = logging.handlers.QueueListener(q, console)
    _state["queue_listener"].start()

    _state["configured"] = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with repository defaults."""
    configure_logging()
    return logging.getLogger(name)
