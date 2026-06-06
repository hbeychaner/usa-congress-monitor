#!/usr/bin/env python3
"""Generic ingest script (renamed from ingest_congress.py).

Defaults to the Congress specs and behavior from the original script.
"""

from __future__ import annotations

import argparse
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, field
from typing import Iterable, Optional, List

# Ensure known specs are registered (importing the package imports submodules)
import congress_sdk.data_collection.specs  # noqa: F401
from congress_sdk.data_collection.client import get_client
from congress_sdk.data_collection.endpoint_registry import get_spec
from congress_sdk.data_collection.id_utils import canonical_id
from congress_sdk.data_collection.utils import resolve_pagination
from congress_sdk.utils.logger import get_logger

logger = get_logger(__name__)


class FatalIngestError(RuntimeError):
    """Raised when a non-recoverable error is detected during ingest.

    The pipeline will stop processing further chunks when this is raised.
    Typically triggered by a pycongress model bug (AttributeError / TypeError)
    that indicates a code fix is required before continuing.
    """


def _attempt_law_fallback(
    client, meta_mapping: dict, meta, aggregated_items: list, seen_ids: set
) -> bool:
    """Attempt to fetch a bill fallback for a failed law item fetch.

    Returns True when a fallback item was successfully appended to
    `aggregated_items` (or deduplicated), otherwise False.
    """
    from congress_sdk.data_collection.specs.bill_specs import BILL_ITEM_SPEC

    bill_params = client.resolve_runtime_params_from_record(
        BILL_ITEM_SPEC, meta_mapping
    )
    if not any(k in bill_params for k in ("congress", "number", "bill_slug", "slug")):
        return False
    logger.info("Attempting law->bill fallback with params=%s", bill_params)
    item = client.fetch_one(BILL_ITEM_SPEC, bill_params)
    item_data = item.model_dump(mode="json")
    meta_obj = item_data.setdefault("meta", {})
    meta_obj.setdefault("fallback_from", "bill")
    meta_obj.setdefault(
        "fallback_source_record",
        meta_mapping.get("id") or meta_mapping.get("url") or None,
    )
    # Ensure item has an id; let canonical_id raise if it cannot produce one
    if not item_data.get("id"):
        item_data["id"] = canonical_id(item)
    item_id = item_data.get("id")
    if item_id in seen_ids:
        logger.info("Skipping duplicate fallback item id=%s", item_id)
    else:
        aggregated_items.append(item_data)
        if item_id is not None:
            seen_ids.add(item_id)
    return True


def dump_json(path: Path, obj) -> None:
    """Serialize ``obj`` to JSON and write it to ``path``.

    Non-JSON-serializable values (for example, Pydantic HttpUrl objects)
    are coerced to strings using ``default=str`` so output remains stable
    and human-readable.

    Args:
        path: Destination file path to write the JSON.
        obj: The Python object to serialize (commonly a list or mapping).
    """
    # Use `default=str` to coerce non-JSON-serializable types (e.g., HttpUrl) to strings
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )


def fetch_and_save_all(
    outdir: Path,
    resource: Resource | str = "congress",
    api_key: str | None = None,
    fetch_items: bool = False,
    max_items: int | None = None,
    max_pages: int | None = None,
    congress: int | None = None,
    pause_on_error: bool = False,
    save_raw_items: bool = False,
) -> None:
    """Compatibility wrapper that delegates work to :class:`IngestRunner`.

    The project has moved to a typed runner; this wrapper preserves the
    original function API for callers while routing execution through the
    strongly-typed implementation.
    """
    runner = IngestRunner(
        outdir=outdir,
        resource=Resource(resource) if isinstance(resource, str) else resource,
        api_key=api_key,
        fetch_items=fetch_items,
        max_items=max_items,
        max_pages=max_pages,
        congress=congress,
        pause_on_error=pause_on_error,
        save_raw_items=save_raw_items,
    )
    runner.run()


class Resource(Enum):
    """Enumeration of commonly-ingested resources.

    Values correspond to the short resource name used to derive spec
    names (``{value}_list`` / ``{value}_item``).
    """

    AMENDMENT = "amendment"
    BILL = "bill"
    BOUND_CONGRESSIONAL_RECORD = "bound_congressional_record"
    COMMITTEE = "committee"
    COMMITTEE_MEETING = "committee_meeting"
    COMMITTEE_PRINT = "committee_print"
    COMMITTEE_REPORT = "committee_report"
    CONGRESS = "congress"
    CRSREPORT = "crsreport"
    DAILY_CONGRESSIONAL_RECORD = "daily_congressional_record"
    HEARING = "hearing"
    HOUSE_COMMUNICATION = "house_communication"
    SENATE_COMMUNICATION = "senate_communication"
    HOUSE_REQUIREMENT = "house_requirement"
    HOUSE_VOTE = "house_vote"
    LAW = "law"
    MEMBER = "member"
    NOMINATION = "nomination"
    SUMMARIES = "summaries"
    TREATY = "treaty"

    def list_spec_name(self) -> str:
        return f"{self.value}_list"

    def item_spec_name(self) -> str:
        return f"{self.value}_item"


