# Configuration, development, and deployment

[Documentation home](../README.md) | [Architecture](../architecture.md)

## Requirements and initial setup

The application targets Python 3.13 or newer. Use the existing `uv` dependency
workflow, Docker for infrastructure, and Node/npm for the React app and static
TypeScript documentation extraction. Congress.gov acquisition needs an API key;
GovInfo bulk acquisition does not use that key.

```bash
uv sync --all-extras
npm --prefix frontend/app ci
make local
# Set CONGRESS_API_KEY in .env; never commit credentials.
make es-api-key
```

`make local` initializes local environment files through
[bootstrap_env.py](../../scripts/bootstrap_env.py) and starts infrastructure.
`make es-api-key` creates the local application search credential.
Avoid running either against a deployment you do not own.

The managed API retains development hot reload, scoped to `/workspace/cdm`.
Do not watch the entire bind-mounted checkout: retained acquisition directories,
archives and frontend dependencies can otherwise create an unbounded inotify
watch set and consume the API container's memory outside Python RSS. Changes to
application Python still reload; Compose/environment changes require restarting
the affected service. Frontend hot reload is independent.

The sustained-operation observer uses Python's nonadjustable
`mach_absolute_time()` clock for elapsed time and Darwin's suspend-inclusive
`CLOCK_MONOTONIC_RAW` for independent sleep detection. It compares elapsed
increments, never the clocks' unrelated absolute origins. Both scheduling
gaps and sleep discrepancies retain the original two-second limit; the
required day remains 86,400 seconds. UTC timestamps remain in journals, but
ordinary automatic NTP corrections must not masquerade as suspended execution.
Do not disable time synchronization or change the machine clock to force a pass.
The controller explicitly rejects an unsupported clock implementation.

## Settings ownership

[AppConfig and section definitions](../../cdm/config/app_config.py) are the
source for current typed defaults. Settings sections use `pydantic-settings`
and read the root `.env` and `elastic-start-local/.env`, ignoring unrelated
keys. Environment variables override dotenv values. With the declared file
sequence, the later dotenv file takes precedence when a value exists in both.
[get_config](../../cdm/config/__init__.py) exposes the cached application config;
[Container](../../cdm/container.py) wires collaborators from it.

Field names map to uppercase environment names without a per-section prefix,
except where an explicit validation alias is declared. For example,
`QueueConfig.ingest_max_concurrent_jobs` is `INGEST_MAX_CONCURRENT_JOBS`,
and `ApiConfig.cors_origins_csv` uses `CORS_ORIGINS`.

