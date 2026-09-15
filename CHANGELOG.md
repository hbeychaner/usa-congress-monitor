# Changelog

## 2026-09-15

### Changed

- Bill backfill switched from the rate-limited Congress.gov API to GovInfo
  bulk data (unmetered): the GovInfo BILLSTATUS/BILLSUM parsers now emit
  snake_case fields matching the API hydration path and the legislation
  mapping (`introduced_date`, `latest_action.action_date`,
  `sponsors[].bioguide_id/full_name`, `policy_area`, `subjects
  .legislative_subjects`, committee `system_code`, summary
  `action_date/action_desc/version_code`), so bulk records merge cleanly onto
  the same documents. `queue_govinfo_bulk.py` no longer requires
  `--staging-version` — omitting it merges into the live alias. Queued
  BILLSTATUS+BILLSUM+BILLS for congresses 116–119 (~211k packages) and
  cancelled the four API hydration backfill jobs they supersede. Removed the
  completed one-time `scripts/migrate_jsonl_to_sqlite.py` and stale `data/`
  checkpoint directories.

### Fixed

- Pipeline audit follow-ups: hydrated bill items carried a
  `:{introduced_date}` id suffix from the ingest runner, so they indexed as
  duplicates instead of upserting over their skeleton list records — the
  indexer now canonicalizes bill ids (24 existing duplicates merged and
  removed). The legislation mapping gained `sponsors`, `policy_area`,
  `introduced_date`, `latest_action`, `type`, `reference_id`, and
  `version_code` (all previously unqueryable under `dynamic: false`, which
  made the `policy_area.name`/`sponsors.full_name` search clauses dead code);
  pushed live in place. Cancelled the four stale historical bill jobs
  (superseded by the hydration backfill). Queued a historical treaty backfill
  — the treaty index was empty because treaties only ever ran in 2-day daily
  windows.
- Bill hydration never ran through the worker pipeline: `Pipeline` ignored
  `fetch_items=True` for bills because `fetch_items_default=False` always won,
  so every indexed bill was a skeleton (no sponsors, actions, subjects,
  summaries, or text). New `PipelineConfig.item_resources` override lets
  payloads opt specific large resources into item fetch; daily, coverage-gap,
  and full-ingest payloads now pass `item_resources: ["bill"]`. Hydration
  backfill jobs queued for congresses 116–119.
- Bill detail API now falls back to the latest GovInfo `bill-text:` record
  (ranked by text-version lifecycle) when the bill document has no inline
  `full_text`.
- Coverage-gap ingest jobs now pass the current Congress, matching daily
  ingest. Previously they hit the bare `/v3/bill?fromDateTime=...` endpoint,
  which returns records from *any* congress touched by Congress.gov metadata
  backfills — ~16,000 bills from congresses 91–112 (e.g. 1978's SJRES 105 with
  a 2026 updateDate) leaked into the index this way. Existing old records are
  retained.

## 2026-09-14

### Added

- Unified member activity: amendments now index flattened
  `sponsor_bioguide_ids` / `cosponsor_bioguide_ids` (plus newly mapped
  `purpose` and `submitted_date`), and all 128,750 existing amendment docs were
  backfilled in place. New `GET /api/v1/members/{bioguide_id}/activity`
  endpoint merges bill and amendment activity (sponsor/cosponsor detection,
  per-type counts, type filter, pagination), and the member profile page gained
  an "All Activity" section with document-type filter and paging.
- spaCy lemmatization (`en_core_web_md`) for search: the mappings loader now
  injects a `{field}_lemma` sibling (whitespace analyzer) for every text field
  declaring a `.lemma` multi-field, `to_document` populates the siblings at
  index time (including nested fields like `actions.text`), and bill/member
  search queries lemmatize the user query and match the new fields. Query-time
  lemmatization degrades gracefully when the model is unavailable; index-time
  lemmatization fails loudly. Mapping additions were pushed in place to all 19
  live indices (existing docs gain lemmas as they are re-indexed).

### Fixed

- `IndexManager.ensure_aliases` (invoked by every index-job `create(...,
  exists_ok=True)`) no longer moves aliases that already exist — it only adds
  missing ones. Previously any routine index job could silently steal the
  read/write aliases back to the bare index, undoing a versioned migration's
  alias flip.
