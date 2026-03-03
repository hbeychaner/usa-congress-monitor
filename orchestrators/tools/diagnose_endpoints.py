"""Quickly benchmark top-level Congress.gov endpoints (single-page)."""

from __future__ import annotations

import json
import time


def main() -> None:
    from src.data_collection.client import CDGClient
    from settings import CONGRESS_API_KEY

    client = CDGClient(api_key=CONGRESS_API_KEY)
    endpoints = [
        "amendment",
        "bill",
        "bound-congressional-record",
        "committee",
        "committee-meeting",
        "committee-print",
        "committee-report",
        "congress",
        "congressional-record",
        "crsreport",
        "daily-congressional-record",
        "hearing",
        "house-communication",
        "house-requirement",
        "house-vote",
        "law",
        "member",
        "nomination",
        "senate-communication",
        "summaries",
        "treaty",
    ]

    results = []
    for ep in endpoints:
        params = {"limit": 1, "offset": 0}
        if ep == "congressional-record":
            params.update({"y": 2024, "m": 1, "d": 1})
        start = time.perf_counter()
        try:
            resp = client.get(ep, params=params, timeout=10)
            elapsed = time.perf_counter() - start
            results.append(
                {
                    "endpoint": ep,
                    "elapsed_sec": round(elapsed, 3),
                    "ok": True,
                    "keys": list(resp.keys()) if isinstance(resp, dict) else str(type(resp)),
                }
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start
            results.append(
                {
                    "endpoint": ep,
                    "elapsed_sec": round(elapsed, 3),
                    "ok": False,
                    "error": str(exc),
                }
            )

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
