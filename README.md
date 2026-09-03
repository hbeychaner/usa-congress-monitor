# Congress Tracker

Congress Tracker collects typed Congress.gov records, stores compressed,
deduplicated SQLite archives, and indexes them into OpenSearch. The system
supports one-off runs, scheduled daily collection, and resumable historical
backfills without staging large JSON or JSONL files.

Endpoint configuration uses centralized string enums for HTTP methods, parameter
locations, pagination modes, ingest resources, and identifier sources. Their
serialized values remain compatible with Congress.gov and the existing endpoint
specifications.

## Quick Start

Requirements: Python 3.13+, `uv`, Docker Desktop, and a Congress.gov API key.

```bash
uv sync --all-extras
# Create .env with CONGRESS_API_KEY and local service settings
make local
make worker
make beat
```

For unattended local operation, use `make start`. It starts OpenSearch,
Redis, and RabbitMQ, then opens a Celery worker and beat scheduler. Beat runs
the normal daily overlap and, every 24 hours, checks durable coverage windows
for date-capable endpoints. When a successful endpoint window is more than 24
hours behind UTC, it queues an idempotent gap job with indexing enabled. The
worker publishes hydrated records to Redis and automatically dispatches their
OpenSearch indexing jobs; no separate indexing command is required.

Inspect durable job states and coverage with:

```bash
make status
```

Static endpoints are not gap-scheduled because their APIs do not expose a
reliable time cursor; they remain covered by the historical/static ingest
plan.

`make worker` uses Celery's `solo` pool for macOS local development. Linux
deployments can use the default prefork pool with multiple processes.

## Run A Backfill

Submit work through the durable job ledger and RabbitMQ queue:

```bash
uv run python scripts/submit_ingest.py \
    --outdir data/full_history \
    --resources bill,committee \
    --from-date 2020-01-01T00:00:00Z \
    --to-date 2020-12-31T23:59:59Z \
    --fetch-items
```

Repeated submissions with the same parameters return the existing job instead
of creating duplicate work. Job records live in SQLite, configured with
`JOB_DB_PATH` (default: `data/jobs.sqlite3`). RabbitMQ is the delivery layer;
SQLite is the durable job history and idempotency store.

Date filters are sent only to resources whose API endpoints support them.
Amendments and other static/global resources are ingested without date filters;
the resource catalog is the source of truth for this behavior.

## Queue A Full Ingest

Start a worker, run the bounded smoke job, then queue the complete historical
plan:

```bash
make worker
uv run python scripts/queue_full_ingest.py --smoke
uv run python scripts/queue_full_ingest.py
```

The planner queues static resources once, date-windowed resources in one-year
windows from 1789 through today, and congress-scoped resources once per
Congress. Use `--dry-run` to inspect a plan, or override the bounds with
`--first-congress`, `--last-congress`, `--start-date`, `--end-date`, and
`--window-days`.

Each job writes fetched list pages to a compressed SQLite cache and item records
to `data/full_history/<job-id>/<resource>/records.sqlite3`. Checkpoints advance
only after a page is persisted, and canonical IDs make retries and overlapping
windows idempotent. Redis remains the indexing handoff, while SQLite tracks job
attempts, failures, and resumable archive state.

## System Flow

```text
Celery Beat or submit_ingest.py
    -> SQLite JobStore
    -> RabbitMQ
    -> Celery worker
    -> Congress.gov -> Redis Stream
    -> RedisIndexingRunner -> OpenSearch
```

Ingest publishes records directly to a durable Redis Stream. Indexing consumes
through a Redis consumer group, transforms and validates records, sends bounded
bulk upserts, and acknowledges entries only after a successful bulk response.
Pending entries can be reclaimed after a worker failure.

The C4 container architecture is in
[worker-architecture.mmd](worker-architecture.mmd),
and operational details are in [documentation/README.md](documentation/README.md).

## Autonomous Operation

