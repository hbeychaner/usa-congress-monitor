# Operations runbook

Current procedures for the managed local deployment, durable jobs, backups,
staging and rollback. See [configuration and deployment](guides/configuration-and-deployment.md)
for profiles, capacity admission and supported entry points.

## Health check

```sh
make stack-status
make health-check
make status
make worker-monitor
```

`make status` requests `/api/v1/admin/system-status`; `make worker-monitor`
requests `/api/v1/admin/ingest-progress`. Both print one JSON snapshot.
`make health-check` requests `/ready`, which checks the API/search connection,
not broker health, worker liveness, ledger integrity or corpus completeness.
All three HTTP commands have a 30-second timeout, propagate failures and accept
`API_URL` to select another owned deployment.

Check active worker queues, durable job states, Redis pending/lag, source
coverage and the exact search aliases independently. Index presence and API
visibility are separate checks. Bill reads include bill/law projections with
valid canonical identities. Do not change their classification or download them
again to fix a read-path problem. A missing `source_checked_at` is unknown
freshness, not proof that the document is missing.

### Current operating posture

The default managed topology runs the API, frontend and a serial
index/maintenance worker over Elasticsearch, Redis and RabbitMQ.
The operations worker has a 1 GiB memory limit and uses 32-document bulk/prefetch
bounds. NLP processes 8,192-character chunks within a 200,000-character derived
lemma limit; stored full source text remains intact.

Acquisition, analytics and scheduling require explicit profiles and capacity
admission. To enable the daily current-Congress bill refresh at 02:00 UTC:

```sh
make up STACK_PROFILES=operations,scheduler
```

Plain `make up` selects only the operations profile and can remove
inactive-profile containers. Refresh runs through the serial operations worker
and shared request budget. Readiness does not certify source freshness,
complete content, uninterrupted operation or disaster recovery.

## Restart

Compose owns the managed application processes:

```sh
make up
make stack-status
make health-check
make down
```

`make services`, `make start` and `make stack-up` select the same startup path.
`make restart` stops, rebuilds and restarts it. `make down` preserves data
volumes; `make local-stop` stops only infrastructure. **`make local-down`
deletes infrastructure volumes and is destructive.**

Do not run another worker supervisor or Beat alongside the managed services.
Startup refuses conflicting service registrations without stopping them.
Inspect ownership and stop conflicting processes through their owning
supervisor before retrying. Do not use process-name kills.

Startup waits for infrastructure and API readiness, reuses/starts native
Ollama, verifies the configured label model and checks access from the backend
container. `make ensure-ollama` checks/starts the native server separately.
Install missing models explicitly; startup neither downloads models nor rewrites
stored labels. If the container check fails, inspect `CONTAINER_OLLAMA_URL` and
host routing. Containers remain running for diagnosis. `make down` leaves the
shared native Ollama service running.

On a fresh setup, run `make local && make es-api-key` before application startup.
Docker Desktop must be running on macOS. Restart policies do not wake a sleeping
host or restart a merely unhealthy process. Workers have a 60-second stop grace;
pause/drain submissions before maintenance. RabbitMQ's seven-day consumer
timeout is configured in
[`rabbitmq.conf`](../elastic-start-local/config/rabbitmq.conf).

Keep the checkout at its configured absolute path: Compose mounts it at both
`/workspace` and that path so queued archive references resolve. Archives outside
the checkout require matching explicit mounts. Beat stores its schedule under
`data/`; retain it with the corresponding deployment.

### Live SQLite operating boundary

All managed Python services share `ledger-data:/var/lib/congress` and
`JOB_DB_PATH=/var/lib/congress/jobs.sqlite3`. Project `congresstracker` uses
volume `congresstracker_ledger-data`. Keep all live ledger operations inside
Docker, including read-only diagnostics and backups. Host-native SQLite readers
may inspect only closed offline snapshots, not the live WAL database.
Ordinary shutdown must not remove this volume.

For an explicit integrity check, use a lightweight reader inside Docker:

