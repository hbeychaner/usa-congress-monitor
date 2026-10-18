# Changelog

## 2026-10-19

### Changed

- A bill's Votes tab now merges Voteview roll calls (House and Senate, 113th Congress onward) with Congress.gov House votes, de-duplicated by chamber, session and Clerk roll number; Senate votes are now shown and each vote is labelled with its chamber.

### Added

- Each vote on a bill's Votes tab shows a chart of the yea, nay, present and not-voting share per party (`GET /api/v1/votes/{rollcall_id}/breakdown`); selecting a segment lists those members with links to their profiles.
- Bills page: a "Has votes" filter (`has_votes` on `GET /api/v1/bills/recent`) and a Votes column showing each bill's recorded vote count.

## 2026-10-18

### Changed

- Parties page language is now evidence-backed: each party shows the CRS subjects its bills carry more often than the other party's, plus phrases that must appear in at least 5 bills from 3 sponsors; clicking a phrase lists example bills. Plural and word-order variants are merged, rare member names are dropped from phrases, and a party or bipartisan group with fewer than 5 supported phrases shows no cloud instead of noise.
- Near-duplicate subjects (one is the other plus trailing words, e.g. "Housing and Community Development" and "... funding") are shown once.
- Approach summaries are written from subjects and sample bill titles rather than raw phrases, and avoid generic wording. Rebuild with `scripts/build_perspectives.py` to refresh stored results.

### Added

- Parties page (`/parties`, `GET /api/v1/parties`, `GET /api/v1/parties/topics/{id}`): the topics each party sponsors most per Congress, a per-party phrase cloud (bigrams and trigrams) with a one-sentence Ollama summary of each party's approach, and a "Bilateral Support" section for topics where at least a quarter of bills draw cosponsors from the other party. Procedural measures and ceremonial bills are excluded.
- `scripts/build_perspectives.py` builds and stores the analysis (`--congress` repeatable, `--all-topics`, `--dry-run`); learned cross-topic boilerplate, sponsor names and states are filtered from the phrases. Topic clusters ("Perspectives") are shown only when they pass the stability gate.

## 2026-10-17

### Added

- `make up`, `make down`, `make restart` and `make stack-status` (`scripts/stack.sh`) start or stop containers, Celery agents, the API and the frontend in one command; `ingest_launch_agent.sh stop` unloads the agents without removing their plists.

### Changed

- At most `ingest_max_concurrent_jobs` (2) ingest jobs run at once; further jobs are deferred and rechecked every `ingest_defer_seconds` (300s), so a few congresses finish instead of all crawling together on the shared API budget.

### Fixed

- Crash recovery asks the workers which jobs they are actually running before requeueing silent ones, so a laptop sleep no longer turns live ingest jobs into queued rows with duplicate messages; live jobs get their heartbeat refreshed instead.

## 2026-10-16

### Changed

- Ingest jobs are no longer failed after 6 hours: ingest tasks have a 5-day time limit (`celery_ingest_soft_time_limit`), and a task that does hit its soft limit retries in place instead of being marked failed and waiting behind other jobs.
- Running ingest jobs queue an index job every 100 new records (`ingest_partial_index_every`) instead of only when the attempt ends, so long jobs bank progress continuously and a retry or restart skips what is already indexed.

## 2026-10-15

### Fixed

- The admin ingest page's active-jobs table is now titled "Per Ingest Job" and notes that index jobs appear only in the Job Ledger, which counts every job kind.
- Ingest attempts that fail or hit the time limit now queue index jobs for the records they already fetched, so retries skip them instead of refetching the same bills every attempt (long-running congress jobs were looping without ever indexing anything).

## 2026-10-14

### Fixed

