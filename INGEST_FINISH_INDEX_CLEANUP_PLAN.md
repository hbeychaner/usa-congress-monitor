# Ingest Completion, OpenSearch Indexing, and Data Cleanup Plan

**Prepared:** 2026-08-23  
**Purpose:** Finish the current historical ingest, ensure fetched records are indexed in OpenSearch, and reclaim storage without deleting resumability or canonical data.

## Current Starting Point

Observed before beginning this plan:

- Ingest jobs: 2,268 `succeeded`, 11 `retrying`.
- Index jobs: 101 `succeeded`.
- Host free space: approximately 68 GiB.
- `data/` size: approximately 2.3 GiB.
- `data/full_history/`: approximately 1.8 GiB.
- `data/full_history/ingest:<job-id>/`: approximately 1.14 GiB across 2,276 directories.
- The 11 retrying ingest job directories occupy approximately 266 MB.
- Succeeded per-job ingest directories occupy approximately 874 MB.
- `data/bills_bulk/`: approximately 490 MB; it is not referenced by the job ledger.
- All previously checked SQLite databases passed `PRAGMA integrity_check`.

The current retrying job directories are retained until those jobs either succeed or are explicitly classified as permanently failed. No deletion should begin while a worker, Beat scheduler, migration, or cleanup process is active.

## Safety Rules

1. Do not run `make local-down`; it removes Docker volumes and can delete OpenSearch, RabbitMQ, Redis, and Kibana state.
2. Use `make stop` only when containers need to be stopped while preserving volumes.
3. Do not delete `data/jobs.sqlite3`, retrying job directories, checkpoints, consolidated `data/full_history` outputs, manual-review files, or current daily data.
4. Do not run `docker system prune --volumes`.
5. Take a backup or snapshot before deleting the large succeeded per-job archive set.
6. Delete only after an inventory command has produced a saved report and the report has been reviewed.
7. Stop immediately if SQLite integrity checks fail, job counts decrease unexpectedly, or OpenSearch document counts regress.

## Phase 0: Prepare a Baseline

Run from the repository root with the virtual environment available:

```bash
mkdir -p tmp/ingest-maintenance

date > tmp/ingest-maintenance/baseline.txt
sqlite3 -header -column data/jobs.sqlite3 \
  "select kind,status,count(*) as count from jobs group by kind,status order by kind,status;" \
  | tee -a tmp/ingest-maintenance/baseline.txt

du -sh data data/full_history data/bills_bulk \
  | tee -a tmp/ingest-maintenance/baseline.txt
df -h . | tee -a tmp/ingest-maintenance/baseline.txt
```

Record the current OpenSearch state before indexing:

```bash
uv run python scripts/create_indices.py --status \
  | tee tmp/ingest-maintenance/opensearch-before.txt
```

If OpenSearch is not available, start Docker safely with `make start`; do not
remove volumes.

## Phase 1: Finish Ingest

### 1. Start services

Use separate terminals:

```bash
make start
make worker
make beat
```

`make start` starts Elasticsearch/OpenSearch, Kibana, RabbitMQ, and Redis.
`make worker` processes queued Celery tasks. `make beat` schedules the daily
incremental job and periodic failed-job recovery. The worker and Beat commands
remain foreground processes and should be stopped with `Ctrl-C` when finished.

### 2. Allow existing retries to drain

The 11 `retrying` jobs are the first priority. They contain resumable archives
and must not be replaced by a new broad ingest. Monitor the ledger:

```bash
watch -n 30 'sqlite3 -header -column data/jobs.sqlite3 \
  "select kind,status,count(*) as count from jobs group by kind,status order by kind,status;"'
```

If `watch` is unavailable on macOS, repeat the SQLite query manually every few
minutes. The expected result is that retrying jobs become `succeeded` or remain
retrying with a changing `updated_at` timestamp.

Inspect retry errors without editing the database:

```bash
sqlite3 -header -column data/jobs.sqlite3 \
  "select id,status,attempts,updated_at,last_error from jobs where kind='ingest' and status in ('retrying','failed') order by updated_at;"
```

