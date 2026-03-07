"""Shared logging utilities for the repo."""

from __future__ import annotations

import logging
import logging.handlers
import os
import queue
from typing import Optional

_CONFIGURED = False
_QUEUE_LISTENER: logging.handlers.QueueListener | None = None


def configure_logging(level: Optional[str] = None) -> None:
    """Configure root logging once for the application.

    Uses a background `QueueListener` + `QueueHandler` so logging emits
    do not block asyncio event loops or other tight code paths.
    """
    global _CONFIGURED, _QUEUE_LISTENER
    if _CONFIGURED:
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
    _QUEUE_LISTENER = logging.handlers.QueueListener(q, console)
    _QUEUE_LISTENER.start()

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with repository defaults."""
    configure_logging()
    return logging.getLogger(name)