- Sparse historical API records no longer fail ingest: sponsors with blank `sponsorshipDate`/withdrawn dates or a null/missing `state`, recorded votes without a `url`, actions without `text`, and bill relationships identified by the Government Publishing Office now validate (about 2,900 items were being skipped).
- Crash recovery no longer requeues live long-running jobs: every running job now heartbeats its ledger row (`job_heartbeat_seconds`, 60s), so all kinds use the 15-minute stale cutoff and jobs stranded by a worker restart or kill are requeued within about 20 minutes.
- Coverage-gap planning treats queued, running and retrying windows as covered and no longer re-dispatches existing jobs, so waiting jobs are not duplicated against the API budget.
- Failed ingest jobs are requeued only when no ingest job is queued, running or retrying, so retries use idle API budget instead of competing with live jobs.
- Failure recovery and log trimming run on a dedicated `congress-maintenance` queue and worker, so saturated ingest workers can no longer starve the 5-minute recovery sweep.

## 2026-10-11

### Removed

- Admin ingest progress no longer calls Congress.gov on each page poll (it previously made uncached, unmetered requests that spent API budget); progress comes from the ledger only.
- Dead code found by a vulture audit and verified by AST/reference checks: unused response/meta models (`meta_models`, `data_types`, `consumer_models`), unused helpers and enums, and unused `Pipeline.run_*` and index-manager methods.
- Legacy local ingest CLIs `scripts/ingest.py`, `scripts/ingest_all.py` and `scripts/ingest_history.py` (they bypassed the job ledger and the shared rate budget), their tests, and the unused `cdm.services` package. Ingest unit tests import `cdm.ingest.runner` directly.

### Fixed

- `CDGClient` takes an injectable `sleeper`, so rate-limit backoff is tested with a recording fake instead of real waits.
- Ingest jobs now draw from one Redis-backed Congress.gov request budget (`SharedTokenBucket`, `INGEST_RATE_LIMIT_PER_HOUR` total) instead of one budget per job; concurrent jobs previously exceeded the API key's hourly limit and all stalled on 429 backoff.
- Integration tests are opt-in (`RUN_INTEGRATION_TESTS=1`) so a test run no longer spends API budget.

### Added

- Fresh-clone bootstrap: `.env.example`, `make env-init` (also run by `make local`) generates local secrets and links the compose env file, `make es-api-key` mints the OpenSearch API key; integration tests are skipped by default.
- Stale-bill refresh: `submit_ingest.py --refresh-stale` lists a Congress, compares each bill's list `updateDate` with the indexed `update_date`, and hydrates only changed bills or never-hydrated skeletons; admin progress targets just those bills.
- Record library: `--retain-records` upserts every fetched record into `data/record_library/congress-N/records.sqlite3` (latest write wins, outside job retention) for future reindexing.
- Admin ingest job table shows per-job speed (items/hour since start) and ETA, and a single `completed / total` progress indicator instead of the Observed/Target/Remaining columns.

- Topic page "Related Topics" chart: nearest topics by embedding-centroid similarity. Training now stores each topic's `centroid`; the current model was backfilled from its saved embeddings.
- Member profile "Legislative Topics" bars link to the topic page (`topic_id` added to member topic items).
- Topic-centered member graph: `GET /api/v1/graph/topic-neighborhood` centers on a metasubject, topic or CRS subject and shows its top sponsors with their collaboration/voting/topic links. The graph page has a "Centered on topics" mode with a picker.

### Fixed

- Admin ingest job table shows "Congress N" in the Scope column for jobs without a date window.

- `scripts/submit_ingest.py` accepts `--item-resources` so bills can be hydrated (bill detail fetches were silently skipped).

- Member graph no longer returns a 500 (shown as "Failed to fetch") when several seeds and a large limit push an edge query past the 10,000-result window.

### Changed

- Recounted missing legislative subjects per Congress (all of the 91st-107th, 117th-119th largely upstream gaps).
- Deleted archive directories of succeeded GovInfo jobs for the 118th and earlier (19 GB to 2.4 GB); ledger rows kept.
- README documents the topic model, metasubjects and archive retention.

## 2026-09-16

### Added

- Metasubject builder resolves duplicate names after naming: the largest group (or any override-pinned group) keeps the name and the rest are renamed by a second Ollama pass that sees example topics from every colliding group, with a deterministic fallback.

