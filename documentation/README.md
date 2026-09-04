# Congress Tracker

## Worker Service

The production execution path separates durable state from message delivery:

| Component | Responsibility | Durable state |
|---|---|---|
| Celery Beat | Enqueues the daily UTC ingest window at 02:00 | SQLite job record |
| RabbitMQ | Delivers ingest and indexing messages | Persistent broker volume |
| Celery worker | Runs ingest and indexing tasks | SQLite job lifecycle |
| `JobStore` | Owns idempotency, status, attempts, and errors | `JOB_DB_PATH` SQLite database |
| `IngestRunner` | Pulls Congress.gov lists and publishes details | Redis Stream entries |
| `RedisIndexingRunner` | Consumes, transforms, and bulk-upserts records | Redis pending-entry state |
| OpenSearch | Serves indexed documents and aliases | OpenSearch indices |

[C4 worker architecture diagram](../worker-architecture.mmd)

The C4 boundary separates four kinds of state: RabbitMQ transports Celery
messages, SQLite records job identity and lifecycle, Redis Streams are the
durable replayable ingest handoff, and OpenSearch is the searchable projection.
The worker task is orchestration; `IngestRunner` and `RedisIndexingRunner` own
the domain behavior and can be tested independently of Celery.

### Job lifecycle

Jobs use a deterministic idempotency key derived from their kind and payload.
The lifecycle is `queued -> running -> retrying -> succeeded` or `failed`. A worker marks
the job running before work begins and marks it succeeded only after all work,
including child indexing jobs, has been dispatched successfully.

Celery is configured with late acknowledgements and worker-loss requeue.
Transient task failures retry without a fixed terminal count, using capped
exponential backoff. Non-transient failures remain terminal, and a scheduled
recovery task requeues transient failures stranded by older workers. The task functions are thin
wrappers; ingest, transformation, validation, and checkpoint semantics remain
in ordinary Python services so they can be tested without a broker.

### Retry and failure behavior

- Congress.gov request retries remain inside the API client.
- Celery retries transient task-level failures indefinitely; `CELERY_RETRY_MAX`
  remains the bound for non-transient failures.
- Backoff is capped by `CELERY_RETRY_BACKOFF_MAX` seconds.
- Index checkpoints advance only after `bulk_upsert()` reports no errors.
- A failed batch is retried from its prior offset; already committed batches
  are skipped on restart.
- A source fingerprint resets indexing to offset zero when the durable input
  file changes.

### Daily ingestion

Celery Beat schedules `schedule_daily_ingest` at 02:00 UTC and
`recover_failed_ingest_jobs` every 10 minutes. The daily task submits a
two-day overlapping window ending on the current UTC date, includes only
date-windowed and valid Congress-scoped resources, and excludes static/global
endpoints. The overlap catches late API updates; canonical IDs and OpenSearch
upserts make it idempotent.

### Historical backfills

Use the submission CLI for backfills rather than invoking worker internals:

```bash
uv run python scripts/submit_ingest.py \
  --outdir data/full_history \
  --resources bill,committee \
  --from-date 2020-01-01T00:00:00Z \
  --to-date 2020-12-31T23:59:59Z \
  --fetch-items \
  --index-batch-size 500
```

The same payload produces the same job ID. Existing ingest files and indexing
checkpoints prevent completed work from being repeated unnecessarily.

Local commands:

```bash
make worker  # macOS-safe solo pool
make beat
```

For Linux production workers, omit `--pool=solo` and choose concurrency based
on API rate limits and OpenSearch capacity.

### GovInfo coverage audits

Before scaling a historical GovInfo run, compare the discovered package
inventory with the durable per-job manifests:

```bash
uv run python scripts/report_govinfo_coverage.py \
  --congress 118 \
  --manifest-root data/full_history/govinfo \
  --out data/full_history/govinfo/coverage-report-118.json
```

The report classifies each expected package as `available`, `failed`,
`not_available`, or `pending`. It exits with status 2 while failed or pending
packages remain, and preserves the non-available distinctions for acceptance
reporting. A parsed package counts as available.

## Setup

