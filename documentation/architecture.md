# Architecture

[Documentation home](README.md) | [Visual atlas](reference/visuals.md)

## Purpose and boundaries

Congress Tracker collects U.S. legislative data, saves raw archives so data can
be replayed locally without re-downloading, indexes normalized records into
Elasticsearch, and serves search and analysis through a FastAPI backend and
React frontend.

To keep long-running data collection reliable on a single machine, the system
separates four responsibilities:
- **Task delivery (RabbitMQ):** Routes background tasks to Celery workers.
- **Durable job history & archives (SQLite):** Tracks job status, retries, and
  downloaded source payloads so interrupted runs can resume or replay cleanly.
- **Record handoff (Redis Streams):** Buffers fetched records between
  acquisition workers and indexing workers.
- **Search & analysis store (Elasticsearch):** Holds searchable entity
  documents, cached embeddings, topic models, party perspectives, and member
  graphs.

## C4 zoom levels

| View | Question answered | Diagram |
|---|---|---|
| C4 level 1: context | Who uses Congress Tracker, and which external systems feed it? | [Context](reference/visuals.md#system-context) |
| C4 level 2: containers | Which applications, workers, and data stores run together? | [Container view](reference/visuals.md#worker-architecture) |
| C4 level 3: components | How do the React frontend and FastAPI backend handle a request? | [Backend components](reference/visuals.md#backend-components) |
| Data-flow view | How does a record move from Congress.gov/GovInfo into Elasticsearch? | [Ingest flow](reference/visuals.md#ingest-dataflow) |
| Logical data view | How do IDs link bills, members, votes, topics, and graph edges? | [Data relationships](reference/visuals.md#data-model) |
| Request sequence | What happens step-by-step when a user opens a bill page? | [Request sequence](reference/visuals.md#bill-request-sequence) |
| Deployment view | How does the local Docker Compose stack compare to the GCP design? | [Deployment](reference/visuals.md#deployment) |

## Runtime responsibilities

| Component | Primary responsibility | What it does not own |
|---|---|---|
| Operator CLIs (`scripts/`) | Plan and submit jobs, inspect status, run imports/rebuilds | Serving live web traffic |
| Celery Beat | Enqueue scheduled refresh tasks when the `scheduler` profile is enabled | Job state history |
| RabbitMQ | Deliver Celery task messages to worker queues | Permanent job history |
| Celery workers | Run acquisition, indexing, maintenance, and analytics jobs | HTTP API request handling |
| SQLite job ledger | Track job identity, status, heartbeats, retries, and date coverage | Full-text search |
| SQLite archives & library | Store raw downloaded pages/items for local replay | Serving end-user search queries |
| Redis | Buffer records in Redis Streams and coordinate rate limits | Long-term archival storage |
| Elasticsearch | Store and query bills, members, votes, embeddings, topics, and graphs | Task scheduling |
| FastAPI | Validate HTTP parameters and return typed Pydantic responses | Background data collection |
| React / Vite | Render pages, charts, and interactive graphs | Direct database access |
| Native host Ollama | Generate human-readable labels for topics and metasubjects | Authoritative legislative facts |

All managed Docker Compose Python containers mount a shared SQLite job ledger
volume at `/var/lib/congress/jobs.sqlite3`. See the
[live SQLite operating boundary](OPERATIONS_RUNBOOK.md#live-sqlite-operating-boundary)
before backing up or restoring the ledger, and see the
[ingestion guide](guides/ingestion.md) and
[indexing reference](reference/indexing.md) for pipeline details.

## Code map

| Package / Folder | Role | Learn more |
|---|---|---|
| [cdm/config](../cdm/config) | Typed `pydantic-settings` configuration sections | [Configuration guide](guides/configuration-and-deployment.md) |
| [cdm/container.py](../cdm/container.py) | Main composition root for the API and CLI tools | [Composition symbols](reference/symbols/composition.md) |
| [cdm/data_collection](../cdm/data_collection) | Congress.gov endpoint specs, URL parsers, HTTP client, pagination | [Ingestion guide](guides/ingestion.md) |
| [cdm/models](../cdm/models) | Pydantic models for upstream Congress.gov records | [Data models](reference/data-models.md) |
| [cdm/ingest](../cdm/ingest) | Ingestion planning, item hydration, SQLite archives, GovInfo & Voteview | [Ingestion guide](guides/ingestion.md) |
| [cdm/jobs](../cdm/jobs) | Typed job payloads and SQLite `JobStore` lifecycle | [Data models](reference/data-models.md) |
| [cdm/workers](../cdm/workers) | Celery worker entry points and task dispatch | [Ingestion guide](guides/ingestion.md) |
| [cdm/store](../cdm/store) | Elasticsearch index manager, projections, bulk indexing, repositories | [Indexing reference](reference/indexing.md) |
| [cdm/graph](../cdm/graph) | Member collaboration, voting agreement, and topic-similarity graphs | [Analytics guide](guides/analytics.md) |
| [cdm/perspectives](../cdm/perspectives) | Party-topic framing clusters and distinguishing phrase extraction | [Analytics guide](guides/analytics.md) |
| [cdm/topics](../cdm/topics) & [cdm/utils](../cdm/utils) | Lemmatization, cached embeddings, BERTopic training, Ollama labeling | [Analytics guide](guides/analytics.md) |
| [cdm/backend](../cdm/backend) | FastAPI application, dependency providers, error handlers, query services | [API and frontend reference](reference/api-and-frontend.md) |
| [cdm/contracts](../cdm/contracts) | Typed Pydantic request and response models for the HTTP API | [API and frontend reference](reference/api-and-frontend.md) |
| [frontend/app/src](../frontend/app/src) | React pages, visualization components, and typed API client wrappers | [API and frontend reference](reference/api-and-frontend.md) |
| [scripts](../scripts) | CLI utilities for setup, ingestion, analytics, and maintenance | [Operations runbook](OPERATIONS_RUNBOOK.md) |
| [infra](../infra/terraform) / [deploy](../deploy/gcp) | Terraform and Docker Compose templates for Google Cloud deployment | [Deployment guide](guides/configuration-and-deployment.md) |

## Configuration and dependency injection

- **[AppConfig](../cdm/config/app_config.py)** organizes all environment
  settings into typed `pydantic-settings` sections (`elastic`, `congress_api`,
  `queue`, `redis`, `ledger`, `ollama`, `api`, etc.).
- **[Container](../cdm/container.py)** is the composition root for the FastAPI
  server and job-submission CLIs. It constructs and caches clients and query
  services without importing heavy ML training libraries (`torch`, `bertopic`,
  `sentence-transformers`).
- **[OperationsContainer](../cdm/workers/operations.py)** extends `Container`
  with ingestion, indexing, and maintenance runners.
- **[WorkerContainer](../cdm/workers/runtime.py)** extends
  `OperationsContainer` with [analytics tasks](../cdm/workers/analytics_tasks.py)
  (BERTopic training, graph building, and party perspectives) and is loaded
  only by workers consuming the analytics queue.
- Docker builds two targets from `Dockerfile.python` / `Dockerfile.prod`:
  - `api`: Used by FastAPI, operational workers, and Celery Beat (excludes the
    heavy `analysis` dependency group while keeping `spacy` and `numpy` for
    query lemmatization).
  - `analysis`: Used only by `worker-analytics` (adds `bertopic` and
    `sentence-transformers`).

## Data contracts and identifiers

A single legislative concept passes through several distinct typed models as it
moves through the pipeline:

1. **Upstream validation (`cdm/models/`):** Validates raw JSON or XML from
   Congress.gov, GovInfo, or Voteview.
2. **Canonical IDs:** Unifies records across sources (for example,
   `bill:119:hr:1` or `member:A000360`).
3. **Elasticsearch documents (`cdm/store/`):** Flattens key fields for fast
   filtering and stores full text and lemmatized text directly on the bill
   document.
4. **API response contracts (`cdm/contracts/`):** Defines the exact JSON shape
   returned by FastAPI and mirrored into TypeScript via OpenAPI generation.

See [Data structures](reference/data-models.md) and the
[Generated source symbol index](reference/symbols/README.md) for field-level
details.

## Reliability model

- **Idempotent indexing & local replay:** Raw fetched pages and items are saved
  to SQLite archives before being pushed to Redis Streams. Indexing workers use
  canonical document IDs and null-safe merges so replaying an archive or
  retrying a batch converges cleanly without duplicating documents.
- **Versioned analytics publication:** Topic models, member graphs, and party
  perspectives publish immutable versioned snapshots and retain one previous
  generation for rollback. After a successful build, a maintenance cleanup job
  verifies the live HTTP version before pruning older artifacts. See the
  [analytics retention policy](guides/analytics.md#6-rebuilds-retention-and-operational-checks)
  and the [operations runbook](OPERATIONS_RUNBOOK.md).

## Local versus production

- **Local (Docker Compose):** Runs Elasticsearch, RabbitMQ, Redis, FastAPI,
  React/Vite, and one `operations` worker (handling indexing and maintenance)
  by default, talking to native host Ollama. Acquisition workers, analytics
  workers, Celery Beat, and Kibana are opt-in Compose profiles; see the
  [profile table](guides/configuration-and-deployment.md#managed-stack-compose).
- **Google Cloud (`infra/` & `deploy/`):** Deploys the frontend and FastAPI
  backend on Cloud Run behind HTTPS/IAP, connecting over a private VPC to
  worker and Elasticsearch VMs. See
  [Google Cloud deployment constraints](guides/configuration-and-deployment.md#google-cloud)
  for details on cross-VM file boundaries.