- Member graph metasubject overlay: `include_metasubjects` / `metasubjects_per_member` on `/graph/neighborhood` return each member's dominant metasubjects (from sponsored-bill assignments), with a "Show metasubjects" toggle and detail panels on the graph page.
- `SponsoredBillReader` shares the sponsored-bill lookup between the topic and metasubject overlay builders (constructor-injected).

- CRS subject tracking as a human-annotated complement to modeled topics:
  `GET /api/v1/subjects` aggregates legislative subjects and policy areas,
  `/bills/recent` accepts a `subject` filter, and member topic responses now
  include per-member subject/policy-area shares. Frontend: Topics page lists
  CRS subjects with counts, bill pages link subject badges to filtered bill
  lists, bills page gained a subject filter (URL-drivable via `?subject=`),
  and member profiles show a CRS Subjects breakdown.
- Fixed the govinfo BILLSTATUS parser never extracting legislative subjects:
  it looked for `<legislativeSubject>` elements, but the real feed nests them
  as `<legislativeSubjects><item><name>` — every hydrated bill had
  `legislative_subjects: []`. Already-processed packages need a manifest-forced
  re-parse to backfill subjects.
- GovInfo bulk downloads are now rate limited (`GOVINFO_RATE_LIMIT_PER_HOUR`,
  default 1,200 per worker process via a token bucket) after the unthrottled
  backfill drew connection-level throttling from govinfo.gov (SSL EOF, DNS
  resolution failures, 429s) and failed 4,061 package jobs.
- `scripts/relemmatize_indices.py` recomputes stale `*_lemma` fields in place
  for every index that declares lemma siblings, needed after the lemmatizer
  started dropping stop words.
- Topic API surface: `GET /api/v1/topics` and `/topics/{topic_id}` (topic list,
  time trend, representative bills), `GET /api/v1/bills/{bill_id}/topics`
  (per-bill topic labels), and `GET /api/v1/members/{bioguide_id}/topics`
  (topic share + per-quarter trend over the member's sponsored/cosponsored
  bills), all served from the latest model version in
  `congress-analysis-topics`. `MemberProfileResponse.topics` is now populated.
  Frontend: TopicsPage and TopicDetailPage render live model output, bill pages
  show topic badges, and member profiles show a Legislative Topics card with a
  topics-over-time breakdown.

- Discovery-phase BERTopic topic modeling: `cdm/utils/topic_modeler.py` wraps
  batch BERTopic (all-mpnet-base-v2 embeddings, bigram vectorizer with
  legislative-boilerplate stopwords) over bill titles + latest summaries, with
  `topics_over_time` for temporal trends and `transform` for assigning new
  documents. `scripts/train_topic_model.py` trains on the legislation index,
  saves versioned models under `models/topics/`, and writes topics,
  per-document assignments, and topics-over-time rows to the
  `congress-analysis-topics` index. Batch + periodic refit was chosen over
  online `partial_fit` (fixed cluster count, no outlier handling) because the
  corpus is bounded with a small daily trickle.

### Changed

- Resolved remaining pyright/ruff findings: typed `SimilarMember` construction, Pydantic aggregation models for the member subject overlay, `Self` return for `AgreementCounts.__iadd__`, and specs registry import ordering pinned with `isort: skip_file`.

- Typing sweep: `JsonObject`/`JsonValue` (covariant) and `Elasticsearch` client types replace most `dict[str, Any]`/`Any` in ingest, store, models, and job code; Elasticsearch responses are read via `.body`; `JobStore` returns typed `JobRow`/`PrunedJob`.
- `cdm/data_collection` helpers are classes: `UrlIdParser`, `CanonicalIdBuilder`, `PaginationResolver`, `IdStrategyApplier` (injected into `CDGClient`), and `SpecRegistry` (module aliases kept for spec registration).