### Prerequisites
- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for local OpenSearch)
- A [Congress.gov API key](https://api.congress.gov/sign-up/)

### Install dependencies

```bash
# Install uv if you don't have it
brew install uv

# Create .venv and install all dependencies (reads pyproject.toml)
uv sync --all-extras

# Activate the virtual environment (optional — prefix commands with 'uv run' instead)
source .venv/bin/activate
```

### Environment variables

Create a `.env` file in the project root:

```
CONGRESS_API_KEY=your_key_here
ELASTIC_API_URL=http://localhost:9200
ELASTIC_API_KEY=...          # preferred over user/password
ES_LOCAL_PASSWORD=...        # local dev only
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
JOB_DB_PATH=data/jobs.sqlite3
OPENAI_API_KEY=...           # optional — generative features
```

### Start local OpenSearch

```bash
# Requires Docker Desktop running
cd elastic-start-local && ./start.sh
```

### Run tests

```bash
PYTHONPATH=. uv run pytest -q
```

---

## Architecture

```
cdm/                    — Congress Data Model (core library)
  data_collection/
    client.py            — Congress.gov HTTP client; enforces rate limiting
                           on every request via an injected/default TokenBucket
  utils/
    rate_limiter.py      — Thread-safe token bucket (default 4800 req/hr)
  ingest/               — API collection pipeline
    resource_config.py  — Per-resource metadata (scope, date params, etc.)
    runner.py           — Single-resource ingest (list + items, concurrent)
    pipeline.py         — Multi-resource orchestration
    archive.py          — Compressed SQLite record archives and list caches
    checkpoint.py       — Resume state tracking
  jobs/store.py         — SQLite job ledger and idempotency store
  workers/              — Celery app, beat schedule, and task wrappers
  store/                — OpenSearch integration
    index_manager.py    — Loads opensearch_mappings.yaml, manages indices
    opensearch.py       — Bulk upsert helpers
    indexer.py          — Transforms records into OpenSearch documents
    redis_indexing.py    — Redis Stream consumer and bulk indexing runner
  links/                — Cross-index relationship resolution
  search/               — Query helpers

scripts/
  ingest_history.py     — Full-history bulk ingest CLI (year-by-year + congress-by-congress)
  submit_ingest.py      — Idempotent RabbitMQ/Celery job submission CLI
  create_indices.py     — OpenSearch index creation/update CLI
  ingest.py             — Single-resource ingest CLI

documentation/
  opensearch_mappings.yaml  — Single source of truth for all 17 OpenSearch indices
  README.md                 — This file
```

### Ingest pipeline

Resources are classified into three scopes:

| Scope | Strategy | Examples |
|---|---|---|
| `date_window` | Uses configured date parameter names | bill, committee, member, nomination, … |
| `congress_scoped` | Requires a Congress path parameter | law |
| `static` | No server-side incremental filter | amendment, house_vote, congress, and reference collections |

Item fetches use a `ThreadPoolExecutor`. A single `TokenBucket` rate limiter
(worker default: 4800 req/hr) is injected into `IngestRunner` and shared by
every per-thread `CDGClient`, which enforces it on every HTTP call (both list
pages and item fetches) so the pipeline stays within the API's 4 800 req/hr
limit with one coordinated budget instead of per-client throttling. Each
deduplicated item is published directly to the resource's Redis Stream;
consumer-group pending state provides crash recovery. List pages and item
records are compressed and deduplicated in per-resource SQLite databases.

### Full-history ingest

```bash
uv run python scripts/ingest_history.py \
  --from-year 2020 --to-year 2026 \
  --items \
  --outdir data/full_history \
  --resume \
  --concurrency 20 \
  --rate-limit 4800
```

For durable queue submission, use `scripts/queue_full_ingest.py`; it creates
idempotent jobs for static resources, date windows, and Congress-scoped
resources. `scripts/ingest_history.py` remains a local compatibility/backfill
tool. Both use SQLite checkpoints and avoid large local JSON or JSONL staging
files.

For a complete historical legislation corpus, discover and queue official
GovInfo packages into a precreated versioned OpenSearch index:

```bash
uv run python scripts/queue_govinfo_bulk.py --congress 118
uv run python scripts/queue_govinfo_bulk.py \
  --congress 118 --queue --staging-version 118 \
  --outdir data/full_history/govinfo
```

The first command is a dry run. Queueing requires `--staging-version`; workers
fail closed if that physical staging index does not exist. Switch aliases only
after package, document, and reconciliation acceptance checks pass.

### OpenSearch indices

17 indices defined in `documentation/opensearch_mappings.yaml`:

| Index | Description |
|---|---|
| `legislation` | Bills and resolutions |
| `amendment` | Floor and committee amendments |
| `communication` | House and Senate communications |
| `committee` | Standing, select, and joint committees |
| `committee_meeting` | Committee meeting records |
| `committee_print` | Committee print publications |
| `committee_report` | Committee reports |
| `congressional_record` | Bound and daily Congressional Record |
| `hearing` | Congressional hearings |
| `house_vote` | House roll-call votes |
| `member` | Members of Congress |
| `nomination` | Presidential nominations |
| `treaty` | Treaties |
| `congress_ref` | Reference anchor per Congress (116–119) |
| `house_requirement` | Statutory reporting requirements |
| `sponsorship` | Bridge index: member ↔ legislation |
| `vote_position` | Bridge index: member ↔ house_vote |

Create or update all indices:

```bash
uv run python scripts/create_indices.py            # create all
uv run python scripts/create_indices.py --status   # show index stats
uv run python scripts/create_indices.py --update   # update mappings in place
```

---

# Data Structures Overview

This diagram summarizes the core data models, their relationships, and the field(s) used as unique identifiers where applicable. Composite IDs are noted when a single field is not sufficient.

## Using the Client

The project uses its native `CDGClient` to wrap the Congress.gov API. The client reads the API key from `CONGRESS_API_KEY`, and response models are defined in `cdm.models`.

```python
from cdm.data_collection.client import CDGClient

client = CDGClient()  # reads CONGRESS_API_KEY from environment
members = client.get_members(limit=5)
```

## Using Endpoint Helpers

Endpoint modules live under cdm/data_collection/specs and provide typed endpoint specifications for parsed API responses.

```python
from cdm.data_collection.client import CDGClient
from cdm.data_collection.endpoints.member import get_members_list, gather_members

client = CDGClient(api_key="YOUR_API_KEY")

# raw paginated response
page = get_members_list(client, offset=0, pageSize=250)

# aggregated results for non-paginated endpoints
members = gather_members(client)
```

For paginated endpoints that expose list-level results, use the shared pagination helpers in cdm/data_collection/utils.py. They accept a page-fetcher and the response list key from `CongressDataType` in cdm/models/data_types.py.

```python
from cdm.data_collection.client import CDGClient
from cdm.data_collection.utils import gather_paginated_metadata
from cdm.data_collection.data_types import CongressDataType
from cdm.data_collection.endpoints.bill import get_bills_metadata

client = CDGClient(api_key="YOUR_API_KEY")

all_bills = gather_paginated_metadata(
    lambda offset, page_size: get_bills_metadata(
        client, offset=offset, pageSize=page_size
    ),
    data_key=CongressDataType.BILLS,
    desc="Bills",
    unit="bill",
)
```

## Data Collection Orchestration

> **Note:** the `cdm/data_collection/collector.py` module this section used to document
> was unused dead code and has been removed. Current ingest orchestration lives in
> `cdm/ingest/pipeline.py` and `cdm/ingest/runner.py`, dispatched via
> `cdm/workers/tasks.py` Celery tasks.


## Daily Window Collector

Use cdm/data_collection/daily_collector.py to gather all top-level list endpoints in a
24-hour window, fetch detail records for each item URL, and collect member metadata
referenced by any details. Outputs are written as JSON files grouped by endpoint name.

## Streamlit App

The Streamlit app now lives under app/. Launch it from the repository root with:

```
streamlit run app/dashboard.py
```

Additional Streamlit pages are located in app/pages.

## Documentation Index

- [AmendmentEndpoint.md](AmendmentEndpoint.md)
- [BillEndpoint.md](BillEndpoint.md)
- [BoundCongressionalRecordEndpoint.md](BoundCongressionalRecordEndpoint.md)
- [CommitteeEndpoint.md](CommitteeEndpoint.md)
- [CommitteeMeetingEndpoint.md](CommitteeMeetingEndpoint.md)
- [CommitteePrintEndpoint.md](CommitteePrintEndpoint.md)
- [CommitteeReportEndpoint.md](CommitteeReportEndpoint.md)
- [CongressEndpoint.md](CongressEndpoint.md)
- [CRSReportEndpoint.md](CRSReportEndpoint.md)
- [DailyCongressionalRecordEndpoint.md](DailyCongressionalRecordEndpoint.md)
- [HearingEndpoint.md](HearingEndpoint.md)
- [HouseCommunicationEndpoint.md](HouseCommunicationEndpoint.md)
- [HouseRequirementEndpoint.md](HouseRequirementEndpoint.md)
- [HouseRollCallVoteEndpoint.md](HouseRollCallVoteEndpoint.md)
- [MemberEndpoint.md](MemberEndpoint.md)
- [NominationEndpoint.md](NominationEndpoint.md)
- [SenateCommunicationEndpoint.md](SenateCommunicationEndpoint.md)
- [SummariesEndpoint.md](SummariesEndpoint.md)
- [TreatyEndpoint.md](TreatyEndpoint.md)

## People & Identity

```mermaid
classDiagram
  direction TB
  class Member
  Member : +bioguide_id [ID]
  Member : +first_name
  Member : +middle_name
  Member : +last_name
  Member : +full_name
  Member : +party
  Member : +state
  Member : +district
  Member : +url
  Member : +is_original_cosponsor
  Member : +is_by_request
  class Sponsor
  Sponsor : +sponsorship_date
  Sponsor : +sponsorship_withdrawn_date
  Member <|-- Sponsor

  class Depiction {
    +image_url
    +attribution
  }
  class Term {
    +chamber
    +start_year
    +end_year
  }
  Member o-- Depiction
  Member o-- Term
```

## Bills & Amendments

```mermaid
classDiagram
  direction TB
  class Bill {
    +congress
    +type
    +number [ID*]
    +title
    +update_date
  }
  class BillLatestAction {
    +action_date
    +text
  }
  class Action {
    +action_date
    +text
  }
  class Summary {
    +action_date
    +action_desc
    +version_code
  }
  class TextVersion {
    +date
    +type
  }
  class Title {
    +title
    +title_type
  }
  class LawMetadata {
    +number [ID*]
    +law_type
  }
  class Subjects {
    +legislative_subjects
    +policy_area
  }
  class PolicyArea {
    +name
    +update_date
  }
  class LegislativeSubject {
    +name
    +update_date
  }
  class CommitteeMetadata {
    +system_code [ID]
    +name
  }
  class Amendment {
    +congress
    +type
    +number [ID*]
    +update_date
  }

  Bill o-- BillLatestAction
  Bill o-- Action
  Bill o-- Summary
  Bill o-- TextVersion
  Bill o-- Title
  Bill o-- LawMetadata
  Bill o-- Subjects
  Subjects o-- PolicyArea
  Subjects o-- LegislativeSubject
  Bill o-- CommitteeMetadata
  Bill o-- Sponsor
  Bill o-- Amendment

  Amendment o-- Action
  Amendment o-- Member
  Amendment o-- TextVersion
```

## Congressional Records

```mermaid
classDiagram
  direction TB
  class CongressionalRecordIssue {
    +Id [ID]
    +Congress
    +Issue
    +PublishDate
  }
  class BoundCongressionalRecord {
    +id [ID]
    +congress
    +volume
    +issue
  }
  class DailyCongressionalRecordIssue {
    +volume_number [ID*]
    +issue_number [ID*]
  }
```

## List-level API Items (1/3)

```mermaid
classDiagram
  direction TB
  class MemberListItem {
    +bioguideId [ID]
    +name
    +updateDate
  }
  class CommitteeListItem {
    +systemCode [ID]
    +name
    +updateDate
  }
  class CommitteeReportListItem {
    +cmte_rpt_id [ID]
    +citation
  }
  class CommitteePrintListItem {
    +jacketNumber [ID]
  }
  class CommitteeMeetingListItem {
    +eventId [ID]
  }
  class HearingListItem {
    +jacketNumber [ID]
  }
```

## List-level API Items (2/3)

```mermaid
classDiagram
  direction TB
  class HouseCommunicationListItem {
    +congress
    +communicationType
    +number [ID*]
  }
  class SenateCommunicationListItem {
    +congress
    +communicationType
    +number [ID*]
  }
  class HouseRequirementListItem {
    +number [ID]
  }
  class HouseRollCallVoteListItem {
    +identifier [ID]
    +rollCallNumber
  }
```

## List-level API Items (3/3)

```mermaid
classDiagram
  direction TB
  class NominationListItem {
    +citation [ID*]
    +number
  }
  class CRSReportListItem {
    +id [ID]
    +title
  }
  class BillListItem {
    +congress
    +type
    +number [ID*]
  }
  class AmendmentListItem {
    +congress
    +type
    +number [ID*]
  }
  class TreatyListItem {
    +congressReceived
    +number [ID*]
  }
  class LawListItem {
    +congress
    +number [ID*]
  }

  %% [ID]  = single-field unique identifier
  %% [ID*] = composite identifier; typically requires (congress + type + number) or similar
```

## ID Notes
- **Bills**: typically identified by `(congress, type, number)`.
- **Amendments**: typically identified by `(congress, type, number)`.
- **Treaties**: typically identified by `(congressReceived, number, suffix)`.
- **House/Senate communications**: often `(congress, communicationType.code, number)`.