Celery Beat submits a bounded daily job at 02:00 UTC. The job covers a
two-day-overlapping window ending on the current UTC date and limits
Congress-scoped resources to the current Congress. Static resources are
excluded because their endpoints do not provide a safe incremental filter.

Transient HTTP, timeout, and connection failures retry with capped exponential
backoff. A recovery task runs every 10 minutes and requeues transient failures
left by older workers or interrupted deliveries. Celery late acknowledgements
and worker-loss requeue protect jobs during process failure.

The migration utility is restart-safe and deletes legacy sources only after
successful verification:

```bash
uv run python scripts/migrate_jsonl_to_sqlite.py data --delete-source
```

## Tests

```bash
make uv-test
OPENSEARCH_INTEGRATION=1 uv run pytest -q tests/integration/test_opensearch_connection.py tests/integration/test_opensearch_roundtrip.py
```

The repository validation baseline is:

```bash
uv run --with ruff ruff check .
uv run pytest -q tests/unit
uv run python -m compileall -q cdm scripts tools
```

## Data Model

The diagram below summarizes the core data models, their relationships, and
the fields used as unique identifiers.

flowchart TB
    subgraph ref["Reference Anchors"]
        CR["**congress_ref**\nid: congress:{N}"]
        MEM["**member**\nid: member:{bioguide_id}"]
    end

    subgraph leg["Legislative"]
        LEG["**legislation**\nid: bill:{congress}:{type}:{number}"]
        AMD["**amendment**\nid: amendment:{congress}:{type}:{number}"]
        HV["**house_vote**\nid: house-rollcall-vote:{congress}:{session}:{roll}"]
        CREC["**congressional_record**\nrecord_subtype: bound|daily"]
    end

    subgraph com["Committee"]
        COM["**committee**\nid: committee:{chamber}:{system_code}"]
        CMTG["**committee_meeting**"]
        CPRT["**committee_print**"]
        CRPT["**committee_report**"]
        HRG["**hearing**"]
    end

    subgraph exec["Executive / Other"]
        NOM["**nomination**"]
        TRE["**treaty**"]
        COMM["**communication**\nchamber: House|Senate"]
        HREQ["**house_requirement**"]
    end

    %% ── congress → congress_ref (shared by almost everything) ──────────────
    LEG  -->|"congress (int)"| CR
    AMD  -->|"congress (int)"| CR
    HV   -->|"congress (int)"| CR
    CREC -->|"congress (int)"| CR
    COM  -->|"congress (int)"| CR
    CMTG -->|"congress (int)"| CR
    CPRT -->|"congress (int)"| CR
    CRPT -->|"congress (int)"| CR
    HRG  -->|"congress (int)"| CR
    NOM  -->|"congress (int)"| CR
    TRE  -->|"congress_received (int)"| CR
    COMM -->|"congress (int)"| CR

    %% ── legislation is the hub ──────────────────────────────────────────────
    AMD  -->|"amended_bill_id = legislation.id"| LEG
    HV   -->|"legislation_id = legislation.id"| LEG
    CRPT -.->|"bill ref (item-level only)"| LEG

    %% ── member links ────────────────────────────────────────────────────────
    AMD  -->|"sponsor_bioguide_id = member.bioguide_id"| MEM
    LEG  -.->|"sponsors / cosponsors (item-level only)"| MEM
    NOM  -.->|"nominees (item-level only)"| MEM

    %% ── committee is a second hub ───────────────────────────────────────────
    COM  -->|"parent_system_code → system_code (self-join)"| COM
    CMTG -.->|"system_code (item-level only)"| COM
    CPRT -.->|"system_code (item-level only)"| COM
    CRPT -.->|"system_code (item-level only)"| COM
    HRG  -.->|"system_code (item-level only)"| COM

    %% ── amendment voted on ──────────────────────────────────────────────────
    HV   -->|"amendment_type + amendment_number"| AMD