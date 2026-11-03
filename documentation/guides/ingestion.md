# Ingestion and replay

There are three distinct acquisition paths:

* Congress.gov API: endpoint specs → validated list/item models → archives and
  Redis → index jobs.
* GovInfo: package discovery/download → XML adapters → archives and Redis →
  index jobs, with a separate reconciliation replay path.
* Voteview: cached CSVs → validated rows → one replacement document per
  rollcall, written directly to the search store.

These paths share canonical bill/member relationships where possible, but do
not have identical schemas, scheduling, or replacement semantics.
See [data models](../reference/data-models.md) and
[indexing](../reference/indexing.md) before treating a successful fetch as
proof that every field is searchable.
The [ingest](../reference/symbols/ingest.md),
[data-collection](../reference/symbols/data_collection.md), and
[job](../reference/symbols/jobs.md) symbol indexes provide declaration-level
navigation alongside this operational guide.

## Congress API: entry points and planning

[`IngestRunner`](../../cdm/ingest/runner.py) fetches one resource.
[`Pipeline`](../../cdm/ingest/pipeline.py) runs resources sequentially, applying
shared bounds and configuring each runner from
[`RESOURCE_CONFIGS`](../../cdm/ingest/resource_config.py).
Its `run_all()` uses all 20 `Resource` enum values.
Item-fetch concurrency is within a resource, not parallel pipeline resources.

For durable work, [`submit_ingest.py`](../../scripts/submit_ingest.py) submits
an idempotent ledger job through `WorkerContainer`.
For example, after configuring the application's normal dependencies:

```bash
uv run python scripts/submit_ingest.py \
  --resources bill --congress 119 \
  --fetch-items --item-resources bill \
  --from-date 2025-01-01 --to-date 2025-01-31 \
  --retain-records
```

Submission queues work; it does not wait for acquisition or indexing.
Dates are normalized to UTC timestamps accepted by Congress.gov. A bare
`--to-date` is midnight, not implicitly the end of that day.
Full-history planning explicitly generates end-of-day upper bounds.

[`FullIngestConfig`](../../cdm/ingest/full_ingest.py) validates historical
bounds, window size, concurrency, and batch size.
`plan_full_ingest()` produces independent static-resource jobs, contiguous
nonoverlapping date-window jobs, and congress-scoped jobs.
`smoke_job()` bounds the Congress reference resource to one list page/item
limit with item hydration disabled. Planning creates payloads, not an
assertion that every historical endpoint is available.

### Scope and item-fetch policy

The current catalog classifies resources as follows:

| Resources | Planning scope | Item-fetch policy when `fetch_items=True` |
|---|---|---|
| `bill`, `member` | Date-windowed | Default off; opt in through `item_resources`. |
| `committee`, `committee_meeting`, `committee_print`, `nomination`, `treaty` | Date-windowed | Default on. |
| `amendment`, `committee_report`, `congress`, `crsreport`, `hearing`, `house_communication`, `senate_communication`, `house_vote` | Static | Default on. |
| `bound_congressional_record`, `daily_congressional_record`, `house_requirement` | Static | Default off; opt in selectively. |
| `law` | Congress-scoped | List-only by normal policy; the registered list spec requires congress. |
| `summaries` | Date-windowed | List-only; no independent item endpoint. |

`effective_scope()` corrects declared congress scope when the registered
list spec does not actually require congress. Scope comments are not the
final authority: `list_spec_requires_congress()` inspects required path
parameters. Static resource notes reflect observed API filtering limitations,
not a promise that upstream behavior can never change.

Pipeline hydration requires the global fetch flag **and** the resource's
default/explicit opt-in. `force_item_fetch` overrides the per-resource policy
when fetching is enabled, but the runner still treats summaries as list-only.
Setting `--fetch-items` alone does not hydrate bills.
Date parameters are sent only for catalog-supported resources.
When congress is supplied, the runner selects congress-list variants where
registered, including a dedicated bill list.

## Endpoint specs and HTTP boundary

[`cdm/data_collection/specs`](../../cdm/data_collection/specs) registers named
list/item/detail specs on import.
[`EndpointSpec`](../../cdm/models/endpoint_spec.py) defines path/query inputs,
pagination metadata, wrapper extraction, response models, and optional ID
strategy. `SpecRegistry` and module helpers register and resolve those definitions.

[`CDGClient`](../../cdm/data_collection/client.py):

1. Renders validated spec parameters and requests JSON.
2. Extracts records using configured data/unwrap keys and wrapper heuristics.
3. Resolves/validates Pydantic response models.
4. Normalizes notes, derives model IDs, and applies spec ID/reference strategy
   when that spec is passed to coercion.
