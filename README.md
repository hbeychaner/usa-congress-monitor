# Congress Tracker

Congress Tracker collects typed Congress.gov records and public GovInfo
bulk data, stores compressed, deduplicated SQLite archives, and indexes
resource-specific projections in Elasticsearch, merging bill sources into a
single canonical document per bill. The system
supports one-off runs, scheduled daily collection, and resumable historical
backfills without staging large JSON or JSONL files. A FastAPI backend and
React web app serve search, bill detail (including inline full text), and
member activity on top of the search store.

Bulk writes share one fail-closed boundary: any rejected item fails its batch
with all rejected document IDs/details retained, and Redis acknowledgements wait
for success. Archive recovery requires a complete snapshot rather than adding
possibly overlapping stream/replay counts. See the
[recovery ownership table](documentation/OPERATIONS_RUNBOOK.md#recovery-ownership).

GovInfo reconciliation now defaults to a bounded, read-only preview; offline
inspection is explicit with `--archives-only`. Verified, field-complete snapshots
can correct or remove fields only in an explicitly requested unaliased staging
index. Sparse records preserve richer values, conflicts block writes, and
coverage/freshness gaps remain explicit. Live additive merging is unchanged.
See the [source contract](documentation/guides/ingestion.md#govinfo-replay-and-reconciliation)
and [safe preview procedure](documentation/OPERATIONS_RUNBOOK.md#source-contract-preview-and-staging).
The [dated live inventory](documentation/IMPLEMENTATION_PLAN.md#r03) records
actual aliases, schema differences, observed coverage and remaining release
gates; it does not certify complete upstream history.

Versioned bill hydration evidence is explicitly source-only in the legislation
mapping; its derived `hydration_status` remains searchable. Full-suite mapping
audits guard against silently omitting newly emitted provenance fields.

Graph repair now has a sealed, read-only capture and isolated staging/rollback
workflow. It reconstructs the affected Congress 114 votes from retained CSVs,
stages the full voting scope without publication, and rejects the serving
cluster UUID as a rehearsal target. A separate bounded source-repair command
requires a full historical graph backup/restore proof and conflict-checked,
receipted writes. Voting publication uses a separate measured serving gate and
compare-and-swap pointer switch. See the
[graph rehearsal procedure](documentation/OPERATIONS_RUNBOOK.md#sealed-graph-repair-rehearsal).

The approved retained-deployment repair has restored all 1,824 Congress 114
roll-call source links and added the eight graph mapping paths. Approved voting
promotion now serves 116,450 edges over Congresses 113-119, including 48,655 with
Congress 114 evidence. Real API/desktop/narrow browser checks passed before and
after publication. Other pointers, source versions and historical edges are
preserved. The approved controlled Compose cutover now serves API/UI plus one
index/maintenance worker; all old native agents/processes are retired. Acquisition,
analytics publication, automatic retention scheduling and Beat remain disabled.
Scoped release acceptance passed; this is not full-history, full-load or
unattended-operation certification. See the [dated Gate 4 evidence and limits](documentation/OPERATIONS_RUNBOOK.md#controlled-cutover-acceptance).

Managed startup now checks the combined local Compose memory limits, existing
containers and host free disk before starting services. Run `make stack-capacity`
for a read-only report. This admission check does not certify ingestion capacity,
freshness, sustained performance or independent-host durability.
Historical recovery probes also exposed a member-name serialization defect:
canonical `fullName` output now preserves valid names through alias-based
rehydration, including null alternate names, without weakening validation.
Episode-aware co-sponsor retrieval preserves withdrawal/rejoining history and
checks active and overall source counts separately. Subject counts include the
policy-area row; contradictory source counts still fail closed.
Related-bill totals count nested relationships, not unique bill objects; evidence
also retains the distinct top-level record count so these cannot be confused.
Nested anonymous relationship duplicates remain in the source list; proof
separates source rows from distinct relationships within each related bill.
Action retrieval reconciles source-row counts separately from distinct action
bodies and retains anonymous duplicate multiplicities in source-only proof.
Duplicates do not invent event identities or waive pagination/count checks.
The [local readiness gates](documentation/IMPLEMENTATION_PLAN.md#local-readiness-follow-through)
remain in progress; isolated retrieval candidates are not repaired serving rows.
The isolated backfill's checkpoint distinguishes `retrying` from `failed`;
bounded network recovery preserves candidates without weakening count checks.
This staging experiment does not increase application job/client retry limits.
Full-text download failures now retain a typed network boundary and original
request cause, so existing bounded retries recognize transient disconnects
without retrying permanent HTTP or parsing failures.

## Documentation

The published [wiki](https://github.com/hbeychaner/usa-congress-monitor/wiki)
contains current implementation and operating reference. Planning, incident
history and repository-only evidence are retained in the repository, not
published as wiki pages.

Start with the [documentation home](documentation/README.md), organized by the
questions you need answered:

- [Current engineering/refactoring roadmap](documentation/IMPLEMENTATION_PLAN.md):
  prioritized findings, existing-plan crosswalk, target state and acceptance gates.
- [Architecture and C4 views](documentation/architecture.md) and the
  [rendered visual atlas](documentation/reference/visuals.md).
- [Data structures, identifiers, and relationships](documentation/reference/data-models.md).
- [Index families, field mapping, merging, and acknowledgement rules](documentation/reference/indexing.md).
- [Acquisition and replay data flows](documentation/guides/ingestion.md).
- [API, frontend, and service responsibilities](documentation/reference/api-and-frontend.md).
- [Topics, embeddings, party perspectives, and graph analysis](documentation/guides/analytics.md).
- [Every declared source function/class and typed fields](documentation/reference/symbols/README.md).
- [Configuration and deployment](documentation/guides/configuration-and-deployment.md)
  and the [operations runbook](documentation/OPERATIONS_RUNBOOK.md).

Repository documentation is canonical. The
[GitHub wiki](https://github.com/hbeychaner/usa-congress-monitor/wiki) is its
generated publication copy, not a separate editing location. Prepare pages
locally without publishing:

```bash
uv run python tools/build_documentation.py --wiki documentation/wiki
uv run python tools/build_documentation.py --check --wiki documentation/wiki
```

See [documentation maintenance and wiki publishing](documentation/CONTRIBUTING.md)
for prerequisites, scope, and the later manual publication workflow.
Historical `opensearch` module and mapping names remain in the code; the shipped
runtime uses Elasticsearch and does not promise OpenSearch server compatibility.

Endpoint configuration uses centralized string enums for HTTP methods, parameter
locations, pagination modes, ingest resources, and identifier sources. Their
serialized values remain compatible with Congress.gov and the existing endpoint
specifications.

## Quick Start

Requirements: Python 3.13+, `uv`, Docker with Compose v2 (Docker Desktop on macOS),
and a Congress.gov API key.

```bash
uv sync --all-extras
make local          # creates .env from .env.example (generated local secrets), starts Elasticsearch, Redis, RabbitMQ
# Set CONGRESS_API_KEY in .env
make es-api-key     # one time, once Elasticsearch is up: writes ES_LOCAL_API_KEY / ELASTIC_API_KEY to .env
make up             # API, frontend, one bounded index/maintenance worker; no acquisition or Beat
```

Indices are created on demand by the indexing worker; the job ledger, archives
and record library are created under `data/` on first use.

Normal `uv sync` includes the `dev` and `analysis` dependency groups, preserving
the full development/worker environment. API-only installs use
`--no-default-groups` in a separate environment. Production builds default to the
full `analysis` target for worker/deployment compatibility; opt into the smaller
API image with `docker build --target api -f Dockerfile.prod -t congress-api .`.
Both retain the pinned spaCy model and existing query normalization; only the
analysis target installs BERTopic, Sentence Transformers and their training
dependencies. See [image acceptance](documentation/OPERATIONS_RUNBOOK.md#release-image-and-routing-acceptance)
before using either image.

Compose is the sole supported managed stack; `make up`, `make start`, and
`make services` are aliases. Containers restart after process failure while
Docker is running; on macOS, enable Docker Desktop startup at login. Native
launchd management is retired. Existing agents must be explicitly migrated
before Compose startup; the [runbook](documentation/OPERATIONS_RUNBOOK.md#retiring-native-agents)
preserves their registrations and data. Nothing automatically stops old agents.
Enable optional roles only after reviewing their queues and resource budget in
the [profile guide](documentation/guides/configuration-and-deployment.md#managed-stack-compose).
When explicitly enabled, Beat runs
the normal daily overlap and, every 24 hours, checks durable coverage windows
for date-capable endpoints. When a successful endpoint window is more than 24
hours behind UTC, it queues an idempotent gap job with indexing enabled. The
worker publishes hydrated records to Redis and automatically dispatches their
Elasticsearch indexing jobs; no separate indexing command is required.

Inspect durable job states and coverage with:

```bash
make status
```

Static endpoints are not gap-scheduled because their APIs do not expose a
reliable time cursor; they remain covered by the historical/static ingest
plan.

Use `make stack-status` and `make stack-logs` to inspect managed processes.
Foreground `make worker`, `make worker-index`, `make worker-maintenance`, and
`make beat` remain debugging tools, not a second supervised stack. Do not run
them against the same queues while Compose owns those roles.

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

To refresh only bills whose upstream `updateDate` is newer than the indexed copy,
and keep the refreshed records in a durable local library
(`data/record_library/congress-N/records.sqlite3`):

```bash
uv run python scripts/submit_ingest.py --resources bill --congress 117 \
    --fetch-items --item-resources bill --refresh-stale --retain-records
```

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
API: the bulk endpoints are public and unauthenticated; downloads still use
the application's configured pacing. Three
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
Per-job archive directories are the replay source and are deleted by the daily
retention task 30 days after a job finishes.

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
    -> Redis Stream -> RedisIndexingRunner -> Elasticsearch
    -> FastAPI backend -> React web app
```

Ingest publishes records directly to a durable Redis Stream. Indexing consumes
through a Redis consumer group, transforms and validates records, sends bounded
bulk upserts, and acknowledges entries only after a successful bulk response.
Pending entries can be reclaimed after a worker failure. Bill documents merge
null-safely — list-page skeletons, API hydration, and GovInfo bulk records all
converge on one canonical document per bill, with full text stored inline.

Bill detail pages distinguish **unknown**, **partial**, and versioned **complete**
Congress API detail retrieval. Legacy labels and rich GovInfo records do not
prove API hydration; complete retrieval does not certify full text or historical
coverage. See [hydration evidence](documentation/guides/ingestion.md#bill-hydration-evidence).

Graph publication rejects incompatible mappings and unlinked roll-call inputs.
Graph coverage means observed inputs, not complete legislative history; see the
[graph schema and coverage gates](documentation/guides/analytics.md#schema-and-source-coverage-gates).

Visual documentation ([rendered atlas](documentation/reference/visuals.md);
editable Mermaid sources):

| Diagram | Shows |
|---|---|
| [documentation/diagrams/system-context.mmd](documentation/diagrams/system-context.mmd) | System context: users, web app, backend, workers, external sources |
| [documentation/diagrams/ingest-dataflow.mmd](documentation/diagrams/ingest-dataflow.mmd) | Data flow: sources → jobs → ingest → indexing (merge semantics) → search → serving |
| [documentation/diagrams/backend-components.mmd](documentation/diagrams/backend-components.mmd) | Application components on the serving path (pages, routes, services) |
| [documentation/diagrams/data-model.mmd](documentation/diagrams/data-model.mmd) | Indexed data models, join keys, and unique identifiers |
| [worker-architecture.mmd](worker-architecture.mmd) | Application processes and stores (C4 container view) |
| [documentation/diagrams/bill-request-sequence.mmd](documentation/diagrams/bill-request-sequence.mmd) | Bill request, dependencies, query service, and typed response |
| [documentation/diagrams/deployment.mmd](documentation/diagrams/deployment.mmd) | Local versus GCP runtime and filesystem boundaries |

Start with the [architecture](documentation/architecture.md) for boundaries and
the [indexing reference](documentation/reference/indexing.md) for exact write
semantics; use the [operations runbook](documentation/OPERATIONS_RUNBOOK.md) for recovery.

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

Local defaults (from `.env` via `cdm/config`): RabbitMQ at
`amqp://guest:guest@localhost:5672/`, Redis at `redis://localhost:6379/0`,
Elasticsearch at `http://localhost:9200` (Kibana at `:5601`), backend API
at `http://localhost:8000`, frontend dev server at `http://localhost:5173`.

### One managed stack (Compose, Docker Desktop)

```bash
make down          # stop application containers and infra (volumes kept)
make up            # start Docker if needed, await infra/API readiness, start all roles
make restart       # down, then up
make stack-status  # what is running
```

Interrupted ingest jobs resume automatically after `make up`: the maintenance
worker requeues jobs whose heartbeat went silent within about 20 minutes.

`make stack-up` is the same managed startup path. It builds frozen dependencies
once per image, rather than syncing/installing packages in every process at
startup. The stack includes API, frontend, ingest, bulk/default, indexing,
maintenance, analytics and exactly one Beat service. Frontend is
`http://localhost:5173`, backend `http://localhost:8000`.

### Check health

```bash
make status         # durable job states and ingest coverage from SQLite
make health-check    # SQLite, Celery, Redis, Elasticsearch, backlog, failures
celery -A cdm.workers.celery_app:celery_app status   # confirm workers are online
```

### Restart

```bash
make local-stop && make local     # restart infra containers, keep volumes
make restart                      # rebuild/restart the managed stack, keep volumes
```

The local RabbitMQ configuration allows long-running tasks to survive extended
laptop sleep without expiring their delivery acknowledgements. If RabbitMQ is
recreated after a Compose change, Celery reconnects; verify with
`make stack-status` and `make health-check`.

### Kill

```bash
# Native foreground Celery/API/frontend processes:
# Use Ctrl+C in each owning terminal, or kill only a verified PID you own.

# Infra containers (preserves volumes/data)
make local-stop

# Infra containers + delete volumes (destructive, wipes local Elasticsearch data)
make local-down

# Full containerized stack
make stack-down
```

Always stop old worker/Beat processes before switching managers; duplicate Beat
schedulers can enqueue duplicate scheduled/recovered jobs. The retired native
service targets now fail with migration guidance rather than installing agents.

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

Compose rendering tests run from their isolated project directory with a
matching `PWD`, keeping absolute archive-mount checks independent of the runner's
Compose environment handling.

The repository validation baseline is:

```bash
uv run --with ruff ruff check .
uv run pytest -q tests/unit
uv run python -m compileall -q cdm scripts tools
```

Frontend checks (Node 22.18+):

```bash
npm --prefix frontend/app ci
npm --prefix frontend/app run audit
npm --prefix frontend/app test
npm --prefix frontend/app run contracts:check
cd frontend/app
npx playwright install chromium
npm run test:browser
```

The [contracts workflow](.github/workflows/contracts.yml) also runs the browser
gate. It builds and owns an isolated preview, uses typed API fixtures, and blocks
unexpected network requests; no running backend or live API budget is needed.
Audits include development dependencies and fail on low-or-higher advisories.
Offline contract generation uses Hey API's type-only generator; it does not add
a runtime client or require a running API.
See [browser acceptance](documentation/reference/api-and-frontend.md#browser-acceptance-gate)
for coverage, failure artifacts, and the remaining integration/release gates.

The same workflow provisions bounded, disposable Elasticsearch and Redis services
for real partial-bulk/reclaim/archive-recovery, publication/rollback, and measured
query-budget tests. It also checks durable job recovery and lints the new pipeline
acceptance module. These selected suites use synthetic records, not source APIs.
See [controlled pipeline acceptance](documentation/OPERATIONS_RUNBOOK.md#controlled-pipeline-acceptance)
for isolated-service requirements, the exact selectors, and limits of this gate.
The recovery case also captures a live SQLite WAL through the backup API, kills
the writer process, restores ledger/archive snapshots without deleting the
pre-restore files, and verifies recovery dispatch plus archive replay.

Production-image checks are a separate **manual pre-release** job in that workflow
(Actions -> API contracts -> Run workflow). They build locally, never push images,
and verify bounded API/frontend startup plus real RabbitMQ delivery and prefork
worker discovery. See [release image acceptance](documentation/OPERATIONS_RUNBOOK.md#release-image-and-routing-acceptance).

## Data Model

The core indexed models, their join keys, and unique identifiers are diagrammed
in [documentation/diagrams/data-model.mmd](documentation/diagrams/data-model.mmd).
Bills use canonical `bill:{congress}:{type}:{number}` IDs. Member relationships
use bare Bioguide IDs; House votes join bills by Congress/type/number components,
while resolved Voteview roll calls carry `legislation_id`. Mapped relationship
fields are not always synthesized by the normal indexer, and declared bridge
indices are not automatically populated. These are logical query joins, not
database-enforced foreign keys. Bill full text lives inline on the legislation
document -- there is no separate bill-text index. See the
[data structures](documentation/reference/data-models.md) and
[indexing rules](documentation/reference/indexing.md) for precise behavior.

## Topic Model And Metasubjects

`scripts/train_topic_model.py` (or the Retrain button on the Admin page) embeds
every bill from `--min-congress` onward, clusters the embeddings with BERTopic,
labels topics with Ollama, then groups topic centroids into about 30
metasubjects. Embeddings live in the `congress-embeddings` index (one vector per
bill, cached by content hash, also used by `GET /bills/{id}/similar`); topics,
metasubjects, assignments and quarterly trends live in
`congress-analysis-topics`, and each retrain prunes superseded versions.

- Outlier bills are reassigned to the nearest metasubject and flagged
  `low_confidence` below `metasubject_low_confidence_similarity` (0.5).
- Group ids are stable across retrains (centroid matching). Names carry over
  unless a group's size changes by more than 3x; duplicate names are resolved by
  a second Ollama pass.
- Rename a group by hand with
  `uv run python scripts/set_metasubject_override.py <id> "Name"` (`--clear`,
  `--history`); overrides apply on the next retrain.
- `GET /topics/metasubjects/{id}` returns the group's topics, trend and related
  groups by centroid similarity.
- `GET /topics/{id}` includes `related` topics ranked by centroid similarity (centroids are stored on topic documents at training).
- `GET /graph/topic-neighborhood?kind=metasubject|topic|subject&key=...` returns
  the top sponsors of a metasubject, topic or CRS subject (same node/link shape as
  the member neighborhood). The graph page's "Centered on topics" mode uses it.

## Parties And Perspectives

`scripts/build_perspectives.py --congress 119 --all-topics` reads one Congress's
policy bills (resolutions and ceremonial measures excluded), assigns them to
the latest topic model, and stores per-topic party contrast documents
(`kind=party_topic`) in the analysis index. Each topic gets the CRS subjects and
phrases (backed by bill and sponsor counts) each party uses more than the other, a one-sentence Ollama summary per party, a
bipartisan-support share (cross-party cosponsors or a qualifying passage vote;
"Bilateral Support" at 25% or more), and optional
clusters that are surfaced only when stable. Use `--dry-run` to print instead
of write and `--no-llm-labels` to skip Ollama. The frontend `/parties` page
reads `GET /api/v1/parties?congress=` and `GET /api/v1/parties/topics/{id}`.

The current Congress is rebuilt automatically every Monday at 07:00 (after the
Sunday topic retrain) and on demand from the Admin page's "Party perspectives"
card (`GET`/`POST /api/v1/admin/perspectives`). Status is kept in
`data/perspective_build_status.json` and output in `logs/perspectives.log`.

## Deploying To Google Cloud

Terraform in `infra/terraform` provisions a private deployment behind Google sign-in (Identity-Aware Proxy).

```text
Browser -> HTTPS load balancer + IAP (allowed Google accounts only)
  /api/*, /health, /docs -> Cloud Run: API   (Direct VPC egress)
  everything else        -> Cloud Run: frontend (nginx static build)
Cloud Run API -> VPC -> worker VM (RabbitMQ, Redis) and search VM (Elasticsearch)
Worker VM: Celery workers + beat, jobs ledger, status files, build logs on a snapshotted disk
```

- Search runs as self-managed Elasticsearch 9 on a Compute Engine VM. The code uses the `elasticsearch` client, so OpenSearch is not a drop-in replacement.
- Worker VM state (`data/`, `logs/`, `models/`) lives on a persistent disk with daily snapshots. Admin status routes that read those local files only work where that disk is mounted, not on Cloud Run.
- Vertex AI access (`roles/aiplatform.user`) is granted to the API and worker service accounts; the LLM client is still Ollama until a Vertex client is added.

Steps:

1. Create a state bucket, then `cd infra/terraform && terraform init -backend-config="bucket=<bucket>"`. Copy `terraform.tfvars.example` to `terraform.tfvars` and set `project_id` and `iap_members`; export `TF_VAR_congress_api_key`.
2. Create the registry: `terraform apply -target=google_artifact_registry_repository.images -target=google_project_service.apis`.
3. Push images: `deploy/gcp/build_push.sh <project_id> [region] [tag]`.
4. `terraform apply` to create the network, secrets and VMs. The search VM publishes the app API key to Secret Manager on first boot; the worker VM waits for it.
5. Configure the project OAuth consent screen once, set `deploy_apps = true`, and `terraform apply` for Cloud Run, the load balancer and IAP.
6. Point a DNS A record for `domain` at the `dns_a_record` output; the managed certificate activates after DNS resolves.

## Planning & Notes

In-progress design docs, operational runbooks, and architecture review notes
live in `planning/` and are untracked (see `.gitignore`) — they're working
notes, not committed history. `CHANGELOG.md` (this directory) remains the
tracked, dated record of completed work.