Do not manually resubmit a retrying job unless its Celery task has definitely
been lost. The job ID and archive are already the resumability boundary.

### 3. Confirm the historical plan is complete

A full plan is complete only when:

- No expected historical job is still queued, running, or retrying.
- Every failed job is either recovered or explicitly documented as a vendor/API
  failure with a retained list archive.
- Static resources have one successful job.
- Date-windowed resources have successful jobs for every requested window.
- Congress-scoped resources have successful jobs for every requested Congress.
- The corresponding `run_summary.json` files show no unhandled resource errors.

Use the planner in dry-run mode to understand the expected job shape before
queueing anything new:

```bash
uv run python scripts/queue_full_ingest.py --dry-run \
  > tmp/ingest-maintenance/full-plan.txt
```

Do not queue the complete historical plan again just because old per-job
folders exist. The durable job ledger and deterministic idempotency keys are the
source of truth.

### 4. Handle the missed daily gap separately

The daily scheduler covers only a two-day overlap. It does not reconstruct an
arbitrarily long outage. If the service was offline for more than two days,
submit one targeted date-window backfill for the missed period. Use only
resources whose endpoints support date filters; do not add amendments or static
resources to a date-window payload.

Example:

```bash
uv run python scripts/submit_ingest.py \
  --outdir data/gap-2026-08 \
  --resources bill,committee,committee_meeting,committee_print,member,nomination,summaries,treaty \
  --from-date 2026-08-14T00:00:00Z \
  --to-date 2026-08-23T23:59:59Z \
  --fetch-items
```

Adjust dates and resources to the actual outage. Repeated submission of the
same payload is idempotent.

## Phase 2: Index Fetched Documents into OpenSearch

### 1. Verify mappings and indices

Create missing indices without deleting existing ones:

```bash
uv run python scripts/create_indices.py
uv run python scripts/create_indices.py --status \
  | tee tmp/ingest-maintenance/opensearch-after-create.txt
```

If mappings changed, use the additive mapping update command and inspect its
output:

```bash
uv run python scripts/create_indices.py --update
```

Do not delete or recreate indices as part of this plan.

### 2. Understand the indexing handoff

For each successful ingest job with item records:

1. `IngestRunner` writes compressed records to SQLite.
2. The worker publishes records to a Redis Stream.
3. The ingest task submits a durable index job.
4. `RedisIndexingRunner` validates and bulk-upserts records into OpenSearch.
5. Redis entries are acknowledged only after a successful bulk response.
6. Index checkpoints and consumer-group pending state permit recovery.

Therefore, an ingest job being `succeeded` does not by itself prove that all
OpenSearch documents are indexed. Index jobs and Redis pending entries must be
checked separately.

### 3. Drain index jobs

Keep the worker running and inspect index status:

```bash
sqlite3 -header -column data/jobs.sqlite3 \
  "select kind,status,count(*) as count from jobs group by kind,status order by kind,status;"

sqlite3 -header -column data/jobs.sqlite3 \
  "select id,status,attempts,updated_at,last_error from jobs where kind='index' and status <> 'succeeded' order by updated_at;"
```

Expected steady state:

- No queued, running, retrying, or failed index jobs, except documented
  transient retries that are actively progressing.
- Redis consumer-group pending counts are zero or explained by an actively
  running index worker.
- OpenSearch index status shows nonzero document counts for resources that
  produced item records.

Use the project’s OpenSearch status command:

```bash
uv run python scripts/create_indices.py --status
```

For a deeper check, compare representative resource counts between successful
archive databases and OpenSearch. Use canonical IDs and allow for intentional
list-only resources and deduplication. Do not require raw row counts to equal
OpenSearch counts when duplicate IDs or retries are present.

### 4. Verify representative documents

Check at least these resource classes:

- A date-windowed resource: `bill`.
- A static resource: `congress` or `house_vote`.
- A Congress-scoped resource: `law` list records or its bill fallback output.
- A resource with known nested fields: `committee`, `nomination`, or `summaries`.

Verify that:

- Canonical IDs exist.
- Expected mappings are present.
- Re-running the same index job does not create duplicate documents.
- A failed bulk operation leaves the checkpoint behind the failed batch.

Run the focused and full automated checks before cleanup:

```bash
uv run pytest -q tests/unit/test_worker_retry.py tests/unit/test_archive.py tests/unit/test_list_cache.py
uv run pytest -q tests/unit
```

## Phase 3: Inventory Cleanup Candidates

Create a cleanup inventory before removing anything:

```bash
mkdir -p tmp/ingest-maintenance
find data -type f -print > tmp/ingest-maintenance/data-files.txt
du -sh data/* 2>/dev/null | sort -h \
  | tee tmp/ingest-maintenance/data-sizes.txt
```

Classify candidates as follows.

### Tier 1: disposable test and verification outputs

These are normally safe once no investigation depends on them:

- `data/local_sample/`
- `data/*_verify/`
- `data/bills_ingest/`
- `data/bills_ingest2/`
- `data/bills_ingest100/`
- Empty directories such as `data/bills_ingest_last/`, `data/bills/`, and
  `data/daily/`
- `data/full_history/smoke/`

Before deletion, confirm no current script or job payload uses them:

```bash
grep -RInE 'local_sample|amendments_verify|bills_ingest|bills_verify|law_verify|full_history/smoke' \
  cdm scripts tests README.md documentation || true
sqlite3 data/jobs.sqlite3 \
  "select id,status,json_extract(payload,'$.outdir') from jobs where json_extract(payload,'$.outdir') like '%local_sample%' or json_extract(payload,'$.outdir') like '%bills_ingest%';"
```

Delete only the paths confirmed disposable, preferably by moving them outside
the repository first if they may be useful for a short period.

### Tier 2: standalone legacy snapshots

Review these individually:

- `data/bills_bulk/` is approximately 490 MB and is not referenced by the job
  ledger. It is likely an older standalone bill backfill, but it may contain
  the only local copy of that work.
- `data/congress/` is approximately 3.3 MB and may duplicate
  `data/full_history/static/congress/`.
- `data/bills_recent/` contains recent JSON snapshots and should be retained
  unless explicitly no longer needed.
- `data/amendments_ingest/items_manual.json` and
  `items_manual_failures.json` are manual-review records and should be
  retained.

For `data/congress/`, compare canonical IDs against the consolidated archive
before removal. For `data/bills_bulk/`, compare its IDs and coverage against
OpenSearch and the current full-history bill archives. Preserve it if coverage
cannot be proven.

### Tier 3: succeeded per-job archives

The 2,266 succeeded per-job directories occupy approximately 874 MB. They are
potentially redundant, but they are also useful forensic and replay inputs.
Do not delete them based only on job status.

First produce a candidate report:

```bash
sqlite3 -header -column data/jobs.sqlite3 \
  "select id,status,datetime(created_at) as created, json_extract(payload,'$.resources') as resources, json_extract(payload,'$.outdir') as outdir from jobs where kind='ingest' and status='succeeded' order by created_at;" \
  > tmp/ingest-maintenance/succeeded-ingest-jobs.txt
```

Then verify, per resource and date/Congress partition, that:

- The consolidated archive contains the same or greater set of canonical IDs.
- OpenSearch contains the expected indexed projection.
- No checkpoint or retry process still points to the candidate directory.
- No unresolved error report or manual review depends on the raw archive.

Only after that comparison should the succeeded per-job directories be moved
to an external backup or deleted. Retain the 11 retrying directories until
those jobs are complete and indexed.

## Phase 4: Safe Deletion Procedure

For every approved deletion batch:

1. Stop Beat so no new daily job is scheduled.
2. Stop the worker only after queued/retrying work is complete.
3. Confirm no migration or cleanup process is running.
4. Save the candidate path list and sizes.
5. Move the candidate directory to an external backup location, or delete it
   only when an external backup is not required.
6. Run SQLite integrity checks on all remaining databases.
7. Re-run job status and OpenSearch status checks.
8. Compare free disk space and retain the report.

Example integrity check:

```bash
uv run python - <<'PY'
from pathlib import Path
import sqlite3

failures = []
for path in sorted(Path("data").rglob("*.sqlite3")):
    try:
        with sqlite3.connect(path, timeout=5) as db:
            result = db.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            failures.append((str(path), result))
    except Exception as exc:
        failures.append((str(path), repr(exc)))
print(f"sqlite_files={len(list(Path('data').rglob('*.sqlite3')))} failures={len(failures)}")
for failure in failures:
    print(failure)
raise SystemExit(bool(failures))
PY
```

Do not delete Docker volumes during host-data cleanup. Docker volume cleanup
is a separate, explicitly destructive operation that requires an OpenSearch,
RabbitMQ, and Redis backup.

## Targeted Retry Triage Log (2026-08-23)

This section tracks the manual diagnosis and targeted fixes for the 11 stuck
ingest jobs so a new VS Code window can resume without re-discovery.

### Triage Checklist

- [x] Confirmed there were 11 retrying ingest jobs and 0 retrying index jobs.
- [x] Captured original retry errors in `tmp/ingest-maintenance/retrying-ingest-before-quarantine.txt`.
- [x] Quarantined stale retries to stop infinite crash/retry cycling.
- [x] Added a finite transient retry cap in worker settings (`CELERY_RETRY_MAX_TRANSIENT`).
- [x] Added poisoned-list-page handling: after repeated HTTP 5xx at one offset,
      ingest now logs the failure and advances to the next offset instead of
      failing the whole job.
- [x] Fixed poisoned-page log path to write to
  `data/full_history/<job-id>/<resource>/list_page_failures.jsonl`.
- [x] Added unit coverage for poisoned-page logging (`tests/unit/test_runner_list_page_failures.py`).
- [x] Hotfixed hearing model validation to tolerate API records missing
      `title` (`cdm/models/bills.py`) and added regression coverage in
      `tests/unit/test_hearing_ingest.py`.
- [x] Identified payload variants per window and marked high-page-size jobs as
  superseded (`superseded_by_list_page_size_50_variant`).
- [x] Purged stale Celery queue messages and re-enqueued canonical jobs only.
- [ ] Allow patched worker to finish the 5 canonical non-daily jobs and verify final states.
- [ ] Resolve the old daily job payload separately (do not blindly requeue).

### Handoff Checkpoint

- Current worker command is running: `make worker`.
- 2026-08-23 14:05 local: worker was restarted to load the `Hearing.title`
  optional-field hotfix; active worker terminal session id:
  `1ef8e3f5-4093-4813-91f4-f456281cb436`.
- Canonical queued jobs now in-flight:
  - `ingest:ea25650fd6f2defa6bb982cb` (hearing, `list_page_size=50`)
  - `ingest:c504803c53fc3f0b441a8e69` (bill 2022-11-06..2023-11-05, `list_page_size=50`)
  - `ingest:28f3773dc41c579dc85a4967` (bill 2023-11-06..2024-11-04, `list_page_size=50`)
  - `ingest:aecba5fbd9f53a05b7435c86` (bill 2024-11-05..2025-11-04, `list_page_size=50`)
  - `ingest:0b7cd33794717e105234093b` (bill 2025-11-05..2026-08-09, `list_page_size=50`)
- Superseded variants (do not requeue) are marked failed with
  `superseded_by_list_page_size_50_variant`.
- Quick status check command:

```bash
sqlite3 -header -column data/jobs.sqlite3 \
  "select id,status,attempts,datetime(updated_at) as updated,last_error from jobs where kind='ingest' and status in ('queued','running','retrying','failed') order by updated_at desc;"
```

### Per-Job Findings and Action

All 10 historical jobs share one failure pattern: deterministic Congress API
HTTP 500 at a specific list offset, even after page-size fallback to `limit=1`.