```sh
docker compose -f docker-compose.fullstack.yml exec -T backend \
  python - <<'PY'
import sqlite3
from contextlib import closing
from pathlib import Path

from cdm.config import get_config

path = Path(get_config().ledger.job_db_path).resolve()
with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
    result = connection.execute("PRAGMA integrity_check").fetchall()
if result != [("ok",)]:
    raise RuntimeError(f"Ledger integrity check failed: {result}")
print("ok")
PY
```

Schedule full scans around maintenance: read-only diagnostics still consume
memory and I/O. Inspect only relevant job identities with bounded queries.
Keep failed job rows and their explicit dispositions rather than clearing them
for a green report.

API reload watches application Python, not the full checkout or retained-data
tree. Monitor cgroup/kernel memory as well as Python RSS; a running reload
supervisor does not prove its server child or `/ready` is healthy.
`PYTHONFAULTHANDLER=1` enables native-crash diagnostics.

## Recovery

Use the single-flight, rate-limited recovery task for stale worker messages and
transient failures. Do not bulk requeue vendor 4xx, malformed XML, validation,
disk-I/O or expected non-indexed failures. Do not reset successful jobs.

### Recovery ownership

| State/boundary | Owner and action | Guard/evidence |
|---|---|---|
| Broker delivery/worker loss | Celery redelivery; `JobStore.mark_running` claims the job. | Duplicate active/terminal claims skip. |
| Raised task failure | `TaskRetrier` records it; `FailureClassifier` schedules transient retries. | Permanent rejection leaves affected jobs failed, entries unacknowledged and archives intact. |
| Silent running/retrying row | `JobRecoveryService` checks heartbeat and worker liveness under a Redis lock. | Live jobs are touched; analytics attempts are bounded. |
| Orphan queued row | The recovery sweep redispatches stale jobs. | Age, batch, queue-depth and active-package ownership guards apply. |
| Redis pending entry | `RedisRecordStream` reclaims with `XAUTOCLAIM`; `StreamIndexer` retries failed buffers. | A bulk rejection raises before acknowledgement. |
| Missing/trimmed stream body | `IndexJobRunner` invokes `ArchiveReplayer` when pending count is zero and stream count is insufficient. | Archive replay must independently satisfy the expected snapshot count; overlapping counts cannot be added. |
| Permanent rejected source | The failed job, pending entries and retained archive record the disposition. | Correct the cause and explicitly requeue; no automatic deletion or acknowledgement. |

`bulk_upsert` raises on partial failure. Successful items can remain written:
a multi-item bulk is not atomic. Idempotent replay converges without treating
partial success as batch completion. For acknowledged streams, replay the
durable archive or re-ingest the package; do not redispatch an index job whose
stream body has already been acknowledged.

### Resuming bounded missing-only content recovery

Keep identity creation, content acquisition and serving publication separate.
Create-only replay must verify exact readback and unchanged pre-existing
document versions. Metadata presence is not detail/text recovery.

1. Retain the immutable candidate roster, code/config seals, request journal,
   response cache, archives and explicit failure dispositions.
2. Verify there is one producer. Reuse shared request pacing and cached responses;
   extra threads do not increase the upstream budget.
3. Check persisted request/deadline limits, disk reserve and RSS before dispatch.
   Keep the host awake and stop on safety guards without silently extending them.
4. When separately downloading public text, defer hydration's automatic text fetch.
   Never forward API credentials to public text hosts. Retain every available
   version and explicit extraction/download failures.
5. Treat archive checkpoints as staged acquisition, not indexed coverage.
   Publish only the owned scope with fresh identity/version checks, conditional
   writes, exact readback and API acceptance.
6. Preserve known source blockers separately instead of retrying them indefinitely.
   Draining healthy work must not turn unresolved content into a complete result.

Alternate-source evidence is not a successful Congress API response. Retain
source URLs, package identities and hashes without relabeling API-only evidence.
An introduced-version roster proves original membership, not later episodes or
withdrawals.

### Exclusive staging within existing capacity

An idle operations consumer may yield its allocation to an explicitly approved,
bounded staging process. Verify no active/reserved/scheduled work and obtain
approval for the consumption gap. Pin its image, command, queues and allocation;
stop it before starting staging. Never overlap allocations or bypass request,
memory, disk, archive or identity guards.