| Section | Important settings | Meaning |
|---|---|---|
| `elastic` | `ES_LOCAL_URL`, `ES_LOCAL_API_KEY`, `ELASTIC_API_URL`, `ELASTIC_API_KEY` | Local/remote search connections; avoid mixing environments |
| `elastic` | `STAGING_INDEX`, `ANALYSIS_INDEX`, `EMBEDDINGS_INDEX`, `METASUBJECT_OVERRIDES_INDEX` | Explicit derived/staging destinations |
| `congress_api` | `CONGRESS_API_KEY`, `CONGRESS_API_URL`, `TIMEOUT_SECS` | Upstream authentication, endpoint and request timeout |
| `congress_api` | `INGEST_RATE_LIMIT_PER_HOUR`, `INGEST_RATE_LIMIT_KEY` | API request budget and shared Redis coordination key |
| `queue` | `RABBITMQ_URL`, `CELERY_INGEST_QUEUE`, `CELERY_BULK_QUEUE`, `CELERY_INDEX_QUEUE`, `CELERY_MAINTENANCE_QUEUE` | Broker and work routing |
| `queue` | `INGEST_MAX_CONCURRENT_JOBS`, `INGEST_DEFER_SECONDS` | Bound active ingest work; defer excess jobs |
| `queue` | `CELERY_RETRY_MAX`, `CELERY_RETRY_BACKOFF_MAX`, task time limits | Retry/backoff and task execution bounds |
| `queue` | `JOB_HEARTBEAT_SECONDS` | Running-job heartbeat frequency |
| `redis` | `REDIS_URL`, `REDIS_STREAM_MAXLEN`, `REDIS_CONSUMER_GROUP` | Record handoff and consumer coordination |
| `ledger` | `JOB_DB_PATH`, `RETENTION_DAYS`, `COVERAGE_LOOKBACK_DAYS`, `RECORD_LIBRARY_ROOT` | Durable ledger, retention and latest-record library |
| `govinfo` | `GOVINFO_RATE_LIMIT_PER_HOUR`, `GOVINFO_ARCHIVE_ROOT` | Local bulk-download pacing and archive location |
| `indexing` | `INDEX_BATCH_JOBS`, `INDEX_BATCH_DOCS`, `INGEST_PARTIAL_INDEX_EVERY` | Bounded indexing batches and incremental dispatch; managed operations overrides the bulk/prefetch bound to 32 documents |
| `lemmatization` | `SPACY_MODEL`, `LEMMA_MAX_CHARS`, `LEMMA_CHUNK_CHARS`, `LEMMA_BATCH_SIZE`, `LEMMA_EXCLUDED_COMPONENTS` | Defaults: `en_core_web_md`, 200,000-character total allowance, 8,192-character inference chunks, one chunk per microbatch, excluded `parser`/`ner`; each chunk owns a serialized memory zone |
| `embedding` | `EMBEDDING_MODEL`, `EMBEDDING_BATCH_DOCS` | Vector model identity and batching |
| `metasubject` | `METASUBJECT_TARGET_GROUPS`, matching/confidence settings | Group construction and identity carry-over |
| `perspective` | `PERSPECTIVE_*` | Evidence thresholds, exclusions, stability and display rules |
| `analytics_retention` | `ANALYTICS_MODEL_ROOT`, `ANALYTICS_LIVE_API_URL`, `ANALYTICS_CLEANUP_BATCH`, `ANALYTICS_CLEANUP_TIMEOUT`, `ANALYTICS_GENERATION_LIMIT` | Owned model root (`models/topics`), worker-reachable API (`http://backend:8000/api/v1`), deletion batches (500), request timeout (300 seconds) and exact-inventory bound (1,000 generations per scope); match the root when using training's `--model-dir` |
| `ollama` | `OLLAMA_URL`, `OLLAMA_MODEL`, timeouts and temperature | Optional local labeling/summarization |
| `openai` | `OPENAI_API_KEY` | Declared optional credential; not a replacement for the Ollama implementation |
| `api` | `CORS_ORIGINS`, `LOG_LEVEL` | Browser origins and application logging |

Index-consuming Celery workers warm the existing CPU spaCy model in the parent
before the prefork pool starts. The selected consumption queues gate warmup;
ingestion-only workers retain their existing startup behavior. Forked children
share model weights, while per-call memory zones still own transient NLP state.
The parent collects unreachable objects and freezes its remaining heap before
forking, preventing child GC from copying the long-lived import/model graph.
Future task objects still undergo ordinary GC. Check the observed parent
warm/freeze markers and stable worker start/restart state, not only an OOM
counter that resets when Docker restarts the container.
Operational task discovery uses `OperationsContainer`, without importing
training/graph/perspective implementations. Analytics-consuming workers register
their implementation module through Celery's loader during `worker_init`, before
the pool is created. All Python imports remain at module level; nothing is
imported lazily inside a job. Analytics task names, routing and time limits
follow the durable task contract; deployment config owns worker concurrency,
child rotation and memory allocation. Do not move warmup into execution children or increase
worker limits to hide duplicated model memory.

For **all declared field types**, see the generated
[config reference](../reference/symbols/config.md). It is a static declaration
reference, not a dump of effective values or secrets. Trace the typed
configuration section, constructor and composition root when changing a value.

## Local runtime choices

### Managed stack: Compose

