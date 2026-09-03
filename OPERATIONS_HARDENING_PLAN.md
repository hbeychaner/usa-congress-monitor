# Operations Hardening Plan

**Status:** in progress  
**Started:** 2026-09-03

This plan covers the operational gaps discovered while the GovInfo historical
ingest and OpenSearch indexing queues are draining. It complements the
ingestion and OpenSearch implementation plans; the durable SQLite ledger,
Redis Streams, RabbitMQ, and OpenSearch remain the system of record boundaries
described there.

## Baseline

- GovInfo ingest is active and advancing.
- SQLite integrity is checked before and after maintenance operations.
- Celery uses one ingest worker, one index worker, and one Beat scheduler.
- Recovery is single-flight and does not republish ordinary queued jobs.
- OpenSearch indices and aliases are present and authenticated status checks
  work through the project client.
- The index queue is materially larger than the ingest queue and needs
  controlled throughput tuning.

## Execution Order

### 1. Add a repeatable health check

**Status:** complete

Add `scripts/health_check.py` and a Makefile target that report:

- SQLite integrity and job counts.
- Recent ingest and index throughput.
- Celery node liveness and duplicate-node warnings.
- Redis connectivity.
- Authenticated OpenSearch connectivity and cluster health.
- Failure categories and queue backlog.

The command must distinguish warnings, such as backlog, from failures, such as
ledger corruption or unavailable dependencies. It must not modify application
data.

### 2. Reduce indexing lag safely

**Status:** complete

Observed baseline was approximately 14.3 completed index jobs per minute over
15 minutes. The index worker was increased from concurrency 2 to 4 while the
ingest worker remained at 8. The live worker reports a four-process pool, and
the first post-change window measured approximately 18.6 completed index jobs
per minute. SQLite integrity and dependency health remained clean; the queue
is still monitored because ingest continues to add work.

- Establish a throughput baseline from completed index jobs.
- Confirm OpenSearch bulk latency and error rate.
- Increase index worker capacity only in a controlled step.
- Recheck SQLite integrity and index failures after each change.
- Keep ingest capacity unchanged unless API rate limits require adjustment.

### 3. Correct endpoint scope and daily-ingest failures

**Status:** complete

The repeated 400 responses were caused by fractional seconds in `toDateTime`,
not by unsupported endpoint scopes. Congress.gov accepts the configured
date-window resources when timestamps use second precision, but rejects values
such as `2026-08-28T07:21:49.330791Z`. The shared ingest runner now canonicalizes
both date parameters to UTC second precision before requests, with regression
coverage.

- Verify each resource producing repeated HTTP 400 responses against its
  registered endpoint parameters.
- Move resources that ignore or reject date filters to static or supported
  scopes.
- Add regression tests for the scope catalog and daily payload.
- Preserve list-only behavior for resources whose item endpoints are known to
  fail at the source.

### 4. Reconcile recoverable failures

**Status:** in progress

Current failures are classified in the health report: GovInfo download
timeouts are transient, Congress.gov 400s are vendor/input errors from the
historical fractional-second window, validation/XML failures require manual
review, and index failures remain unclassified pending targeted inspection.
No bulk requeue is performed while the live backlog is draining; the next
maintenance window must back up SQLite before retrying exhausted transient
jobs.

- Requeue only transient download or transport failures.
- Leave malformed XML, validation failures, vendor 4xx responses, and known
  denormalized resources in manual-review categories.
- Keep a timestamped SQLite backup before bulk status changes.
- Verify that retries do not create duplicate batch ownership.

### 5. Add sustained-operation tests and documentation

**Status:** queued

- Test concurrent claims, recovery lock contention, stale-task recovery, and
  batch fan-out.
- Document restart, backup, health-check, and rollback procedures.
- Observe ledger integrity, throughput, and failure rate across multiple
  scheduler cycles before declaring the system fully operational.

## Completion Gate

This plan is complete only when the health check reports no failed dependency,
the SQLite ledger remains integrity-clean during sustained concurrent writes,
the index queue is draining, and every remaining failure has an explicit
recoverable or manual-review classification.