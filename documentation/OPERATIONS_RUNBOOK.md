# Operations Runbook

This runbook covers local restart, health checks, recovery, backup, and rollback
for the Congress Tracker workers and durable job ledger.

## Health Check

The finite [local release closeout](IMPLEMENTATION_PLAN.md#fixed-local-release-closeout)
tracks content/freshness, analytics, the real 24-hour observation, recovery and
final disposition. A ready API or passing isolated fixture does not close those
gates.

### Latest local acceptance disposition

The fixed implementation closeout finished on **2026-11-08** with evidence or
explicit blockers for every gate. It is not an all-history freshness or full
disaster-recovery certificate.

- **C2 accepted:** the expanded 109,726-input model and current topic, graph
  and all 707 perspective HTTP contracts remain exact after the day; all five
  published model-file hashes are unchanged.
- **C3 passed:** **86,400.149 uninterrupted seconds**, **432,000 offered and
  completed reads**, zero failures/gaps, **p95 0.343 seconds** against the
  2-second objective, and **1,440 timed indexing jobs/28,800 records**.
  The interval ran from **2026-11-07 01:54:45 UTC** to
  **2026-11-08 01:54:46 UTC**. The 3.779-second maximum request latency is
  retained; the objective bounds p95, not maximum latency.
  All **4,319 resource samples** preserve the original safety floors;
  the original worker/allocation/command remained stable with no restart/OOM.
  All **1,922** separately accounted warm/stress/timed jobs, exact retained
  archives, dispatch identities and zero-pending/zero-lag receipts pass.
  No warm/stress/failed time is added to the qualifying day.
- **Preservation:** all **371,366 original document versions**, **10,449
  accepted enriched sources**, **three blocked metadata records** and
  **628,082 original ledger rows** remain exact; ledger integrity is `ok`.
  Only accepted, exactly owned test streams/index were retired. Every archive,
  source seal and failed observation remains retained.
- **C1 blocked:** two law PDFs exceed the unchanged 32 MiB response bound and
  one complete cosponsor collection fails upstream. Ordering remains unresolved
  for 487 representatives; 19,832 Congress 119 records lack document source-check
  evidence; the 69 pre-93 records do not prove wider historical coverage.
- **C4 not passed:** the 77.4035-second controlled interruption and exact
  five-file model restore passed, but a later SQLite incident exceeded
  15 minutes and full index restoration stopped at the original resource guard.
  Full-library/broker-volume/off-host recovery remains unproved.
  Single-host topology blocks independent-host failover, not a waived objective.
- **C5 complete:** validation and current source-pinned documentation/wiki
  publication record these distinctions, without another open-ended retry queue.

Index presence and Bill API visibility are separate checks. Shared bill reads
include bill/law projections with canonical bill identities; law detail reads
validate agreement between the identity fields. Do not change `source_type` or
download an existing law projection to repair read visibility. Exact canonical
IDs bypass NLP, but this does not certify the memory use of general text queries.
Keep conditional-write acknowledgements and preservation evidence; do not reapply
acknowledged content repairs. Retire only the recorded owned, unaliased scratch
shadow after current-code strict source/version/sentinel/API verification.

Upstream catalog counts are not identity-set reconciliation or full-detail/text
freshness evidence. Compare official IDs against the physical index, including
law projections, before proposing create-only ingest. A missing
`source_checked_at` is unknown freshness, not proof that a document is absent or
stale. Preserve captured catalog pages and their provenance; do not stamp
individual records as source-checked merely because a collection count matches.

### Resuming bounded missing-only content recovery

Keep identity creation, content acquisition and serving publication separate.
Create-only replay must finish with exact readback and proof that original
document versions are unchanged; metadata presence is not detail/text recovery.
Never restart acknowledged replay to enrich those records.

For a sealed acquisition queue:

1. Retain the immutable candidate roster, code/config seals, request journal,
   successful-response cache, archived records and failure dispositions. Resume
   the same execution only with matching seals; preserve failed executions.
2. Verify there is no second producer. Reuse the shared upstream rate limiter;
   extra HTTP threads cannot increase the allowed request budget. Resume cached
   responses and staged IDs without redownloading successful work.
3. Check persisted request/deadline limits, disk reserve and RSS before dispatch.
   Keep the host awake, monitor checkpoint progress and stop on safety guards.
   Do not reset counters or extend deadlines silently to force completion.
4. Defer hydration's automatic text fetch when using a separate public downloader.
   Never forward API credentials to public text hosts. Retain each available
   version and explicit unsupported, extraction or download failures; an empty
   version listing alone does not prove historical text is unavailable.
5. Treat archive checkpoints as staged acquisition, not indexed coverage.
   Publish only the owned identity scope using fresh source/version checks,
   conditional writes, exact readback and actual API acceptance. Keep original
   records unchanged and reconcile changed analytics inputs before certification.
6. Preserve known source blockers in a sealed explicit inventory rather than
   retrying them indefinitely ahead of healthy pending work. Report them
   separately in checkpoints and retain their partial content and failure
   evidence. They remain unresolved coverage obligations: draining the other
   records must not produce a complete-content certificate or a successful final
   exit. New unexpected consecutive failures still trigger investigation.

### Backup and actual recovery boundaries

Back up indices, alias inventory, ledger, record archives and published model
artifacts separately. A consistent backup is not proof of restoration, and an
API restart is not broker-volume or independent-host disaster recovery.
Measure the full recovery interval, including diagnosis; a shorter, separate
restart exercise cannot certify a later incident's recovery time.

Elasticsearch 9 can omit dense vectors from ordinary `_source` retrieval.
Export with `source_exclude_vectors=False`; verify the resulting source rather
than assuming a default scan contains embeddings. For exact vector readback,
owned restore targets use `index.mapping.exclude_source_vectors=False`.
Preserve index mappings/settings and alias inventory separately. Never restore
over serving indices or attach serving aliases to a test target.

Restore model artifacts into an owned scratch directory, preserving relative
paths, then verify every file's size/hash against the published manifest.
Retain the archive after retiring only that verified scratch directory.
Keep source/version and protected-ledger-row preservation checks separate from
restore success. Resource-guarded partial restoration is a failure, even when
every acknowledged record in the partial target verifies exactly.

<!-- wiki:repository-only:start -->
### Local closeout recovery evidence

The local closeout backup contains **25 business indices and 3,244,277
documents**, including dense vectors, plus a **448,028,672-byte** consistent
online SQLite ledger backup. These are frozen backup counts, not a claim that
later analytics publications are included.

Actual restoration exactly verified **1,504,221 graph documents** and
**413,506 topic documents**, then acknowledged and verified **116,500
legislation documents** before the combined disk-or-RSS guard stopped it.
The failure did not record individual resource values, so neither the specific
bound nor a full-restoration success can be inferred. All three owned restore
targets were retired after UUID/owner/no-alias checks. **The complete restore
and its 15-minute recovery objective did not pass.** Retain the complete
backup and partial-attempt receipts; do not lower safety floors or prune data
to force a passing result.

A separate actual interruption stopped the original operations worker, durably
queued an owned 20-document archive/Redis/index job, restarted the existing
RabbitMQ, Redis and API containers, then restarted the same worker. Recovery
took **77.4035 seconds**, with exact indexed sources, no pending stream entries,
API readiness and scratch retirement. All **628,082 pre-existing job rows**,
including five failed rows, were unchanged; the worker retained its **1 GiB**
allocation. Subsequent readback also preserved all **371,366 original document
versions**, **10,449 accepted enrichments** and **three blocked metadata records**.

The current model `20261106T165556Z-a4db27dfa2624216b7c60c1e4caf12f3`
was subsequently backed up and actually restored: **five files, 27,890,390
bytes**, with exact hashes and owned restored scratch retirement. The archive
remains retained. Full archive/broker-volume restoration, independent-host
failover and off-host disaster recovery remain unproved.

During the first sustained-operation attempt, the host live ledger passed
integrity checks while the container view was malformed and differed in size.
Both writers were stopped; the healthy current online backup matched the host
ledger's all-table logical dump digests. The old host inode and malformed
container-visible file were retained, and the live inode was atomically replaced
with the verified current snapshot. The exact queued job resumed from its
original serialized payload, indexed all 20 exact records and left no pending
entries. All **628,082 original job rows** remain unchanged. The precise
filesystem/cache mechanism is not proved; the divergent views are observed
facts. **This incident exceeded 15 minutes.**

The next observation failed after **215.814 seconds**, with 970 offered/920
completed reads and an API cgroup OOM kill. It is not a qualifying day.
The corrected helper imports only ledger/broker collaborators, not the full
application container: measured import peak **67,256 KiB**, with a regression
ceiling of 96 MiB. Warm acceptance passed 75 reads at p95 **0.452 seconds**
while the original worker indexed 20 exact records; no new API OOM occurred.
These are preparation checks, not 24-hour evidence. That next observation also
failed: **3,913.009 seconds**, 19,516 offered/19,515 completed reads, p95
**0.348 seconds**, zero scheduling gaps and another API OOM kill. Its receipt
records 65 consumed indexing results; the journal proves 66 completed timed
batches plus smoke. All 628,082 protected original ledger rows still verify
unchanged, with full integrity, and the owned failed target is retired.

The supervisor was watching **104,893 directories** under `/workspace`; even
after its server child died, the cgroup retained about **166 MiB of kernel
memory**. Bounding hot reload to `/workspace/cdm` reduced the watches to **42**
and kernel memory to about **4.6 MiB**. Warm HTTP/index smoke now measures
about **213 MiB/512 MiB** for the API, p95 **0.353 seconds** over 75 reads and
20 exact indexed records. The original worker's container identity, command
and 1 GiB allocation are unchanged. These observations support the bounded-watch
fix; they do not prove a day.

The observation that started **2026-11-06 18:58:06.015273 UTC** failed after
**5,881.866 seconds**: 28,200 offered/28,199 completed reads, p95 **0.342 seconds**
and zero scheduling gaps. The API remained ready with no new OOM; the original
1 GiB worker OOM-killed its child during batch 94. Broker redelivery skipped
the still-running durable job; it did not automatically recover that claim.
After proving the executor dead and the worker idle, the same worker was
restarted without changing its identity, command or allocation. Only the exact
owned interrupted job was deliberately requeued, preserving its original wire
payload. Recovery verifies all 20 exact sources, zero pending/lag, full ledger
integrity and all 628,082 protected original rows unchanged. Its owned scratch
target is retired; archives and failed receipts remain retained.

The bounded NLP implementation now serializes spaCy memory zones, excludes
unused parser/NER components and uses one text per inference microbatch with
the same model, cap and filtering. Sixty captured pre-change projections and
all **9,120 complete frozen workload projections** match exactly. Offline peak
RSS is **673.1 MiB**, with the string store unchanged at 709,118 entries.
The vocabulary's cumulative `len()` counter is not a live-retention measure in
this spaCy version; real transient-lexeme membership and string cleanup are
tested directly. Actual warm acceptance passes 75 reads at p95 **0.433 seconds**
plus two exact 20-record batches, including the longest-text group, with no
worker OOM. These checks are not a day or a new 15-minute recovery certificate.
A replacement observation must restart from zero, sealing the NLP source and
configuration as well as the exact API memory/reload command and watch bound.
That observation began **2026-11-06 21:03:41.112 UTC** and stopped after
**6,491.686 seconds**. All 32,459 offered reads completed successfully at p95
**0.346 seconds**; neither the API nor worker recorded an OOM. The receipt
consumed 108 indexing results, while the journal independently accounts for
109 completed timed batches plus two preflight batches. All original job rows
verify unchanged, with full ledger integrity; its owned target is retired.

The macOS time-service log proves a successful **89.289665-millisecond backward
UTC adjustment** at the failure instant. The old observer rejected any negative
wall-clock increment; the maximum actual request-offer interval was only
**0.509 seconds**. The failed receipt remains false and receives no qualifying
time. The replacement uses Python's nonadjustable monotonic clock and Darwin's
nonadjustable, suspend-inclusive `CLOCK_MONOTONIC_RAW`, retaining the same
two-second scheduling/suspend limits and all other original gates. UTC remains
an event timestamp. Tests reproduce the old NTP false alarm, still reject real
sleep/pauses, and compare the entire load/resource/journal/acceptance loop
against the sealed original after normalizing only the continuity clock call.

The next attempt retained zero clock/scheduling gaps but stopped when the worker
OOM-killed its child during batch 65, before its existing 200-task rotation.
Its false receipt records 4,142.229 seconds including the bounded drain wait,
19,500 offered/19,499 completed reads, p95 **0.345 seconds** and 64 consumed
indexing results. The API remained ready. The exact interrupted job was
recovered with its original wire payload and 20 exact sources, zero pending/lag,
all 628,082 original job rows unchanged and owned scratch retirement.

The existing worker parent retains heavy imports. Index-consuming workers now
warm the CPU NLP model before forking, sharing model-weight pages rather than
allocating another model in a child. Commands, concurrency, 200-task rotation
and the 1 GiB allocation remain unchanged; ingestion-only workers are not warmed.
Before another genuine day, require **480 real indexing jobs/9,600 exact
projections**, every one of the **9,120 frozen inputs**, and **two actual child
rotations** with zero worker OOM. All stress archives remain retained.
An initial preflight's additional peak check rejected a transient kernel peak
just above `memory.max`, despite the exact unchanged limit and zero OOM.
That failed preflight is retained and its 22 completed owned jobs are accounted
for. The corrected check verifies the actual effective `memory.max == 1 GiB`,
retains raw peak/current measurements, and preserves the original observer RSS,
disk, host-memory and other guards. It does not resize or hide an OOM.
The subsequent full preflight stopped after 160 successful jobs when the
original worker unexpectedly restarted, stranding the next exact job's RUNNING
claim. A new cgroup showed zero OOM kills; that reset counter does not establish
an uninterrupted worker. All 163 owned jobs are now exactly terminal, every
archived source is verified, and its failed unstarted scratch is retired.
A controlled warm-worker fork measured 42,782 minor faults from a full child GC
without a frozen heap versus 17 with one. The indexing parent now collects
unreachable objects and freezes the remaining long-lived import/model graph
before forking; future task objects still undergo normal GC. Require the
observed warm/freeze markers, stable original worker start/restart state, and
the full two-rotation stress proof before another day. Failed stress contributes
no qualifying observation time. Retention resumes both four-digit warm/timed
and five-digit stress receipts without revisiting an already deleted stream.
Frozen-only stress completed 328 jobs and one original child rotation but
stopped on another unexpected worker restart. Its exact interruption is
recovered, all 331 owned jobs/6,620 archived records are terminal and verified,
and its failed scratch is retired. The core remaining footprint was unrelated
analytics imports in the operational task composition root. Operational task
discovery now uses `OperationsContainer`; analytics implementations are
registered through Celery's loader at startup only for analytics-consuming
workers, before forking, with module-level Python imports and unchanged
serialized task name/route/time limits. Fresh operations import/model warmup
measured 305,201,152/595,853,312 bytes with no unrelated analysis modules loaded.
Require the same complete stress, rotations, runtime, allocation and original
resource floors; no previous failed time is credited.
The complete queue-scoped preflight now passes: **480 jobs/9,600 exact
projections/all 9,120 inputs**, **three child PIDs/two original rotations**,
zero restart/OOM and unchanged 1 GiB allocation, in 1,233.788 seconds.
All 482 warm/stress jobs and retained archive/zero-pending receipts, all
24 resource samples, and all 628,082 protected original ledger rows/integrity
are independently verified. The closed backup ledger was byte-exact
native-compressed (448,028,672 logical bytes; 93,687,808 currently allocated);
the no-saving analytical-source attempt was refused and its bytes retained.
Neither stress nor previous failures count toward the required new genuine day.
The fresh genuine observation ran from **2026-11-07 01:54:45 UTC** to
**2026-11-08 01:54:46 UTC** after source and source-pinned wiki publication.
The full **86,400.149-second/432,000-read/1,440-timed-batch** contract passed
and its complete read/resource/job/archive/preservation reconciliation is done.
All 1,922 warm/stress/timed jobs and archives remain accounted for, and the
accepted owned target is retired. The 480 stress and two warm jobs remain
separate and do not count toward the 1,440 timed jobs or qualifying duration.
Completed owned test streams are retired only after terminal indexing,
exact readback, a retained exact archive and zero pending/lag proof. Every
archive remains at its original path; native compression is used only when
byte-exact and beneficial, with explicit no-saving dispositions otherwise.
Duplicate failed-run source storage was replaced with independent byte-identical
APFS clones, not removed. Original Docker allocations, rates, the 8 GiB disk
floor and other guards remain unchanged.

Maintenance receipts reference explicit recovery dispositions, not a complete
restore certificate. Preserve failed observations and their zero qualifying
time; never add elapsed intervals across incidents or sleep.
<!-- wiki:repository-only:end -->

### Live SQLite operating boundary

Keep all live ledger operations inside Docker while the managed stack is
running. Do not mix host-native SQLite connections with container writers on the
same bind-mounted WAL ledger, including read-only diagnostics and backups.
Readiness/stack checks do not require a second ledger runtime:

```sh
make stack-status
curl --fail http://127.0.0.1:8000/ready
```

The legacy `make status`, `make health-check`, and direct
`scripts/job_status.py`/`scripts/health_check.py` commands open the native
ledger. **Do not run them against a Docker-managed live ledger.** They also
materialize job rows and are not qualified within the small API container's
memory budget; do not merely wrap the full scripts in `docker exec`.
Use bounded Docker-side ledger queries and independently check the existing
worker/broker and serving API. Readiness alone is not a queue, source freshness,
restore or sustained-operation certificate. Keep historical failed job rows and
their explicit dispositions rather than clearing them for a green report.

For an independent live integrity check, use a lightweight Docker-side reader:

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

Schedule full integrity scans around maintenance, not alongside a sustained-load
acceptance run; even read-only diagnostics consume memory and I/O.

Keep API reload watching scoped to application source, not the entire checkout.
Large retained-data trees can consume substantial kernel watch/slab memory that
Python RSS does not show. Monitor the container cgroup as well as process RSS;
a live reload supervisor does not prove its server child or `/ready` is healthy.

Stop all ledger writers before replacement/restoration, preserve the current
file and sidecars, and verify a current consistent backup before replacing any
inode. Never overwrite the ledger from an older backup to hide corruption.
After recovery, check full integrity, protected original rows, exact interrupted
job identity/payload, terminal status, indexed sources and pending stream entries.
Native access to a closed offline snapshot is different from native access to
the shared live WAL file. Keep full scans and heavyweight diagnostic imports out
of tightly allocated serving containers.

## Restart

Stop workers and Beat before changing the ledger or restoring a backup.
Compose is the sole supported managed local stack:

```sh
make up
make stack-status
curl --fail http://127.0.0.1:8000/ready
```

`make services`/`make start`/`make stack-up` are aliases for that path.
`make restart` stops/rebuilds/restarts it; `make down` stops application and
infrastructure containers without deleting data volumes. `make local-stop`
stops only infrastructure. Do not also run foreground workers or another Beat.
Docker Desktop must start at login on macOS; Compose cannot wake a sleeping
machine or start the Docker engine after a reboot by itself.

Startup waits for infrastructure and API `/ready` rather than only open ports.
Mint the local search key with `make local && make es-api-key` on a fresh setup
before starting the application stack. Running containers use `unless-stopped`;
an unhealthy healthcheck alone does not trigger a restart. Workers have a
60-second stop grace before Docker may terminate them; pause/drain submissions
before maintenance and rely on durable recovery for interrupted work.

After a default restart, confirm exactly one `operations@...` worker consumes
only the index and maintenance queues, and no acquisition/analytics/Beat process
is active. Other [profiles](guides/configuration-and-deployment.md#managed-stack-compose)
need explicit approval/capacity review. Duplicate workers can cause unnecessary redelivery
and database contention. RabbitMQ uses the repository configuration in
`elastic-start-local/config/rabbitmq.conf`; its seven-day consumer timeout
allows a long-running task to survive extended laptop sleep while retaining
protection against permanently abandoned consumers.

## Retiring Native Agents

The launchd installer is removed. Startup refuses known old registrations or
plists, even if an agent is currently unloaded. This migration is **manual**:
pause submissions, record active jobs, and allow work to drain first. Do not
start Compose until old foreground API/worker/Beat processes are also stopped
from their owning terminals or by a verified owned PID.

Run this from the checkout that installed the agents. It verifies each plist's
working directory, unloads only the four known labels, and moves registrations
into a timestamped backup instead of deleting them. A missing/mismatched owner
stops the migration; inspect that registration manually rather than guessing.
It does not delete jobs, archives, models, queues or Docker volumes.
For a loaded label, first inspect `launchctl print gui/$(id -u)/LABEL` and confirm
its working directory also matches the verified plist; do not unload a different
checkout's agent.

```sh
# Retire legacy agents only after pausing submissions and draining work.
(
  set -eu
  repo_root=$(pwd -P)
  retired="$HOME/Library/LaunchAgents/retired-congress-tracker-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir "$retired"
  for name in ingest-recovery index maintenance beat; do
    label="com.congress-tracker.$name"
    plist="$HOME/Library/LaunchAgents/$label.plist"
    service="gui/$(id -u)/$label"
    if [ ! -f "$plist" ]; then
      if launchctl print "$service" >/dev/null 2>&1; then
        printf 'Loaded agent has no verifiable plist: %s\n' "$label" >&2
        exit 1
      fi
      continue
    fi
    owner=$(/usr/libexec/PlistBuddy -c 'Print :WorkingDirectory' "$plist")
    if [ "$owner" != "$repo_root" ]; then
      printf 'Agent belongs to another checkout: %s\n' "$label" >&2
      exit 1
    fi
    if launchctl print "$service" >/dev/null 2>&1; then
      launchctl bootout "$service"
    fi
    mv "$plist" "$retired/"
  done
)
```

Keep the checkout at its original absolute path during the transition.
Compose mounts that path alongside `/workspace`, preserving existing absolute
archive references; archives outside the checkout need matching explicit
mounts. Back up the ledger/archives first and verify mounts before resuming.
The new scheduler keeps its own state at `data/celerybeat-schedule`; retain any
old root-level `celerybeat-schedule*` files as backup rather than assuming native
and Linux dbm formats are interchangeable. Review due/recovered jobs at cutover;
a new scheduler clock can enqueue overlapping work, which the durable job
identities must deduplicate.
`launchctl bootout` can return before the registration disappears. Poll only
that exact label with a bounded timeout, then verify every recorded PID's start
time/ownership and absence; a completed bootout is not proof that all children
are gone. Suspended old-code processes must not be blindly resumed with
`SIGCONT`. Stop and investigate unexpected live identities rather than running
process-name kills or retrying teardown without checking its effects.
Use `make up`, `make stack-status`, and the Docker-side checks above afterward. The old
native targets now fail with this migration guidance; no agent is uninstalled
or service switched by an ordinary startup/test run.

<!-- wiki:repository-only:start -->
## Controlled cutover acceptance

**2026-11-03, approved controlled scope:** old checkout-owned API/Vite processes
and all four native launchd registrations/19 original worker identities were
retired after drain/backup. Native plist backups remain under the user's
LaunchAgents directory. Compose now owns API/UI, one concurrency-one
index/maintenance worker and the retained search/broker/Redis services.
Acquisition, analytics publication, Beat and automatic retention scheduling
remain disabled. This is not a full unattended-production release.

Before startup, offline broker/Redis volume snapshots and a complete
198,359-file data backup were made. All 99,044 archive SQLite databases and the
628,077-row job ledger passed backup integrity checks. No active/queued/retrying
jobs or broker messages required migration. Redis restored 41 streams with
zero pending deliveries. The three historical connection-refused ingest failures
remain failed and explicitly **acquisition deferred**; they were not relabeled,
requeued or hidden by the otherwise-healthy status.

Scoped acceptance includes five actual production API/worker/frontend image
and broker/restart tests, 93 isolated real-store pipeline/publication/recovery
cases (including an actual 8 MiB server-limit rejection), 593 configured Python
regressions, the focused documentation/deployment checks, 67 frontend tests,
42 mocked browser cases and two desktop/narrow checks against the actual managed
UI/API. The production frontend builds; its existing large-chunk warning remains
an optimization concern, not a failed build.

To repeat the opt-in voting check against an **already-running managed UI**,
run from `frontend/app`, using the expected member/version from its sealed
promotion plan and a new external evidence destination:

```bash
BROWSER_EXTERNAL_SERVER=1 BROWSER_BASE_URL=http://localhost:5173 \
GRAPH_VOTING_ACCEPTANCE_MEMBER=MEMBER_FROM_PROMOTION_PLAN \
GRAPH_VOTING_ACCEPTANCE_VERSION=VERSION_FROM_PROMOTION_PLAN \
PLAYWRIGHT_JSON_OUTPUT_NAME=/absolute/new/evidence/managed-browser.json \
npm run test:browser -- live-voting.spec.ts --reporter=list,json
```

`BROWSER_EXTERNAL_SERVER=1` suppresses the test-owned build/preview server;
the existing UI must already point at the intended API. `BROWSER_API_BASE_URL`
configures only the test-owned server, not a running Compose frontend. Default
mocked browser tests still build/use their isolated preview.

Backups, retirement receipts, sealed preservation checks and test/browser reports
persist in the operator's external `gate4-cutover-v1` evidence directory; they
are not repository data or portable backup locations. The source-repair and
voting-publication seals remain the authority for exact source/graph comparisons.
The retained cluster UUID, all 12,621 scoped source bodies/versions, all
1,148,223 original graph documents (with the intended promoted pointer), and
116,450 staged edge bodies/versions were reverified after the actual Compose
restart. Graph mappings, aliases and sibling pointers remain unchanged.
Elasticsearch indexing counters reset at restart; compare a new post-restart
baseline rather than interpreting zero as lost records or requiring the old
118,275 counter value. The new graph index baseline is zero indexes, failures
and deletes; exact sealed document comparisons, not that reset counter, prove
preservation. All six managed containers had zero OOM events/kills and restarts
at closeout. Initial Redis sizing failure occurred before this accepted runtime.

Remaining limits: collaboration/topic lineage/scope remain unknown, topic
publication is not certified, historical/freshness coverage is not globally
complete, and 3,047 legacy hydration rows still lack proof. Yellow replica health
does not certify durability. No full-load, Mac wake/engine-start, cloud cutover,
data pruning, commit/push or remote wiki publication is implied.

<!-- wiki:repository-only:end -->

## Recovery

<!-- wiki:repository-only:start -->
### Local readiness recovery in progress

The approved follow-through is local-only, retaining all source-supported
historical scopes and current freshness. See the ordered
[capacity/recovery/lineage/soak gates](IMPLEMENTATION_PLAN.md#local-readiness-follow-through).
Run `make stack-capacity` before expanding roles; the current VM cannot admit
the default acquisition or analytics expansion. Do not resize Docker, lower
search heap, delete backups or requeue the three uncapped historical failures
to bypass this result.

An exact, checksummed before-image census covers all 3,047 unproven legislation
rows. Bounded live retrieval exposed and fixed a shared member-name alias
round-trip failure; all eleven representative identities then retrieved valid
complete detail assessments. Initially twelve candidates passed isolated
acquisition staging under the actual operations-container limit, without serving
writes or failed-job status changes. The stage is not a full-history/freshness certificate,
and must pass projection comparison, preservation/conflict checks and conditional
write/rollback gates before serving repair.
The expanded stage stopped at 27 candidates on legitimate withdrawn/rejoined
co-sponsor history. The corrected producer now verifies the exact failure's
70 episodes/67 active and 111 subject rows, including one policy area. Preserve
the v1 archive for comparison; stricter v2 retrieval refetches all frozen
identities rather than declaring older count evidence newly certified.
V2 subsequently stopped at15 candidates on grouped related-bill counts.
S.J.Res.106 has two relationships to one bill, repeated intact across
page-size-one offsets. Count distinct nested links once, retain the separate
top-level record count, and refetch v3 proof; neither prior archive is silently
recertified. Missing relationship lists or contradictory metadata remain gates.

The isolated v3 acquisition checkpoint is
`data/local-readiness-hydration-v3/checkpoint.json`; it is not an application
ledger job. A stopped network attempt preserved 1,495 complete candidates;
an integrity-checked archive snapshot was retained before resuming the exact
failed bill. The staging runner now uses the existing `FailureClassifier` only
for request exceptions: at most three full-item attempts with 30/60-second
cooldowns, and at most six extra network retries across a process. These are
additional to the API client's existing bounded HTTP attempts. The same shared
rate limiter, request-token, memory, disk and archive limits still apply.
`retrying`, `retry_attempt`, `retry_after_seconds` and
`network_retries_this_process` make recovery visible in the checkpoint.
Validation/count/identity/storage failures stop without this retry path.
Exhaustion leaves a failed checkpoint and preserved archive, not success.
The exact Congress 94 S.12 retry passed, reaching 1,496 candidates with zero
serving writes. This is staging-only recovery, not a production client retry
policy change or proof of historical completeness.

The run later preserved 2,068 complete candidates before a full-text server
disconnect. Bill/amendment full-text retrieval now raises typed
`FullTextDownloadError`, retaining the original request exception as its cause.
Both normal job classification and isolated staging recognize only that typed
network boundary; 404/permanent failures, missing causes and unrelated runtime
errors do not gain retries. Staging retains the same three-attempt/six-extra-
retry caps, cooldowns and resource checks. Preserve the 2,068-candidate snapshot
and failed checkpoint before resuming the exact bill.

**2026-11-04 frozen-set completion:** acquisition and the independent archive
audit passed for all **3,047 identities**. All nine collection counts reconcile;
780 records contain nonblank full text. Preserve `audit-receipt.json` and
`audit-manifest.jsonl` beside the sealed archive. Detail proof is not a
certificate of full text or all historical/current source coverage.

The complete set then passed exact projection/merge and collection-count checks
in an owned unaliased shadow index, including stale-CAS rejection and conditional
rollback/reapplication. No implicit mapping expansion was needed. Drained
API/operations consumers loaded the current evidence schema before promotion.
A single-record API canary preceded the remaining repairs. All **3,047 serving
writes** now have fsynced intents/acknowledgements and exact content/version
readback. Seventeen real API cases across eleven Congresses passed. Original
source images, sealed projections, topology, rehearsal, canary and final receipts
are retained under `data/local-readiness-hydration-v3/repair-20261104/`.
Serving aliases/mappings and analysis-index state are unchanged. The acquisition
checkpoint still correctly reports zero serving writes: it records a separate
phase; `apply-complete.json` records the later live repair.

The three original Congress 94/95/117 failures remain failed, not requeued or
relabeled by this repair. Their recorded errors are connection refusal, with
10/10/9 attempts respectively. A subsequent read-only, fully paginated census
captured **64,426 canonical source identities** with 260 shared-limit request
tokens/pages. Independent hash/count checks found no canonical duplicates or
serving-only identities. There are **26,694 missing identities** and **35,573
existing rows without valid complete proof**. Congress 94 accounts for
16,979 missing/6,163 unproven, Congress 95 for 9,715/11,582, and Congress 117
for 0/17,828. Legacy root completeness labels do not establish versioned proof.
The sealed receipt and per-scope files are under
`data/local-readiness-hydration-v3/failed-scope-inventory/`. This is not an atomic
upstream snapshot or a fresh-detail certificate.

The first 500 sorted existing/unproven Congress 94 IDs have separately sealed
full before-images/sequence terms and authoritative upstream acquisition
metadata in `data/local-readiness-scope-recovery/congress-94-existing-0001/`.
The original sources lack acquisition URLs; do not overwrite or invent fields
to make them usable as metadata. The helper reuses the bounded serial staging
runner and tightens its token cap to 10,000. Initial memory preflight could not
retain the 256 MiB container reserve alongside the running consumer. The user
approved temporarily exchanging only the idle operations consumer for acquisition
in the same 1 GiB allocation, without adding roles or lowering guards.

The one-record exclusive smoke passed with ten request tokens and no retries:
`bill:94:hconres:1` has valid complete proof and independently reconciled collection
counts. All 500 original serving sources/versions remain unchanged. The original
consumer was restored automatically and responded through the broker; the app
remained available. `execution-smoke-20261104.json`, `acquisition-smoke-20261104.log`
and `smoke-verification.json` retain the actual outcome. Five supervisor tests
also cover failure/interruption restoration, false-success rejection and log
transport failure.

The full exclusive run subsequently completed **500/500** candidates, retrieving
the remaining 499 with 5,036 request tokens and no extra item-level network retries.
It exited without OOM and restored the original consumer automatically, with a
verified broker response. Independent archive integrity, exact-identity,
stored-name model and all nine collection-count checks passed for every record.
All 500 serving sources/versions remain unchanged; the app is responsive.
Keep `execution-acquisition-20261104.json`, `audit-receipt.json`,
`audit-manifest.jsonl` and `acquisition-preservation.json` beside the sealed
archive. None of these candidates has nonblank full text; never erase retained
GovInfo text because the staged Congress API representation lacks it.
Subsequent exact production-merge inventory found 484 committee count/URL
descriptors that would become invalid list entries, plus 16 empty slots. Guarded
shadow rehearsal expands only pure descriptors with the exact bill/collection
target and equal audited count, never discarding real committee data or unknown
extra fields. Empty slots become explicit empty lists. All 500 accepted candidates
pass exact readback, nine-collection reconciliation and idempotent ordinary
replay. Descriptor and empty cases both reject stale writes and pass conditional
rollback/reapplication. Eight focused guard tests and six existing repair tests
pass, with clean lint/types.

At that rehearsal checkpoint, all serving sources/versions, aliases/mappings and
protected analysis state were unchanged. Retain `merge-review-20261104/` and
`guarded-shadow-20261104/`, including
the sealed guarded receipt, projections and per-record pointer resolutions.
The owned unaliased shadow was retained for conditional-plan verification.

**2026-11-04 live repair completed:** a separate typed acceptance receipt seals
the guarded policy, implementation and all input evidence. The unchanged proven
CAS writer applied one canary, verified its actual API response, then applied the
remaining 499. All **500/500** writes have fsynced intents/acknowledgements and
exact source/version readback; all 500 distinct API detail responses match the
accepted identity, content, exposed collections and complete proof.

An initial unversioned API probe returned 404. Injecting the actual
`http://127.0.0.1:8000/api/v1` base URL corrected only the verifier configuration;
the acknowledged canary was not rewritten and sealed helper bytes were preserved.
The browser displays the canary's title, expanded committee and missing-text
state. The exact owned unaliased shadow was retired only after final API checks
and another complete serving readback. Keep `apply-complete.json`,
`api-canary.json`, `api-final.json` and `shadow-retired.json` alongside all original
evidence. The accepted receipt SHA is
`cc0bf5a8f3dfbb8902fc3bf25d63d28cf520891a81995d91ad3e1d47f494310d`;
the final API receipt SHA is
`790ef5ef75b6900d3f6c02ca76aba01e533a6442ae25540e5302d865ef02e03c`.

Serving aliases/mappings and protected analysis state remain unchanged. Health,
API/frontend readiness and the original operations consumer pass; existing
analytics-lineage warnings and three actionable failed jobs remain visible.
The acquisition checkpoint remains staging-only; separate repair receipts prove
the 500 serving changes. Default application merging is unchanged, and this
bounded repair does not close an original failed scope or certify all history.

**2026-11-04 continuation test gate passed:** the complete normal Python suite
passes 966 cases, with 144 upstream/integration cases intentionally gated.
Frontend tests pass 67 cases; isolated browser fixtures pass 42 with two opt-in
live-voting checks skipped. CI run `41837406434` succeeds, including isolated
pipeline/publication failure checks. No failing repository test was reproduced.
Failed durable ingestion rows are operational evidence, not automated test
failures.

The next 500-record batch is sealed in
`data/local-readiness-scope-recovery/congress-94-existing-0002/`. Its manifest SHA
is `18743231295bd848ce363c00946283a4e284b72fd137c4581de7674f4d69cabd`.
Selection first verifies the previous repair/API/retirement seals and reads back
all 500 acknowledged source versions, then excludes exactly those identities.
The derived remaining Congress 94 roster has 5,663 identities; this is not a
fresh global census. Every newly selected row must still match its original
source/version and lack complete proof. The batch is disjoint from its
predecessor.

The new one-record exclusive smoke stages `bill:94:hconres:55` with ten request
tokens, zero extra network retries, no OOM and no serving writes. The original
consumer is restored and broker-verified. Independent SQLite integrity,
stored-name model and nine-collection count checks pass; all 500 serving
originals/versions remain unchanged. Keep the execution receipt, acquisition log
and `smoke-verification.json`, plus
`selection-congress-94-existing-0002/continuation-receipt.json`. Twenty-six
continuation/acquisition/supervisor tests and lint/types pass. The remaining 499
subsequently completed acquisition with 5,071 request tokens, no extra network
retries and no OOM; the original consumer was restored and broker-verified.

**2026-11-04 second chunk repair complete:** all 500 archived identities and
nine collection counts pass independent audit. Archive SHA is
`3d3aaa5fcaf5e191290463f0c6e64b825fbc435cbf6c5d8e9937d8151fcb95b3`.
Two sparse originals (`bill:94:hjres:1022`, `bill:94:hjres:148`) omit text and
audited-empty collection fields. Separate control probes now respect existing
model/API presence semantics without adding fields to those sources, changing
the default merge policy or modifying earlier sealed implementations.
Forty-one control/CAS cases, lint and types pass; missing nonempty collections
and explicit invalid text still reject.

The new owned shadow passed all 500 exact/count/idempotency checks and two
stale-CAS/rollback probes. The real API canary and remaining 499 conditional
writes passed, with fsynced intent/acknowledgement journals, exact source/version
readback and all 500 distinct actual API checks. Accepted receipt SHA is
`5aa0bfa158fd8269ef84f2c54d48174a57d09ffb8a0d882fdc45f23dee195d6d`;
final API receipt SHA is
`f3f2bbb581a16d1193a19bffe1696c31773289fb1f8dbbd2941640a3747a6471`.
The exact owned unaliased shadow was retired only after final verification.
Serving mappings/aliases, protected analysis and original failed jobs remain
unchanged. Retain all audit, review, guarded plan, journal, API and retirement
evidence in the batch directory.

The third disjoint batch is sealed in
`data/local-readiness-scope-recovery/congress-94-existing-0003/`, with manifest
SHA `9066957f7ba466edcbb15bb1756d8096c2a216e9194217888afb19ee82fd1ff0`.
Its derived remaining roster contains 5,163 identities, not a fresh census.
The one-record exclusive smoke for `bill:94:hjres:181` passes independent archive,
model and nine-collection checks and restores the consumer. All 500 new serving
originals remain unchanged and disjoint from the 1,000 prior chunk repairs.
This proof-driven continuation was superseded by the user's existence-first
criterion. Its acquisition was deliberately interrupted at 459 archived bills;
SQLite integrity is `ok`, the original consumer is restored and broker-verified,
the owned helper is removed and no serving writes occurred. Preserve the staged
data; do not automatically resume or promote it. The execution receipt's failed
state records intentional interruption, not OOM or a completed acquisition.

The replacement read-only reconciliation scanned 344,672 serving root documents,
24 physical user indices, 176 central archives and 59 bill-list caches. Of the
64,426 captured identities, 37,732 already exist in serving and must be skipped.
The remaining 26,694 are absent from indexed document/source IDs but have local
list metadata: 16,979 in Congress 94 and 9,715 in Congress 95; Congress 117 has no
identity gap. All 32,378 scoped archived bill identities are already indexed.
The GovInfo XML downloads are for Congress 119, not these gaps. Evidence is under
`data/local-readiness-presence-20261104/`; no upstream requests or serving writes
were made. Prepare local-only replay of missing identities, separately deciding
metadata versus full-detail output. Proof-only backlog counts are not ingestion
requirements.

**Local-only replay is now complete:** 26,694 metadata projections passed an
owned unaliased shadow, including a real richer-source conflict-preservation
probe. A live API canary preceded the remaining creates. Every live source and
acknowledged version matches its projection, all 37,732 pre-existing versions
remain unchanged, and a fresh comparison finds all 64,426 captured identities
present: 24,285 in Congress 94, 22,313 in Congress 95 and 17,828 in Congress 117.
Twenty final API cases pass with honest unknown detail evidence. No upstream
requests, new workers, additional Docker allocation, source requeues or changes
to serving mappings/aliases and protected analysis were required.

Retain `data/local-readiness-local-replay-20261104/`, including its sealed
ten-group plan, source projections, original versions, fsynced create intents and
acknowledgements, shadow/API acceptance, `complete.json` and `retired.json`.
The final receipt SHA is
`e417addf0e14b7633b2c9cca470263a8b0612a262e519759255d348b518fa141`.
The exact owned shadow was retired after full live readback. Offline projection
took 55.75 seconds and the bulk continuation 7.38 seconds; these local timings
are not the outstanding sustained-operation acceptance. Missing full details
and text are not certified complete, and original failed hydration jobs remain
historical failures rather than being relabeled by metadata replay.

**Subsequent local-content enrichment:** the 459 complete archived bills retained
from the deliberately interrupted third acquisition have now passed independent
nine-collection audit, pointer-aware shadow rehearsal and conditional serving
promotion. A real API canary preceded the remaining writes; all 459 actual API
responses and exact stored source/versions passed. This restores 500 committee
rows and the archived subject evidence without new acquisition. The other 41
original source/version images are unchanged. The exact owned shadow was
retired; preserve `data/local-readiness-local-enrichment-20261104/`, including
the frozen inputs, projection, fsynced journals and final API/retirement receipts.
Original acquisition failure history remains unchanged.

**Historical law-text staging:** four official Statutes XML volumes are sealed
under `data/local-readiness-statutes-20261104/`. Use the final `verified/`
evidence, not its preliminary report: 573 of 645 indexed references have
independently matched law identity, PDF citation and XML bill reference.
Another 68 conflict and four lack an accepted match; seven XML components
are explicitly quarantined. No Congress API requests or serving text writes
were performed. These are enacted-law texts, not proof of available earlier bill
drafts. The next serving gate must retain this distinction and source provenance.

**Subsequent verified law-text publication:** all 573 final candidates are now
indexed and available through the real API, with explicit enacted-law version
codes and UI labels. An owned-shadow rehearsal included stale-write and exact
rollback probes; the live API/browser canary preceded 572 remaining conditional
writes. Final exact source/version and API checks passed for all 573; 560
noncandidate source/version sentinels remained exact. Detail/hydration/analysis,
serving mappings/aliases and original failed-job history were preserved. No
upstream requests, extra workers or expanded allocation were used. Only the exact
owned unaliased shadow was retired after final verification.

Retain `data/local-readiness-statute-publication-20261104/` for the fresh
before-images, expected projections, input/controller seals, fsynced intent/ack
journals, final API verification and retirement receipt. Its run-seal SHA is
`dcbab36e7b56e0bfac19efa871c5250cc5a4c69d9f405ba6c7b91e2799b5a88a`.
Do not replay writes when any intent exists: reconcile ambiguous acknowledgements
and current versions explicitly. At that checkpoint, the 72 unresolved
references remained untouched; the original 645 references were not a complete
available-law catalog.

**Subsequent catalog closure:** all 72 references are now independently
recovered, together with another 887 enacted laws discovered through four
volume-level MODS catalogs. The 959 additional texts comprise 807 XML, 148
publisher PDF text-layer and four complete on-device facsimile OCR recoveries.
Adjacent laws are excluded from shared-page PDFs. Exact retained Congress law
actions corroborate damaged printed primary-bill numbers; Public Law 94-284
uses an independent official Code citation to retain complete XML at page 503
while marking the conflicting page-508 PDF as partial.

Fresh projection, owned-shadow stale-write/rollback rehearsal, live browser/API
canary and conditional writes passed. All 959 new and 573 previous laws passed
exact source/version and actual API checks: **1,532 scoped enacted laws**.
All **1,061** preserved sentinel source/versions passed, including the previous
573. Browser/API equality was checked for the canary, every complete OCR
recovery and the partial-PDF case. The exact owned shadow was retired.
Details/hydration/analysis, mappings/aliases, failed jobs and the original 1 GiB
operations worker are unchanged. No Congress API acquisition was used.

Retain `data/local-readiness-law-closure-20261104/` for the catalog, XML/PDF
inputs, Code witness, OCR sidecars/images and staged text, and
`data/local-readiness-law-closure-publication-20261104/` for the fresh plan,
fsynced journals and final/catalog/retirement receipts. Its publication seal SHA
is `aec93a6e8a0b7688d5e5e6d9369354697a31b0c9e3af1bbe95904273fbc9e1f6`.
Retain the independent on-device OCR programs in the session evidence; their
hashes are sealed. These operator controllers are not automatic worker jobs.
Do not replay acknowledged writes or discard the original XML rejection
diagnostics: independently recovered text does not repair the publisher's XML.
Three older catalog reprints are outside scope. This closes the retained
Congress 94/95 enacted-law catalog, not earlier drafts or full bill details.

The requested 24-hour/5-requests-per-second acceptance has **not** run. A single
Mac cannot provide independent-host failover; its on-host backups do not prove
off-host disaster recovery. Keep these limitations visible rather than converting
a smoke test or local restart into a production acceptance result.

<!-- wiki:repository-only:end -->

### Exclusive staging within existing capacity

Declared stack capacity does not establish spare memory inside a running worker.
For an explicitly approved external, staging-only recovery experiment, an idle
operations consumer can temporarily yield its allocation to a bounded acquisition
process. This is an operator procedure, not an additional default profile or a
packaged application job.

- Verify the exact consumer is responsive and has no active, reserved or scheduled
  tasks. Obtain approval for the index/maintenance consumption gap; queued work
  waits while existing-data reads remain available.
- Seal acquisition identities, metadata, originals and implementation hashes
  first. Pin the existing image and retain its original command, queues and
  memory allocation. Check host capacity and disk before pausing the consumer.
- Stop that consumer before starting the isolated process. Never overlap both
  allocations, start dependencies implicitly or bypass request, memory, disk,
  archive, completeness or identity guards.
- Keep acquisition checkpoints separate from the durable application ledger.
  Staged data must not change serving sources, failed jobs, aliases or analytics
  pointers. Archive audit and preservation-aware conditional repair remain
  separate gates.
- On completion, failure or a handled interruption, stop the owned acquisition
  container before restoring the original consumer. Retain logs and exit/OOM
  evidence, and verify the restored consumer responds through the broker.
- A host outage or unhandled process kill can prevent automatic cleanup. Inspect
  both containers before manual recovery; confirm acquisition is stopped before
  starting the operations consumer. Do not run normal stack startup concurrently
  with an exclusive recovery window.

This pause-and-stage procedure is not a continuous ingestion/indexing or
high-availability acceptance result.

Before requeueing exhausted jobs, create a timestamped ledger backup:

```sh
backup="data/jobs.sqlite3.pre-recovery-$(date -u +%Y%m%dT%H%M%SZ)"
docker compose -f docker-compose.fullstack.yml exec -T backend \
  python - data/jobs.sqlite3 "$backup" <<'PY'
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

source, target = (Path(argument).resolve() for argument in sys.argv[1:])
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

The ledger uses WAL: copying only its main file while it is live can omit
committed rows. The backup API includes committed WAL contents in a consistent
standalone snapshot. For a coordinated ledger **and** archive backup, pause all
writers and keep their original paths/layout; independently consistent SQLite
files are not automatically an atomic cross-store snapshot. Preserve each
archive's `records.sqlite3` with the same backup API. This is not a replacement
for Elasticsearch index/alias/model-artifact backups.

Run the online backup in the existing container, not through a native connection
to its live WAL file. The resulting closed snapshot may be inspected offline.

Use the recovery task for stale worker messages and transient failures. It is
single-flight and rate-limited; do not bulk requeue vendor 4xx, malformed XML,
validation, disk-I/O, or expected non-indexed failures.

Check only the relevant job identities through bounded Docker-side reads.
Do not invoke the native full-ledger status/health scripts while Docker writers
are active.

For acknowledged Redis streams, replay from the durable `records.sqlite3`
archive or re-ingest the source package. Do not blindly redispatch an index job
whose stream entries have already been acknowledged.

## Rollback

Rollback is a maintenance operation:

1. Stop workers, Beat, and API/admin writers; close all SQLite connections.
   Use `make down` for the managed stack; stop any old native/foreground writers
   explicitly as described above before restoring.
2. Preserve the current ledger, WAL/SHM sidecars, and archives; record the reason.
3. Verify the intended backup with `PRAGMA integrity_check`.
4. Restore the backup only after the verification succeeds.
5. Start services and run the health check.
6. Confirm queue state and OpenSearch aliases before resuming work.

Example ledger restoration after services are stopped and the backup is verified:

```sh
(
  set -e
  before="data/pre-restore-$(date -u +%Y%m%dT%H%M%SZ)"
  mkdir "$before"
  for path in data/jobs.sqlite3 data/jobs.sqlite3-wal data/jobs.sqlite3-shm; do
    if [ -e "$path" ]; then mv "$path" "$before/"; fi
  done
  cp -p data/jobs.sqlite3.pre-recovery-TIMESTAMP data/jobs.sqlite3
)
```

Do not restore over an open database or leave the previous database's sidecars
beside a restored snapshot. Restore matching archives to the paths recorded in
job payloads; do not silently point restored jobs at newer/unrelated archives.

Never delete corrupt GovInfo manifests or source archives during cleanup.
Manifest recovery quarantines corrupt files using a `.corrupt-*` suffix so the
original artifact remains available for investigation.

## Production Cutover Gate

Do not move the legislation read/write aliases until:

- the target index has complete, verified multi-Congress coverage;
- all remaining failures have a documented disposition;
- SQLite integrity and dependency health are clean;
- no queue backlog or active recovery sweep remains; and
- representative reads and writes have been tested against the target index.

## Source Contract Preview and Staging

Start with read-only evidence, never a live corpus rewrite:

```sh
uv run --frozen python scripts/reconcile_govinfo_bulk.py \
  --archive-root data/full_history/govinfo \
  --target-index congress-legislation-read --max-records 100 \
  --report-path /tmp/congress-source-preview.json
```

This inventories the target and reads at most 100 combined parent/text payloads.
It neither submits a job nor indexes documents. If search is intentionally
unavailable, use `--archives-only` **instead of** `--target-index`; the report
explicitly lacks alias/mapping evidence. It is not a successful serving inventory.
Keep reports outside source package directories.

Only after reviewing source conflicts, quarantine, field authority, counts and
coverage gaps may an operator explicitly request an existing, unaliased physical
staging target:

```sh
uv run --frozen python scripts/reconcile_govinfo_bulk.py \
  --archive-root data/full_history/govinfo \
  --target-index congress-source-shadow --write-staging \
  --report-path /tmp/congress-source-staging.json
```

This submits durable work scanning the selected archive root without a preview
limit; it is not read-only. `--max-records` cannot accompany `--write-staging`.
The helper rechecks physical target/alias safety before writes. Do not select
live indices, start old workers, or assume this command creates mappings.
No automatic cutover is provided.

`completed` means the selected replay finished, not that upstream discovery,
hydration or indexing is globally complete. Reports deliberately retain partial
source coverage and `promotable=false`. Unknown support/count/freshness evidence
must remain explicit. Required scope is every implemented resource across
source-supported history; daily current-Congress checks and the 24-hour freshness
target are acceptance requirements, not newly certified scheduler behavior.
See the [source semantics](guides/ingestion.md#govinfo-replay-and-reconciliation).

### Sealed Graph Repair Rehearsal

This command family is tooling/isolated validation only. Use the worker-capable
Python environment from the repository root. Confirm the recorded worker hold
and serving index/delete/failure counters before and after read-only capture.
Never use the ordinary graph-build command for this procedure; it publishes.

```bash
# New directories only; never reuse an incomplete or successful output directory.
uv run python scripts/stage_graph_repair.py capture --bundle /absolute/new/bundle
uv run python scripts/stage_graph_repair.py verify --bundle /absolute/new/bundle

# Supply an explicitly provisioned disposable cluster, NOT the serving endpoint.
uv run python scripts/stage_graph_repair.py rehearse \
  --bundle /absolute/new/bundle --output /absolute/new/rehearsal \
  --staging-url http://127.0.0.1:19397
```

Capture performs only search-store reads and local file writes; it does not
download CSVs, add mappings or publish pointers. A cluster UUID check rejects
the serving cluster even if supplied through a different URL. Rehearsal creates
and deletes only nonce-owned scratch indices on the different cluster, with
one primary shard and no replicas. It never accepts arbitrary restore targets.
The caller owns provisioning/stopping that disposable cluster; live search is
not stopped by these commands.

| Artifact | Contract |
| --- | --- |
| `manifest.json` | Final capture completion marker, typed config/counts, timestamp and SHA-256/size seals. |
| `state.json` | Source cluster UUID, physical mappings/settings/aliases and raw per-signal pointer images. |
| `source.jsonl` | Complete captured configured scope, with IDs, source, sequence numbers and primary terms. |
| Six CSVs | Frozen Congress 114 House/Senate members, roll calls and positions; no network refresh. |
| `repairs.jsonl`, `diffs.jsonl` | Exact candidate sources and reviewed before/after fields; unrelated metadata preserved. |
| `candidate-edges.jsonl`, `candidate-pointer.json` | Exported stage-only graph, sealed by the acceptance report. |
| `acceptance.json` | Written only after successful candidate checks, exact isolated rollback and scratch cleanup; binds the input manifest seal. |

Failed captures/rehearsals may retain partial local files but have no success
marker. Do not delete their contents indiscriminately or treat candidate files
alone as acceptance. Missing, changed, unexpected or symlinked bundle artifacts
fail verification. Checksums detect corruption/drift, not authorization or
signatures. Preserve bundles/reports locally rather than committing corpus data.

The full retained-input rehearsal passed with 12,621 source records, 1,824
Congress 114 repairs and 116,450 voting edges over Congresses 113-119; 48,655
edges carry searchable Congress 114 evidence. Original cloned source bodies
and all raw pointers were restored; owned scratch indices were removed.
Serving write counters stayed zero and all 19 original processes remained held.
This does not certify replica durability, current upstream freshness or a live
restore. Before any separately approved live repair, revalidate captured
document versions, aliases, pointers, backups and resource budgets.
Additive mapping fields cannot simply be removed for rollback.
<!-- wiki:repository-only:start -->
Follow the [ordered rollout](IMPLEMENTATION_PLAN.md#ordered-graph-repair-rollout).
<!-- wiki:repository-only:end -->

### Bounded Live Schema and Source Repair

This is a separately approved operation, not part of the staging command.
The [source-repair CLI](../scripts/repair_graph_sources.py) exposes only
`prepare`, `apply` and `rollback`; it cannot publish graph pointers.

```bash
# New evidence directory: full physical graph backup and different-cluster restore proof.
uv run python scripts/repair_graph_sources.py prepare \
  --bundle /absolute/sealed/bundle --rehearsal /absolute/accepted/rehearsal \
  --evidence /absolute/new/live-evidence --staging-url http://127.0.0.1:19397

# Only after explicit gate-two approval and worker/budget/precondition revalidation.
uv run python scripts/repair_graph_sources.py apply \
  --bundle /absolute/sealed/bundle --evidence /absolute/new/live-evidence

# Separate source rollback decision; additive mapping fields remain installed.
uv run python scripts/repair_graph_sources.py rollback \
  --bundle /absolute/sealed/bundle --evidence /absolute/new/live-evidence
```

`prepare` is read-only on serving Elasticsearch. It verifies the accepted
candidate seals and CSV derivation, exact source versions, cluster/topology/
pointer identity and exactly eight missing mapping paths. It streams the
**entire physical graph index**, including historical versions, to
`graph-before.jsonl` (default bound: 2,000,000 records), then restores and verifies
every raw source/ID/count on a fresh owned index on a different cluster. Bounded
real-time multi-get batches avoid loading the complete graph into memory.
Only successful restore and cleanup produce `repair-plan.json`.

`apply` revalidates the input/backup seals, every graph before-image/version,
the complete scoped source corpus, health and topology before any write.
It creates exclusive `repair-started.json`, adds only the approved mapping
properties, then replaces approved existing source IDs with sequence/primary-term
preconditions. Each acknowledged write is flushed/fsynced to
`repair-receipts.jsonl`. Any rejection or uncertain response stops the operation;
there is no success-shaped partial completion or automatic retry.
`repair-applied.json` appears only after exact whole-scope source verification,
unchanged unrelated versions, unchanged graph sources/versions/pointers and
the expected receipt identity set pass.

`rollback` restores only receipted source writes using exact body/version checks
and CAS. Its own fsynced `rollback-receipts.jsonl` allows an interrupted,
acknowledged rollback to resume under an advisory file lock. A lost response,
truncated journal, unknown write, changed pointer or concurrent source version
fails closed: inspect and explicitly reconcile rather than guessing ownership.
No live mapping is deleted, no index recreated and no alias changed. Mapping
rollback requires a separately approved reconstructed/restored-index cutover;
the isolated restore proves raw source/schema reconstruction, not replica,
alias-cutover or power-loss durability. Yellow health with available primaries
does not certify replica protection.

<!-- wiki:repository-only:start -->
On 2026-11-03 UTC, approved gate two completed: all 1,148,223 historical graph
documents were backed up and restore-tested, the eight mapping paths were
added, and exactly 1,824 Congress 114 sources were repaired (1,322 House/502
Senate). All 12,621 scoped bodies match the approved result and the other 10,797
source versions are unchanged. Full graph body/version verification passed;
graph document writes, pointer changes, alias changes, index failures and deletes
were zero. Total application index operations were exactly 1,824. The successful
`repair-applied.json` binds the sealed plan and all per-write receipts.
At gate-two closeout, original pointers were unchanged; voting publication followed at gate three.
No live source rollback, index recreation, worker restart, commit or push occurred.

<!-- wiki:repository-only:end -->

### Sealed Voting-Only Graph Promotion

The [promotion CLI](../scripts/promote_voting_graph.py) is distinct from ordinary
graph builds. Its `stage`, `accept`, `publish` and `rollback` operations are
restricted to the gate-one voting candidate and the successfully applied
gate-two source repair. Keep the worker hold in effect throughout.

```bash
# New directory; installs create-only edges but does not publish a pointer.
uv run python scripts/promote_voting_graph.py stage \
  --bundle /absolute/sealed/bundle --repair-evidence /absolute/live-evidence \
  --candidate /absolute/accepted/rehearsal --output /absolute/new/promotion

# After real read-only shadow API/browser acceptance, seal its measured report.
uv run python scripts/promote_voting_graph.py accept \
  --bundle /absolute/sealed/bundle --repair-evidence /absolute/live-evidence \
  --output /absolute/new/promotion \
  --browser-report /absolute/new/promotion/browser-before.json

# Revalidates source versions, history, candidate receipts and serving evidence.
uv run python scripts/promote_voting_graph.py publish \
  --bundle /absolute/sealed/bundle --repair-evidence /absolute/live-evidence \
  --output /absolute/new/promotion

# Separate rollback decision: restores the raw old voting pointer, not sources.
uv run python scripts/promote_voting_graph.py rollback \
  --bundle /absolute/sealed/bundle --repair-evidence /absolute/live-evidence \
  --output /absolute/new/promotion
```

`stage` verifies frozen CSV derivation, exact acknowledged repaired-source
versions, original pointer/topology identity, accepted candidate seals and the
complete historical graph. It validates every voting edge before writing:
unique computed IDs, distinct endpoints, finite bounded scores, vote-count
consistency and full Congress scope. A version collision is rejected.
Create-only bulk actions prevent overwriting existing IDs. After refresh, every
candidate body/version is captured in `voting-staged-documents.jsonl`; complete
history/source preservation and exact searchable nested Congress counts must
pass before `voting-staged.json` is written. A partial failure leaves an
unpublished orphan and exclusive evidence, never a success marker. Do not retry
blindly or delete it without separately reviewing identity/ownership.

Before publication, serve the real API against those physical edges using a
read-only, voting-pointer-pinned container; other signals retain their original
pointers. Do not mock members, edges or analysis statuses. In `frontend/app`,
run the opt-in `live-voting.spec.ts` against an unused local API/preview port:

```bash
BROWSER_BASE_URL=http://127.0.0.1:4176 \
BROWSER_API_BASE_URL=http://127.0.0.1:18400 \
GRAPH_VOTING_ACCEPTANCE_MEMBER=MEMBER_FROM_PROMOTION_PLAN \
GRAPH_VOTING_ACCEPTANCE_VERSION=VERSION_FROM_PROMOTION_PLAN \
PLAYWRIGHT_JSON_OUTPUT_NAME=/absolute/new/promotion/browser-before.json \
npm run test:browser -- live-voting.spec.ts --reporter=list,json
```

The test selects Congress 114 through the UI and requires the exact graph
version, available voting analysis, a rendered canvas, finite scores, positive
voting links and no browser errors at desktop 1280x900 and narrow 320x740.
`accept` parses the actual Playwright report and its embedded API response for
both viewports; failed/skipped/retried/missing/wrong-version results cannot
be accepted. Its report seal is bound to the exact staged graph. This is
observed serving acceptance, not corpus freshness or global completeness.

`publish` uses the original raw voting pointer's sequence/primary-term CAS,
not the ordinary unconditional publication method. It saves the acknowledged
new pointer and then rechecks all historical bodies/versions, candidate receipts,
source versions, sibling pointers and aliases before `voting-promoted.json`.
An interrupted/lost response never establishes rollback ownership. Intent and
receipt files are exclusive and fsynced; failures require explicit reconciliation,
not automatic retry. `rollback` requires the acknowledged promoted pointer and
CAS-restores the exact original raw source. Both old and candidate edges remain;
there is no pruning, source rollback, alias cutover or worker restart.
Repeat the real API/browser check without pointer pinning after publication.

<!-- wiki:repository-only:start -->
On 2026-11-03 UTC, approved voting promotion completed. The new version is
`20261103T091601Z-4b9d26b3167844a790a5f1aded61143f`: **116,450 edges** over
Congresses **113-119**, including **48,655** with searchable Congress 114 evidence.
All **1,148,223** original physical graph documents were checked; historical
edge bodies/versions and sibling pointers are unchanged, with only the exact
voting pointer replacement permitted. All 12,621 repaired/unaffected source
bodies and versions still match gate-two receipts. The physical graph count
is **1,264,673**. Real API/desktop/narrow checks passed before and after
publication, and topic analysis remains explicitly unknown.

The measured gate-three write delta is **116,451 successful indexes**
(116,450 new edges plus one voting pointer), **zero failures and zero deletes**;
cumulative application counters including source repair are **118,275/0/0**.
No live rollback, pruning, alias changes, worker restart or additional signal
publication occurred. Preserve the staged document receipts, measured browser
reports, raw pointer receipt and `voting-promoted.json` outside the repository.

### Temporary Live-Inventory Hold

Graph preflight blocks writes/publication on incompatible mappings. Gate two
installed the eight missing paths, including `shared_topics`, and repaired the
1,824 unlinked Congress 114 sources after numeric ICPSR normalization.
Approved voting publication records Congress 113-119 scope. Unchanged
collaboration/topic pointers still lack recorded Congress scope; the topic
pointer also lacks verified model lineage. Mapping compatibility/source repair
alone does not publish a graph. Empty sponsorship/vote-position bridges are unused
by current builders and do not justify a backfill.
See [graph rollout gates](guides/analytics.md#schema-and-source-coverage-gates).

Hydration hardening is implemented and tested, **not deployed by resuming these
workers**. Legacy root labels are not versioned proof; the updated bill read
boundary reports them unknown. Of 151,993 unlabeled records, 148,946 carry
BILLSTATUS provenance and 3,047 have no source-metadata provenance. All 3,047
have URL pointers, but none have mapped reference IDs/source-update timestamps.
Twenty bounded samples had no matching bill identity in their read-only retained
Congress library archives; this does not establish absence from all recovery
sources or describe every record's richness. Do not blanket-fill labels, erase
records or queue mass hydration. Assess supported historical scope and recover
evidence before an explicitly approved bounded repair.
See [hydration semantics](guides/ingestion.md#bill-hydration-evidence).

On 2026-11-03 UTC, the operator approved suspending all four legacy worker/Beat
service trees (19 processes) before starting only the existing `es-local-dev`
container with its retained Elasticsearch data volume. Search is online;
workers and Beat remain suspended for review. No registrations were removed,
restart policy changed or aliases moved. At that initial inventory no mappings
or documents were changed; the separately approved gate-two changes above are
the only subsequent live repair. The original inventory found all 21 declared families, seven missing graph field
paths, empty sponsorship/vote-position bridges and uncertified hydration/freshness
coverage. See [R03 evidence](IMPLEMENTATION_PLAN.md#r03).

This SIGSTOP hold is temporary, not a native-service retirement or a durable
maintenance mode. Logout, reboot or supervision changes can replace processes.
The session suspension report records service roots, exact PIDs, start times
and whether this operation suspended each process. Do not send SIGCONT to stale
PIDs, resume workers or switch managed stacks without explicit approval.
Long holds can expire broker connections/heartbeats; inspect durable jobs,
leases and queues before deciding how to resume or recover.
Paused workers may also have older application code loaded; resuming them does
not reload the recent changes. Prefer an explicitly approved managed restart.
Use the [preserved-registration migration](#retiring-native-agents) for an
approved permanent transition, not automatic cleanup of these paused services.

The existing search container has `restart=no`, unlike the revised Compose
specification. It was started without recreation or policy changes; do not assume
it will restart with Docker. Yellow cluster health also does not establish
replica availability or a production recovery certificate.

<!-- wiki:repository-only:end -->

## Controlled Pipeline Acceptance

The [contracts workflow](../.github/workflows/contracts.yml) runs explicitly
selected synthetic suites against disposable Elasticsearch 9.3.1 and Redis 7.
It does not run the broader integration directory, which includes upstream API
tests. Never point these suites at production or an existing source-data cluster.
The query-budget fixture requires an empty cluster and creates canonical aliases;
the other fixtures own UUID-prefixed indexes, streams, and an ingest pipeline.
SQLite ledgers/archives live in pytest temporary directories. Cleanup removes only
fixture-owned service objects, not source records or other Redis keys.

For local reproduction, choose unused loopback ports and unique container names.
These example names must refer only to services you create for this test:

```sh
docker run -d --name congress-acceptance-es --cpus=1 --memory=1536m \
  -p 127.0.0.1:19393:9200 \
  -e discovery.type=single-node -e xpack.security.enabled=false \
  -e xpack.ml.enabled=false -e http.max_content_length=8mb \
  -e 'ES_JAVA_OPTS=-Xms512m -Xmx512m' \
  docker.elastic.co/elasticsearch/elasticsearch:9.3.1
docker run -d --name congress-acceptance-redis --cpus=0.5 --memory=192m \
  -p 127.0.0.1:16393:6379 redis:7-alpine \
  redis-server --save '' --appendonly no --maxmemory 96mb \
  --maxmemory-policy noeviction
curl --retry 30 --retry-all-errors --retry-delay 2 --max-time 10 --fail \
  'http://127.0.0.1:19393/_cluster/health?wait_for_status=yellow&timeout=5s'
docker exec congress-acceptance-redis redis-cli ping
```

Run only the safe selectors below. The HTTP limit and
`PERSPECTIVE_PUBLICATION_TEST_MAX_BYTES` must match: 8 MiB / 8,388,608 bytes.
Do not export a global integration opt-in and then run all integration tests.

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

After testing, stop/remove only your disposable containers and their volumes:

```sh
docker stop congress-acceptance-es congress-acceptance-redis
docker rm -v congress-acceptance-es congress-acceptance-redis
```

### Recovery Ownership

These are distinct responsibilities, not five interchangeable retry systems.

| State/boundary | Owner and action | Guard/evidence |
| --- | --- | --- |
| Broker delivery/worker loss | Celery late acknowledgement/redelivery; `JobStore.mark_running` claims the durable job. | Duplicate terminal/active claims skip. Redelivery is not evidence that a source task completed. |
| Raised task failure | `TaskRetrier` records the failure; `FailureClassifier` schedules only transient retries. | A permanent bulk rejection leaves every contributing owner failed, its stream entries unacknowledged, and the archive intact. |
| Silent RUNNING/RETRYING row | `JobRecoveryService` checks stale heartbeats and worker liveness under one Redis lock, then requeues/dispatches. | Live jobs are touched, analytics attempts are bounded; terminal failed analytics are not automatically restarted. |
| Orphan QUEUED row | The same recovery sweep redispatches stale jobs. | Separate ingest age, bounded batches, index queue-depth watermarks, and active GovInfo batch ownership prevent indiscriminate resubmission. |
| Redis pending entry | `RedisRecordStream` reclaims abandoned entries with `XAUTOCLAIM`; `StreamIndexer` retries the whole failed buffer. | A single shared `bulk_upsert` boundary raises on any item rejection before acknowledgement. Successful writes may be replayed idempotently. |
| Missing/trimmed stream body | `IndexJobRunner` invokes `ArchiveReplayer` when stream count is insufficient and pending count is zero. | The archive replay count must independently satisfy the expected snapshot count; stream and replay counts cannot be added because they may overlap. |
| Permanent rejected source | The existing FAILED ledger row and retained pending entries/archive are the disposition. | Error text includes all returned rejected IDs/index/status/reasons. Correct the cause and explicitly requeue; no new quarantine database, acknowledgement, source deletion or automatic retry is introduced. |

`bulk_upsert` now raises for partial failure instead of returning `errors=True`.
Successful return dictionaries retain their previous fields. Every production
caller uses the same boundary, so graph publication, Voteview counts, archive
completion and reconciliation reporting cannot accidentally ignore rejection.
This does not make a multi-item bulk atomic: successful items remain written,
and replay converges without treating that partial success as batch completion.

### Manual Serving Repair Safety

For presence-based historical recovery, first follow
[existence-first reconciliation](guides/ingestion.md#reconcile-existing-data-before-historical-acquisition).
Missing modern completeness evidence alone does not authorize re-downloading or
repairing an existing bill. The procedure below is for separately approved
changes to existing fields, not routine replay of already indexed identities.

Ordinary bill `bulk_upsert` uses additive merging with conflict retries; it is
not a version-conditional repair boundary. Never replay a staged candidate over
serving data with unconditional replacement.

For an explicitly approved bounded repair, retain checksummed original sources
and their sequence/primary terms, audit archive identities and versioned proof,
then compare real projections in an owned unaliased shadow index. Confirm
mapping compatibility, field preservation, stale-version rejection and
conditional rollback before changing serving rows. Refresh drained consumers
when the evidence schema has changed, then verify a live API canary.

A legacy count/URL descriptor is not a collection record. Ordinary additive
merging can mix it into an expanded record list; such a mixture must not be
certified complete. In an explicitly bounded repair, expand only a pure
descriptor whose bill/collection URL and count agree with a fully audited fresh
list, retaining the original descriptor in the sealed before-image. Extra fields,
real collection records, changed targets or count disagreements require explicit
conflict review, not replacement by assumption. Verify empty collections
explicitly and recheck all collection proof after projection. This procedure does
not change the default application's merge policy.

Apply only the accepted merged sources, conditional on their original versions.
Persist and fsync an intent before submission and the exact returned
acknowledgement afterward, including durable journal directory entries. Do not
blindly retry an uncertain write. An intent without acknowledgement requires
explicit reconciliation; any unexpected content/version or topology change
stops repair. Before resumption, verify acknowledged rows against their recorded
versions and untouched rows against their originals. Finish with exact readback
and API checks, without changing unrelated aliases or publication state.
Repair evidence is distinct from acquisition progress and job-ledger outcomes;
neither repaired documents nor legacy hydration labels prove an entire upstream
scope complete.

Use the configured API mount (`/api/v1` by default) for canary and final detail
checks. A missing route is not a reason to repeat an acknowledged write. Keep
endpoint configuration separate from sealed repair implementation and bind a
successful canary to the accepted plan and acknowledged source digest before
bulk continuation. Verify actual exposed collection content and hydration proof,
not just HTTP status or counts; source readback covers fields the DTO omits.
Retire only the exact owned, unaliased shadow after complete source/version and
API verification, retaining before-images, accepted candidates and journals.

Compare API values using the actual DTO's nullable/default semantics, while
retaining exact raw-source readback. Omitted text is not necessarily a stored
empty string. An omitted collection can match an empty API list only when
independently retrieved, versioned proof and normalized count validation certify
zero entries. Never turn unknown or nonzero missing data into a successful empty
result, or silently materialize missing fields in accepted sources.

### Failure Boundaries Covered

| Boundary | Executed application behavior |
| --- | --- |
| Mixed bulk success/failure | A real ingest pipeline rejects one of two documents sharing a bulk. The other document exists, both owners fail, and neither stream entry is acknowledged. |
| Abandoned pending entries | Redis `XCLAIM` ages pending IDs without sleeps; a fresh production `StreamIndexer` reclaims them with `XAUTOCLAIM`, retries both documents, and acknowledges only after success. Repeated draining creates no duplicates. |
| Archive handoff interruption | The fixture constructs the committed-archive/unpublished-stream state; the real `IndexJobRunner` restores both records and completes the durable job. |
| Trimmed/lost stream | Pending bodies are trimmed, or only the fixture-owned stream is deleted. The real runner clears reclaimable ghost entries and restores records from the archive. |
| Duplicate terminal delivery | A fresh runner skips a succeeded ledger claim; records and the terminal ledger row remain unchanged. |
| Incomplete archive | Expected counts cannot be satisfied; the runner raises rather than reporting success, including an archived record already counted from the stream. |
| Permanent batched rejection | Actual bulk rejection leaves every owner FAILED with rejected IDs in the ledger, no automatic retry, all entries pending, and source archives retained. |
| Killed writer and SQLite restore | A spawned writer commits a claim, archive records, and progress while keeping the ledger WAL open. The backup API captures both stores; SIGKILL stops the writer. Newer original files are preserved, snapshots restore to the original paths, and the real recovery service/index runner finishes archive replay without rerunning terminal work. |
| Projection/publication | Existing suites cover missing explicit targets, text arrival orders, partial topic writes, publication CAS/rollback, graph refresh/write failures, perspective write/HTTP-size rejection, and source preservation. |
| Measured query budgets | Existing real-index cases check the 100-hit activity page and response below 50,000 bytes, stable sorting, grouped search, and complete-or-reject vote joins. |

Most cases construct interrupted handoff states or inject server-side rejections.
The restore case really kills a writer process after committed writes, but it
does not kill a Celery task/source fetcher mid-execution or simulate power loss.
Worker-liveness and queue-depth probes are injected in that case; recovery uses
the real SQLite ledger/Redis lock and dispatcher, with transport recorded rather
than sending a source job. Paired backups are captured at a quiescent checkpoint.
RabbitMQ restart/redelivery, Elasticsearch/model snapshots, and a full-system
backup/restore drill remain outside this gate.
Durable admission/retry/cancellation/recovery is separately checked by existing
SQLite-backed unit tests in the same workflow. Production alias cutover/rollback,
image/resource/queue-routing release smoke (below), full restore, and
sustained-operation acceptance remain separate checks. No deployment is
authorized by passing this suite alone.

The opt-in pipeline fixture accepts `PIPELINE_TEST_SEARCH_URL`,
`PIPELINE_TEST_SEARCH_API_KEY` (optional for an authenticated search endpoint)
and `PIPELINE_TEST_REDIS_URL`. Supply credentials through the process environment,
never a committed command or file. The fixture creates UUID-owned
`pipeline-acceptance-*` indices/pipelines and scoped stream keys, and removes only
its own resources. Use a separate Redis database for the drill; never point a
test that flushes a database at application Redis. This fixture does not restart
the shared broker or search service.

<!-- wiki:repository-only:start -->
The bounded handoff comparison uses the same 100 synthetic bills, 25-document
bulks, real normalization (warmed before timing), SQLite archive and isolated
Elasticsearch/Redis fixtures. Both paths preserve all 100 records. One local run
measured stream/archive fallback at 0.249/0.214 seconds and retained Redis memory
at 19,660/1,016 bytes respectively. The archive path still creates an empty
consumer group; it is **not a Redis-free implementation**. This small serial
fixture does not establish backpressure, large-corpus memory, concurrent-reader,
mid-write crash or shared-rate-limit equivalence. Keep Redis Streams and the
existing recovery boundaries; transport removal is not justified by this result.

<!-- wiki:repository-only:end -->

## Release Image and Routing Acceptance

The existing **API contracts** workflow exposes **Run workflow** for manual
pre-release acceptance. The user selected this policy because rebuilding the
full Python/NLP image is expensive. Queue/deployment unit checks still run on
every push and PR; the manual image job depends on the normal contracts gate.
It has a 45-minute timeout, builds both production Dockerfiles locally, and never
logs into a registry, publishes images, deploys, or starts Beat.

Local reproduction from the repository root:

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

The separate environment avoids replacing the development environment. The
`release` dependency group installs only the host test driver, not training/NLP
packages. Application startup and worker imports execute inside the built images.
The opt-in `api` target excludes the `analysis` dependency group. The default,
last `analysis` target retains the full worker/training stack; existing build
and deployment commands therefore keep their previous capabilities. Both retain
spaCy, the same pinned English model and NumPy for query normalization. Do not
run a worker using the API-only image. No live image selection is changed by
these tests. Allow substantial free disk for the full image and build layers.
Image sizes are logged rather than substituted for an application resource SLA.

The fixture creates a UUID-named **internal** Docker network and bounded
containers: API/worker 1 CPU and 1,536 MiB each, nginx 1 CPU/128 MiB, RabbitMQ
1 CPU/512 MiB. It publishes no host ports, mounts no source data, generates
throwaway broker credentials, and removes only its containers, anonymous volumes,
and network on success or failure. The probe is streamed over stdin, not installed
into or copied into the runtime image.

| Check | Required outcome |
| --- | --- |
| API default command | Honors a nondefault Cloud Run `PORT`; `/health` is 200 with the expected model. |
| Unavailable dependency | Unreachable synthetic search endpoint makes `/ready` return typed 503, not readiness success. |
| Runtime resources | The image loads every packaged mapping family and contains no retained uv installer cache; running containers have the exact configured CPU/memory caps and are not OOM-killed. |
| Serving/analysis boundary | The API image has no installed or loaded BERTopic, Sentence Transformers, SciPy, scikit-learn or PyTorch. The full image retains all five; real spaCy normalization and OpenAPI hashes match between the images. A fresh-process unit regression also rejects direct training imports by the API/submission CLIs in a full environment. |
| nginx | Serves the compiled SPA and deep-link fallback, immutable JavaScript assets, and 404 for missing assets rather than successful SPA HTML. The production bundle has no localhost API fallback. |
| AMQP delivery | The actual `JobDispatcher` and Celery app publish every `JobKind`; the probe receives and acknowledges each exact task envelope from its expected queue **before any worker starts**. No source/analytics task executes. |
| Worker | A real singleton prefork worker registers every dispatched task, reports exactly one child process, and consumes all configured queues on the disposable broker. |
| Deployment parity | Unit checks cover both Compose files' consumer coverage and analytics bounds/shared ledger; all job kinds also check immediate/delayed dispatch with overridden queue names. |

This is a low-load startup/routing smoke, not the complete deployed worker
topology, an ingest/training execution, throughput/peak-memory benchmark, broker
crash/redelivery drill, backup restore, or production cutover. The existing
deployment configuration is not started. Passing the manual gate does not
authorize a deployment.