- Worker code converted from module functions to injected classes:
  `cdm/workers/tasks.py` is now only thin Celery wrappers; logic lives in
  `IngestJobRunner`, `GovInfoPackageRunner`, `GovInfoBatchRunner`,
  `IndexJobRunner`, `ReconciliationRunner`, the planners (`DailyIngestPlanner`,
  `CoverageGapPlanner`, `StaticRefreshPlanner`), `JobRecoveryService`,
  `RetentionService`, `JobDispatcher`, and `JobSubmitter`, wired by
  `WorkerContainer` (`cdm/workers/runtime.py`). Job payloads are Pydantic
  models (`cdm/jobs/payloads.py`) that serialize to the same JSON, so ledger job
  ids are unchanged. `submit_job` and `index_streams` were replaced by
  `JobSubmitter.submit` and `StreamIndexer`; the unused
  `cdm/store/redis_indexing.py` was removed. Recovery now routes every job kind
  to its own task and queue (reconcile jobs were previously sent to the
  GovInfo task).
- Typed ledger rows (`JobRow`, `CoverageRow`) and JSON aliases
  (`cdm/utils/json_types.py`) replace `dict[str, Any]` in the job store and
  Redis stream code.

- Transient-error detection for worker jobs now unwraps
  `GovInfoDownloadError.__cause__` (requests SSL/connection/timeout errors were
  previously classified permanent), and the failed-job recovery sweep
  recognizes throttling signatures (`max retries exceeded`, `failed to
  resolve`, `sslerror`, `disk i/o error`) as retryable — the 4,061 failed
  backfill jobs requeue automatically.
- Topic modeling now runs on lemma fields: `build_topic_documents` prefers
  `title_lemma`/summary `text_lemma` for the c-TF-IDF vectorizer while keeping
  raw text for sentence embeddings (embedders degrade on lemmatized input).
- Fixed ~10-15s of overhead on every Celery task: each task constructed a
  fresh `JobStore`, whose init re-registered ingest windows for every ingest
  job row under an exclusive cross-process file lock — six workers serialized
  behind it, so even a no-op task took ~12s. The store is now cached per
  worker process and the init reconciliation is set-based (only repairs
  jobs with missing window rows plus one bulk status sync).
- GovInfo bulk backfill traffic (batch fan-out and package jobs) moved to a
  dedicated `congress-bulk` Celery queue; the ingest worker now consumes
  `congress-ingest,congress-bulk` round-robin. Previously ~83k backfill
  messages shared one FIFO queue with operational tasks, so the daily sweep,
  coverage-gap, retention, and `recover_failed_ingest_jobs` messages sat
  behind the entire backlog — beat kept sending recovery tasks that were
  never consumed, leaving crashed ingest jobs stuck in "running".
- Admin page now shows real backfill progress: a GovInfo bulk backfill card
  with a progress bar, package counts, trailing-hour throughput, and an
  estimated completion time, plus progress bars for the overall ingest window
  and each active job. The progress endpoint no longer enumerates every
  queued GovInfo package as an "active job" (211k rows with a COUNT query
  per batch every 10 seconds — it hammered the jobs SQLite the workers write
  to); the backfill is aggregated in two GROUP BY queries instead.
- Launchd ingest worker concurrency raised from 2 to 6: the two long-running
  daily API-ingest tasks were pinning both slots, starving the queued GovInfo
  bulk package tasks.

## 2026-09-15

### Changed

- Lemma fields are now reserved for semantically meaningful free text:
  legislation title/full text/summaries/notes/amendment purpose+description,
  amendment purpose/description, nomination description, treaty topic, and
  CRS report title/summary. Names, committee names, related-bill titles, and
  formulaic action strings dropped their `.lemma` multi-fields (keyword-only).
  `full_text` is now lemmatized into a searchable `full_text_lemma` sibling
  and carried through the version-ranked bill-text merge script; bill search
  queries `full_text_lemma` instead of `latest_action_text_lemma`, member
  search dropped its `name_lemma` clause, and the lemmatizer truncates inputs
  at spaCy's `max_length` so huge bill texts can't fail the pipeline.
  Mappings pushed live (additive) and workers restarted.
