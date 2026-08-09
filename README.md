# Congress Tracker

Congress Tracker collects typed Congress.gov records, stores durable ingest
outputs, and indexes them into OpenSearch. The system supports one-off runs,
scheduled daily collection, and resumable historical backfills.

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

`make worker` uses Celery's `solo` pool for macOS local development. Linux
deployments can use the default prefork pool with multiple processes.

## Run A Backfill

Submit work through the durable job ledger and RabbitMQ queue:

```bash
uv run python scripts/submit_ingest.py \
    --outdir data/full_history \
    --resources amendment,bill \
    --from-date 2020-01-01T00:00:00Z \
    --to-date 2020-12-31T23:59:59Z \
    --fetch-items
```

Repeated submissions with the same parameters return the existing job instead
of creating duplicate work. Job records live in SQLite, configured with
`JOB_DB_PATH` (default: `data/jobs.sqlite3`). RabbitMQ is the delivery layer;
SQLite is the durable job history and idempotency store.

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
and operational details are in [Documentation/README.md](Documentation/README.md).

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