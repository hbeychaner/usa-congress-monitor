"""Collect daily-window Congress.gov data and related metadata.

This module gathers all top-level list endpoints within a 24-hour window,
fetches detail records for list items that include an API URL, and
collects member metadata for any referenced member IDs.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

from requests.exceptions import HTTPError, RequestException

from src.data_collection.client import CDGClient
from src.data_collection.utils import extract_offset
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ListSpec:
    """Definition for a top-level list endpoint."""

    name: str
    endpoint: str
    data_key: str
    supports_datetime: bool
    date_fields: tuple[str, ...]
    filter_by_window: bool = True
    supports_date_parts: bool = False
    pagination_param: str = "limit"
    max_records: int | None = 250
    max_pages: int | None = None


TOP_LEVEL_SPECS: tuple[ListSpec, ...] = (
    ListSpec("amendment", "amendment", "amendments", True, ("updateDate",)),
    ListSpec("bill", "bill", "bills", True, ("updateDate", "latestAction.actionDate")),
    ListSpec(
        "bound-congressional-record",
        "bound-congressional-record",
        "boundCongressionalRecord",
        False,
        ("updateDate", "date"),
        max_pages=1,
    ),
    ListSpec("committee", "committee", "committees", True, ("updateDate",)),
    ListSpec(
        "committee-meeting",
        "committee-meeting",
        "committeeMeetings",
        True,
        ("updateDate", "date"),
    ),
    ListSpec(
        "committee-print",
        "committee-print",
        "committeePrints",
        True,
        ("updateDate",),
    ),
    ListSpec(
        "committee-report",
        "committee-report",
        "reports",
        True,
        ("updateDate",),
    ),
    ListSpec(
        "congress",
        "congress",
        "congresses",
        False,
        ("updateDate",),
        filter_by_window=False,
    ),
    ListSpec(
        "congressional-record",
        "congressional-record",
        "Issues",
        False,
        ("PublishDate", "publishDate", "issueDate"),
        supports_date_parts=True,
    ),
    ListSpec("crsreport", "crsreport", "CRSReports", True, ("updateDate",)),
    ListSpec(
        "daily-congressional-record",
        "daily-congressional-record",
        "dailyCongressionalRecord",
        False,
        ("updateDate", "issueDate"),
        max_pages=1,
    ),
    ListSpec(
        "hearing",
        "hearing",
        "hearings",
        False,
        ("updateDate", "date"),
        max_pages=1,
    ),
    ListSpec(
        "house-communication",
        "house-communication",
        "houseCommunications",
        False,
        ("updateDate", "referralDate"),
        max_pages=1,
    ),
    ListSpec(
        "house-requirement",
        "house-requirement",
        "houseRequirements",
        False,
        ("updateDate",),
        max_pages=1,
    ),
    ListSpec(
        "house-vote",
        "house-vote",
        "houseRollCallVotes",
        False,
        ("updateDate", "startDate"),
        max_pages=1,
    ),
    ListSpec(
        "law",
        "law/{congress}",
        "bills",
        False,
        ("updateDate",),
        filter_by_window=False,
    ),
    ListSpec("member", "member", "members", True, ("updateDate",)),
    ListSpec("nomination", "nomination", "nominations", True, ("updateDate",)),
    ListSpec(
        "senate-communication",
        "senate-communication",
        "senateCommunications",
        False,
        ("updateDate", "referralDate"),
        max_pages=1,
    ),
    ListSpec("summaries", "summaries", "summaries", True, ("updateDate",)),
    ListSpec("treaty", "treaty", "treaties", True, ("updateDate",)),
)


def _format_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_nested(record: dict[str, Any], field: str) -> Any:
    current: Any = record
    for part in field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        try:
            if text.endswith("Z"):
                return datetime.fromisoformat(text.replace("Z", "+00:00"))
            parsed = datetime.fromisoformat(text)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
    return None


def _within_window(
    record: dict[str, Any], fields: tuple[str, ...], start: datetime, end: datetime
) -> bool:
    for field in fields:
        value = _extract_nested(record, field)
        dt = _parse_datetime(value)
        if dt and start <= dt <= end:
            return True
    return False


def _endpoint_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    path = parsed.path
    if "/v3/" in path:
        path = path.split("/v3/", 1)[1]
    else:
        path = path.lstrip("/")
    endpoint = path
    if parsed.query:
        endpoint = f"{endpoint}?{parsed.query}"
    return endpoint


def _resolve_endpoint(client: CDGClient, endpoint: str) -> str:
    if "{congress}" in endpoint:
        response = _safe_get(client, "congress/current")
        congress_number = response.get("congress", {}).get("number")
        if congress_number is None:
            raise ValueError("Unable to resolve current congress number")
        return endpoint.format(congress=congress_number)
    return endpoint


def _safe_get(
    client: CDGClient, endpoint: str, params: dict[str, Any] | None = None
) -> dict:
    """Call the API with retries and return a dict response or raise."""
    attempts = 3
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = client.get(endpoint, params=params)
            return response if isinstance(response, dict) else {}
        except (HTTPError, RequestException) as exc:
            last_error = exc
            logger.warning(
                "Request failed (%s/%s) for %s: %s", attempt, attempts, endpoint, exc
            )
    raise last_error or RuntimeError("Request failed")


def _collect_paginated(
    client: CDGClient, spec: ListSpec, start: datetime, end: datetime, page_size: int
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    endpoint = _resolve_endpoint(client, spec.endpoint)
    date_parts: list[date] = []
    if spec.supports_date_parts:
        current = start.date()
        last = end.date()
        while current <= last:
            date_parts.append(current)
            current += timedelta(days=1)
    else:
        date_parts = [start.date()]

    for day in date_parts:
        offset = 0
        pages_fetched = 0
        while True:
            params: dict[str, Any] = {
                "offset": offset,
                spec.pagination_param: page_size,
            }
            if spec.supports_datetime:
                params["fromDateTime"] = _format_datetime(start)
                params["toDateTime"] = _format_datetime(end)
            if spec.supports_date_parts:
                params["y"] = day.year
                params["m"] = day.month
                params["d"] = day.day

            try:
                response = _safe_get(client, endpoint, params=params)
            except Exception as exc:
                logger.error("Skipping %s due to error: %s", spec.name, exc)
                break
            if spec.endpoint == "congressional-record" and isinstance(response, dict):
                page_records = list(response.get("Results", {}).get("Issues", []))
            else:
                page_records = (
                    list(response.get(spec.data_key, []))
                    if isinstance(response, dict)
                    else []
                )
            if not page_records:
                break
            if spec.supports_datetime:
                records.extend(page_records)
            elif spec.filter_by_window:
                records.extend(
                    r
                    for r in page_records
                    if _within_window(r, spec.date_fields, start, end)
                )
            else:
                records.extend(page_records)

            if spec.max_records is not None and len(records) >= spec.max_records:
                return records[: spec.max_records]

            pages_fetched += 1
            if spec.max_pages is not None and pages_fetched >= spec.max_pages:
                break

            pagination = (
                response.get("pagination", {}) if isinstance(response, dict) else {}
            )
            next_url = pagination.get("next") if isinstance(pagination, dict) else None
            if not next_url:
                break
            new_offset = extract_offset(next_url)
            if new_offset == offset:
                break
            offset = new_offset
    return records


def _extract_urls(data: Any) -> set[str]:
    urls: set[str] = set()
    if isinstance(data, dict):
        for key, value in data.items():
            if key in {"url", "URL"} and isinstance(value, str):
                urls.add(value)
            else:
                urls.update(_extract_urls(value))
    elif isinstance(data, list):
        for item in data:
            urls.update(_extract_urls(item))
    return urls


def _collect_details(
    client: CDGClient,
    records: Iterable[dict[str, Any]],
    *,
    follow_related: bool = True,
    max_related_per_record: int = 20,
) -> tuple[list[dict[str, Any]], set[str]]:
    details: list[dict[str, Any]] = []
    member_ids: set[str] = set()
    seen_urls: set[str] = set()

    for record in records:
        url = record.get("url") or record.get("URL")
        if not isinstance(url, str):
            continue
        if url in seen_urls:
            continue
        endpoint = _endpoint_from_url(url)
        if not endpoint:
            continue
        seen_urls.add(url)
        detail = client.get(endpoint)
        if isinstance(detail, dict):
            details.append(detail)
            member_ids.update(_extract_member_ids(detail))

            if follow_related:
                related_urls = sorted(_extract_urls(detail))[:max_related_per_record]
                for related_url in related_urls:
                    if related_url in seen_urls:
                        continue
                    related_endpoint = _endpoint_from_url(related_url)
                    if not related_endpoint:
                        continue
                    seen_urls.add(related_url)
                    related_detail = client.get(related_endpoint)
                    if isinstance(related_detail, dict):
                        details.append({"_source_url": related_url, **related_detail})
                        member_ids.update(_extract_member_ids(related_detail))

    return details, member_ids


def _extract_member_ids(data: Any) -> set[str]:
    member_ids: set[str] = set()
    if isinstance(data, dict):
        for key, value in data.items():
            if key in {"bioguideId", "bioguideID", "bioguide_id"} and isinstance(
                value, str
            ):
                member_ids.add(value)
            else:
                member_ids.update(_extract_member_ids(value))
    elif isinstance(data, list):
        for item in data:
            member_ids.update(_extract_member_ids(item))
    return member_ids


def _collect_member_details(
    client: CDGClient, member_ids: Iterable[str]
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for member_id in sorted(set(member_ids)):
        details.append(client.get(f"member/{member_id}"))
    return details


def collect_daily_window(
    client: CDGClient,
    start: datetime,
    end: datetime,
    output_dir: Path,
    page_size: int = 250,
    *,
    fetch_details: bool = False,
    follow_related: bool = True,
) -> None:
    """Collect list data, detail metadata, and member metadata for a time window."""
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Collecting daily window data from %s to %s", start, end)

    for spec in TOP_LEVEL_SPECS:
        logger.info("Collecting list for %s", spec.name)
        try:
            list_records = _collect_paginated(client, spec, start, end, page_size)
        except Exception as exc:
            logger.error("Failed to collect %s: %s", spec.name, exc)
            continue
        spec_dir = output_dir / spec.name
        spec_dir.mkdir(parents=True, exist_ok=True)
        (spec_dir / "list.json").write_text(
            json.dumps(list_records, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info("%s: wrote %s records", spec.name, len(list_records))

        if not fetch_details:
            continue

        detail_records, member_ids = _collect_details(
            client, list_records, follow_related=follow_related
        )
        if spec.name == "house-vote":
            for record in list_records:
                url = record.get("url") or record.get("URL")
                if not isinstance(url, str):
                    continue
                endpoint = _endpoint_from_url(url)
                if not endpoint:
                    continue
                members_detail = client.get(f"{endpoint}/members")
                if isinstance(members_detail, dict):
                    detail_records.append(
                        {"_source_url": f"{url}/members", **members_detail}
                    )
                    member_ids.update(_extract_member_ids(members_detail))
        (spec_dir / "details.json").write_text(
            json.dumps(detail_records, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        if member_ids:
            members_dir = output_dir / "members"
            members_dir.mkdir(parents=True, exist_ok=True)
            member_details = _collect_member_details(client, member_ids)
            (members_dir / f"members_from_{spec.name}.json").write_text(
                json.dumps(member_details, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect daily Congress.gov data.")
    parser.add_argument("--api-key", required=True, help="Congress.gov API key")
    parser.add_argument("--out", default="daily_output", help="Output directory")
    parser.add_argument("--page-size", type=int, default=250, help="Page size")
    parser.add_argument(
        "--details",
        action="store_true",
        help="Fetch detail records for list items (depth > 1)",
    )
    parser.add_argument(
        "--start",
        help="Window start (ISO, default: now-24h)",
    )
    parser.add_argument(
        "--end",
        help="Window end (ISO, default: now)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=24)
    if args.start:
        start = _parse_datetime(args.start) or start
    if args.end:
        end = _parse_datetime(args.end) or end

    client = CDGClient(api_key=args.api_key)
    logger.info("Starting daily collection")
    collect_daily_window(
        client,
        start,
        end,
        Path(args.out),
        page_size=args.page_size,
        fetch_details=args.details,
    )
    logger.info("Daily collection complete")


if __name__ == "__main__":
    main()