- Rebuilt `congress-legislation` from the canonical spec: the live index had
  drifted to `actions.source_system: keyword` while the spec (and all
  documents produced by ingest) use an object (`name`/`code`), causing
  `document_parsing_exception` failures for every bill with actions. All
  25,350 documents and both aliases were preserved; the two index jobs that
  failed on the bad mapping were requeued and succeeded.
- Pushed additive mapping updates (lemma multi-fields, `_meta.mapping_version`
  stamps) in place to the 18 remaining indices; a full audit now reports zero
  drift between live mappings and `documentation/opensearch_mappings.yaml`.
- Replaced the four failed index jobs targeting the deleted
  `congress-legislation-v118` staging index with live-alias replays (archive
  fallback), all succeeded; cancelled the archiveless legacy bill index job as
  superseded by the historical congress-scoped re-ingest.

### Added

- Added a daily retention maintenance task: prunes succeeded/cancelled jobs
  older than `RETENTION_DAYS` (default 30) from the ledger, deletes their
  Redis record streams and per-job archive directories, removes orphaned
  streams, and vacuums SQLite. Coverage history (`ingest_windows`) is always
  preserved so gap scheduling and future historical backfills are unaffected,
  and jobs referenced by unfinished index jobs are protected until those
  resolve.
- Index jobs now fall back to replaying the durable per-job archive when the
  Redis stream no longer holds the expected records (Redis restart or maxlen
  eviction), healing the "Indexed 0 records, expected N" failure class
  automatically.
- Cancelling a job now stops its in-flight run: the ingest progress callback
  polls the job ledger about once a minute and raises `IngestCancelledError`,
  which propagates through the item-fetch pool and ends the task without a
  retry instead of burning API budget until the soft time limit.

### Fixed

- Terminal job-store updates (`mark_succeeded`/`mark_failed`) no longer
  overwrite an ingest window that was cancelled while an attempt was still
  in flight; cancelled coverage windows stay cancelled.
- Cancelled the redundant `2022-11-06 → 2023-11-05` date-window job whose
  coverage fully overlaps the Congress 117/118 congress-scoped historical
  jobs, freeing shared API budget.
- Fixed historical ingest resume never skipping archived items: list-cache
  payloads are snake_case model dumps but were validated without `by_name`,
  silently dropping alias-only fields such as `introduced_date` and
  `latest_action`; archive record ids also carried datetime suffixes that
  never matched date-only list identities. Every retry refetched all items
  from scratch, which is why large historical jobs repeatedly exhausted the
  six-hour task limit.
- Added HTTP timeouts to bill and amendment full-text fetches; a dead
  connection previously blocked an ingest thread in a socket read
  indefinitely, stalling historical jobs without failing them.
- Made `SoftTimeLimitExceeded` failures retryable by automatic recovery. Now
  that resume dedupe banks progress across attempts, timed-out historical
  jobs converge instead of restarting from zero.
- Fixed `schedule_coverage_gaps` crashing with a naive/aware datetime
  comparison when completed coverage windows mixed timestamp formats.
- Automatic recovery now redispatches ingest jobs that remain queued in SQLite
  for more than 24 hours without a broker delivery, repairing the stranded-job
  state caused by interrupted worker or RabbitMQ handoffs.

## 2026-09-13

### Added

- Added macOS launchd supervision for the ingest worker, OpenSearch index
  worker, and Celery Beat. `make services` now installs and starts all three
  agents, while `make ingest-service-status` reports their state.
- Added persistent RabbitMQ configuration with a seven-day consumer
  acknowledgement timeout so historical tasks can survive extended laptop
  sleep and resume through durable job/archive recovery.

### Changed

- Updated the README and operations documentation to distinguish unattended
  launchd operation from foreground development commands and to prevent
  duplicate workers or Beat schedulers.
- Moved ingest activity classification and heartbeat timestamps into the
  backend's durable progress response, simplifying the admin page to display
  worker-owned state.

### Fixed

- Hardened job claiming, terminal-state protection, stale-job recovery, and
  archive/checkpoint resumption so interrupted workers do not overwrite
  cancelled jobs or repeat completed records.
- Accepted nullable or missing fields present in real Congress.gov bill
  payloads and corrected the OpenSearch mapping for structured
  `actions.source_system` values.

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