Staging checkpoints must not mutate serving sources, failed jobs, aliases or
analytics pointers. Stop the owned staging process before restoring the original
consumer, then verify broker responsiveness. After an interruption, inspect both
process identities before restarting either. Do not run stack startup
concurrently with an exclusive recovery window.

## Backup and actual recovery boundaries

Back up indices, alias inventory, ledger, source archives and published model
artifacts separately. A consistent component backup is not an atomic common
recovery point or proof of complete restoration. Measure the full recovery
interval, including diagnosis; component checks do not certify host failover.

Elasticsearch 9 can omit dense vectors from ordinary `_source` retrieval.
Export with `source_exclude_vectors=False` and verify actual vector values.
For exact scratch readback, set `index.mapping.exclude_source_vectors=False`.
Preserve mappings, settings and aliases separately; never attach serving aliases
to test targets.

Bound restore batches by actual serialized bytes as well as row count.
Use at most 32 MiB/1,000 records per request and check actual NDJSON size before
submission. Large district geometries can exceed HTTP limits in small batches.
Keep acknowledgements, exact source/vector readback and owned-target cleanup
evidence. Partial restoration remains a failed restore.

Restore model artifacts into an owned scratch directory, preserve relative
paths and verify each file against the published manifest's size/hash.
Keep protected-row preservation and recovery timing separate from restore success.

### Consistent ledger backup

Run the online backup inside the existing container:

```sh
backup="data/jobs.sqlite3.pre-recovery-$(date -u +%Y%m%dT%H%M%SZ)"
docker compose -f docker-compose.fullstack.yml exec -T backend \
  python - "$backup" <<'PY'
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from cdm.config import get_config

source = Path(get_config().ledger.job_db_path).resolve()
target = Path(sys.argv[1]).resolve()
target.touch(exist_ok=False)
with (
    closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as live,
    closing(sqlite3.connect(target)) as snapshot,
):
    live.backup(snapshot)
    if snapshot.execute("PRAGMA integrity_check").fetchone() != ("ok",):
        raise RuntimeError(f"Backup integrity check failed: {target}")
PY
```

Copying only a live WAL database's main file can omit committed rows. The
backup API creates a standalone consistent snapshot, which may then be inspected
offline. For coordinated ledger/archive recovery, pause all writers and back up
each `records.sqlite3` with the same API. Preserve recorded paths/layout;
individually consistent databases do not establish cross-store atomicity.

### Independent dated data-only backups

Use a private dedicated cloud folder and a new dated snapshot directory.
Never mirror deletions, overwrite an earlier snapshot or create a public link.
Check authenticated quota and preserve at least 8 GiB host free disk.
Cloud revisions and desktop synchronization are not verified backup receipts.

| Payload | Recovery content |
|---|---|
| `manifest.json` | Application revision, capture times, index identities, sizes/hashes, counts and exclusions. |
| `indices/*.jsonl.gz` | `_id`, complete `_source` including available vectors, and sequence/term evidence. |
| `indices/*.metadata.json` | Mappings, settings and alias inventory. |
| `models/` | Published manifest's hash-verified model files. |
| `public-source-records.jsonl.gz` | Deduplicated logical archive records with relative origins and identities. |
| `public-source-files.tar.gz` | Public XML/CSV inputs with safe relative paths and no host owner metadata. |
| `official-pdfs/` | Sealed official PDFs with URLs and content hashes. |

Export indices between unchanged metadata/shard-sequence captures. Read only
closed archives and export logical rows, not free pages or live WAL state.
Canonical raw-source roots are `data/full_history`, `data/daily`,
`data/record_library` and `data/voteview`. Exclude operational journals,
credentials, private code/host paths and acquisition-state trackers. Inventory
exclusions and duplicate counts explicitly. Audit decompressed contents before
uploading.

For an authorized rclone destination:

```sh
rclone copy PAYLOAD REMOTE:DEDICATED_FOLDER/NEW_DATE --immutable --checksum
rclone hashsum sha256 REMOTE:DEDICATED_FOLDER/NEW_DATE --download
```

Compare exact remote names, sizes and independently downloaded hashes against
the sealed manifest, including the manifest itself. Never upload the parent
directory containing private execution state. Retain token-free receipts and
finite retry/error evidence. Publish `VERIFIED.json` only after download and
actual restore checks, and download-check that summary too.