- Frontend surfaces the full indexed record set: bill detail now returns and
  renders action history, cosponsors, summaries, titles, text versions,
  committees, related bills, and the bill-text version code; member profiles
  now include honorific, birth/death years, current-member status, contact
  details (website, office, phone), leadership roles, and the full service
  history; the admin page gained a live system-status panel (new
  `/admin/system-status` endpoint) showing per-index document counts and job
  ledger counts by kind and status.
- Bill text now lives on the bill document: `bulk_upsert` converts GovInfo
  BILLS records into version-ranked scripted updates on the parent
  `bill:{congress}:{type}:{number}` document (later lifecycle stages win:
  `ih` → `enr`; API-hydrated text is never overwritten). The 24 existing
  `bill-text:*` child documents were merged onto their parents and deleted,
  the backend's child-doc fallback was removed, and the legislation mapping
  gained `full_text_version_code`/`full_text_version_rank` (pushed live).
- Documentation refresh: new C4-style Mermaid diagrams under
  `documentation/diagrams/` (system context, ingest→indexing→search data
  flow, application components, data model); worker-architecture.mmd updated
  for the GovInfo live-alias merge; README rewritten to cover the GovInfo
  bulk backfill path and link the diagram set.

- Bill backfill switched from the rate-limited Congress.gov API to GovInfo
  bulk data (unmetered): the GovInfo BILLSTATUS/BILLSUM parsers now emit
  snake_case fields matching the API hydration path and the legislation
  mapping (`introduced_date`, `latest_action.action_date`,
  `sponsors[].bioguide_id/full_name`, `policy_area`, `subjects
  .legislative_subjects`, committee `system_code`, summary
  `action_date/action_desc/version_code`), so bulk records merge cleanly onto
  the same documents. `queue_govinfo_bulk.py` no longer requires
  `--staging-version` — omitting it merges into the live alias. Queued
  BILLSTATUS+BILLSUM+BILLS for congresses 116–119 (~211k packages) and
  cancelled the four API hydration backfill jobs they supersede. Removed the
  completed one-time `scripts/migrate_jsonl_to_sqlite.py` and stale `data/`
  checkpoint directories.

### Fixed

- Pipeline audit follow-ups: hydrated bill items carried a
  `:{introduced_date}` id suffix from the ingest runner, so they indexed as
  duplicates instead of upserting over their skeleton list records — the
  indexer now canonicalizes bill ids (24 existing duplicates merged and
  removed). The legislation mapping gained `sponsors`, `policy_area`,
  `introduced_date`, `latest_action`, `type`, `reference_id`, and
  `version_code` (all previously unqueryable under `dynamic: false`, which
  made the `policy_area.name`/`sponsors.full_name` search clauses dead code);
  pushed live in place. Cancelled the four stale historical bill jobs
  (superseded by the hydration backfill). Queued a historical treaty backfill
  — the treaty index was empty because treaties only ever ran in 2-day daily
  windows.
- Bill hydration never ran through the worker pipeline: `Pipeline` ignored
  `fetch_items=True` for bills because `fetch_items_default=False` always won,
  so every indexed bill was a skeleton (no sponsors, actions, subjects,
  summaries, or text). New `PipelineConfig.item_resources` override lets
  payloads opt specific large resources into item fetch; daily, coverage-gap,
  and full-ingest payloads now pass `item_resources: ["bill"]`. Hydration
  backfill jobs queued for congresses 116–119.
- Bill detail API now falls back to the latest GovInfo `bill-text:` record
  (ranked by text-version lifecycle) when the bill document has no inline
  `full_text`.
- Coverage-gap ingest jobs now pass the current Congress, matching daily
  ingest. Previously they hit the bare `/v3/bill?fromDateTime=...` endpoint,
  which returns records from *any* congress touched by Congress.gov metadata
  backfills — ~16,000 bills from congresses 91–112 (e.g. 1978's SJRES 105 with
  a 2026 updateDate) leaked into the index this way. Existing old records are
  retained.

## 2026-09-14

### Added

