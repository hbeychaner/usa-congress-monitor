"""Shared logging utilities for the repo."""

from __future__ import annotations

import logging
import os
from typing import Optional

_CONFIGURED = False


def configure_logging(level: Optional[str] = None) -> None:
    """Configure root logging once for the application."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    log_level = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured with repository defaults."""
    configure_logging()
    return logging.getLogger(name)
