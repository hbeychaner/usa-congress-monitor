# Congress Tracker

Congress Tracker collects typed Congress.gov records and unmetered GovInfo
bulk data, stores compressed, deduplicated SQLite archives, and indexes
everything into a single canonical document per bill in OpenSearch. The system
supports one-off runs, scheduled daily collection, and resumable historical
backfills without staging large JSON or JSONL files. A FastAPI backend and
React web app serve search, bill detail (including inline full text), and
member activity on top of the search store.

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
make ingest-service-install
```

For unattended macOS operation, use `make services`. It starts OpenSearch,
Redis, and RabbitMQ, then installs launchd-supervised ingest, indexing, and Beat
agents. The agents restart after process failure and resume after login or wake;
they do not require an open Terminal window. Beat runs
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

On macOS, use `make ingest-service-install` for unattended operation and
`make ingest-service-status` to inspect all three agents. Use `make worker`,
`make worker-index`, and `make beat` only for foreground development or
diagnostics. Linux deployments can use the foreground commands or a process
manager with the default prefork pool.

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

Start the supervised services, run the bounded smoke job, then queue the
complete historical plan:

```bash
make services
uv run python scripts/queue_full_ingest.py --smoke
uv run python scripts/queue_full_ingest.py
```

The planner queues static resources once, date-windowed resources in one-year
windows from 1789 through today, and congress-scoped resources once per
Congress. Use `--dry-run` to inspect a plan, or override the bounds with
`--first-congress`, `--last-congress`, `--start-date`, `--end-date`, and
`--window-days`.

A default plan submits ~2,000 jobs. To avoid bursting the broker in one shot,
dispatch is paced with `--batch-size` (default 50) and `--batch-delay` (default
2.0s) — the loop pauses briefly every `batch-size` jobs. Pass `--batch-size 0`
to disable pacing.

## GovInfo Bulk Backfills (bills)

Historical bill work should use GovInfo bulk data instead of the rate-limited
API: the bulk endpoints are public, unauthenticated, and unmetered. Three
collections are supported — BILLSTATUS (full metadata: sponsors, cosponsors,
actions, committees, subjects, summaries, text versions, laws), BILLS
(published text), and BILLSUM (summaries). Parsed records use the same
snake_case field names as the API path, so they merge onto the same canonical
`bill:{congress}:{type}:{number}` documents.

```bash
uv run python scripts/queue_govinfo_bulk.py --congress 118          # dry run
uv run python scripts/queue_govinfo_bulk.py --congress 118 --queue  # merge into live alias
```

Pass `--staging-version N` to write into a versioned staging index instead of
merging live. Downloads are manifest-tracked in SQLite and resumable; each
package is an independently retryable durable job, dispatched in batches.
Bill text from BILLS packages is merged onto the parent bill's `full_text`
field with lifecycle version ranking (`ih` → `enr`; later stages win, and
API-hydrated text is never overwritten). The Congress.gov API remains the
source for daily incremental updates and resources GovInfo does not publish
(amendments, members, nominations, treaties, hearings, votes).

Each job writes fetched list pages to a compressed SQLite cache and item records
to `data/full_history/<job-id>/<resource>/records.sqlite3`. Checkpoints advance
only after a page is persisted, and canonical IDs make retries and overlapping
windows idempotent. Redis remains the indexing handoff, while SQLite tracks job
attempts, failures, and resumable archive state.

## System Flow

```text
Celery Beat / operator CLIs
    -> SQLite JobStore -> RabbitMQ -> Celery worker
         ├─ Congress.gov API pipeline (list + item hydration)
         └─ GovInfo bulk jobs (BILLSTATUS/BILLSUM/BILLS XML)
    -> Redis Stream -> RedisIndexingRunner -> OpenSearch
    -> FastAPI backend -> React web app
