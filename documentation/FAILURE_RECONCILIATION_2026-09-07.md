# Failure Reconciliation: 2026-09-07

This report records the disposition of the failed durable jobs after the
historical ingest recovery pass. Original failed rows remain unchanged for
auditability.

## Group 1: Archive Recovery

The following acknowledged-stream failures were replayed from durable
`records.sqlite3` archives:

- One `bill` record into `congress-legislation-v118`.
- Two `bill_text` records into `congress-legislation-v118`.
- 843 `member` records into `congress-member`.

All replayed records passed document validation and OpenSearch bulk writes.
The original daily bill archive cannot be replayed because its artifact
directory is empty. A fresh durable replay was queued as
`manual-recovery:daily-bill:2026-08-20:2026-08-22:20260907`; its result must be
verified before this gap is closed.

## Group 2: Malformed and Validation Data

- GovInfo manifest corruption: 25 packages recovered by quarantining the
  corrupt per-package manifest and recreating it. Source artifacts were kept.
- The malformed `BILLS-118HR184IH` XML package was redownloaded and parsed
  successfully; its repair job succeeded.
- Two member validation failures succeeded after applying a URL-derived
  Bioguide fallback because the source item supplied a valid member URL but
  omitted `bioguideId`.
- One GovInfo `BILLSTATUS-118hr485` package remains manual review because its
  archive reports SQLite disk I/O failure.

## Group 3: Manual Review

The original rows remain unchanged as audit records. Six rows are formally
closed without retry because they are stale, superseded, or intentionally
quarantined:

- `ingest:ab9823416038e07d4c2e6184`: stale retry quarantined; replacement
  daily replay is recorded above.
- `ingest:641536bbdd334f47d9e60172` and
  `ingest:7c159d0ede91144a0a3ad63d`: superseded by the page-size-50 variant.
- `ingest:ffb12a6d0755265f831f41b5`,
  `ingest:2555b9c68ca93209f7b54287`, and
  `ingest:0c3620585ef4994c9a1665e5`: superseded historical variants.

The two disk-I/O rows were recovered successfully:

- `index:2db25a851e47692291fada7f`: disk I/O failure reading a bill-text
  archive; do not retry until the archive storage is independently repaired.
- `govinfo_bulk:1d27a10f250b716db6df0d81`: disk I/O failure in the
  `BILLSTATUS-118hr485` package; source integrity remains unverified.
- Replacement index job: `manual-recovery:index:4510ba28441c5a5a3e7f7dd0:20260907`.
- Replacement GovInfo job: `manual-recovery:govinfo:BILLSTATUS-118hr485:20260907`.

The GovInfo replacement and its generated index job succeeded. The old
bill-text index stream had no pending entries, so its replacement correctly
found zero records; that original row is formally closed as an acknowledged
archive gap. All eight original manual-review rows now have explicit
dispositions and remain unchanged for auditability.

## Group 4: Vendor/Input Failures

Fourteen historical Congress.gov jobs failed with HTTP 400 responses caused by
fractional-second `toDateTime` values. The current runner emits second-
precision UTC boundaries, so all fourteen were backed up and redispatched with
the corrected runner. Thirteen retries have succeeded. One bill retry remains
running; it has no error yet and must settle before this group is closed. Any
new vendor or validation errors remain separate dispositions.

## Current Gate

The health check should report all remaining rows by category and expose
`actionable_failure_count`. Alias cutover remains blocked until the target
index has complete verified multi-Congress coverage. A production rebuild into
`congress-legislation-v2` completed with 23,807 documents, matching production
counts, mappings, mapping version, and sampled IDs; aliases were intentionally
left unchanged.

The missing oldest bill window was queued as
`manual-recovery:historical-bill:2022-11-06:2023-11-05:20260907` to complete
the requested last-four-Congresses coverage. Alias cutover remains blocked
until that job, the daily bill recovery, and the health gates are verified.
