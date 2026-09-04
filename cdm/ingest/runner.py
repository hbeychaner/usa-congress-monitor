"""Generic ingest script (renamed from ingest_congress.py).

Defaults to the Congress specs and behavior from the original script.
"""

from __future__ import annotations

import argparse
import json
import threading
import zlib
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import NotRequired, TypedDict

import requests
from sqlalchemy import Column, MetaData, String, Table, create_engine, select
from sqlalchemy.exc import SQLAlchemyError

# Ensure known specs are registered (importing the package imports submodules)
import cdm.data_collection.specs  # noqa: F401
from cdm.data_collection.client import get_client
from cdm.data_collection.endpoint_registry import get_spec
from cdm.data_collection.id_utils import canonical_id
from cdm.data_collection.utils import resolve_pagination
from cdm.ingest.archive import SQLiteListCache
from cdm.ingest.rate_limiter import TokenBucket
from cdm.jobs.store import CoverageStage
from cdm.utils.logger import get_logger

logger = get_logger(__name__)

_ARCHIVE_METADATA = MetaData()
_ARCHIVE_RECORDS = Table(
    "records",
    _ARCHIVE_METADATA,
    Column("record_id", String),
    Column("resource", String),
    Column("payload", String),
)


def _normalize_api_datetime(value: str) -> str:
    """Format an ISO timestamp in the precision accepted by Congress.gov."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class FatalIngestError(RuntimeError):
    """Raised when a non-recoverable error is detected during ingest.

    The pipeline will stop processing further chunks when this is raised.
    Typically triggered by a CDM model bug (AttributeError / TypeError) that
    indicates a code fix is required before continuing.
    """


class IngestCounts(TypedDict):
    """Counts and records returned by an ingest run."""

    list_count: int
    item_count: int
    records: NotRequired[list[dict]]


def _attempt_law_fallback(
    client, meta_mapping: dict, meta, aggregated_items: list, seen_ids: set
) -> bool:
    """Attempt to fetch a bill fallback for a failed law item fetch.

    Returns True when a fallback item was successfully appended to
    `aggregated_items` (or deduplicated), otherwise False.
    """
    from cdm.data_collection.specs.bill_specs import BILL_ITEM_SPEC

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


def fetch_and_save_all(
    outdir: Path,
    resource: Resource | str = "congress",
    api_key: str | None = None,
    fetch_items: bool = False,
    max_items: int | None = None,
    max_pages: int | None = None,
    congress: int | None = None,
    pause_on_error: bool = False,
    from_date: str | None = None,
    to_date: str | None = None,
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
        from_date=from_date,
        to_date=to_date,
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
    _LIST_PAGE_FALLBACK_LIMITS = (100, 50, 25, 10, 1)

    outdir: Path
    resource: Resource = Resource.CONGRESS
    api_key: str | None = None
    fetch_items: bool = False
    force_item_fetch: bool = False
    max_items: int | None = None
    max_pages: int | None = None
    list_page_size: int = 250
    congress: int | None = None
    pause_on_error: bool = False
    # Date window for endpoints that support fromDateTime/toDateTime
    from_date: str | None = None  # ISO-8601 e.g. "2025-01-01T00:00:00Z"
    to_date: str | None = None  # ISO-8601 e.g. "2025-01-31T23:59:59Z"
    from_date_param: str = "fromDateTime"
    to_date_param: str = "toDateTime"
    # Arbitrary extra query params (e.g. {"sort": "updateDate"}) merged last
    extra_params: dict | None = None
    # Concurrency: number of parallel item-fetch workers (1 = serial)
    concurrency: int = 1
    # Rate limiter: if provided, each worker calls limiter.acquire() before each request
    rate_limiter: TokenBucket | None = field(default=None, repr=False)
    record_sink: Callable[[str, dict], None] | None = field(default=None, repr=False)
    progress_sink: Callable[[str, CoverageStage, dict], None] | None = field(
        default=None, repr=False
    )
    record_archive_sink: Callable[[str, dict], None] | None = field(
        default=None, repr=False
    )
    # Guardrail for API pages that consistently return HTTP 5xx at a fixed offset.
    # We skip a bounded number of poisoned offsets and continue the ingest.
    max_skipped_list_pages: int = 0

    def _append_list_page_failure(
        self,
        resource_dir: Path,
        *,
        list_url: str,
        params: dict,
        status_code: int | None,
        error: str,
    ) -> None:
        resource_dir.mkdir(parents=True, exist_ok=True)
        failure_path = resource_dir / "list_page_failures.jsonl"
        payload = {
            "ts": datetime.now(UTC).isoformat(),
            "resource": self.resource.value,
            "list_url": list_url,
            "status_code": status_code,
            "offset": params.get("offset"),
            "limit": params.get("limit"),
            "from_date": self.from_date,
            "to_date": self.to_date,
            "error": error,
        }
        with failure_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")

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
        cached_factory = getattr(_thread_local, "client_factory", None)
        if cached is None or cached_key != key or cached_factory is not get_client:
            _thread_local.client = get_client(api_key=key)
            _thread_local.client_key = key
            _thread_local.client_factory = get_client
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

        if self.resource is Resource.BILL and meta_mapping.get("introduced_date"):
            response = client.request_for_spec(item_spec, runtime_params)
            version_records = client._extract_records_from_response(item_spec, response)
            if version_records and version_records[0].get("detailUrl"):
                target_date = str(meta_mapping["introduced_date"])
                version = next(
                    (
                        record
                        for record in version_records
                        if str(record.get("introducedDate", "")) == target_date
                    ),
                    None,
                )
                if version is None or not version.get("detailUrl"):
                    raise ValueError(
                        f"no matching bill version for introducedDate={target_date}"
                    )
                detail_response = client.get_json(str(version["detailUrl"]))
                detail_records = client._extract_records_from_response(
                    item_spec, detail_response
                )
                detail_models = client.coerce_records(
                    client._resolve_response_model(item_spec), detail_records
                )
                if not detail_models:
                    raise ValueError("bill version detail response contained no item")
                item = detail_models[0]
            else:
                detail_models = client.coerce_records(
                    client._resolve_response_model(item_spec), version_records
                )
                if not detail_models:
                    raise ValueError("bill detail response contained no item")
                item = detail_models[0]
        else:
            item = client.fetch_one(item_spec, runtime_params)
        hydration_sources: list[str] = []
        if self.resource is Resource.BILL:
            hydrate_details = getattr(item, "add_bill_details", None)
            if callable(hydrate_details):
                hydrate_details(client)
                hydration_sources.append("congress.gov_api")
        item_data = item.model_dump(mode="json", exclude_none=True)
        if hydration_sources:
            item_data.update({
                "hydration_status": "complete",
                "hydrated_at": datetime.now(UTC).isoformat(),
                "hydrated_sources": hydration_sources,
            })
            detail_hydration = getattr(item, "detail_hydration", None)
            if isinstance(detail_hydration, dict):
                item_data["detail_hydration"] = detail_hydration

        if self.resource is Resource.BILL and meta_mapping.get("introduced_date"):
            base_id = meta_mapping.get("id") or item_data.get("id")
            if base_id:
                item_data["id"] = f"{base_id}:{meta_mapping['introduced_date']}"

        if not item_data.get("id"):
            try:
                item_data["id"] = canonical_id(item)
            except Exception:  # noqa: BLE001, S110 - ID enrichment is best effort.
                pass

        if not item_data.get("referenceId"):
            try:
                from cdm.data_collection.id_utils import parse_url_to_id

                if item_data.get("url"):
                    item_data["referenceId"] = parse_url_to_id(str(item_data["url"]))
            except Exception:  # noqa: BLE001, S110 - reference ID enrichment is best effort.
                pass

        return item_data

    def _request_list_page(
        self,
        client,
        list_url: str,
        params: dict,
        configured_limit: int,
    ) -> tuple[requests.Response, int]:
        """Fetch a list page, shrinking the page only after an HTTP 5xx."""
        limits = [configured_limit]
        limits.extend(
            limit
            for limit in self._LIST_PAGE_FALLBACK_LIMITS
            if limit < configured_limit
        )
        last_error: Exception | None = None
        for page_limit in limits:
            request_params = {**params, "limit": page_limit}
            logger.info("Requesting list page: %s params=%s", list_url, request_params)
            try:
                response = client._request_with_backoff(
                    list_url,
                    params={k: str(v) for k, v in request_params.items()},
                )
            except requests.HTTPError as exc:
                response = getattr(exc, "response", None)
                if response is None or response.status_code < 500:
                    raise
                last_error = exc
                logger.warning(
                    "List page returned HTTP %s at offset %s with limit %s; "
                    "retrying with a smaller limit",
                    response.status_code,
                    params.get("offset"),
                    page_limit,
                )
                continue
            if page_limit != configured_limit:
                logger.warning(
                    "Recovered list page at offset %s with limit %s",
                    params.get("offset"),
                    page_limit,
                )
            return response, page_limit
        if last_error is not None:
            raise last_error
        raise RuntimeError("No usable list page limit configured")

    def run(self) -> IngestCounts:
        outdir = self.outdir
        outdir.mkdir(parents=True, exist_ok=True)
        client = self._client()

        list_spec = get_spec(self.resource.list_spec_name())
        if self.resource is Resource.BILL and self.congress is not None:
            list_spec = get_spec("bill_list_by_congress")
        item_spec = None
        if self.resource != Resource.SUMMARIES:
            item_spec = get_spec(self.resource.item_spec_name())
        # Prefer bill item endpoints for law resources to avoid known server-side
        # errors on the `/law/{congress}/{lawType}/{lawNumber}` item handler.
        if self.resource == Resource.LAW and not self.force_item_fetch:
            from cdm.data_collection.specs.bill_specs import BILL_ITEM_SPEC

            logger.info(
                "Resource=law: preferring bill item spec to avoid /law item 5xx"
            )
            item_spec = BILL_ITEM_SPEC
        logger.info("Fetching %s list spec: %s", self.resource.value, list_spec.name)

        offset = 0
        if self.list_page_size < 1:
            raise ValueError("list_page_size must be positive")
        configured_list_limit = self.list_page_size
        all_models: list = []
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
        checkpoint_path = outdir / "list_checkpoint.json"
        cache_path = outdir / "list_records.sqlite3"
        legacy_cache_path = outdir / "list_records.jsonl"
        checkpoint_params = {
            "resource": self.resource.value,
            "spec": list_spec.name,
            "congress": self.congress,
            "from_date": self.from_date,
            "to_date": self.to_date,
            "from_date_param": self.from_date_param,
            "to_date_param": self.to_date_param,
            "extra_params": self.extra_params,
        }
        checkpoint = self._load_list_checkpoint(checkpoint_path, checkpoint_params)
        if checkpoint is None:
            cache_path.unlink(missing_ok=True)
            legacy_cache_path.unlink(missing_ok=True)
        if checkpoint is not None:
            next_offset = int(checkpoint["next_offset"])
            if cache_path.exists():
                all_models = SQLiteListCache(cache_path).load(
                    list_model_cls, next_offset
                )
            elif legacy_cache_path.exists():
                all_models = self._load_cached_list_models(
                    legacy_cache_path, list_model_cls, next_offset
                )
                cache = SQLiteListCache(cache_path)
                cache.write_many([
                    (
                        next_offset if next_offset != -1 else 0,
                        model.model_dump(mode="json", exclude_none=True),
                    )
                    for model in all_models
                ])
            offset = int(checkpoint["next_offset"])
            if offset == -1:
                logger.info(
                    "Resuming %s list from completed cache (%d records)",
                    self.resource.value,
                    len(all_models),
                )
            else:
                logger.info(
                    "Resuming %s list at offset %d (%d cached records)",
                    self.resource.value,
                    offset,
                    len(all_models),
                )
        seen_list_keys = {
            key
            for model in all_models
            if (key := self._model_identity(model)) is not None
        }
        skipped_list_pages = 0
        resource_dir = outdir
        while True:
            if offset == -1:
                break
            params: dict = {"offset": offset}
            if self.from_date:
                params[self.from_date_param] = _normalize_api_datetime(self.from_date)
            if self.to_date:
                params[self.to_date_param] = _normalize_api_datetime(self.to_date)
            if self.extra_params:
                params.update(self.extra_params)
            try:
                resp_obj, page_limit = self._request_list_page(
                    client, list_url, params, configured_list_limit
                )
            except requests.HTTPError as exc:
                response = getattr(exc, "response", None)
                status_code = getattr(response, "status_code", None)
                if status_code is None or status_code < 500:
                    raise
                skipped_list_pages += 1
                self._append_list_page_failure(
                    resource_dir,
                    list_url=list_url,
                    params={**params, "limit": configured_list_limit},
                    status_code=status_code,
                    error=str(exc),
                )
                next_offset = int(params.get("offset", 0)) + 1
                self._save_list_checkpoint(
                    checkpoint_path,
                    checkpoint_params,
                    int(params.get("offset", 0)),
                )
                if skipped_list_pages > self.max_skipped_list_pages:
                    if self.max_skipped_list_pages == 0:
                        raise
                    raise RuntimeError(
                        "Exceeded max_skipped_list_pages "
                        f"({self.max_skipped_list_pages}) for {self.resource.value}"
                    ) from exc
                logger.warning(
                    "Skipping poisoned list page for %s at offset %s after HTTP %s; "
                    "continuing at offset %s",
                    self.resource.value,
                    params.get("offset"),
                    status_code,
                    next_offset,
                )
                self._save_list_checkpoint(
                    checkpoint_path,
                    checkpoint_params,
                    next_offset,
                )
                offset = next_offset
                continue
            parsed = resp_obj.json()
            records = client._extract_records_from_response(list_spec, parsed)
            logger.info("Parsed response; extracted %d records", len(records))
            if not records:
                break
            page_models = client.coerce_records(list_model_cls, records, spec=list_spec)
            unique_page_models = []
            for model in page_models:
                model_key = self._model_identity(model)
                if model_key is not None and model_key in seen_list_keys:
                    continue
                if model_key is not None:
                    seen_list_keys.add(model_key)
                unique_page_models.append(model)
            page_models = unique_page_models
            all_models.extend(page_models)
            cache = SQLiteListCache(cache_path)
            cache.write_many([
                (offset, model.model_dump(mode="json", exclude_none=True))
                for model in page_models
            ])
            if self.record_archive_sink is not None and not self.fetch_items:
                for model in page_models:
                    record = model.model_dump(mode="json", exclude_none=True)
                    self.record_archive_sink(
                        self.resource.value,
                        record,
                    )
                    if self.record_sink is not None:
                        self.record_sink(self.resource.value, record)
            meta = resolve_pagination(
                parsed, records_len=len(records), offset=offset, page_size=page_limit
            )
            page_count += 1
            next_offset = meta.next_offset
            self._save_list_checkpoint(
                checkpoint_path,
                checkpoint_params,
                next_offset if next_offset != offset else -1,
            )
            if self.progress_sink is not None:
                self.progress_sink(
                    self.resource.value,
                    CoverageStage.DISCOVERY,
                    {
                        "discovered_count": len(all_models),
                        "checkpoint_offset": next_offset,
                    },
                )
            if self.max_pages is not None and page_count >= self.max_pages:
                break
            if next_offset == -1 or next_offset == offset:
                break
            offset = next_offset

        # List-only resources: LAW (item endpoint returns 5xx) and SUMMARIES
        # (no individual item endpoint exists in the API).
        _LIST_ONLY = (
            {Resource.SUMMARIES}
            if self.force_item_fetch
            else {
                Resource.LAW,
                Resource.SUMMARIES,
            }
        )
        if self.resource in _LIST_ONLY:
            logger.info(
                "Resource=%s: list-only ingest; skipping item fetch",
                self.resource.value,
            )
            if self.progress_sink is not None:
                self.progress_sink(
                    self.resource.value,
                    CoverageStage.HYDRATION,
                    {
                        "discovered_count": len(all_models),
                        "hydrated_count": len(all_models),
                        "target_count": len(all_models),
                    },
                )
            return IngestCounts(list_count=len(all_models), item_count=0, records=[])

        if not self.fetch_items:
            if self.progress_sink is not None:
                self.progress_sink(
                    self.resource.value,
                    CoverageStage.HYDRATION,
                    {
                        "discovered_count": len(all_models),
                        "hydrated_count": len(all_models),
                        "target_count": len(all_models),
                    },
                )
            return IngestCounts(list_count=len(all_models), item_count=0)

        if item_spec is None:
            raise ValueError(f"No item spec available for {self.resource.value}")

        to_fetch_list: list = (
            all_models if self.max_items is None else all_models[: self.max_items]
        )
        successes = [0]  # wrapped in list for mutation in nested closure
        failures = [0]
        records: list[dict] = []
        seen_ids: set = self._load_archived_item_ids(outdir)
        archived_signatures = self._load_archived_item_signatures(outdir)
        write_lock = threading.Lock()
        counters_lock = threading.Lock()
        abort_event = threading.Event()  # set when a fatal error is detected

        pending = [(idx, meta) for idx, meta in enumerate(to_fetch_list, start=1)]

        def _meta_already_archived(meta) -> bool:
            # Resume checkpoints store archived item IDs (record_id). For some list
            # models, the list identity (often a URL) differs from item IDs, so
            # check both the list identity and best-effort canonical item ID.
            model_key = self._model_identity(meta)
            if model_key in seen_ids:
                return True
            meta_data = meta.model_dump(mode="json")
            if self.resource is Resource.BILL and meta_data.get("introduced_date"):
                signature = self._bill_signature(meta_data)
                return signature in archived_signatures
            try:
                item_key = canonical_id(meta)
            except Exception:  # noqa: BLE001 - best effort dedupe only.
                item_key = None
            return bool(item_key and item_key in seen_ids)

        pending = [
            (idx, meta) for idx, meta in pending if not _meta_already_archived(meta)
        ]
        skipped_count = len(to_fetch_list) - len(pending)
        total = len(pending)

        concurrency = max(1, self.concurrency)
        logger.info(
            "Fetching %d items with concurrency=%d rate=%.0f/hr",
            len(pending),
            concurrency,
            self.rate_limiter.rate_per_hour if self.rate_limiter else float("inf"),
        )
        logger.info("Skipping %d previously archived items", skipped_count)

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
                    records.append(item_data)
                    if self.record_archive_sink is not None:
                        self.record_archive_sink(self.resource.value, item_data)
                    if self.record_sink is not None:
                        self.record_sink(self.resource.value, item_data)
                with counters_lock:
                    successes[0] += 1
                    hydrated_count = successes[0] + skipped_count
                if self.progress_sink is not None:
                    self.progress_sink(
                        self.resource.value,
                        CoverageStage.HYDRATION,
                        {
                            "discovered_count": len(all_models),
                            "hydrated_count": hydrated_count,
                            "target_count": len(to_fetch_list),
                        },
                    )
                if successes[0] % 100 == 0:
                    logger.info(
                        "Progress: %d/%d items fetched (%d failures so far)",
                        successes[0],
                        total,
                        failures[0],
                    )
            except (AttributeError, TypeError) as exc:
                # These indicate a CDM model bug — stop immediately so
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
            except Exception as exc:  # noqa: BLE001 - continue after ordinary item failures.
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

        logger.info(
            "Finished fetching items: %d succeeded, %d failed",
            successes[0],
            failures[0],
        )

        if abort_event.is_set():
            raise FatalIngestError(
                f"Aborted after fatal model error during {self.resource.value} item fetch. "
                "Fix the CDM model and re-run with --resume."
            )
        return IngestCounts(
            list_count=len(all_models), item_count=successes[0], records=records
        )

    @staticmethod
    def _load_archived_item_ids(outdir: Path | None) -> set[str]:
        if outdir is None:
            return set()
        ids: set[str] = set()

        # In Pipeline runs, runner.outdir is often <job_root>/<resource>, while
        # record archives are stored at <job_root>. Probe both locations.
        archive_roots = [outdir]
        if outdir.parent != outdir:
            archive_roots.append(outdir.parent)

        for archive_root in archive_roots:
            sqlite_path = archive_root / "records.sqlite3"
            if sqlite_path.exists():
                try:
                    engine = create_engine(f"sqlite:///{sqlite_path}")
                    with engine.connect() as connection:
                        rows = connection.execute(
                            select(_ARCHIVE_RECORDS.c.record_id)
                        )
                        ids.update(row[0] for row in rows)
                except (OSError, SQLAlchemyError):
                    logger.warning(
                        "Could not read SQLite archive for resume: %s", sqlite_path
                    )

            for archive_path in archive_root.glob("records-attempt-*.jsonl"):
                try:
                    with archive_path.open(encoding="utf-8") as archive:
                        for line in archive:
                            try:
                                record = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            record_id = record.get("id")
                            if isinstance(record_id, str):
                                ids.add(record_id)
                                if record_id.startswith("amendment:"):
                                    ids.add(
                                        "bill:" + record_id.removeprefix("amendment:")
                                    )
                except OSError:
                    logger.warning(
                        "Could not read archive for resume: %s", archive_path
                    )
        return ids

    @staticmethod
    def _bill_signature(record: dict) -> tuple:
        latest = record.get("latest_action") or {}
        return (
            record.get("congress"),
            str(record.get("type", "")).lower(),
            str(record.get("number", "")),
            record.get("title"),
            latest.get("action_date") or latest.get("actionDate"),
            latest.get("text"),
        )

    @staticmethod
    def _load_archived_item_signatures(outdir: Path | None) -> set[tuple]:
        if outdir is None:
            return set()
        signatures: set[tuple] = set()
        archive_roots = [outdir]
        if outdir.parent != outdir:
            archive_roots.append(outdir.parent)
        for archive_root in archive_roots:
            sqlite_path = archive_root / "records.sqlite3"
            if not sqlite_path.exists():
                continue
            try:
                engine = create_engine(f"sqlite:///{sqlite_path}")
                with engine.connect() as connection:
                    rows = connection.execute(
                        select(_ARCHIVE_RECORDS.c.payload).where(
                            _ARCHIVE_RECORDS.c.resource == "bill"
                        )
                    )
                    for (payload,) in rows:
                        try:
                            record = json.loads(zlib.decompress(payload))
                        except (
                            TypeError,
                            ValueError,
                            zlib.error,
                            json.JSONDecodeError,
                        ):
                            continue
                        signatures.add(IngestRunner._bill_signature(record))
            except (OSError, SQLAlchemyError):
                logger.warning(
                    "Could not read bill signatures from SQLite archive: %s",
                    sqlite_path,
                )
        return signatures

    @staticmethod
    def _load_list_checkpoint(path: Path, expected: dict) -> dict | None:
        if not path.exists():
            return None
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Ignoring unreadable list checkpoint: %s", path)
            return None
        if state.get("parameters") != expected:
            logger.info("Ignoring list checkpoint with mismatched parameters: %s", path)
            return None
        next_offset = state.get("next_offset")
        if not isinstance(next_offset, int) or next_offset < -1:
            logger.warning("Ignoring invalid list checkpoint: %s", path)
            return None
        return state

    @staticmethod
    def _model_identity(model) -> str | None:
        data = model.model_dump(mode="json")
        identity = data.get("id") or data.get("url")
        if (
            model.__class__.__name__ == "BillMetadata"
            and data.get("introduced_date")
            and identity
        ):
            return f"{identity}:{data['introduced_date']}"
        if identity is not None:
            return str(identity)
        return json.dumps(data, sort_keys=True, separators=(",", ":"))

    @staticmethod
    def _save_list_checkpoint(path: Path, parameters: dict, next_offset: int) -> None:
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"parameters": parameters, "next_offset": next_offset}, indent=2
            ),
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def _load_cached_list_models(path: Path, model_cls: type, next_offset: int) -> list:
        if not path.exists():
            return []
        models = []
        seen_keys: set[str] = set()
        with path.open(encoding="utf-8") as cache:
            for line in cache:
                try:
                    entry = json.loads(line)
                    page_offset = entry["offset"]
                    if next_offset != -1 and page_offset >= next_offset:
                        continue
                    model = model_cls.model_validate(entry["record"])
                    identity = IngestRunner._model_identity(model)
                    if identity is not None and identity in seen_keys:
                        continue
                    if identity is not None:
                        seen_keys.add(identity)
                    models.append(model)
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    logger.warning("Skipping invalid cached list record in %s", path)
        return models


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the ingest script.

    Returns an ``argparse.Namespace`` with the standard flags used by
    ``fetch_and_save_all`` (output dir, resource, max limits, API key, etc.).
    """
    p = argparse.ArgumentParser(description="Ingest Congress lists and publish items")
    p.add_argument(
        "--outdir", default="data/congress", help="Output directory for run metadata"
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
        from_date=args.from_date,
        to_date=args.to_date,
    )


if __name__ == "__main__":
    main()