| Job ID | Resource | Window | Checkpoint Offset | Finding | Action |
|---|---|---|---:|---|---|
| `ingest:0c3620585ef4994c9a1665e5` | hearing | static | 34425 | 500 at offset 34425 after recovering 34417-34424 at `limit=1`; high-page-size variant | Marked superseded by list_page_size=50 variant. |
| `ingest:ea25650fd6f2defa6bb982cb` | hearing | static | 34417 | same poisoned hearing segment | Run under patched worker; skip poisoned offset and continue. |
| `ingest:2555b9c68ca93209f7b54287` | bill | 2022-11-06..2023-11-05 | 3247 | deterministic 500 at 3246 and 3247; high-page-size variant | Marked superseded by list_page_size=50 variant. |
| `ingest:c504803c53fc3f0b441a8e69` | bill | 2022-11-06..2023-11-05 | 3246 | duplicate stuck window of row above | Run under patched worker; skip poisoned offset and continue. |
| `ingest:ffb12a6d0755265f831f41b5` | bill | 2023-11-06..2024-11-04 | 72818 | deterministic 500 at offset 72818; high-page-size variant | Marked superseded by list_page_size=50 variant. |
| `ingest:28f3773dc41c579dc85a4967` | bill | 2023-11-06..2024-11-04 | 72818 | duplicate stuck window of row above | Run under patched worker; skip poisoned offset and continue. |
| `ingest:7c159d0ede91144a0a3ad63d` | bill | 2024-11-05..2025-11-04 | 175622 | deterministic 500 at offset 175622; high-page-size variant | Marked superseded by list_page_size=50 variant. |
| `ingest:aecba5fbd9f53a05b7435c86` | bill | 2024-11-05..2025-11-04 | 175622 | duplicate stuck window of row above | Run under patched worker; skip poisoned offset and continue. |
| `ingest:641536bbdd334f47d9e60172` | bill | 2025-11-05..2026-08-09 | 46575 | healthy advancing window; high-page-size variant | Marked superseded by list_page_size=50 variant. |
| `ingest:0b7cd33794717e105234093b` | bill | 2025-11-05..2026-08-09 | 44575 | duplicate window of row above | Continue normally under patched worker. |
| `ingest:ab9823416038e07d4c2e6184` | daily mixed run | 2026-08-20..2026-08-22 | n/a | original error was HTTP 400 on amendment date-filter URL; payload had no explicit `resources` list | Keep quarantined; replace with explicit daily payload from current `daily_ingest_payload` resource set, then run a targeted backfill if needed. |

### Runtime Evidence to Inspect

- Worker logs clearly showed repeated 500s at offsets `34425`, `3246`, `72818`, and `175622`.
- Worker logs later confirmed offset `3247` also 500 in the same bill window,
  indicating a poisoned segment rather than a single record.
- Hearing item payloads may omit `title`; this caused per-item validation
  failures until `Hearing.title` was made optional.
- New poisoned-page records are written to:
  - `data/full_history/<job-id>/<resource>/list_page_failures.jsonl`
- Use these files to audit any skipped offsets before final cleanup.

## Completion Criteria

This plan is complete when all of the following are true:

- Historical ingest jobs are no longer unexpectedly queued, running, or
  retrying.
- Any remaining failure is documented with a reason and a next action.
- All item-producing ingest jobs have corresponding completed index jobs.
- Redis pending entries are drained or explicitly explained.
- OpenSearch mappings and representative document samples are verified.
- The daily Beat job is running again after any gap backfill is submitted.
- Only approved non-needed data has been removed.
- Remaining SQLite archives pass integrity checks.
- The post-cleanup data-size and free-space reports are saved.

## Recommended Execution Order

1. `make start`, `make worker`, and `make beat`.
2. Let the 11 retrying ingest jobs drain; investigate only if progress stops.
3. Submit a targeted gap backfill if the outage exceeded the daily two-day
   overlap.
4. Create/update OpenSearch indices and drain index jobs.
5. Verify representative OpenSearch documents and run the unit suite.
6. Remove Tier 1 disposable artifacts.
7. Compare and decide on `data/bills_bulk/` and `data/congress/`.
8. Compare succeeded per-job archives against consolidated archives before
   reclaiming the remaining approximately 874 MB.
9. Run integrity, job, OpenSearch, and disk-space checks again.
10. Restart/confirm Beat and worker for ongoing autonomous daily ingestion.
