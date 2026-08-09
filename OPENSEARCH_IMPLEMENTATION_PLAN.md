# OpenSearch Implementation Plan

This plan prepares the ingest pipeline for reliable OpenSearch indexing. Each item is implemented and tested before the next item begins.

## Execution Order

- [x] 1. Wire scoped checkpoints into historical ingestion
  - Persist one checkpoint per completed history chunk.
  - Include scope parameters and resource names so stale checkpoints cannot be mistaken for current work.
  - Use Redis Stream pending-entry state as the record-level recovery mechanism.
  - Test completed, failed, and parameter-mismatch behavior.

- [x] 2. Resolve resources to OpenSearch indices
  - Map consolidated resources to their target logical indices.
  - Add discriminator fields such as `source_type`, `chamber`, and `record_subtype` where needed.
  - Test every resource mapping and reject unsupported resources.

- [x] 3. Define the document transformation contract
  - Normalize IDs and reference IDs.
  - Preserve raw payloads under `_raw` where configured.
  - Validate required IDs and transform fields expected by the mappings.
  - Add representative bill/law, communication, and record tests.
  - Every OpenSearch `text` field has a `lemma` text multifield using the
    built-in `whitespace` analyzer for future spaCy-generated lemma arrays;
    OpenSearch-native analysis is not the lemma source of truth.

- [x] 4. Harden bulk indexing behavior
  - Test idempotent upserts, missing IDs, partial failures, and bulk result reporting.
  - Add index and alias lifecycle checks.

- [x] 5. Validate mappings against live-shaped data
  - Compare representative processed records with the OpenSearch mappings.
  - Resolve unmapped or incorrectly shaped fields before indexing.
  - Mapping audits report intentional sparse-schema drift without silently
    discarding fields.

- [x] 6. Add local OpenSearch integration
  - Verify connection and health checks.
  - Create indices and aliases from the mapping definitions.
  - Index and retrieve representative documents.
  - The Makefile now starts Docker Desktop correctly on macOS.
  - Live connection and round-trip tests pass against the local service.

- [x] 7. Connect ingestion to indexing
  - Add an explicit indexing stage after Redis Stream publication.
  - Acknowledge stream entries only after successful bulk responses.
  - Reclaim pending entries after worker crashes and test partial-failure recovery.
  - Add durable SQLite job records with idempotency keys; RabbitMQ carries
    Celery messages but is not the job history or result store.
  - Add late acknowledgements, worker-loss requeue, and bounded exponential
    retry/backoff for transient ingest and OpenSearch failures.
  - Run daily ingestion through Celery beat and submit historical backfills
    through the same idempotent job API.

## Worker Architecture

The worker boundary is intentionally thin:

```text
Celery beat / submit_ingest.py
  -> SQLite JobStore (idempotency and lifecycle)
  -> RabbitMQ
  -> run_ingest_job
  -> Redis Stream consumer group
  -> run_index_job
  -> OpenSearch
```

Start the worker and scheduler with:

```bash
uv run celery -A cdm.workers.celery_app:celery_app worker --pool=solo --loglevel=INFO
uv run celery -A cdm.workers.celery_app:celery_app beat --loglevel=INFO
```

The `solo` pool is used for local macOS development because Celery's default
prefork pool can trigger Objective-C fork-safety aborts. Linux deployments can
use the default prefork pool with multiple worker processes.

Submit a backfill with `uv run python scripts/submit_ingest.py`. Repeating the
same submission returns the existing job instead of creating another run.
The SQLite database is configured by `JOB_DB_PATH` and should live on durable
storage shared by the scheduler and workers. RabbitMQ should use its persistent
Docker volume for message durability.

## Validation Gate

After each item, run its focused tests. Before connecting ingestion to OpenSearch, run the full test suite and the local OpenSearch integration tests when Docker is available.