5. Resolves item parameters from list metadata using dotted source paths or
   URL segments; normalizes law type/number and most path strings.

Non-JSON responses and unexpected object shapes are errors, not byte fallbacks.
The client uses a token bucket; worker runners inject a shared limiter so
per-thread HTTP sessions do not each consume a separate full API budget.
Without an injected limiter, clients have their own default 5,000/hour bucket.
The runner caches clients per thread, key, factory, and limiter.

`_request_with_backoff()` separately handles 429 responses (including
`Retry-After`, with a larger fallback backoff) and ordinary network/5xx retry
limits. A list page that still raises HTTP 5xx is retried at progressively
smaller page limits, from the configured size through eligible values
100/50/25/10/1. This fallback does not apply to every error category.

## Discovery, checkpoints, and list caches

`IngestRunner.run()` creates the resource directory, resolves specs and
runtime bounds, and reads:

* `list_checkpoint.json`: exact request-context parameters plus next offset.
* `list_records.sqlite3`: compressed validated list records by page offset.
* Legacy `list_records.jsonl`, only as a compatibility input when needed.

A checkpoint is usable only when its parameters match and its offset is an
integer at least `-1`; `-1` marks completed discovery. A mismatch removes the
old list caches. Page-size and sample limits are not all part of the stored
parameter context; do not interpret a checkpoint as a full run configuration.
Cache reload validates by Python field name to preserve snake_case dumps.

For each page, the runner extracts and validates list records, deduplicates
model identities, writes the list cache, then advances the atomic checkpoint.
It reports discovered count/checkpoint offset through the progress sink.
Bill metadata with an introduced date uses an augmented list identity so
legacy entries sharing a bill key can remain distinct.

For list-only runs, newly fetched validated list records are archived and
published while each page is handled. Cached pages restored on resume are not
automatically republished through those same callbacks.
No standard `items.jsonl` output is produced by this runner.

Persistent 5xx list-page failures are recorded in the resource's
`list_page_failures.jsonl` with offset/limit/date/source/error context.
By default no skipped page is permitted. With `max_skipped_list_pages>0`,
the runner can continue at **offset + 1**, not a whole page-width jump, after
recording the failure. Exceeding the configured allowance raises.
A permitted skip is a discovery gap, not evidence that the missing record was
ingested. `max_pages`/`max_items` are sampling controls, not completeness claims.

The separate [`checkpoint.py`](../../cdm/ingest/checkpoint.py) generic JSON
checkpoint helpers are not the runner's primary list-cache protocol.
Follow the runner's job/resource-local files when diagnosing worker resume.

## Item selection and hydration

After discovery, the runner applies the item limit, excludes already archived
identities/signatures, and optionally applies
[`StaleBillFilter`](../../cdm/ingest/stale_bills.py).
Archived IDs are read from resource and parent job roots; legacy attempt
JSONL files are compatibility inputs. Bill dates ending in midnight are
normalized for identity comparisons.

Bill resume also compares signatures comprising congress/type/number/title
and latest-action date/text when introduced-date variants are involved.
The stale filter compares indexed canonical bill state against list metadata:
new IDs, newer upstream update **dates** (day precision), or unhydrated
skeletons without subject/policy data need refresh. It is not a byte-level or
full-timestamp freshness check.

`_fetch_single_item()` derives item parameters and obtains the typed detail.
For legacy bill entries with `introduced_date`, it can select the matching
version from `detailUrl` responses before coercion, then appends that date to
the archived item ID. The indexer later collapses the date suffix back to
the four-part bill identity.

### Bill hydration evidence

For bills, [`Bill.add_bill_details()`](../../cdm/models/bills.py) requests:
`actions`, `amendments`, `committees`, `cosponsors`, `relatedbills`, `subjects`,
`summaries`, `text`, and `titles`.
[`BillDetailFetcher`](../../cdm/contracts/hydration.py) follows pagination,
detects cycles/changing totals/conflicting identities, enforces the page bound,
and validates response shapes. Expected counts must match distinct retrieved
records exactly. A valid exhausted pagination protocol can establish retrieval
completeness when no count is supplied; this is not authoritative global coverage.
Nonzero count/URL envelopes remain incomplete; authoritative zero is explicit
empty evidence. Object-shaped subjects preserve policy area and expand
`legislativeSubjects`; a missing list is not an empty list.

