# Changelog

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