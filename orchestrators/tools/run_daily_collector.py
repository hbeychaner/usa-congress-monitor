"""Run daily collector for the last 7 days using .env config."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    from src.data_collection.daily_collector import collect_daily_window
    from src.data_collection.client import CDGClient
    from settings import CONGRESS_API_KEY

    if not CONGRESS_API_KEY:
        raise RuntimeError("CONGRESS_API_KEY not set in .env")

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=7)
    out_dir = repo_root / "daily_output_7d"

    collect_daily_window(
        CDGClient(api_key=CONGRESS_API_KEY),
        start,
        end,
        out_dir,
        page_size=250,
    )


if __name__ == "__main__":
    main()