```

Ingest publishes records directly to a durable Redis Stream. Indexing consumes
through a Redis consumer group, transforms and validates records, sends bounded
bulk upserts, and acknowledges entries only after a successful bulk response.
Pending entries can be reclaimed after a worker failure. Bill documents merge
null-safely — list-page skeletons, API hydration, and GovInfo bulk records all
converge on one canonical document per bill, with full text stored inline.

Visual documentation (Mermaid, C4-style):

| Diagram | Shows |
|---|---|
| [documentation/diagrams/system-context.mmd](documentation/diagrams/system-context.mmd) | System context: users, web app, backend, workers, external sources |
| [documentation/diagrams/ingest-dataflow.mmd](documentation/diagrams/ingest-dataflow.mmd) | Data flow: sources → jobs → ingest → indexing (merge semantics) → search → serving |
| [documentation/diagrams/backend-components.mmd](documentation/diagrams/backend-components.mmd) | Application components on the serving path (pages, routes, services) |
| [documentation/diagrams/data-model.mmd](documentation/diagrams/data-model.mmd) | Indexed data models, join keys, and unique identifiers |
| [worker-architecture.mmd](worker-architecture.mmd) | Worker and indexing containers (C4 container view) |

Operational details are in [documentation/README.md](documentation/README.md).

## Autonomous Operation

Celery Beat submits a bounded daily job at 02:00 UTC. The job covers a
two-day-overlapping window ending on the current UTC date and limits
Congress-scoped resources to the current Congress. Static resources are
excluded because their endpoints do not provide a safe incremental filter.

Transient HTTP, timeout, and connection failures retry with capped exponential
backoff. A recovery task runs every 10 minutes and requeues transient failures
left by older workers or interrupted deliveries. It also repairs ingest jobs
that remain queued in SQLite for more than 24 hours without a broker delivery.
Celery late acknowledgements and worker-loss requeue protect jobs during
process failure.

## Operations: Start / Restart / Kill Everything

Local defaults (from `.env` / `settings.py`): RabbitMQ at
`amqp://guest:guest@localhost:5672/`, Redis at `redis://localhost:6379/0`,
OpenSearch/Elastic at `http://localhost:9200` (Kibana at `:5601`), backend API
at `http://localhost:8000`, frontend dev server at `http://localhost:5173`.

### Start everything (native processes, macOS)

```bash
make services                 # containers plus launchd-supervised Celery agents
make ingest-service-status    # verify ingest, index, and Beat agents
make backend-api              # FastAPI backend (optional, only if using the web UI)
make frontend-dev             # Vite dev server (optional, only if using the web UI)
```

`make services` uses launchd on macOS, so do not also run the foreground worker,
index worker, or Beat commands for the same queues. On other platforms it
starts those processes in the background with logs under `logs/`.

### Start everything (containerized full stack)

```bash
make stack-up      # infra + backend + worker + worker-index + beat + frontend
```

This builds/starts `docker-compose.fullstack.yml` on top of the local infra
stack. Frontend is served at `http://localhost:5173`, backend at
`http://localhost:8000`.

### Check health

```bash
make status         # durable job states and ingest coverage from SQLite
make health-check    # SQLite, Celery, Redis, OpenSearch, backlog, failures
celery -A cdm.workers.celery_app:celery_app status   # confirm workers are online
```

### Restart

On macOS, restart the supervised agents with `make ingest-service-install`.
Containers only need a restart if their image or Compose file changed:

```bash
make local-stop && make local     # restart infra containers, keep volumes
make stack-down && make stack-up  # restart the full containerized stack
```

The local RabbitMQ configuration allows long-running tasks to survive extended
laptop sleep without expiring their delivery acknowledgements. If RabbitMQ is
recreated after a Compose change, launchd reconnects the Celery agents; verify
with `make ingest-service-status` and `make health-check`.

### Kill

```bash
# Native Celery worker/beat processes (foreground development only)
pkill -f "celery -A cdm.workers.celery_app:celery_app worker"
pkill -f "celery -A cdm.workers.celery_app:celery_app beat"

# macOS launchd-supervised agents
make ingest-service-uninstall

# Native backend/frontend dev servers
pkill -f "uvicorn cdm.backend.app:app"
pkill -f "vite"

# Infra containers (preserves volumes/data)
make local-stop

# Infra containers + delete volumes (destructive, wipes local OpenSearch data)
make local-down

# Full containerized stack
make stack-down
```

Always stop old worker/beat processes before starting new ones after a code
change to `cdm/workers/`. On macOS, use the launchd commands above rather than
starting a second generation in a Terminal; duplicate Beat schedulers can
enqueue duplicate scheduled/recovered jobs.

## Tests

```bash
make uv-test
OPENSEARCH_INTEGRATION=1 uv run pytest -q tests/integration/test_opensearch_connection.py tests/integration/test_opensearch_roundtrip.py
```

The unit suite (`tests/unit`) runs in a few seconds — `tests/unit/conftest.py`
neutralizes the Congress.gov client's real rate-limit sleep (~0.72s/call) so
fixture-driven ingest tests don't incur real wall-clock delay. Tests that
assert on retry/backoff timing (e.g. `tests/unit/test_client.py`) override
this locally and are unaffected.

The repository validation baseline is:

```bash
uv run --with ruff ruff check .
uv run pytest -q tests/unit
uv run python -m compileall -q cdm scripts tools
```

## Data Model

The core indexed models, their join keys, and unique identifiers are diagrammed
in [documentation/diagrams/data-model.mmd](documentation/diagrams/data-model.mmd).
`legislation` is the hub (amendments, votes, and reports join on its canonical
id), `member` joins via flattened bioguide-id arrays, and nearly everything
anchors to `congress_ref`. Bill full text lives inline on the legislation
document -- there is no separate bill-text index.

## Planning & Notes

In-progress design docs, operational runbooks, and architecture review notes
live in `planning/` and are untracked (see `.gitignore`) — they're working
notes, not committed history. `CHANGELOG.md` (this directory) remains the
tracked, dated record of completed work.