Startup includes native Ollama for topic/group labels. Install Ollama and pull
`OLLAMA_MODEL` once (default `ollama pull llama3.1`). `make ensure-ollama`
reuses a responding server; otherwise it starts the default local endpoint
through Homebrew's Ollama service on macOS, the installed Ollama app when no
Homebrew formula exists, or an already configured `systemctl --user` Ollama
service on Linux. Missing installations/service registrations fail explicitly;
install/configure them before retrying. No standalone background shell process
or competing Docker Ollama container is created.

`make up` checks native readiness/model installation after Docker capacity
admission and before starting Compose, then checks the effective container
endpoint/model from the backend before printing success. Each HTTP probe is
bounded by `OLLAMA_PROBE_TIMEOUT_SECS`; the post-start readiness wait uses
`OLLAMA_TIMEOUT_SECS`. A failed final check leaves containers running for
diagnosis, but the command exits nonzero. An unreachable custom/remote URL is
never replaced with a different local server. Remote endpoints must be started
by their own operator. Set `OLLAMA_URL` for the host-side check and, if needed,
`CONTAINER_OLLAMA_URL` for Docker routing to the same server.

Missing models stop startup with an explicit `ollama pull` instruction rather
than an implicit multi-gigabyte download. The checks do not load a model for
inference; budget native model memory in addition to the Docker VM before
running analytics. Docker admission does not account for native model weights.
`make down` leaves the potentially shared native service running. Starting the
server does not retroactively relabel published topics: use the existing
analytics publication workflow and inspect label provenance/fallback reasons.