Counts follow actual endpoint semantics, not just array lengths. Pagination
accepts `count` and the legacy `total` spelling, rejects contradictory totals
and detects changes between pages. Co-sponsors are identified by member identity
**and sponsorship date**: withdrawing and later rejoining is two preserved
episodes, not a conflicting duplicate person. Contradictions within the same
episode still fail. `countIncludingWithdrawnCosponsors` is the overall expected
row count; `count` is the separate active count. Optional `expected_active_count`
and `fetched_active_count` retain that distinction in detail evidence, and both
must agree before completeness. Subject pagination includes a nonempty policy
area as one row alongside distinct legislative subjects, counted once even when
repeated across pages. Neither counter is a distinct-member/support score.

All nine relationship updates, including committees, validate before the original
bill mutates. Partial responses preserve existing richer arrays.
`add_full_text()` separately retrieves formatted text, rejects unsuccessful HTTP
responses and empty bodies, and cannot establish historical/text completeness.

The runner and indexer derive `hydration_status` from the versioned
`HydrationAssessment`, never from successful return alone. The assessment records
source, assessment time, per-detail counts/state/reasons and the scoped status.
`complete` requires all nine complete details; `partial` has assessed unresolved
details; `unknown` has no certified retrieval evidence. Legacy root labels and
old detail reports alone are not proof. Only an actual assessment supplies the
hydration timestamp/source markers. The assessment is retained in `_source`,
not added as searchable mappings; the existing root status remains searchable.

Bill detail API responses expose `hydration`; the UI warns for unknown/partial
without hiding source records, and treats older servers omitting the field as
unknown. Corrupt versioned proof fails validation rather than silently becoming
complete. GovInfo BILLSTATUS v3 and BILLSUM v2 normalization emit source-specific
unknown API assessments in new immutable snapshots; existing snapshots are not
rewritten. Full text, other sources, freshness, and resource/history coverage
remain independent obligations.
Existing assessment records remain readable with the new optional count fields;
this change does not retroactively recertify or relabel them.

Successful items are archived before publication under a write lock.
Ordinary item exceptions are logged and counted, and processing continues.
`AttributeError`/`TypeError` signal fatal model problems: the runner sets an
abort event and ultimately raises `FatalIngestError`.
Cancellation propagates distinctly rather than becoming an ordinary item
failure. A resource can otherwise finish with some ordinary item failures,
so successful resource/job status is not a universal zero-loss guarantee.

## Durable worker handoff and completion

[`IngestJobRunner`](../../cdm/workers/ingest_runner.py) atomically claims the
ledger row. A duplicate delivery of an already running/terminal job does not
start another execution. Concurrency-cap pressure defers dispatch.
The job output root is `{payload.outdir}/{job_id}`; each resource has a
subdirectory for discovery state, while archive/quarantine live at job root.

`IngestSession` supplies the pipeline's callbacks:

* `archive_record()`: insert into per-job `records.sqlite3`, and optionally
  upsert a retained record-library copy.
* `publish_record()`: append a resource record to its Redis stream.
* `flush_resource()`/`flush_all()`: submit incremental index work after the
  configured publication threshold or at final flush.
* `update_progress()`: update coverage counters and periodically poll for
  cancellation (60-second poll interval).
* `quarantine_validation_failure()`: persist raw rejected payload/error/source.

The job archive's compatibility class name is `JsonlRecordArchive`, but it
actually writes compressed SQLite records. It ignores duplicate keys rather
than replacing them. `retain_records=True` additionally updates a latest-value
library under `congress-{number}` or `all`, outside job-retention directories.
This library does not make the job archive itself overwrite old payloads.

Index jobs refer to stream, resource, group, batch size, archive root, and
optionally expected count. Partial jobs carry source-attempt/part identity
and omit a fixed expected count; full-resource jobs can provide one.
`summaries` is explicitly excluded from direct index-job submission.
`index=False` disables index jobs, not necessarily publication/archive sinks.

On pipeline exceptions, already fetched work is flushed for indexing before
the exception propagates, except the dedicated cancellation return.
The ingest row is marked succeeded after acquisition/index-job submission,
**not** after downstream index completion. Pipeline output includes
per-resource `meta.json` and a root `run_summary.json`.

[`JobSubmitter`](../../cdm/workers/dispatch.py) hashes sorted payload JSON;
resubmitting the same payload addresses the same row. The ledger also offers
package-specific GovInfo keys. Changing an output path, explicit default, or
attempt/part field can intentionally change generic job identity.
Celery transports job IDs; SQLite remains the durable lifecycle record.

[`FailureClassifier`](../../cdm/workers/failures.py) distinguishes transient
network/429/5xx, locking, cluster, and other retryable errors.
[`JobRecoveryService`](../../cdm/workers/maintenance.py) recovers stale work,
checks active workers, and budgets orphan redispatch; it does not make every
failure retryable. Retention protects unfinished-job dependencies, prunes
terminal job streams/archives, and preserves ingest-window coverage history.

