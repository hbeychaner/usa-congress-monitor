#!/usr/bin/env python3
"""Thin shim — all logic lives in cdm.ingest.runner.

This file is kept for backwards compatibility with direct invocations of
``python scripts/ingest.py``.  New code should import from cdm.ingest.runner.
"""

from cdm.ingest.runner import *  # noqa: F401, F403
from cdm.ingest.runner import (  # explicit re-export
    main,
    IngestRunner,
    Resource,
    _attempt_law_fallback,
    fetch_and_save_all,
)

if __name__ == "__main__":
    main()