All managed Python services share `ledger-data:/var/lib/congress` and
`JOB_DB_PATH=/var/lib/congress/jobs.sqlite3`. With project name
`congresstracker`, the volume is `congresstracker_ledger-data`.
Host-native tools must not open the managed live ledger. Use Docker-side
readers and consistent backup/restore procedures. See the
[ledger boundary and restoration procedure](../OPERATIONS_RUNBOOK.md#live-sqlite-operating-boundary).
Normal shutdown preserves the volume. Do not remove it with `down --volumes`.

```bash
make up
make stack-status
make stack-logs
make down
```

`make up`, `make start`, `make services`, and `make stack-up` use the same
Compose path. Startup refuses conflicting service registrations without stopping
them. Keep one process owner per role and inspect any conflict before retrying;
see [restart procedures](../OPERATIONS_RUNBOOK.md#restart).

The default `STACK_PROFILES=operations` is deliberately controlled:

| Profile | Services/capability | Default |
|---|---|---|
| Always enabled | API (`api` image target), React/Vite; search, broker, Redis | On |
| `operations` | One `api`-image prefork worker, concurrency 1; index + maintenance queues | On |
| `acquisition` | Ingest worker and bulk/default-queue worker | Off |
| `dedicated` | Separate index and maintenance workers, instead of `operations` | Off |
| `analytics` | Full-image bounded analytics worker | Off |
| `scheduler` | 96 MiB Beat, restricted to current-Congress bill refresh | Off |
| `observability` | Infrastructure Kibana/setup | Off |

`STACK_PROFILES` replaces the default, rather than adding to it. Do not combine
`operations` and `dedicated` unintentionally. After draining work, use the same
profile selection for status/shutdown/restart. Examples for an **approved**
scope change (not commands to run blindly against retained queues):

```bash
make up STACK_PROFILES=                         # API/UI + infrastructure only
make up STACK_PROFILES=operations,acquisition    # no analytics or scheduler
make up STACK_PROFILES=operations,scheduler      # scoped daily bill refresh only
make up STACK_PROFILES=dedicated,acquisition,analytics,scheduler,observability
```

The scoped scheduler sends bill-refresh work through the existing maintenance
queue, not the general acquisition queue. It preserves serial operations-worker
execution and disables unrelated periodic jobs. Frontend cold dependency
optimization is bounded by `GOMAXPROCS=1`, `GOMEMLIMIT=64MiB` and a 96 MiB Node
old-space limit within the unchanged 256 MiB container limit.

Review retained messages, durable jobs, due schedules, source credentials and
capacity before enabling producers/consumers. Maintenance is allowed under the
controlled profile, but automatic retention scheduling and acquisition are not;
manual maintenance submissions still need review.

The measured local Docker VM has about 7.75 GiB. Default controlled limits total
7.375 GiB: search 4 GiB, Redis 1280 MiB, broker 384 MiB, API 512 MiB, operations
1 GiB and UI 256 MiB. Limits are not reservations or a sustained-load guarantee.
Redis's retained snapshot required roughly 835 MB after restoration; lowering
its limit to 128 MiB caused an observed startup OOM and is not safe here.
The optional analytics worker alone allows 8 GiB, so the complete topology does
not fit this measured budget. Do not enable it without a separate capacity plan.
`make stack-capacity STACK_PROFILES=operations` performs the read-only admission
check also required by `make up`, before any Compose services start. It counts
both rendered Compose projects, selected profiles, other running containers
and larger retained limits without double-counting selected services. Missing
memory limits, unknown profiles, Docker/metadata failures, combined limits plus
a 256 MiB Docker reserve exceeding VM memory, or less than 8 GiB host disk free
space refuse startup. These are safety floors, not measured working-set budgets.
Direct `docker compose` commands bypass the Make guard. Existing inactive-profile
containers still consume capacity; changing profiles does not prove they stopped.
The check never resizes Docker, lowers heap, deletes state or stops containers.
`OPERATIONS_MEMORY`, `WORKER_MEMORY`, `WORKER_CPUS`, `ANALYTICS_MEMORY`,
`ANALYTICS_CPUS` and `REDIS_MEMORY` are explicit overrides; do not lower search
heap or discard retained state just to force the stack into memory.

[stack.sh](../../scripts/stack.sh) delegates stack commands and performs
read-only registration checks. No shell helper spawns detached processes
or stops processes by a command-name match. Compose owns application containers;
Docker Desktop must be running on macOS. Restart policies do not wake a sleeping
Mac, start the Docker engine, or restart a merely unhealthy-but-running process.

### Foreground worker development

For an isolated development environment without supervised copies:

```bash
make worker
make worker-index
make worker-maintenance
make beat
```

Run each in its own terminal/process manager. Inspect the
[Makefile](../../Makefile) for queue, pool, concurrency and worker names.
Configured Celery concurrency is not the same as the active-ingest-job bound.

## Supported operational entry points

Keep the small `scripts/` directory: these are operator-facing adapters around
application services. Start with Make and
the admin UI; use a script only for the corresponding explicit operation.
Run ledger-writing/submission commands inside the owning Docker environment
for the managed deployment.

| Purpose | Maintained entry points |
|---|---|
| Local setup and startup | [`bootstrap_env.py`](../../scripts/bootstrap_env.py), [`check_stack_capacity.py`](../../scripts/check_stack_capacity.py), [`ensure_ollama.py`](../../scripts/ensure_ollama.py), [`stack.sh`](../../scripts/stack.sh) (registration checks and command delegation) |
| Search provisioning and staging | [`create_indices.py`](../../scripts/create_indices.py) |
| Legislative acquisition | [`submit_ingest.py`](../../scripts/submit_ingest.py) (one bounded scope), [`queue_full_ingest.py`](../../scripts/queue_full_ingest.py) (planned ranges), [`queue_govinfo_bulk.py`](../../scripts/queue_govinfo_bulk.py), [`report_govinfo_coverage.py`](../../scripts/report_govinfo_coverage.py) |
| Specialized source imports | [`ingest_votes.py`](../../scripts/ingest_votes.py), [`ingest_district_boundaries.py`](../../scripts/ingest_district_boundaries.py); district import remains necessary for a fresh map deployment |
| Analytics and labels | [`train_topic_model.py`](../../scripts/train_topic_model.py), [`build_member_graph.py`](../../scripts/build_member_graph.py), [`build_perspectives.py`](../../scripts/build_perspectives.py), [`set_metasubject_override.py`](../../scripts/set_metasubject_override.py) |
| Guarded replay, repair and rollback | [`reconcile_govinfo_bulk.py`](../../scripts/reconcile_govinfo_bulk.py), [`stage_graph_repair.py`](../../scripts/stage_graph_repair.py), [`repair_graph_sources.py`](../../scripts/repair_graph_sources.py), [`promote_voting_graph.py`](../../scripts/promote_voting_graph.py), [`preview_analytics_retirement.py`](../../scripts/preview_analytics_retirement.py); infrequent recovery use does not make these disposable |
| API contracts | [`export_openapi.py`](../../scripts/export_openapi.py), invoked by the [frontend contract generator](../../frontend/app/scripts/generate-contracts.mjs) |
| Documentation and CI | [`build_documentation.py`](../../tools/build_documentation.py), its [frontend reader](../../tools/build_frontend_reference.mjs), and [`release_smoke_probe.py`](../../tools/release_smoke_probe.py) (test-only image/worker verification) |
| GCP image publishing | [`deploy/gcp/build_push.sh`](../../deploy/gcp/build_push.sh) |

`make status` prints the API's system/job summary; `make worker-monitor`
prints one ingestion-progress JSON snapshot, without launching a terminal or
opening SQLite on the host. Repeat deliberately or use the admin UI for live
monitoring. `make health-check` checks API/search readiness only. All three
propagate HTTP/connection errors, use a 30-second timeout, and accept `API_URL`.
`make worker` runs a foreground ingestion worker without starting another
terminal or monitor.

### Full-stack development Compose

```bash
make stack-up
make stack-logs
make stack-down
```

[docker-compose.fullstack.yml](../../docker-compose.fullstack.yml) defines API,
frontend and profiled operations/acquisition/indexing/maintenance/analytics/
Beat services, on top of the local infrastructure stack. Only the controlled
profile starts by default. A shared YAML anchor owns Python
environment/mount/restart policy; the API and operational services select the
`api` build target. Only `worker-analytics` selects the full `analysis` target;
ingestion, indexing, maintenance and Beat do not need training dependencies.
All consumers use the
configured queue names. The API's `/ready` check gates worker startup; normal
startup waits for infrastructure and application readiness with a bounded timeout.
Dependencies are installed from the frozen lock at build time, not concurrently
at process startup into a shared mutable environment.

Image sizes and build-cache usage are separate. PyTorch's default Linux
analytics dependencies can include multi-gigabyte NVIDIA libraries even on
an ARM64 host; do not install them in operational workers. Reclaim only
inspected, unused build-cache records when needed, never data volumes or
retained archives. Docker Desktop may return freed sparse-disk space to macOS
after a short delay; verify actual host free disk before resuming guarded jobs.
Changing a build target does not shrink an existing image or replace a running
container. Build and verify a replacement separately before a planned cutover.
Operational images exclude Torch, NVIDIA, BERTopic and sentence-transformers.
Logical image sizes and shared-layer disk usage are different measurements;
shared layers are not additional disk usage for every container.

All Python services share the checkout at `/workspace` and at its original
absolute path. This resolves absolute archive paths in queued
job payloads without rewriting source data. Keep running Compose from that same
checkout; external archive locations need explicit matching mounts. Beat keeps
its schedule under `data/`. Routine shutdown preserves named data volumes;
startup renews only the frontend's anonymous dependency volume.

For custom broker credentials requiring URI escaping, set an encoded
`CONTAINER_RABBITMQ_URL`; the default derives the local broker credentials/port
from `.env`. `CONTAINER_OLLAMA_URL` overrides the host-local Ollama URL. Linux
containers receive an explicit host-gateway mapping. Local application ports
bind only to loopback. `make local-down` remains explicitly destructive and is
not part of routine shutdown.

The local host-service routing is verified on Docker Desktop for macOS, not a
Linux-engine parity claim: a Linux host's loopback-only published infrastructure
ports are not necessarily reachable through its bridge gateway. Validate routing
before adopting this development topology there; the GCP files below define
their own deployment networking.

| Service | Local URL |
|---|---|
| React development server | `http://localhost:5173` |
| FastAPI | `http://localhost:8000` |
| OpenAPI schema | `http://localhost:8000/openapi.json` |
| Interactive API docs | `http://localhost:8000/docs` |
| Elasticsearch | `http://localhost:9200` (authentication required) |

`make local-stop` preserves infrastructure volumes. **`make local-down`
removes volumes and is destructive.** Do not use it as a routine restart.

## Testing and contracts

The [hosted workflow](../../.github/workflows/contracts.yml) uses Node.js
24-based actions on `ubuntu-latest` for checkout, tool setup and failure-artifact
uploads in the contract and manual release-smoke jobs. This action runtime is
separate from the frontend's explicitly selected Node.js 22; Python remains 3.13.

```bash
uv run pytest -q
# Focused backend/unit work:
uv run pytest -q tests/unit
# Existing lint baseline:
uv run --with ruff ruff check .
# Syntax compilation:
uv run python -m compileall -q cdm scripts tools
# Frontend type checking and production build:
npm --prefix frontend/app run build
# Keep the dependency audit and bounded glob regressions enforced:
npm --prefix frontend/app run audit
npm --prefix frontend/app test
```

The Vite dependency chain pins `picomatch` to the reviewed npm alias
`@ryotsu/picomatch@4.0.7-a` in both the manifest and integrity-locked dependency
graph. Upstream picomatch through 4.0.7 is affected by
[CVE-2026-112366 / GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf);
no fixed upstream release was available when this remediation was made.
The replacement's runtime changes were compared with the upstream archive and
its [security-fix commit](https://github.com/ryotsu-kankichi/secured-picomatch/commit/3ab5a7627d480259e3d9ca67fbc14c125d374f0e).
It adds no runtime dependencies or install hooks. A child-process deadline
regression reproduces the former event-loop stall and verifies the fix, while
compatibility tests cover Vite's actual matcher consumers, ordinary paths,
extglobs and punctuation. This is a reviewed fork, not an upstream release;
remove the override only after a fixed upstream release passes the same tests.
Keep `npm audit --audit-level=low`; do not suppress the advisory or downgrade
the bundler just to bypass this check.

Tests explicitly gated on live services require a controlled environment and
credentials. They are not substitutes for fixture-driven unit tests.
The [API/frontend chapter](../reference/api-and-frontend.md) explains contract
generation; regenerating TypeScript contracts needs the backend OpenAPI schema.
No live application is required to build the static source reference.

### Automated security checks

The [security policy](../../.github/SECURITY.md) defines supported versions and
private reporting. The [security workflow](../../.github/workflows/security.yml)
runs CodeQL for Python and JavaScript/TypeScript on pushes and pull requests to
`main`, weekly, and on manual dispatch. Analysis uses GitHub-hosted runners
without starting the application, installing its dependencies or accessing local
data. Findings appear in the repository's **Security** tab; a successful scan
does not mean the code has no vulnerabilities.

[Dependabot](../../.github/dependabot.yml) checks uv, npm and GitHub Actions
weekly. Minor/patch version updates are grouped per ecosystem, major updates
remain separate, and each ecosystem allows up to three open version-update PRs.
Security-update PRs are managed separately by GitHub. Review changes and passing
CI before merging; no automatic merging is configured. The existing npm audit
gate remains enabled.

Repository owners must also enable dependency graph, Dependabot alerts and
security updates, private vulnerability reporting, secret scanning and push
protection where available under **Settings > Advanced Security**. These
repository settings are not enabled by committing workflow files. Use the
checked-in CodeQL workflow rather than enabling a second default-setup scan.
Rotate exposed credentials immediately; scanners cannot prove the absence of
secrets or replace a security review.

## Google Cloud

The [Terraform root](../../infra/terraform) provisions:

- private network and subnet;
- Artifact Registry and Secret Manager resources;
- a search VM running self-managed Elasticsearch;
- a worker VM with persistent application state and Docker volumes;
- Cloud Run API/frontend services;
- HTTPS load balancing, path routing, managed certificate and IAP access.

The [deployment diagram](../reference/visuals.md#deployment) shows the process
and persistence boundaries. The [load balancer](../../infra/terraform/modules/apps/load_balancer.tf)
sends `/api/*`, `/health`, `/docs`, `/redoc` and `/openapi.json` to the API;
other requests go to the frontend. HTTP redirects to HTTPS.

The [Cloud Run configuration](../../infra/terraform/modules/apps/cloud_run.tf)
limits ingress to internal/load-balancer traffic and gives the API private
VPC access to worker/search services. IAP is enabled on load-balancer backends;
do not infer standalone application authentication for a different deployment.

### Provisioning outline

1. Prepare a remote Terraform state bucket and initialize the backend.
2. Copy the tracked example variables to your own ignored configuration;
   set the project, region, domain and allowed IAP identities.
3. Supply the Congress.gov credential using the documented Terraform input,
   never a tracked file.
4. Provision the registry/APIs needed for image publishing.
5. Build and push production images with
   [build_push.sh](../../deploy/gcp/build_push.sh).
6. Apply the remaining Terraform resources and wait for startup/health checks.
7. Set the domain's A record to the load-balancer IP and wait for certificate
   provisioning.
8. Verify authenticated frontend/API access, workers, ledger, queues, aliases,
   and representative reads and writes before admitting historical traffic.

For a separately approved cloud deployment, the corresponding commands are:

```bash
# From the repository root; prepare a state bucket first.
cd infra/terraform
terraform init -backend-config="bucket=<state-bucket>"
cp terraform.tfvars.example terraform.tfvars
# Edit the ignored variables file; supply TF_VAR_congress_api_key privately.
terraform apply -target=google_artifact_registry_repository.images \
  -target=google_project_service.apis
cd ../..
deploy/gcp/build_push.sh <project_id> [region] [tag]
cd infra/terraform
terraform apply
# Configure the OAuth consent screen, then set deploy_apps=true and apply again.
```

See the [example variables](../../infra/terraform/terraform.tfvars.example) for
inputs. Configure `project_id` and `iap_members`, and use the `dns_a_record`
output for DNS. Provisioning is not performed by documentation generation or
local startup.

### Persistence and known deployment boundaries

The worker startup template mounts its persistent disk at `/mnt/data` and places
Docker's data root and application `data`, `logs` and `models` directories there.
Search data has its own persistent VM disk. Snapshot policies are infrastructure
configuration, not proof that a particular restore has been tested.

Cloud Run does not mount the worker filesystem in the current configuration.
Features that read worker-local job databases, build status JSON files, model
artifacts or logs cannot assume those files exist on the API container.
Admin-triggered subprocess builds also run where the API executes, not magically
on the worker VM. Treat file-backed admin controls as a deployment limitation,
not a completed distributed-control plane.

The application uses `elasticsearch-py` 9 and the supplied images run
Elasticsearch. Server compatibility is defined by this client and runtime,
not inferred from module or mapping filenames.

Vertex AI permissions do not implement a Vertex client: labels/summaries still
use the configured Ollama path until an explicit alternative is implemented.
GCP IAM grants alone do not redirect application LLM calls.

## Operational acceptance

After any runtime change, check:

```bash
make stack-status
curl --fail http://127.0.0.1:8000/ready
```

`make status` and `make health-check` use the serving API.
Use the owning container for explicit ledger inspection.

Inspect source coverage, active worker queues, archive retention, Redis pending
entries and the exact search aliases. Use the
[operations runbook](../OPERATIONS_RUNBOOK.md) for recovery and rollback.
Do not treat `/health` alone as proof that the full ingestion and analytics
pipeline is healthy.