- Unified member activity: amendments now index flattened
  `sponsor_bioguide_ids` / `cosponsor_bioguide_ids` (plus newly mapped
  `purpose` and `submitted_date`), and all 128,750 existing amendment docs were
  backfilled in place. New `GET /api/v1/members/{bioguide_id}/activity`
  endpoint merges bill and amendment activity (sponsor/cosponsor detection,
  per-type counts, type filter, pagination), and the member profile page gained
  an "All Activity" section with document-type filter and paging.
- spaCy lemmatization (`en_core_web_md`) for search: the mappings loader now
  injects a `{field}_lemma` sibling (whitespace analyzer) for every text field
  declaring a `.lemma` multi-field, `to_document` populates the siblings at
  index time (including nested fields like `actions.text`), and bill/member
  search queries lemmatize the user query and match the new fields. Query-time
  lemmatization degrades gracefully when the model is unavailable; index-time
  lemmatization fails loudly. Mapping additions were pushed in place to all 19
  live indices (existing docs gain lemmas as they are re-indexed).

### Fixed

- `IndexManager.ensure_aliases` (invoked by every index-job `create(...,
  exists_ok=True)`) no longer moves aliases that already exist — it only adds
  missing ones. Previously any routine index job could silently steal the
  read/write aliases back to the bare index, undoing a versioned migration's
  alias flip.
- Rebuilt `congress-legislation` from the canonical spec: the live index had
  drifted to `actions.source_system: keyword` while the spec (and all
  documents produced by ingest) use an object (`name`/`code`), causing
  `document_parsing_exception` failures for every bill with actions. All
  25,350 documents and both aliases were preserved; the two index jobs that
  failed on the bad mapping were requeued and succeeded.
- Pushed additive mapping updates (lemma multi-fields, `_meta.mapping_version`
  stamps) in place to the 18 remaining indices; a full audit now reports zero
  drift between live mappings and `documentation/opensearch_mappings.yaml`.
- Replaced the four failed index jobs targeting the deleted
  `congress-legislation-v118` staging index with live-alias replays (archive
  fallback), all succeeded; cancelled the archiveless legacy bill index job as
  superseded by the historical congress-scoped re-ingest.

### Added

- Added a daily retention maintenance task: prunes succeeded/cancelled jobs
  older than `RETENTION_DAYS` (default 30) from the ledger, deletes their
  Redis record streams and per-job archive directories, removes orphaned
  streams, and vacuums SQLite. Coverage history (`ingest_windows`) is always
  preserved so gap scheduling and future historical backfills are unaffected,
  and jobs referenced by unfinished index jobs are protected until those
  resolve.
- Index jobs now fall back to replaying the durable per-job archive when the
  Redis stream no longer holds the expected records (Redis restart or maxlen
  eviction), healing the "Indexed 0 records, expected N" failure class
  automatically.
- Cancelling a job now stops its in-flight run: the ingest progress callback
  polls the job ledger about once a minute and raises `IngestCancelledError`,
  which propagates through the item-fetch pool and ends the task without a
  retry instead of burning API budget until the soft time limit.

### Fixed

- Terminal job-store updates (`mark_succeeded`/`mark_failed`) no longer
  overwrite an ingest window that was cancelled while an attempt was still
  in flight; cancelled coverage windows stay cancelled.
- Cancelled the redundant `2022-11-06 → 2023-11-05` date-window job whose
  coverage fully overlaps the Congress 117/118 congress-scoped historical
  jobs, freeing shared API budget.
- Fixed historical ingest resume never skipping archived items: list-cache
  payloads are snake_case model dumps but were validated without `by_name`,
  silently dropping alias-only fields such as `introduced_date` and
  `latest_action`; archive record ids also carried datetime suffixes that
  never matched date-only list identities. Every retry refetched all items
  from scratch, which is why large historical jobs repeatedly exhausted the
  six-hour task limit.
- Added HTTP timeouts to bill and amendment full-text fetches; a dead
  connection previously blocked an ingest thread in a socket read
  indefinitely, stalling historical jobs without failing them.
- Made `SoftTimeLimitExceeded` failures retryable by automatic recovery. Now
  that resume dedupe banks progress across attempts, timed-out historical
  jobs converge instead of restarting from zero.
