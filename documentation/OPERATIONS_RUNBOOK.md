# Operations Runbook

This runbook covers local restart, health checks, recovery, backup, and rollback
for the Congress Tracker workers and durable job ledger.

## Health Check

Run the read-only health check before and after maintenance:

```sh
make health-check
uv run python scripts/health_check.py --json
```

A healthy report requires `jobs`, `celery`, `redis`, and `opensearch` to be
`ok`. Warnings may remain for historical audit rows, but every category must
have an explicit disposition. `actionable_failure_count` is the count to use
for the maintenance decision; expected denormalized-summary rows are excluded.

Verify the ledger independently when investigating corruption:

```sh
uv run python -c 'from sqlalchemy import text; from cdm.jobs.store import JobStore; from settings import JOB_DB_PATH; s=JobStore(JOB_DB_PATH); print(s.engine.connect().execute(text("PRAGMA integrity_check")).scalar_one())'
```

## Restart

Stop workers and Beat before changing the ledger or restoring a backup. Start
the local dependencies first, then the workers:

```sh
make local
make worker MONITOR=0
make worker-index
make beat
```

For the full container stack:

```sh
make stack-up
make health-check
```

After restart, confirm that only one ingest worker, one index worker, and one
Beat scheduler are active. Duplicate workers can cause unnecessary redelivery
and database contention.

## Recovery

Before requeueing exhausted jobs, create a timestamped ledger backup:

```sh
backup="data/jobs.sqlite3.pre-recovery-$(date -u +%Y%m%dT%H%M%SZ)"
cp -p data/jobs.sqlite3 "$backup"
```

Use the recovery task for stale worker messages and transient failures. It is
single-flight and rate-limited; do not bulk requeue vendor 4xx, malformed XML,
validation, disk-I/O, or expected non-indexed failures.

```sh
uv run python scripts/job_status.py
uv run python scripts/health_check.py --json
```

For acknowledged Redis streams, replay from the durable `records.sqlite3`
archive or re-ingest the source package. Do not blindly redispatch an index job
whose stream entries have already been acknowledged.

## Rollback

Rollback is a maintenance operation:

1. Stop ingest workers, index workers, and Beat.
2. Preserve the current ledger and record the reason for rollback.
3. Verify the intended backup with `PRAGMA integrity_check`.
4. Restore the backup only after the verification succeeds.
5. Start services and run the health check.
6. Confirm queue state and OpenSearch aliases before resuming work.

Example restoration command after services are stopped:

```sh
cp -p data/jobs.sqlite3 data/jobs.sqlite3.before-rollback-$(date -u +%Y%m%dT%H%M%SZ)
cp -p data/jobs.sqlite3.pre-recovery-TIMESTAMP data/jobs.sqlite3
```

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