Test a finite scope in UUID/owner-marked, unaliased scratch indices. Include
large geometries and real nonempty vectors, read all model/source frames and
validate tar paths without arbitrary extraction. Clean up only owned verified
targets and redundant downloads; preserve snapshots and receipts.

After host loss, retrieve the authorized cloud folder and recorded application
revision, verify hashes and rebuild owned indices with their mappings.
Sequence numbers are evidence, not values to assign to restored indices.
Reconcile aliases only after full destination validation. Job/broker recovery
requires the separate operational backup.

### Portable local operational backup

Keep operational backups private and separate from the cloud data-only payload.
Capture a Docker-side consistent ledger snapshot. Export broker definitions and
record queue emptiness: definitions do not contain messages. Complete Redis
`BGSAVE` before copying its RDB and preserve every logical database. Archive
closed source libraries and models with checksums and safe relative paths.
On ExFAT media, use portable artifacts rather than live database storage.

Operational artifacts may contain sensitive state such as broker password hashes.
Record each component's capture time, application revision and configuration
requirements. An external drive must be mounted before using dependent paths;
inspect symlink destinations before reading or relocating any backup. Backup
verification does not require starting a second stack or interrupting serving.

## Rollback

1. Stop workers, Beat and API/admin writers with `make down`; close all SQLite
   connections and verify no independent writers remain.
2. Preserve the current ledger and WAL/SHM sidecars, archives and failure reason.
3. Verify the intended closed backup's integrity and identity.
4. Restore only after verification, then start services and run health checks.
5. Verify job identities/payloads, queue state, indexed sources and aliases before
   resuming submissions.

After all application writers are stopped, restore through the same project
volume without starting dependencies:

```sh
docker compose -p congresstracker -f docker-compose.fullstack.yml \
  run --rm --no-deps -T --entrypoint python backend \
  - /workspace/data/jobs.sqlite3.pre-recovery-TIMESTAMP <<'PY'
import shutil
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

from cdm.config import get_config

source = Path(sys.argv[1]).resolve(strict=True)
target = Path(get_config().ledger.job_db_path).resolve()
if source == target:
    raise RuntimeError("Backup must differ from the live ledger path")
with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as snapshot:
    if snapshot.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise RuntimeError("Backup integrity failed")
before = target.parent / ("pre-restore-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
before.mkdir()
for path in (target, Path(str(target) + "-wal"), Path(str(target) + "-shm")):
    if path.exists():
        path.rename(before / path.name)
shutil.copy2(source, target)
PY
```

Verify project configuration and capacity before running the restore container.
Never restore over an open database or leave mismatched sidecars beside a restored
snapshot. Restore archives to paths recorded in job payloads. Keep corrupt
GovInfo manifests/source archives quarantined with their `.corrupt-*` suffix.

## Analytics retention