- Fixed `schedule_coverage_gaps` crashing with a naive/aware datetime
  comparison when completed coverage windows mixed timestamp formats.
- Automatic recovery now redispatches ingest jobs that remain queued in SQLite
  for more than 24 hours without a broker delivery, repairing the stranded-job
  state caused by interrupted worker or RabbitMQ handoffs.

## 2026-09-13

### Added

- Added macOS launchd supervision for the ingest worker, OpenSearch index
  worker, and Celery Beat. `make services` now installs and starts all three
  agents, while `make ingest-service-status` reports their state.
- Added persistent RabbitMQ configuration with a seven-day consumer
  acknowledgement timeout so historical tasks can survive extended laptop
  sleep and resume through durable job/archive recovery.

### Changed

- Updated the README and operations documentation to distinguish unattended
  launchd operation from foreground development commands and to prevent
  duplicate workers or Beat schedulers.
- Moved ingest activity classification and heartbeat timestamps into the
  backend's durable progress response, simplifying the admin page to display
  worker-owned state.

### Fixed

- Hardened job claiming, terminal-state protection, stale-job recovery, and
  archive/checkpoint resumption so interrupted workers do not overwrite
  cancelled jobs or repeat completed records.
- Accepted nullable or missing fields present in real Congress.gov bill
  payloads and corrected the OpenSearch mapping for structured
  `actions.source_system` values.

## 2026-09-04

### Fixed

- RabbitMQ backlog explosion: orphan-job recovery now claims stranded jobs
  atomically, caps recovery batches, and refreshes requeue timestamps so a
  crashed worker can no longer cause runaway duplicate redispatch. Lowered
  `RABBITMQ_PREFETCH` default from 200 to 10.
- `cdm/store/index_manager.py` re-parsed the OpenSearch mappings YAML from
  disk on every document validated during indexing; `load_definitions()` is
  now cached with `@lru_cache`.
- `cdm/jobs/store.py` had two near-duplicate atomic job-claim methods
  (`mark_running`/`claim_running`) that could drift; consolidated into one
  `mark_running(job_id, *, update_windows=True)`.
- `cdm/jobs/store.py` list/query methods (`stale_active`, `stale_queued`,
  `failed`, `queued`, `jobs`) had an N+1 query pattern (select ids, then
  `get()` each in a loop); now fetch full rows in a single query.
- `cdm/data_collection/client.py` retried HTTP 429 responses unboundedly
  (up to 1-hour sleeps, no attempt cap) while 5xx errors were capped; added
  `max_rate_limit_attempts` so rate-limit retries also give up and raise.
- `scripts/queue_full_ingest.py` dispatched a full historical plan
  (~2,000 jobs) to Celery in one unthrottled loop; added `--batch-size`/
  `--batch-delay` to pace dispatch.
- Unit test suite took ~3 minutes because ingest fixture tests exercised the
  real client rate-limit sleep (~0.72s per simulated API call, uncapped by
  test mocks). Added `tests/unit/conftest.py` to neutralize it; suite now
  runs in under 3 seconds (202 tests).
- `cdm/ingest/archive.py`, `cdm/ingest/govinfo.py`, and
  `cdm/backend/services/admin_service.py` used raw `sqlite3` connections and
  hand-written SQL alongside the rest of the codebase's SQLAlchemy Core
  usage; migrated to SQLAlchemy for consistency and to fix a PRAGMA
  multi-statement `executescript` call that isn't portable across drivers.
- `cdm/backend/services/admin_service.py` didn't recognize `govinfo_bulk`
  jobs (only `govinfo_bulk_batch`) when reporting active ingest progress,
  undercounting in-flight GovInfo package jobs in the admin UI.
- **Git tracked the docs directory as `Documentation/` (capital D) while
  every reference in code and docs used lowercase `documentation/`**
  (`cdm/store/index_manager.py`'s OpenSearch mappings loader,
  `tools/swagger_to_endpoint_specs.py`). Invisible on macOS's
  case-insensitive filesystem, but a fresh checkout on a case-sensitive
  filesystem (Linux CI, Docker, most production servers) would materialize
  `Documentation/` and silently break OpenSearch index creation. Renamed the
  tracked directory to `documentation/` to match.

