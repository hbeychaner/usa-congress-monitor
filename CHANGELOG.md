# Changelog

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