For acknowledgment, pending-entry recovery, bulk partial failures, and the
expected-count archive fallback, see
[Redis consumption](../reference/indexing.md#redis-consumption-acknowledgment-and-replay).
These mechanisms are repeatable delivery/upsert behavior, not an exactly-once
transaction spanning HTTP, SQLite, Redis, broker, and search server.

## GovInfo acquisition

[`GovInfoDiscovery`](../../cdm/ingest/govinfo.py) supports `BILLSTATUS`,
`BILLSUM`, and `BILLS`, and the eight standard bill/resolution type slugs.
It can construct measure/text package descriptors, probe availability, or
enumerate official JSON directories with HTML-listing fallback.
BILLS text packages have session/version metadata; measure-level packages
do not require session. A 404 probe is `not_available`, distinct from a
network failure.

`GovInfoDownloader.download()` selects an artifact path, checks a prior
`complete` manifest plus matching local SHA-256 for a no-network cache hit,
otherwise performs a rate-limited conditional HTTP request.
It uses ETag/last-modified headers where present, writes `.part` then replaces
the destination, and records byte count/hash/provenance in `manifest.json`
and optional SQLite manifest storage. A BILLS bulk URL 404 triggers a content
URL fallback. Errors remove the partial file and persist failure state.
`extract_zip()` separately validates extraction paths; package runners parse
the returned XML artifact directly rather than automatically using ZIP mode.

The downloader cache is not proof that upstream never changed: a local
matching `complete` record can short-circuit network revalidation.
The package runner later records `parsed` state in SQLite; JSON and SQLite
manifests are separate writes. Parser-version fields document interpretation,
not a global automatic cache-invalidation system.

### XML adapters and worker stages

[`GovInfoPackageRunner`](../../cdm/workers/govinfo_runner.py) claims a package,
downloads it, chooses an adapter, marks the manifest parsed, archives the
normalized record using **package ID** within an immutable artifact/parser/check
snapshot directory, publishes it, creates
an expected-count-one index job, and marks acquisition succeeded.
Its index payload includes source attempt so re-parsing does not collide
with a previously succeeded index job.
The index job points to that snapshot only; older snapshots and legacy package
archives remain retained. Cached reparsing reuses the actual HTTP fetch time,
not the parser's wall clock, and identical snapshots deduplicate.
Dispatch failure after durable index-row creation can be recovered later.
`GovInfoBatchRunner` only fans out package IDs; its success is not package
or index completion.

| Adapter | Output |
|---|---|
| `GovInfoBillStatusParser` | Parent `bill:` record: identity/title, actions, sponsors/cosponsors, committees, related bills, summaries, subjects, titles, text versions, laws, amendments, CBO estimates, committee-report references, dates/chamber/latest action, and `govinfo:billstatus` provenance. |
| `GovInfoBillSummaryParser` | Parent `bill:` record with title, every available published summary, and `govinfo:billsum` provenance. |
| `GovInfoBillsParser` | `bill-text:{congress}:{type}:{number}:{version}` record with full text and `govinfo:bills` provenance. |

Adapters validate collection/package identity against the descriptor and parse
XML; the BILLS adapter retries once after escaping bare ampersands.
This is not the same validation as constructing a Congress API `Bill` model.
Default bill-text indexing updates only parent text; replacement mode instead
stores the text-version record under its own ID.

## GovInfo replay and reconciliation

[`reparse_govinfo.py`](../../scripts/reparse_govinfo.py) selects succeeded
package jobs by collection/congress, deduplicates package IDs, and can report
a dry run before requeueing. Re-parsing executes adapters/archive/publication
again, while the verified local download cache may avoid network access.
Legacy archives keep their original first payload; new snapshots do not rewrite
them. A parser change must have a new parser version to distinguish its output.

[`BillReconciler`](../../cdm/ingest/reconciliation.py) groups canonical parent
bill identities, including legacy introduction-date suffixes. Conflicting
Congress/type/number attributes or incompatible introduction identities are
errors, not permission to combine different records. Text-version IDs are excluded.
[`SourcePolicy`](../../cdm/config/source_policy.py) centralizes authority:
BILLSTATUS, Congress API, then BILLSUM, except summaries prefer BILLSUM.

[`SnapshotEvidence`](../../cdm/ingest/source_contract.py) requires a known parent
source, an unambiguous timezone-aware source version, and fields actually present
in the record. BILLSTATUS certifies only present XML containers, including
explicitly empty containers, using document-level `updateDate` and, when present,
the later `updateDateIncludingText`; nested action dates are not snapshot clocks.
Missing or unusable evidence gets an explicit reason, never invented authority.

For each proven-complete field, choose its authoritative source and newest
comparable version within that source. Explicit empty/null values may remove old
values; sparse/missing fields cannot. Equal-version contradictory values block
writes. Unproven legacy values are conservatively retained/unioned with conflict
and unverified-field diagnostics; their presence does not establish completeness.
Empty complete actions/subjects also clear derived latest action/policy area.
Source metadata retains package URLs, artifact hashes and parser versions.

`replay_govinfo_archives()` reads immediate child `*/records.sqlite3` archives
through read-only SQLite connections. The CLI defaults to **preview**, capped at
100 combined parent/text payload reads across packages. It validates projections
and reports quarantines without changing archives or indexing. Target inventory
reports aliases, document count and mapped top-level fields, not proof every
stored field is searchable. Explicit `--archives-only` skips search access and
reports target inventory unavailable. See the [runbook](../OPERATIONS_RUNBOOK.md#source-contract-preview-and-staging).

Only explicit `--write-staging` submits durable replacement work. Its target must
be an existing physical index with **no aliases**; preview limits are forbidden.
Source conflicts and bulk rejections fail the write rather than emitting a newly
completed report. Text children remain separate and do not automatically fill
parent `full_text`; no aliases are moved or source records deleted.

Reports distinguish operation status (`preview`/`completed`) from source coverage.
They retain `source_coverage=partial` and `promotable=false`: selected archives
cannot certify upstream history or release readiness. Discovery, hydration and
indexing counts have independent states/reasons; complete requires authoritative
expected counts and exact distinct identities. Estimated/unknown equality is not
complete, including zero. The required-history catalog lists every implemented
resource/global or Congress scope through the year-derived current Congress.
Missing applicability/support evidence is unavailable, not inferred not applicable.

Freshness is the age of a verified successful HTTP source check (24-hour target),
not publication date or replay time. Keep the latest check per contributing source;
the oldest of those governs combined freshness, so a fresh summary cannot mask
stale status data. Unknown checks remain explicit. Normal live additive indexing
is unchanged and strips snapshot/check controls; archive evidence and staging
field authority are audit data, not implicitly searchable serving fields.

## Voteview CSV ingestion

[`ingest_votes.py`](../../scripts/ingest_votes.py) creates the rollcall mapping,
then uses [`VoteIngestor`](../../cdm/ingest/voteview.py) to ingest both chambers.
By default it covers Congress 113 through a year-derived current Congress:

```bash
uv run python scripts/ingest_votes.py --congress 119 --refresh
```

`VoteviewClient.fetch()` caches chamber/congress members, rollcalls, and votes
CSVs under `data/voteview`; download writes then replaces a sibling file.
`ingest_range()` always refreshes the current Congress, regardless of the
explicit refresh flag. Historical cache files are reused otherwise.

`CsvReader` validates each row. Blank cells become null; chamber labels are
lowercased. `RollCallBuilder` maps ICPSR IDs to Bioguide IDs/parties, excludes
President rows and missing Bioguide IDs, then groups known-member votes by
roll number. Unknown-member votes are not included in position arrays.

Cast codes 1–3 map to yea, 4–6 to nay, 7–8 to present, and others to not voting.
Party 100 is Democrat, 200 Republican, and all others map to `I`.
Each rollcall includes position arrays, yea/nay counts, optional bill link,
party yea/nay majorities, a split flag when major-party majorities differ,
and defectors on those split votes. Ties do not create a party majority.

`bulk_upsert(..., "rollcall", replace=True)` replaces complete rollcalls and
raises on reported bulk errors. This path does not use job archives,
per-record Redis streams, or the Congress ingest ledger automatically.
Replacement does not delete old rollcall IDs absent from a refreshed source.

## Investigating incomplete data

1. Identify the acquisition path and canonical document ID; do not substitute
   a law number, ICPSR ID, Redis entry ID, or package ID for a bill/member ID.
2. Check ledger stage and per-resource counters; distinguish acquisition from
   downstream index completion and sampled runs from complete discovery.
3. Inspect resource checkpoint/cache, archive keys, and quarantine rather than
   assuming retry fetched everything anew.
4. Check pending Redis entries and index-job expected-count/replay outcome.
5. Audit the transformed source against declared mappings; retained `_source`
   fields may be intentionally unsearchable or have a mismatched shape.
6. For GovInfo, inspect both manifest and replay report, including bulk errors,
   parser version, source priority, and replacement-versus-parent-text mode.
7. Preserve required job archives before retention if replay is needed; use
   the retained record library for latest values, not immutable version history.
