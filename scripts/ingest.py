"""Thin shim — all logic lives in cdm.ingest.runner.

This file is kept for backwards compatibility with direct invocations of
``python scripts/ingest.py``.  New code should import from cdm.ingest.runner.
"""

from cdm.ingest.runner import (  # noqa: F401  # explicit re-export
    IngestRunner,
    Resource,
    _attempt_law_fallback,
    fetch_and_save_all,
    main,
)

if __name__ == "__main__":
    main()