Successful non-preview analytics builds submit a separate `analytics_cleanup`
job to the maintenance queue. It first verifies the actual live HTTP generations.
The [retention policy](guides/analytics.md#6-rebuilds-retention-and-operational-checks)
keeps the published topic model and one predecessor, graph generations per
signal, perspective snapshots per Congress and their required dependencies.
Source records, archives, backups and downloaded base models are not targets.

Run this in the managed backend, never against a host-opened live ledger:

```sh
# Read-only lineage report.
docker compose -f docker-compose.fullstack.yml exec -T backend \
  python -m scripts.preview_analytics_retirement
# Read-only exact retention plan, including owned unmanifested older artifacts.
docker compose -f docker-compose.fullstack.yml exec -T backend \
  python -m scripts.preview_analytics_retirement --plan
# Submit a durable verified cleanup job; requires the maintenance consumer.
docker compose -f docker-compose.fullstack.yml exec -T backend \
  python -m scripts.preview_analytics_retirement --cleanup
```

Inspect the returned job ID and progress in the normal job ledger/API. A failed
live readback, uncertain ownership, missing retained model or publication change
stops cleanup explicitly. Investigate before retrying; do not remove pointers,
model manifests or shared cache indices to bypass the guard.
Keep manual publication/repair operations out of the cleanup interval.
Do not force-merge live indices to accelerate storage reclamation.

## Production cutover gate

Move read/write aliases only after verified target coverage, explicit failure
dispositions, ledger integrity, dependency health, drained recovery/backlogs
and representative target reads/writes. Additive mappings alone do not prove
existing stored values are searchable.

## Source contract preview and staging

Run submission commands in the owning deployment environment when they access
the managed ledger. Start with a read-only bounded preview:

```sh
uv run --frozen python scripts/reconcile_govinfo_bulk.py \
  --archive-root data/full_history/govinfo \
  --target-index congress-legislation-read --max-records 100 \
  --report-path /tmp/congress-source-preview.json
```

This reads at most 100 combined parent/text payloads and inventories the target;
it submits no job and writes no index. Use `--archives-only` instead of
`--target-index` when intentionally omitting search inventory. Keep reports
outside source-package directories.

After reviewing conflicts, quarantine, field authority and coverage gaps,
explicitly request durable staging:

```sh
uv run --frozen python scripts/reconcile_govinfo_bulk.py \
  --archive-root data/full_history/govinfo \
  --target-index congress-source-shadow --write-staging \
  --report-path /tmp/congress-source-staging.json
```

The target must already exist as an unaliased physical index with appropriate
mappings. `--max-records` is forbidden for writes. No alias cutover is provided.
`completed` describes the selected replay, not upstream discovery/hydration;
reports retain partial coverage and `promotable=false`. See
[source semantics](guides/ingestion.md#govinfo-replay-and-reconciliation).

### Sealed graph repair rehearsal

Use a worker-capable environment, hold competing writers and check serving
write/delete counters before and after read-only capture. Ordinary graph builds
publish; they are not this rehearsal procedure.

```sh
uv run python scripts/stage_graph_repair.py capture --bundle /absolute/new/bundle
uv run python scripts/stage_graph_repair.py verify --bundle /absolute/new/bundle
uv run python scripts/stage_graph_repair.py rehearse \
  --bundle /absolute/new/bundle --output /absolute/new/rehearsal \
  --staging-url http://127.0.0.1:19397
```

Use new directories and an explicitly provisioned disposable cluster.
Capture reads search and writes local files only. Rehearsal rejects the serving
cluster UUID and owns nonce-scoped scratch indices. It does not provision or
stop that cluster. Preserve bundles/reports locally, not as committed corpus data.

| Artifact | Contract |
|---|---|
| `manifest.json` | Completion marker, typed counts/config and SHA-256/size seals. |
| `state.json` | Source cluster UUID, mappings/settings/aliases and raw pointers. |
| `source.jsonl` | Captured scope with IDs, sources and sequence/primary terms. |
| Six CSVs | Retained Congress 114 members, roll calls and positions. |
| `repairs.jsonl`, `diffs.jsonl` | Candidate bodies and exact reviewed changes. |
| `candidate-edges.jsonl`, `candidate-pointer.json` | Stage-only graph candidate. |
| `acceptance.json` | Requires verified candidate, exact isolated rollback and cleanup; binds the input manifest. |

Missing, changed, unexpected or symlinked artifacts fail verification.
Partial files are not success markers. Checksums prove consistency, not
authorization. Revalidate source versions, aliases, pointers, backups and resource
budgets before any separately approved live repair.

### Bounded live schema and source repair

The source-repair CLI exposes `prepare`, `apply` and `rollback`; it cannot
publish graph pointers:

```sh
uv run python scripts/repair_graph_sources.py prepare \
  --bundle /absolute/sealed/bundle --rehearsal /absolute/accepted/rehearsal \
  --evidence /absolute/new/live-evidence --staging-url http://127.0.0.1:19397
uv run python scripts/repair_graph_sources.py apply \
  --bundle /absolute/sealed/bundle --evidence /absolute/new/live-evidence
uv run python scripts/repair_graph_sources.py rollback \
  --bundle /absolute/sealed/bundle --evidence /absolute/new/live-evidence
```

`prepare` is read-only on serving search: it verifies seals, CSV derivation,
versions and topology, backs up the complete physical graph and proves exact
restoration on a different cluster. Only successful restore/cleanup creates
`repair-plan.json`.

Separately approve `apply` after worker/budget/precondition revalidation.
It adds approved mapping properties and CAS-replaces approved source IDs.
Exclusive intent files and fsynced receipts bind each acknowledged write.
Rejection or uncertainty stops the operation without automatic retry.
`repair-applied.json` requires exact scoped verification, unrelated-version
preservation and unchanged graph/pointer/alias state.

`rollback` restores only receipted writes with exact body/version checks and CAS.
Its journal supports interrupted acknowledged rollback under an advisory lock.
Unknown writes, lost responses or changed pointers require explicit
reconciliation. Mapping fields are additive; removing them requires a separately
approved reconstructed-index cutover.

### Sealed voting-only graph promotion

The promotion CLI requires the sealed voting candidate and accepted source
repair. Keep competing writers held throughout:

```sh
uv run python scripts/promote_voting_graph.py stage \
  --bundle /absolute/sealed/bundle --repair-evidence /absolute/live-evidence \
  --candidate /absolute/accepted/rehearsal --output /absolute/new/promotion
uv run python scripts/promote_voting_graph.py accept \
  --bundle /absolute/sealed/bundle --repair-evidence /absolute/live-evidence \
  --output /absolute/new/promotion \
  --browser-report /absolute/new/promotion/browser-before.json
uv run python scripts/promote_voting_graph.py publish \
  --bundle /absolute/sealed/bundle --repair-evidence /absolute/live-evidence \
  --output /absolute/new/promotion
uv run python scripts/promote_voting_graph.py rollback \
  --bundle /absolute/sealed/bundle --repair-evidence /absolute/live-evidence \
  --output /absolute/new/promotion
```

`stage` verifies frozen derivation, repaired-source versions, pointer/topology
identity, candidate seals and retained graph generations. Unique IDs, distinct
endpoints, finite scores, vote counts and Congress scope are checked before
create-only writes. Partial failure leaves an unpublished candidate, not success.

Before `accept`, serve the real API against those edges with a read-only pinned
voting pointer; other signals keep their published pointers. In `frontend/app`:

```sh
BROWSER_BASE_URL=http://127.0.0.1:4176 \
BROWSER_API_BASE_URL=http://127.0.0.1:18400 \
GRAPH_VOTING_ACCEPTANCE_MEMBER=MEMBER_FROM_PROMOTION_PLAN \
GRAPH_VOTING_ACCEPTANCE_VERSION=VERSION_FROM_PROMOTION_PLAN \
PLAYWRIGHT_JSON_OUTPUT_NAME=/absolute/new/promotion/browser-before.json \
npm run test:browser -- live-voting.spec.ts --reporter=list,json
```

Acceptance requires actual desktop/narrow Playwright results, exact graph
identity, available Congress 114 voting analysis, rendered canvas and finite
positive voting links. Failed/skipped/retried or wrong-version reports fail.
The report seal binds the staged graph.

`publish` CAS-switches the voting pointer and verifies retained generations,
candidate receipts, sources, sibling pointers and aliases. `rollback` requires
an acknowledged promoted pointer and CAS-restores its captured predecessor.
Both edge sets remain; no source rollback, alias cutover or worker restart occurs.
Repeat real API/browser checks without pointer pinning after publication.

### Manual serving repair safety

For presence-based recovery, follow
[existence-first reconciliation](guides/ingestion.md#reconcile-existing-data-before-historical-acquisition).
Ordinary additive upsert is not a version-conditional repair boundary.

For an approved bounded field repair, retain checksummed before-images and
sequence/primary terms. Audit identities/proof, compare projections in an owned
unaliased shadow, and verify mappings, field preservation, stale-version
rejection and conditional rollback before serving writes.

A count/URL descriptor is not a collection record. Expand only a pure descriptor
whose bill/collection URL and count match a fully audited list. Preserve its
before-image; extra fields, actual records or mismatches require conflict review.
Verify empty collections and projected completeness evidence independently.

Fsync an intent before submission and the exact acknowledgement afterward.
Uncertain writes require reconciliation, not blind retry. On resume, verify
acknowledged versions and untouched originals. Finish with exact source readback
and actual `/api/v1` checks; an absent route is not permission to repeat a write.
Compare DTO nullable/default semantics without converting unknown data to empty
success. Remove only verified owned shadows and retain journals/before-images.

## Controlled pipeline acceptance

The [contracts workflow](../.github/workflows/contracts.yml) selects synthetic
suites against disposable Elasticsearch 9.3.1 and Redis 7. Never point them at
source-data services or enable all integration tests indiscriminately.
Fixtures own UUID-scoped indices/streams/pipelines and temporary SQLite stores;
the query-budget fixture requires an empty cluster.

For local reproduction, provision disposable services on unused loopback ports,
set the following variables and run only these selectors:

```sh
RUN_INTEGRATION_TESTS=1 \
PIPELINE_TEST_SEARCH_URL=http://127.0.0.1:19393 \
PIPELINE_TEST_REDIS_URL=redis://127.0.0.1:16393/0 \
INDEXING_TEST_URL=http://127.0.0.1:19393 \
TOPIC_PUBLICATION_TEST_URL=http://127.0.0.1:19393 \
GRAPH_PUBLICATION_TEST_URL=http://127.0.0.1:19393 \
PERSPECTIVE_PUBLICATION_TEST_URL=http://127.0.0.1:19393 \
PERSPECTIVE_PUBLICATION_TEST_MAX_BYTES=8388608 \
QUERY_READS_TEST_URL=http://127.0.0.1:19393 \
uv run pytest -q \
  tests/integration/test_pipeline_failures.py \
  tests/integration/test_indexing_projection.py \
  tests/integration/test_topic_publication_integration.py \
  tests/integration/test_graph_publication_integration.py \
  tests/integration/test_perspective_publication_integration.py \
  tests/integration/test_query_reads_integration.py \
  -W error::UserWarning
```

The Elasticsearch HTTP limit must match the 8 MiB perspective-test bound.
Supply optional `PIPELINE_TEST_SEARCH_API_KEY` privately through the environment.
Use a separate Redis database; never direct a database-flushing test at
application Redis. Stop/remove only the disposable services you provision.

These suites exercise partial bulk rejection, reclaim/replay, duplicate delivery,
incomplete archives, SQLite backup/restore, CAS publication and real-index query
budgets. They do not prove broker restart behavior, full-system restoration,
source freshness or sustained throughput. Passing fixtures alone does not
authorize deployment.

## Release image and routing acceptance

The API contracts workflow's manual image job builds production images after
the normal contracts gate. It does not publish to a registry, deploy or start
Beat. Queue/deployment unit checks run on pushes and pull requests.

```sh
docker build --target api -f Dockerfile.prod -t congress-release-backend:smoke .
docker build -f Dockerfile.prod -t congress-release-worker:smoke .
docker build -f frontend/app/Dockerfile.prod \
  -t congress-release-frontend:smoke frontend/app
docker pull rabbitmq:3.13-alpine
UV_PROJECT_ENVIRONMENT=tmp/release-smoke-env \
  uv sync --frozen --only-group release
RUN_INTEGRATION_TESTS=1 \
RELEASE_TEST_BACKEND_IMAGE=congress-release-backend:smoke \
RELEASE_TEST_WORKER_IMAGE=congress-release-worker:smoke \
RELEASE_TEST_FRONTEND_IMAGE=congress-release-frontend:smoke \
UV_PROJECT_ENVIRONMENT=tmp/release-smoke-env \
  uv run --frozen --only-group release python -m pytest -q \
    tests/integration/test_release_images.py -W error::UserWarning
```

The `release` environment contains the host test driver. Runtime checks execute
inside images: `api` excludes training dependencies; the default `analysis`
target includes them. Both retain spaCy, its pinned English model and NumPy.
Operational workers select `api`; analytics consumers require `analysis`.

The fixture uses an internal UUID-named Docker network, bounded containers,
throwaway broker credentials, no host ports and no source-data mounts. It checks
runtime mappings, CPU/memory caps, `/health`/`/ready`, SPA/deep-link serving,
OpenAPI/NLP parity, actual AMQP envelopes and singleton worker task registration.
It removes only its owned containers, anonymous volumes and network.
This startup/routing smoke is not a throughput, peak-memory, source-fetch,
training, broker-crash or disaster-recovery benchmark.