# Per-thread client cache so each worker gets its own requests.Session
_thread_local = threading.local()


@dataclass
class IngestRunner:
    outdir: Path
    resource: Resource = Resource.CONGRESS
    api_key: Optional[str] = None
    fetch_items: bool = False
    max_items: Optional[int] = None
    max_pages: Optional[int] = None
    congress: Optional[int] = None
    pause_on_error: bool = False
    save_raw_items: bool = False
    # Date window for endpoints that support fromDateTime/toDateTime
    from_date: Optional[str] = None  # ISO-8601 e.g. "2025-01-01T00:00:00Z"
    to_date: Optional[str] = None  # ISO-8601 e.g. "2025-01-31T23:59:59Z"
    # Arbitrary extra query params (e.g. {"sort": "updateDate"}) merged last
    extra_params: Optional[dict] = None
    # Concurrency: number of parallel item-fetch workers (1 = serial)
    concurrency: int = 1
    # Rate limiter: if provided, each worker calls limiter.acquire() before each request
    rate_limiter: Optional[object] = field(default=None, repr=False)

    def _client(self):
        """Return (or create) a per-thread SDK client."""
        key = self.api_key
        if not key:
            try:
                from settings import CONGRESS_API_KEY  # root project settings

                key = CONGRESS_API_KEY or None
            except ImportError:
                pass
        # Reuse the client stored on the current thread to avoid sharing Sessions
        cached = getattr(_thread_local, "client", None)
        cached_key = getattr(_thread_local, "client_key", None)
        if cached is None or cached_key != key:
            _thread_local.client = get_client(api_key=key)
            _thread_local.client_key = key
        return _thread_local.client

    def _fetch_single_item(
        self,
        meta,
        item_spec,
        outdir: Path,
    ) -> dict:
        """Fetch one item and return its data dict.  Thread-safe; raises on failure."""
        if self.rate_limiter is not None:
            self.rate_limiter.acquire()

        client = self._client()
        meta_mapping = (
            meta.model_dump(mode="json") if hasattr(meta, "model_dump") else dict(meta)
        )
        runtime_params = client.resolve_runtime_params_from_record(
            item_spec, meta_mapping
        )

        if self.save_raw_items:
            parsed_item = client.request_for_spec(item_spec, runtime_params)
            recs = client._extract_records_from_response(item_spec, parsed_item)
            insts = client.coerce_records(
                client._resolve_response_model(item_spec), recs, spec=item_spec
            )
            if not insts:
                raise ValueError(
                    f"no item found for params={runtime_params}; "
                    f"response_keys={list(parsed_item.keys())}"
                )
            item = insts[0]
            # Start from the raw API dict so no fields are silently dropped by
            # the pydantic model (e.g. witnesses, meetingDocuments, videos).
            # Then overlay the model-dumped output so computed fields like `id`
            # and camelCase→snake_case aliases take precedence.
            raw_dict = recs[0] if recs else {}
            item_data = {**raw_dict, **item.model_dump(mode="json", exclude_none=True)}
        else:
            item = client.fetch_one(item_spec, runtime_params)
            item_data = item.model_dump(mode="json", exclude_none=True)

        if not item_data.get("id"):
            try:
                item_data["id"] = canonical_id(item)
            except Exception:
                pass

        if not item_data.get("referenceId"):
            try:
                from congress_sdk.data_collection.id_utils import parse_url_to_id

                if item_data.get("url"):
                    item_data["referenceId"] = parse_url_to_id(str(item_data["url"]))
            except Exception:
                pass

        return item_data

    def run(self) -> None:
        outdir = self.outdir
        outdir.mkdir(parents=True, exist_ok=True)
        client = self._client()

        list_spec = get_spec(self.resource.list_spec_name())
        item_spec = get_spec(self.resource.item_spec_name())
        # Prefer bill item endpoints for law resources to avoid known server-side
        # errors on the `/law/{congress}/{lawType}/{lawNumber}` item handler.
        if self.resource == Resource.LAW:
            from congress_sdk.data_collection.specs.bill_specs import BILL_ITEM_SPEC

            logger.info(
                "Resource=law: preferring bill item spec to avoid /law item 5xx"
            )
            item_spec = BILL_ITEM_SPEC
        logger.info("Fetching %s list spec: %s", self.resource.value, list_spec.name)

        offset = 0
        limit = 250
        all_models: List = []
        raw_records: List[dict] = []
        list_model_cls = client._resolve_response_model(list_spec)

        base_path_params = {}
        if getattr(list_spec, "_param_map", {}) and "congress" in list_spec._param_map:
            if self.congress is None:
                raise ValueError(
                    "List endpoint requires 'congress' path param; pass --congress"
                )
            base_path_params["congress"] = self.congress
        list_url = list_spec.render_path(client.base_url, base_path_params)
        page_count = 0
        while True:
            params: dict = {"offset": offset, "limit": limit}
            if self.from_date:
                params["fromDateTime"] = self.from_date
            if self.to_date:
                params["toDateTime"] = self.to_date
            if self.extra_params:
                params.update(self.extra_params)
            logger.info("Requesting list page: %s params=%s", list_url, params)
            resp_obj = client._request_with_backoff(
                list_url, params={k: str(v) for k, v in params.items()}
            )
            parsed = resp_obj.json()
            records = client._extract_records_from_response(list_spec, parsed)
            logger.info("Parsed response; extracted %d records", len(records))
            raw_records.extend(records)
            if not records:
                break
            coerced = client.coerce_records(list_model_cls, records, spec=list_spec)
            all_models.extend(coerced)
            meta = resolve_pagination(
                parsed, records_len=len(records), offset=offset, page_size=limit
            )
            logger.info(
                "Pagination meta: next_offset=%s total=%s page_size=%s",
                meta.next_offset,
                meta.total,
                meta.page_size,
            )
            page_count += 1
            if self.max_pages is not None and page_count >= self.max_pages:
                logger.info("Reached max_pages=%s; stopping pagination", self.max_pages)
                break
            if meta.next_offset == -1 or meta.next_offset == offset:
                break
            offset = meta.next_offset

        list_data = [m.model_dump(mode="json", exclude_none=True) for m in all_models]
        dump_json(outdir / "list.json", list_data)
        dump_json(outdir / "raw_list.json", raw_records)
        logger.info(
            "Saved list (%d entries) to %s", len(list_data), outdir / "list.json"
        )

        # List-only resources: LAW (item endpoint returns 5xx) and SUMMARIES
        # (no individual item endpoint exists in the API).
        _LIST_ONLY = {Resource.LAW, Resource.SUMMARIES}
        if self.resource in _LIST_ONLY:
            logger.info(
                "Resource=%s: list-only ingest; skipping item fetch",
                self.resource.value,
            )
            return

        if not self.fetch_items:
            return

        to_fetch_list: List = (
            all_models if self.max_items is None else all_models[: self.max_items]
        )
        successes = [0]  # wrapped in list for mutation in nested closure
        failures = [0]
        aggregated_items: List[dict] = []
        seen_ids: set = set()
        write_lock = threading.Lock()
        counters_lock = threading.Lock()
        abort_event = threading.Event()  # set when a fatal error is detected

        # ── incremental resume ────────────────────────────────────────────
        items_jsonl_path = outdir / "items.jsonl"
        already_fetched_urls: set = set()
        if items_jsonl_path.exists():
            for raw_line in items_jsonl_path.read_text(encoding="utf-8").splitlines():
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    existing = json.loads(raw_line)
                    aggregated_items.append(existing)
                    if existing.get("id"):
                        seen_ids.add(existing["id"])
                    if existing.get("url"):
                        already_fetched_urls.add(str(existing["url"]))
                    successes[0] += 1
                except json.JSONDecodeError:
                    pass
            if already_fetched_urls:
                logger.info(
                    "Resume: loaded %d already-fetched items from %s",
                    len(already_fetched_urls),
                    items_jsonl_path,
                )
        items_jsonl_fh = items_jsonl_path.open("a", encoding="utf-8")
        # ─────────────────────────────────────────────────────────────────

        # Filter out already-fetched items before submitting to pool
        pending = [
            (idx, meta)
            for idx, meta in enumerate(to_fetch_list, start=1)
            if not (str(getattr(meta, "url", None) or "") in already_fetched_urls)
        ]
        total = len(to_fetch_list)
        skipped = total - len(pending)
        if skipped:
            logger.info("Resume: skipping %d already-fetched items", skipped)

        concurrency = max(1, self.concurrency)
        logger.info(
            "Fetching %d items with concurrency=%d rate=%.0f/hr",
            len(pending),
            concurrency,
            self.rate_limiter.rate_per_hour if self.rate_limiter else float("inf"),
        )

        def _do_fetch(idx_meta):
            idx, meta = idx_meta
            if abort_event.is_set():
                return  # another worker hit a fatal error — skip
            try:
                item_data = self._fetch_single_item(meta, item_spec, outdir)
                item_id = item_data.get("id")
                with write_lock:
                    if item_id and item_id in seen_ids:
                        logger.debug("Skipping duplicate item id=%s", item_id)
                        return
                    seen_ids.add(item_id or "")
                    aggregated_items.append(item_data)
                    items_jsonl_fh.write(
                        json.dumps(item_data, ensure_ascii=False, default=str) + "\n"
                    )
                    items_jsonl_fh.flush()
                with counters_lock:
                    successes[0] += 1
                if successes[0] % 100 == 0:
                    logger.info(
                        "Progress: %d/%d items fetched (%d failures so far)",
                        successes[0] + skipped,
                        total,
                        failures[0],
                    )
            except (AttributeError, TypeError) as exc:
                # These indicate a pycongress model bug — stop immediately so
                # the code can be fixed before data is silently lost.
                abort_event.set()
                logger.critical(
                    "FATAL error on item %d/%d (url=%s): %s — aborting run; "
                    "fix the model and re-run with --resume",
                    idx,
                    total,
                    getattr(meta, "url", "?"),
                    exc,
                )
            except Exception as exc:
                with counters_lock:
                    failures[0] += 1
                logger.error(
                    "Failed item %d/%d (url=%s): %s",
                    idx,
                    total,
                    getattr(meta, "url", "?"),
                    exc,
                )

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            list(pool.map(_do_fetch, pending))

        items_jsonl_fh.close()
        dump_json(outdir / "items.json", aggregated_items)

        logger.info(
            "Finished fetching items: %d succeeded, %d failed; saved to %s",
            successes[0],
            failures[0],
            outdir / "items.json",
        )

        if abort_event.is_set():
            raise FatalIngestError(
                f"Aborted after fatal model error during {self.resource.value} item fetch. "
                "Fix the pycongress model and re-run with --resume."
            )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the ingest script.

    Returns an ``argparse.Namespace`` with the standard flags used by
    ``fetch_and_save_all`` (output dir, resource, max limits, API key, etc.).
    """
    p = argparse.ArgumentParser(description="Ingest Congress list and items to disk")
    p.add_argument(
        "--outdir", default="data/congress", help="Output directory to write JSON files"
    )
    p.add_argument(
        "--resource",
        choices=[r.value for r in Resource],
        default=Resource.CONGRESS.value,
        help="Resource to ingest (e.g., 'congress' or 'bill')",
    )
    p.add_argument(
        "--items", action="store_true", help="Also fetch individual item endpoints"
    )
    p.add_argument(
        "--max",
        type=int,
        default=None,
        help="Maximum number of items to fetch (for testing)",
    )
    p.add_argument("--api-key", default=None, help="Override API key (optional)")
    p.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Maximum number of list pages to fetch (for testing)",
    )
    p.add_argument(
        "--congress",
        type=int,
        default=None,
        help="Congress number to use for endpoints that require it (e.g., law)",
    )
    p.add_argument(
        "--pause-on-error",
        action="store_true",
        help="Pause and dump partial items when an item fetch raises an exception",
    )
    p.add_argument(
        "--save-raw",
        action="store_true",
        help="Also save raw per-item API JSON to raw_items.json",
    )
    p.add_argument(
        "--from-date",
        default=None,
        help="fromDateTime filter (ISO-8601, e.g. 2025-01-01 or 2025-01-01T00:00:00Z)",
    )
    p.add_argument(
        "--to-date",
        default=None,
        help="toDateTime filter (ISO-8601, e.g. 2025-01-31 or 2025-01-31T23:59:59Z)",
    )
    return p.parse_args()


def main() -> None:
    """CLI entrypoint: parse args and invoke ``fetch_and_save_all``.

    This function exists to provide a minimal, testable entrypoint for
    scripts and for use under ``if __name__ == '__main__'``.
    """
    args = parse_args()
    outdir = Path(args.outdir)
    fetch_and_save_all(
        outdir,
        resource=Resource(args.resource),
        api_key=args.api_key,
        fetch_items=args.items,
        max_items=args.max,
        max_pages=args.max_pages,
        congress=args.congress,
        pause_on_error=args.pause_on_error,
        save_raw_items=args.save_raw,
        from_date=args.from_date,
        to_date=args.to_date,
    )


if __name__ == "__main__":
    main()