### Removed

- Dead code with zero usages anywhere in the codebase, confirmed via
  workspace-wide search and a full test-suite re-run after deletion:
  `cdm/data_collection/collector.py`, `cdm/links/resolver.py`,
  `cdm/search/client.py`.
- The Streamlit dashboard (`cdm/streamlit/`), superseded by the React/Vite
  frontend under `frontend/app/`.
- `INGEST_CHECKLIST.md`, superseded by `README.md`'s Operations section.
- `cdm/backend/api/schemas/` — an entire package of re-export-only modules
  (`members.py`, `search.py`, `states.py`) with no consumers anywhere in the
  codebase; discovered via `ruff`'s `F401` unused-import check.

### Chores

- Fixed all `ruff check` findings repo-wide (unused imports, import
  ordering, an unnecessary `datetime` timezone replacement in
  `cdm/ingest/runner.py`); `ruff check .` and `compileall` are clean.

### Changed

- `scripts/health_check.py` and `scripts/monitor_ingest_progress.py` updated
  to match the current job/coverage schema.
- `frontend/app/src/pages/AdminIngestPage.tsx` simplified to match the
  updated admin ingest-progress API shape.

## 2026-08-22

### Added

- Automatic recovery of transient ingest failures through a Celery Beat task
  that runs every 10 minutes.
- Daily incremental ingestion with a two-day overlap, UTC date boundaries,
  current-Congress selection, and resource-scope-aware query parameters.
- A resource scope catalog that prevents unsupported date filters from being
  sent to static or global Congress.gov endpoints.
- Restart-safe JSONL/JSON-array migration tooling with bounded-memory parsing,
  throttling, progress reporting, integrity verification, and delete-after-
  success behavior.

### Changed

- Replaced legacy JSONL and large JSON-array archives with compressed,
  deduplicated SQLite record archives and list-page caches.
- List-page cache writes now use one SQLite transaction per page, reducing
  connection and commit overhead during large backfills.
- Transient HTTP, timeout, and connection failures retry with capped
  exponential backoff without a fixed terminal retry count. Non-transient
  failures retain bounded retry behavior.
- Corrected resource metadata: amendments and house votes are static/global;
  laws are the Congress-path-scoped resource.
- Removed the legacy whole-file checkpointed paginator; `IngestRunner` now
  owns checkpoint, cache, deduplication, and fallback behavior.

### Verification

- Migrated 140 legacy files containing 734,560 item rows.
- Verified 339 SQLite databases with `PRAGMA integrity_check`.
- Removed legacy migration sources and SQLite sidecar files after verification.
- Full unit suite passes: 128 tests.

## 2026-08-09

### Added

- Durable SQLite job records with idempotent submission and lifecycle status.
- RabbitMQ/Celery worker tasks for ingest and OpenSearch indexing.
- Redis Streams as the primary ingest-to-index handoff, with consumer-group
  recovery and acknowledge-after-bulk semantics.
- Celery Beat scheduling for overlapping daily ingestion windows.
- Bounded retry/backoff, late acknowledgements, and worker-loss requeue.
- `scripts/submit_ingest.py`, `make worker`, and `make beat` operational commands.
- Worker architecture diagram and operational documentation.

### Fixed

- Forwarded date-window arguments through the legacy ingest CLI wrapper.
- Made the local macOS worker command use Celery's `solo` pool to avoid
  Objective-C fork-safety crashes.
- Completed the Ruff and Pylance cleanup across production modules, scripts,
  tools, and tests, including explicit exception handling and typed Pydantic
  defaults.

### Changed

- Centralized endpoint HTTP methods and identifier-reference sources as string
  enums while preserving existing serialized values.
- Added a smoke-tested full-ingest planner with historical date windows,
  congress-scoped jobs, and idempotent queue submission.
- Added per-job, per-attempt durable archives for fetched list and item records,
  with durable persistence before indexing.