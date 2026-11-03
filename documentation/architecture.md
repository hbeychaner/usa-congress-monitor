# Architecture

[Documentation home](README.md) | [Visual atlas](reference/visuals.md)

## Purpose and boundaries

Congress Tracker acquires legislative data, preserves replayable inputs,
projects typed records into Elasticsearch, and serves search and analysis
through FastAPI and React. It is not a legislative source of record, a
transactional relational mirror of Congress.gov, or a real-time guarantee
that every source has been fetched.

The design deliberately separates **work delivery**, **job history**,
**record handoff**, and **searchable projections**. A healthy broker alone
does not prove a healthy corpus. Equally, a completed acquisition job does not
prove that every downstream record is indexed.

## C4 zoom levels

| View | Question | Diagram |
|---|---|---|
| C4 level 1: context | Who uses this system, and what supplies it? | [Context](reference/visuals.md#system-context) |
| C4 level 2: containers | Which independently running applications and stores cooperate? | [Container view](reference/visuals.md#worker-architecture) |
| C4 level 3: components | How does the serving application delegate requests? | [Backend components](reference/visuals.md#backend-components) |
| Data-flow view | Where does data move and become durable? | [Ingest flow](reference/visuals.md#ingest-dataflow) |
| Logical data view | Which identifiers connect source and derived records? | [Data relationships](reference/visuals.md#data-model) |
| Request sequence | What happens when someone opens a bill? | [Request sequence](reference/visuals.md#bill-request-sequence) |
| Deployment view | What differs between local operation and GCP? | [Deployment](reference/visuals.md#deployment) |

The context view treats Congress Tracker as one system. The container view
shows processes/stores, not one container per Python class. Component diagrams
zoom inside an application; the same code may be deployed natively, through
Docker, or as a worker image.

The C4 views use labeled Mermaid flowchart shapes to preserve C4 abstraction
levels while allowing automatic edge routing around nodes. Mermaid's
experimental native C4 renderer uses fixed-position straight connectors, which
can obscure people and system cards. Editable sources and the rendered atlas
use the routed representation rather than that overlapping layout.

## Runtime responsibilities

| Runtime | Responsibility | Does not own |
|---|---|---|
| Operator CLIs | Plan and submit work; inspect jobs; initiate rebuilds | Canonical upstream facts |
| Celery Beat | Submit scheduled tasks | Durable job results or corpus coverage by itself |
| RabbitMQ | Route Celery task messages to workers | Job identity and final history |
| Celery workers | Execute acquisition, indexing, and maintenance orchestration | The web UI request lifecycle |
| SQLite job ledger | Idempotency, job status/attempts/errors and coverage bookkeeping | Full-text search |
| SQLite archives/manifests/library | Replay inputs, progress and retained records | A cross-resource serving database |
| Redis | Stream handoff/consumer state and coordination | Permanent source archive |
| Elasticsearch | Indexed entity projections, lookup keys and analytics documents | Acquisition retry scheduling |
| FastAPI | Validate requests and construct typed service responses | Bulk historical acquisition during ordinary reads |
| React/Vite | Route pages, call typed API wrappers and render results | Server-side indexing or durable jobs |
| Ollama | Optional locally configured labels and summaries | Source evidence, identifiers, or authoritative votes |

See the [ingestion guide](guides/ingestion.md) for precise retry and acknowledgement
ordering, and [indexing reference](reference/indexing.md) for the distinction
between configured mapping families and actively populated indices.

## Code map

| Area | Role | Primary reading |
|---|---|---|
| [config](../cdm/config) | Typed environment-backed configuration sections | [Configuration guide](guides/configuration-and-deployment.md) |
| [Container](../cdm/container.py) | Composition root for serving and durable job submission, without training imports | [Composition symbols](reference/symbols/composition.md) |
| [data_collection](../cdm/data_collection) | Endpoint specs, identifiers, HTTP and pagination | [Ingestion](guides/ingestion.md) |
| [models](../cdm/models) | Pydantic upstream record families and validators | [Data models](reference/data-models.md) |
| [ingest](../cdm/ingest) | Resource planning, fetching, hydration, archives and replay | [Ingestion](guides/ingestion.md) |
| [jobs](../cdm/jobs) | Typed job payloads and SQLite lifecycle | [Data models](reference/data-models.md) |
| [workers](../cdm/workers) | Celery entry points and injected worker services | [Ingestion](guides/ingestion.md) |
| [store](../cdm/store) | Projection, mapping, bulk writing and derived repositories | [Indexing](reference/indexing.md) |
| [graph](../cdm/graph) | Collaboration, voting and topic graph builds | [Analytics](guides/analytics.md) |
| [perspectives](../cdm/perspectives) | Evidence-backed party/topic contrasts | [Analytics](guides/analytics.md) |
| [utils](../cdm/utils) | NLP, embeddings, topic training, labels and upkeep helpers | [Analytics](guides/analytics.md) |
| [backend](../cdm/backend) | FastAPI routes, dependencies and query services | [Serving reference](reference/api-and-frontend.md) |
| [contracts](../cdm/contracts) | Typed backend request/response shapes | [Serving reference](reference/api-and-frontend.md) |
| [frontend](../frontend/app/src) | React pages, components and API wrappers | [Serving reference](reference/api-and-frontend.md) |
| [scripts](../scripts) | Operational entry points | [Operations](OPERATIONS_RUNBOOK.md) |
| [infra](../infra/terraform) / [deploy](../deploy/gcp) | GCP resources and production image deployment | [Deployment guide](guides/configuration-and-deployment.md) |

## Configuration and dependency injection

[AppConfig](../cdm/config/app_config.py) groups settings into sections.
[Container](../cdm/container.py) receives the configuration, constructs
collaborators and caches shared clients/services. FastAPI dependency providers
expose those services to routes. The existing
[WorkerContainer](../cdm/workers/runtime.py) extends that root with ingestion,
topic training, graph building and perspective construction. Analysis factories
are not imported by the API or submission CLIs. Four single-use metasubject
factory wrappers were removed; training collaborators are wired directly at
their one construction boundary. Graph/perspective builds share a stateless
topic-model reader.

The `analysis` dependency group is included in normal development installs but
excluded from the opt-in Docker `api` target. The last/default Docker target,
`analysis`, keeps the full worker runtime. The approved local Compose deployment
now selects `api` for FastAPI and `analysis` for workers. spaCy, its pinned model
and NumPy remain serving
dependencies because search still uses the same lemma fields and normalization.
When training packages are installed, spaCy's optional integrations can also
import PyTorch; the API-only image proves those packages are absent, rather
than hiding them with lazy imports or disabling normalization.

Tests can pass fakes directly or replace providers. A service should receive
its client/store/config dependencies, rather than silently constructing a new
database connection or consulting unrelated global settings.

Follow the actual caller when changing a setting. Older instructions may refer
to a removed top-level `settings` module; use the typed configuration and
composition roots rather than copying those obsolete imports.

## Data contracts and identifiers

An upstream response, a queued payload, an archived record, an indexed document,
and an HTTP response are **different contracts**, even when they describe the
same bill.

- Pydantic validates upstream and application boundaries.
- Canonical IDs unify records from overlapping windows and sources.
- Search documents flatten selected references for inexpensive filtering.
- Rich nested fields preserve detail without creating database joins.
- API response contracts select and transform the fields a page actually needs.
- Analysis records carry derived assignments or evidence, not replacements for
  upstream entities.

The [data structures chapter](reference/data-models.md) describes the exact
families and keys; the [source index](reference/symbols/README.md) gives every
declared field and function a source link. Do not equate a Python model's full
field list with its Elasticsearch mapping or an API's response fields.

## Reliability model

The system is designed around replay and idempotent projections, **not an
exactly-once transaction spanning SQLite, RabbitMQ, Redis and Elasticsearch**.
Canonical document IDs make redelivery converge; archive/checkpoint and stream
acknowledgement ordering control what must be replayed after an interruption.

Useful incident questions are:

1. Was a durable job recorded?
2. Was its task message delivered to a live worker?
3. Which source pages/items were durably archived?
4. Which records were handed off to Redis?
5. Which entries are pending, acknowledged, or no longer retained?
6. Which index or alias received the writes?
7. Is the API reading that same projection?
8. Does a derived analysis need rebuilding after the underlying corpus changed?

Use the [operations runbook](OPERATIONS_RUNBOOK.md) for recovery. Never repair
a perceived gap by deleting ledgers, manifests, broker volumes, or archives.

## Local versus production

Compose is the sole supported managed local path. Its controlled default runs
Elasticsearch, RabbitMQ, Redis, FastAPI, React/Vite and a one-slot
index/maintenance worker. Native launchd agents are retired. Acquisition,
analytics, dedicated workers and Beat are explicit opt-in application profiles;
Kibana is an opt-in infrastructure profile. The logical diagrams show available
capabilities, not proof that every role is running. See the
[profile/resource table](guides/configuration-and-deployment.md#managed-stack-compose)
before expanding that scope. Foreground developer processes remain an isolated
development option, not a second supervisor alongside the managed stack.

The GCP design puts frontend/API on Cloud Run behind HTTPS/IAP, with worker
and search VMs on a private network. Worker-local ledger, status, model and log
files do not automatically appear on the Cloud Run API filesystem. Thus a
successful cloud deployment does not by itself prove that file-backed admin
status and rebuild controls work across that boundary.

See [deployment constraints](guides/configuration-and-deployment.md#google-cloud)
before relying on those controls.
