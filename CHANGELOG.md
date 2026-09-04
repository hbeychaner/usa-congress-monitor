# Changelog

## 2026-09-04

### Fixed

- RabbitMQ backlog explosion: orphan-job recovery now claims stranded jobs
  atomically, caps recovery batches, and refreshes requeue timestamps so a
  crashed worker can no longer cause runaway duplicate redispatch. Lowered
  `RABBITMQ_PREFETCH` default from 200 to 10.
- `cdm/store/index_manager.py` re-parsed the OpenSearch mappings YAML from
  disk on every document validated during indexing; `load_definitions()` is
  now cached with `@lru_cache`.
- `cdm/jobs/store.py` had two near-duplicate atomic job-claim methods
  (`mark_running`/`claim_running`) that could drift; consolidated into one
  `mark_running(job_id, *, update_windows=True)`.
- `cdm/jobs/store.py` list/query methods (`stale_active`, `stale_queued`,
  `failed`, `queued`, `jobs`) had an N+1 query pattern (select ids, then
  `get()` each in a loop); now fetch full rows in a single query.
- `cdm/data_collection/client.py` retried HTTP 429 responses unboundedly
  (up to 1-hour sleeps, no attempt cap) while 5xx errors were capped; added
  `max_rate_limit_attempts` so rate-limit retries also give up and raise.
- `scripts/queue_full_ingest.py` dispatched a full historical plan
  (~2,000 jobs) to Celery in one unthrottled loop; added `--batch-size`/
  `--batch-delay` to pace dispatch.
- Unit test suite took ~3 minutes because ingest fixture tests exercised the
  real client rate-limit sleep (~0.72s per simulated API call, uncapped by
  test mocks). Added `tests/unit/conftest.py` to neutralize it; suite now
  runs in under 3 seconds (202 tests).
- `cdm/ingest/archive.py`, `cdm/ingest/govinfo.py`, and
  `cdm/backend/services/admin_service.py` used raw `sqlite3` connections and
  hand-written SQL alongside the rest of the codebase's SQLAlchemy Core
  usage; migrated to SQLAlchemy for consistency and to fix a PRAGMA
  multi-statement `executescript` call that isn't portable across drivers.
- `cdm/backend/services/admin_service.py` didn't recognize `govinfo_bulk`
  jobs (only `govinfo_bulk_batch`) when reporting active ingest progress,
  undercounting in-flight GovInfo package jobs in the admin UI.
- **Git tracked the docs directory as `Documentation/` (capital D) while
  every reference in code and docs used lowercase `documentation/`**
  (`cdm/store/index_manager.py`'s OpenSearch mappings loader,
  `tools/swagger_to_endpoint_specs.py`). Invisible on macOS's
  case-insensitive filesystem, but a fresh checkout on a case-sensitive
  filesystem (Linux CI, Docker, most production servers) would materialize
  `Documentation/` and silently break OpenSearch index creation. Renamed the
  tracked directory to `documentation/` to match.

### Removed

- Dead code with zero usages anywhere in the codebase, confirmed via
  workspace-wide search and a full test-suite re-run after deletion:
  `cdm/data_collection/collector.py`, `cdm/links/resolver.py`,
  `cdm/search/client.py`.
- The Streamlit dashboard (`cdm/streamlit/`), superseded by the React/Vite
  frontend under `frontend/app/`.
- `INGEST_CHECKLIST.md`, superseded by `README.md`'s Operations section.
- `cdm/backend/api/schemas/` — an entire package of re-export-only modules
  (`members.py`, `search.py`, `states.py`) with no consumers anywhere in the
  codebase; discovered via `ruff`'s `F401` unused-import check.

### Chores

- Fixed all `ruff check` findings repo-wide (unused imports, import
  ordering, an unnecessary `datetime` timezone replacement in
  `cdm/ingest/runner.py`); `ruff check .` and `compileall` are clean.

### Changed

- `scripts/health_check.py` and `scripts/monitor_ingest_progress.py` updated
  to match the current job/coverage schema.
- `frontend/app/src/pages/AdminIngestPage.tsx` simplified to match the
  updated admin ingest-progress API shape.

See `NOTES_FOR_JUNIOR.md` for the full engineering writeup of what was wrong
and why, intended as review notes for less experienced contributors.

## 2026-08-22

### Added

- Automatic recovery of transient ingest failures through a Celery Beat task
  that runs every 10 minutes.
- Daily incremental ingestion with a two-day overlap, UTC date boundaries,
  current-Congress selection, and resource-scope-aware query parameters.
- A resource scope catalog that prevents unsupported date filters from being
  sent to static or global Congress.gov endpoints.
- Restart-safe JSONL/JSON-array migration tooling with bounded-memory parsing,
  throttling, progress reporting, integrity verification, and delete-after-
  success behavior.

### Changed

- Replaced legacy JSONL and large JSON-array archives with compressed,
  deduplicated SQLite record archives and list-page caches.
- List-page cache writes now use one SQLite transaction per page, reducing
  connection and commit overhead during large backfills.
- Transient HTTP, timeout, and connection failures retry with capped
  exponential backoff without a fixed terminal retry count. Non-transient
  failures retain bounded retry behavior.
- Corrected resource metadata: amendments and house votes are static/global;
  laws are the Congress-path-scoped resource.
- Removed the legacy whole-file checkpointed paginator; `IngestRunner` now
  owns checkpoint, cache, deduplication, and fallback behavior.

### Verification

- Migrated 140 legacy files containing 734,560 item rows.
- Verified 339 SQLite databases with `PRAGMA integrity_check`.
- Removed legacy migration sources and SQLite sidecar files after verification.
- Full unit suite passes: 128 tests.

## 2026-08-09

### Added

- Durable SQLite job records with idempotent submission and lifecycle status.
- RabbitMQ/Celery worker tasks for ingest and OpenSearch indexing.
- Redis Streams as the primary ingest-to-index handoff, with consumer-group
  recovery and acknowledge-after-bulk semantics.
- Celery Beat scheduling for overlapping daily ingestion windows.
- Bounded retry/backoff, late acknowledgements, and worker-loss requeue.
- `scripts/submit_ingest.py`, `make worker`, and `make beat` operational commands.
- Worker architecture diagram and operational documentation.

### Fixed

- Forwarded date-window arguments through the legacy ingest CLI wrapper.
- Made the local macOS worker command use Celery's `solo` pool to avoid
  Objective-C fork-safety crashes.
- Completed the Ruff and Pylance cleanup across production modules, scripts,
  tools, and tests, including explicit exception handling and typed Pydantic
  defaults.

### Changed

- Centralized endpoint HTTP methods and identifier-reference sources as string
  enums while preserving existing serialized values.
- Added a smoke-tested full-ingest planner with historical date windows,
  congress-scoped jobs, and idempotent queue submission.
- Added per-job, per-attempt durable archives for fetched list and item records,
  with durable persistence before indexing.