# Engineering improvement plan

**Reviewed:** 2026-11-03

**Status:** core reliability/consolidation work and bounded R03 repair/voting
publication are implemented; approved controlled Compose cutover and scoped
release acceptance are complete. R16 lightweight wiki preparation, refreshed
documentation/visuals and the publication-ready wiki are complete. Historical findings below describe the
original assessment unless followed by dated implementation evidence.
**Scope:** the current working tree, including the existing staged deployment
configuration. This is not a production health or data-completeness certification.

[Documentation home](README.md) | [Current architecture](architecture.md) |
[Data/indexing behavior](reference/indexing.md) |
[Original frontend requirements](../frontend/WEB_APP_IMPLEMENTATION_PLAN.md)

## Executive assessment

The solution is useful and substantially implemented. It does **not** need a
rewrite, more microservices, a graph database, or every index described in an
old design document.

The main complexity problem is **multiple overlapping control paths and
inconsistent meanings**, rather than simply too many classes:

1. Acquisition jobs have a durable ledger, while analytics builds have a
   separate subprocess/PID/JSON-file lifecycle.
2. Live indexing, archive replay and reconciliation do not always select the
   same destination or produce the same canonical bill projection.
3. "Newest analysis documents" can become readable before a build is complete;
   "job succeeded", "API online", "data available" and "corpus complete" mean
   different things but are not consistently surfaced.
4. Deployment configurations describe different worker capabilities, while the
   production image omits a runtime mapping resource.
5. Backend contracts, frontend response interfaces and live-server generation
   coexist; ordinary API imports also pull in training dependencies.
6. Several plans describe a target that differs from the shipped implementation,
   or retain unchecked tasks for features that now exist.

**Recommended order:** protect data and deployment boundaries; establish one
job lifecycle and explicit published analysis versions; make contracts and
failure states trustworthy; then simplify modules, queries and operations.
Do not begin with a framework replacement or indiscriminate file splitting.

## How to use this plan

- This is the canonical cross-solution implementation roadmap. Architecture
  chapters explain current behavior; this document specifies proposed changes.
- Preserve the original feature stories as requirements, not proof of delivery.
  Their current disposition is recorded in the [plan crosswalk](#plan-crosswalk).
- Start a change by selecting a finding ID, checking prerequisites and reading
  its source evidence. Update its status and acceptance evidence with the work.
- A finding is not complete because code exists or a checkbox was ticked.
  Record tests, migration/cutover evidence and remaining limits.
- Proposed targets and decision recommendations are **not already approved
  migrations**. Resolve the [decision gates](#decision-gates) before changes that
  alter deployment, source precedence, analytics semantics or supported scope.
- Keep this file and the root README/changelog current. Regenerate the local
  wiki from repository docs; do not maintain a separate wiki backlog.

### Priority and evidence conventions

| Label | Meaning |
|---|---|
| P0 | A correctness/deployment gate before affected replay, publication or cloud rollout |
| P1 | The next reliability/simplification work after those gates |
| P2 | Follow-on consolidation, product completion or measured optimization |
| Verified | Directly observed in source or a stated local check |
| Risk | A failure path follows from the design, but was not reproduced against live data |
| Unknown | Needs measurement, a product decision or deployment verification |

Priorities are sequencing recommendations, not security severity ratings.
All backlog entries are **open** unless explicitly updated with completion
evidence. No runtime refactor was performed during this assessment.

## Current solution versus recommended target

| Concern | Current implementation | Simpler target |
|---|---|---|
| Application shape | One repository; FastAPI, Celery, detached analytics scripts and React | Modular monolith with clear read, job-execution and analytics responsibilities |
| Job lifecycle | SQLite jobs for acquisition/indexing; file/PID state for topic/graph/perspective builds | One durable job identity/status/admission model; resource-specific execution pools |
| Delivery | RabbitMQ tasks plus Redis record streams and multiple recovery paths | Keep existing transports initially; one documented recovery owner and replay contract |
| Source authority | Archives, latest-record library and merged search documents have different semantics | Archives are replay evidence; retained snapshots are explicitly latest; search is a rebuildable projection |
| Projection | Different merge/replacement paths and destination fallback behavior | One tested normalization/projection policy shared by live and replay entry points |
| Analytics visibility | Topics selected by latest indexed timestamp; graphs use per-signal pointers | Explicit complete/published run manifests and readers pinned to published versions |
| Derived lineage | Some model/version fields; graph freshness inferred from timestamps | Exact input-model/corpus/config lineage and retention that respects references |
| API contracts | Pydantic plus generated TS types plus handwritten duplicate shapes | One backend schema source, deterministic offline generation and checked artifacts |
| User trust | Liveness badge, silent optional-section fallback, inconsistent missing-record errors | Explicit live/ready/fresh/partial/unavailable meanings and consistent error contracts |
| Deployment | Native, development Compose and GCP configurations differ | One supported reference topology per environment, tested capability/queue parity |
| Dependencies | Shared API/worker image with scientific training dependencies | Lightweight read composition and optional analysis dependencies, without lazy-import workarounds |
| Product classification | CRS metadata, discovery topics, metasubjects, perspectives and graph signals | Keep meanings distinct; use source classifications first, discovery explicitly exploratory |
| Planning | Several partially stale plans, including ignored local notes | This roadmap plus current reference docs and historical product requirements |

### Complexity worth retaining

- Canonical IDs, resumable checkpoints, immutable acquisition evidence,
  explicit latest-record snapshots and bounded requests.
- Late acknowledgement and idempotent writes: repeated delivery is not itself
  a defect. Do not promise exactly-once transactions across the stores.
- Pydantic boundary models, constructor injection, small domain collaborators,
  offline heavy computation and typed HTTP contracts.
- Versioned graph publication, source evidence links and supported-example
  thresholds for analytical language.
- Separate source metadata from generated labels and analytical interpretation.

The target is fewer **independent policies and failure meanings**, not fewer
recovery safeguards.

## Decision gates

| Gate | Recommendation | Decide before |
|---|---|---|
| D1: deployment scale and control-plane location | For a single-operator installation, prefer co-located API/workers with the same durable local control plane. If independent Cloud Run API instances are required, use shared durable job/status storage and remote worker execution. Never use a shared network-mounted SQLite file as the shortcut. | R01 production acceptance and R05 implementation |
| D2: source precedence and removals | Define field-level authority, sparse versus complete records and explicit removal semantics. Do not replace every sparse bill payload wholesale. | R03 and any corpus rewrite |
| D3: product scope and coverage | Choose supported Congress/resource ranges and required freshness. The old "1:1 mirror of all data" vision is not an implemented acceptance contract. | R03 coverage gates, R09 budgets and R14 classification |
| D4: discovery versus stable taxonomy | Keep CRS classifications authoritative and discovery views explicitly versioned/exploratory. Build a controlled multilabel taxonomy only if stable reviewed issue classification is a required product outcome. | R14 |
| D5: transport consolidation | Keep RabbitMQ/Redis initially. Benchmark a durable archive-batch-reference handoff before deciding whether Redis Streams is redundant. Redis may still be needed for shared request limits/coordination. | R13 transport removal |
| D6: UI library | Prefer standardizing the existing Radix Themes implementation rather than re-platforming to satisfy the historical shadcn checklist. | R10 shared UI work |
| D7: optional LLM provider | Deterministic labels/fallbacks should remain available. A Vertex client is optional product/infrastructure work, not required merely because IAM grants exist. | R14 cloud enrichment |

Record decisions and reasons here when agreed. PostgreSQL, managed brokers,
new client libraries and new analysis indices are options, not prerequisites
created by this assessment.

## Prioritized backlog

| ID | Priority | Work item | Prerequisites |
|---|---|---|---|
| [R01](#r01) | P0 | Make deployment artifacts self-contained and worker capabilities explicit | D1 for final production topology |
| [R02](#r02) | P0 | Unify destination and canonical live/replay projection rules | Destination inventory |
| [R03](#r03) | P1 | Specify source authority, identity, removal and coverage semantics | D2, D3; R02 before migration |
| [R04](#r04) | P0 | Publish only complete analysis; isolate experiments and previews | R02 for destination policy |
| [R05](#r05) | P1 | Give every long-running operation one durable job lifecycle | D1; preserve existing job compatibility |
| [R06](#r06) | P1 | Store exact analysis lineage and make retention reference-aware | R04 manifests |
| [R07](#r07) | P1 | Make contract generation offline and remove duplicate response types | Existing schema compatibility inventory |
| [R08](#r08) | P1 | Standardize errors, readiness and partial/freshness information | R07 schemas; R05 for job metadata |
| [R09](#r09) | P1 | Bound query work and define deterministic pagination/search behavior | D3; baseline measurements |
| [R10](#r10) | P1 | Finish reproducible frontend request/URL behavior without a new framework | R07, R08; D6 for shared components |
| [R11](#r11) | P1 | Automate boundary, failure and deployment acceptance tests | Start immediately; extend with each item |
| [R12](#r12) | P2 | Separate read/build dependencies and finish targeted typed/DI cleanup | R05, R07; import/size baseline |
| [R13](#r13) | P2 | Consolidate recovery, transport and index policy only where justified | R02, R03, R05; D5 |
| [R14](#r14) | P2 | Reconcile analytics/product goals and implement only justified gaps | D3, D4, D7; R04, R06 |
| [R15](#r15) | P2 | Reduce operational/configuration drift and unsafe process ownership | D1; R01 capabilities |
| [R16](#r16) | P2 | Keep documentation tooling useful without making it another platform | No runtime prerequisite |

<a id="r01"></a>
### R01 - Self-contained images and tested runtime capabilities

**Verified:** [Dockerfile.prod](../Dockerfile.prod#L11) copies project metadata,
`cdm` and `scripts`, but not the YAML resource used by the
[mapping loader](../cdm/store/index_manager.py#L35).
The GCP [worker Compose configuration](../deploy/gcp/docker-compose.worker.yml#L35)
defines consumers for ingest and index, whereas the
[dispatcher](../cdm/workers/dispatch.py#L27) also routes GovInfo work to bulk
and maintenance tasks require their configured consumer.
The [Cloud Run configuration](../infra/terraform/modules/apps/cloud_run.tf#L16)
permits multiple API instances without mounting the worker's local state.

**Impact:** a source checkout can work while its production image cannot load
mappings; a broker can accept work for queues with no consumer; file-backed
admin state/execution is not a valid distributed control plane.
These are source-confirmed configuration/packaging gaps, not evidence that a
particular cloud deployment has failed.

**Target/work:** package runtime mappings with the application or explicitly
copy the required resource; validate all configured task routes against actual
consumers; resolve D1; keep durable broker identity, volumes and restart ownership
explicit. Do not treat Terraform syntax validation as application acceptance.

**Acceptance:**

- An immutable production image loads mapping definitions without a repository
  bind mount and passes a representative projection smoke test.
- Every enabled routed queue has a healthy consumer in the selected topology;
  a test fails for a missing bulk/maintenance consumer.
- A job submitted through the deployed API is observable and executable from
  the worker control plane, including after an API restart.
- The frontend production image and relative API URL path are built and tested.
  No live data or destructive volume cleanup is needed for these tests.

<a id="r02"></a>
### R02 - One destination and canonical projection policy

**Verified:** [IndexJobRunner](../cdm/workers/index_runner.py#L91) warns and
falls back to the live write alias when an explicit target is missing.
[ArchiveReplayer](../cdm/workers/index_runner.py#L25) instead passes the
payload's target through unchanged. [Reconciliation](../cdm/ingest/reconciliation.py#L184)
writes both bill and bill-text records with `replace=True`; that
[bulk branch](../cdm/store/opensearch.py#L126) bypasses the normal bill-text
parent merge.

**Impact:** a replay can write somewhere other than intended, and two replay
paths can produce different bill/full-text storage shapes. A staging request
must never become an implicit live write.

**Target/work:** resolve one explicit destination before execution and pass it
through unchanged. Use one canonical projector/writer policy for a given input,
whether supplied by a live stream or an archive. Preserve deliberate diagnostic
raw-child storage only as a separately named, non-serving mode.

**Acceptance:**

- An absent explicit target fails without modifying live aliases.
- With no explicit target, the normal configured alias remains supported.
- Equivalent source records processed live, through archive fallback, or through
  reconciliation produce equivalent canonical bills, selected full text and
  searchable lemma fields.
- Tests cover partial bulk success, duplicate delivery, sparse API records and
  text-version order. Rollback restores the previous alias and projection.

<a id="r03"></a>
### R03 - Explicit authority, removals, identity and completeness

**Verified:** the [bill merge](../cdm/store/opensearch.py#L149) preserves nonempty
existing values and unions incoming lists; it is not an authoritative deletion
protocol. [Index normalization](../cdm/store/indexer.py#L16) canonicalizes bill
identities. [Resource mappings](opensearch_mappings.yaml) use `dynamic: false`;
undeclared fields can survive in `_source` without becoming searchable.
Declared sponsorship/vote-position bridge schemas do not mean normal runners
populate them. See the [complete identity/storage reference](reference/data-models.md).

**Impact:** a removed upstream relationship can persist; repeated evidence is
not the same as a current snapshot; field/index existence is not proof of
coverage. Conversely, replacing a sparse record can destroy richer information.

**Target/work:** define a small per-resource/source contract for canonical ID,
field authority, missing versus explicit-empty values, deletion/tombstone
semantics, searchable fields and provenance. Distinguish:

- immutable attempt/source archive;
- retained latest accepted snapshot;
- normalized serving projection;
- acquisition coverage, hydration coverage and indexing coverage.

**Approved policy (D2/D3):** use field-aware authoritative
snapshots. Accept verified newer, complete fields; preserve missing/sparse
fields; permit explicit removals only with completeness evidence. Retain all
source archives. Equal-version conflicts and incomparable/unknown versions must
be explicit rather than resolved by arrival order; canonical identity collisions
must block promotion rather than silently combine different records.

Required scope is **all implemented resources across all source-supported
history**, not only recent core entities. Report gaps explicitly and distinguish
acquisition, hydration and indexing coverage. A successful job or multiple
sources do not prove completeness. Count expectations must identify whether they
are authoritative, estimated or unknown; missing evidence is not permission to
label a resource/Congress complete or not applicable.

Check current-Congress updates daily with a 24-hour freshness target. Measure
check age separately from the upstream record's update/publication date so an
unchanged older record can still have a recent successful source check. Unknown
freshness remains explicit. Historical data receives periodic reconciliation;
its exact cadence and upstream limitations must appear in coverage evidence.
These are acceptance requirements, not a claim that the existing scheduler or
live corpus already meets them.

**Implemented shadow contract:** typed evidence/coverage/freshness models,
deterministic field-aware bill reconciliation, source/canonical-identity conflict
guards, actual HTTP-check clocks, immutable versioned normalization snapshots,
read-only bounded preview and unaliased physical staging writes. Source controls
do not leak into unchanged live additive merging. See the
[ingestion contract](guides/ingestion.md#govinfo-replay-and-reconciliation) and
[explicit operator procedure](OPERATIONS_RUNBOOK.md#source-contract-preview-and-staging).

**Retained-source evidence:** an explicit offline preview discovered 49,207
package archives and opened 100, reading exactly 49 parent and 51 text records.
That bounded sample had no quarantine, unknown freshness and partial coverage.
Its 1,082 required resource/history scopes were unavailable for lack of
certification evidence; this is not proof those upstream resources are absent.
**Live inventory (2026-11-03 UTC):** with explicit approval, suspended 19
processes across the four legacy worker/Beat service trees, then started only
the existing Elasticsearch container against its retained volume. Elasticsearch
9.3.1 now serves all **21 declared families**, plus three auxiliary indices:
24 physical application indices contain 2,604,203 projected documents. All
declared read/write aliases resolve to their expected physical index.
Application indexing/deletion/failure counters remained zero during the
inventory; no documents, mappings or aliases were changed.

The legislation alias resolves to `congress-legislation`, with **344,672**
documents: 344,536 bill and 136 law projections, observed across Congress
91-119. Of these, 192,679 carry `hydration_status=complete`; 151,993 lack that
label. These labels/counts do not independently certify upstream completeness.
The live 100-record archive preview retained 49 parents/51 text records and no
quarantine. A separate 100-document serving identity spot check found no missing
source IDs, document/source ID differences or source-contract errors; this is
not a corpus-wide collision proof.

**Remaining inventory findings:**

- `congress-analysis-graph` lacks seven declared field paths:
  `congresses`, `shared_votes`, `source_model_version`, and
  `by_congress.{shared_votes,agreed_votes,shared_split_votes,agreed_split_votes}`.
  No declared field-type or dynamic-policy differences were found. Schema
  comparison did not certify analyzer/query equivalence.
- Sponsorship and vote-position bridges each contain zero documents. Their
  existence is not evidence that the derived relationships are populated.
- Source-check freshness, authoritative historical expectations and nested
  resource history remain uncertified; flat Congress buckets cannot establish
  global coverage.
- Cluster health is yellow (103 active primary shards; 37 unassigned shards),
  not a high-availability certificate. The existing container still has
  `restart=no`; updated Compose policy has not been applied to that runtime.

The live serving inventory gate is now **verified**, replacing the previous
endpoint-unavailable blocker. Its read-only JSON report, bounded preview and
process-suspension record are retained as session deliverables.

**Scope gate:** bill staging semantics and fixtures are implemented; all-resource
live authority, source-supported historical coverage and actual freshness/cadence
compliance are not certified. Graph-schema and empty-bridge findings need an
explicit release disposition, not an automatic rewrite. No live rewrite, cutover,
archive deletion or acquisition is authorized. R03 remains open for those live
evidence gates; release acceptance must carry them explicitly.
Elasticsearch remains online; legacy workers/Beat remain temporarily suspended
for review. This is not a completed native-to-Compose transition; follow the
[operator hold guidance](OPERATIONS_RUNBOOK.md#temporary-live-inventory-hold).

**Hydration follow-up:** source-aware versioned proof now drives ingest,
indexing, bill detail responses and visible unknown/partial UI states.
Subjects objects and exact distinct counts are validated, incomplete updates
preserve richer records, and failed hydration cannot partially mutate a bill.
Unversioned complete labels do not establish proof. All 3,047 provenance-free,
unlabeled records have URL pointers, not evidence of successful hydration;
20 bounded read-only library identity lookups found no retained matches.
No live relabel/reingestion was performed, and recovery scope remains explicit.
See [hydration semantics](guides/ingestion.md#bill-hydration-evidence).

**Verification before hydration hardening:** 447 selected regressions pass with UserWarnings treated
as errors; scoped Ruff and Python type checks report no issues. The isolated
real-store regression established 43 passing cases, with the 21 relevant
pipeline/projection cases rerun after final changes. A retained-version fixture
also verifies old archive bytes remain unchanged and each index job pins its own
snapshot. The pre-existing staged worker Compose blob is unchanged.

**Size before hydration hardening:** production Python is 32,199 lines versus 31,267 before this increment
(+932; tests excluded). This adds explicit correctness/coverage contracts rather
than delivering a net reduction; unrelated legacy formatting growth was removed.

**Hydration verification:** 514 selected Python regressions and 12 isolated
Elasticsearch projection/merge/read cases pass; 67 frontend tests, contract
generation, the production build and eight targeted desktop/narrow browser
cases pass. Production
and hydration-unit types plus scoped Ruff are checked separately.
Current production Python (`cdm/`, `scripts/`, `tools/`, tracked and unignored
new files) is 33,121 lines: +922 from the preceding 32,199 baseline, not a net
reduction. The new dedicated hydration unit suite is 386 lines, counted separately.

**Graph schema/coverage follow-up:** the declared graph schema now includes
`shared_topics`, bringing the live missing-path disposition to eight.
Typed preflight rejects drift before edge writes/pointer publication and does
not repair schemas or aliases. Edge writes share the pointer's physical target.
Health exposes schema drift/unknown scope; empty legacy scope is not a certified
empty graph. The unused bridge indices have no implemented population path.

The read-only input audit found all 1,824 Congress 114 roll calls unlinked,
caused by decimal-string versus integer-string ICPSR joins in retained CSVs.
Typed numeric identities and explicit linkage checks recover all 1,322 House
and 502 Senate roll calls offline, including 984/310 party-split votes.
No live source replacement, mapping update or graph rebuild was performed.
All live pointers lack Congress scope; topic lineage/current publication remain
unverified. See [graph acceptance and rollout gates](guides/analytics.md#schema-and-source-coverage-gates).
Current production Python is 33,225 lines (+104 from the hydration baseline;
tests excluded), adding safeguards rather than a net reduction.
Verification: 576 selected regressions with UserWarnings as errors, 42 isolated
real-store graph/topic/availability/read-budget/projection cases, 67 frontend
tests and all 42 desktop/narrow browser cases pass. Scoped Ruff, Pyright and
the production frontend build pass. Disposable services were removed; all
19 held process identities/start times and zero live application write counters
were reverified. The pre-existing staged worker Compose blob remains unchanged.

#### Ordered graph repair rollout

Execute these gates in order. **Gates 1, 2 and voting-only gate 3 are approved.** Gate 2 is limited
to the sealed 1,824 source replacements and eight additive mapping paths after
backup/restore proof and precondition checks. This does not authorize alias
changes, upstream acquisition or worker resumption. Gate 3 separately permits
only the accepted voting pointer after source/history and real serving checks.
Do not use the ordinary graph-build command for a staging exercise: it publishes.

1. **Capture, stage, and rehearse rollback — approved implementation scope.**
   - Recheck serving availability and the recorded worker hold. Keep search
     read-only and use retained CSVs only; never refresh/download source files.
   - Create a new, non-overwriting local evidence directory. Capture physical
     index identity, mappings/settings/aliases, raw graph-pointer before-images,
     and the complete configured voting-input scope (Congress 113 onward).
     Preserve document IDs, source bodies and sequence/primary-term metadata.
   - Copy and hash all six Congress 114 CSVs. Reconstruct the 1,322 House and
     502 Senate roll calls; require exact identity-set equality with captured
     Congress 114 documents, no duplicates, and no unexplained metadata changes.
     Retain unrelated source fields; only reviewed voter/party-derived fields
     are repair candidates. Emit exact field differences rather than a count-only
     comparison. A mismatch fails the gate; it must not become a partial success.
   - Seal input files and before-images with checksums. Verify the bundle before
     reuse; reject missing/changed files, unsafe paths and incomplete captures.
     Record source scope and freshness limits, not global historical completeness.
   - Require a different Elasticsearch cluster UUID for rehearsal. Use fresh,
     owned, unaliased physical indices; never run the exercise against serving
     indices or accept arbitrary restoration targets. Capture itself needs no
     staging server and performs no search-store writes.
   - Replay frozen inputs into the isolated copy, apply only the 114 candidate
     repairs there, and build the full configured voting graph without changing
     its active pointer. Export the candidate pointer and complete edge set with
     hashes. Check source identities, all stored source bodies, exact edge counts,
     Congress scope and searchable Congress 114 vote evidence.
   - Exercise pointer promotion and rollback **only on the isolated copy**.
     Restore exact original source/pointer images and verify the whole cloned
     source corpus, including unaffected Congresses. Inject failures and prove
     failed staging cannot publish a serving pointer. Remove only owned scratch
     indices; retain the sealed bundle and acceptance report.
   - Stop after this report. Revalidate source versions, aliases, pointers and
     resource budgets before seeking gate 2 approval; a frozen bundle is not
     permission to overwrite later changes.
2. **Live schema and bounded source repair — approved and completed.**
   - Review gate 1 evidence, unexpected differences (must be zero), disk/memory/
     cluster health and backup/restore readiness. Approve an exact repair
     manifest, not an unrestricted ingest job.
   - Add only the eight identified graph paths; do not delete/recreate indices
     or move aliases. Mapping additions do not retroactively index old values
     and cannot simply be removed in place.
   - Recheck captured identity/version preconditions and replace only the
     approved 1,824 roll calls with conflict protection. Stop on concurrent
     changes or any rejection; verify identities and every intended field.
   - Use before-images for an explicitly approved, conflict-checked source
     rollback if needed. Schema rollback requires a restored/rebuilt index,
     not deleting newly added mappings. Do not mix this with worker restart.
3. **Live voting graph promotion — approved; collaboration/topic remain gated.**
   - Begin with voting over Congress 113–119 inputs, not a 114-only graph.
     Verify the sealed input/candidate evidence remains applicable; otherwise
     recapture and restage. Validate complete writes, refresh, searchable nested
     evidence, finite scores, API/browser behavior and observed Congress scope.
   - Switch only the selected signal's pointer with concurrency preconditions;
     preserve the old pointer and old edges for rollback. Do not implicitly
     promote collaboration/topic signals or prune historical versions.
   - Collaboration is a later explicit selection. Topic requires a separately
     verified current topic publication and exact source-model lineage; never
     infer that lineage from timestamps or labels.
4. **Operations and release acceptance — separate approval required.**
   - Retain unused bridge indices without invented backfills. Keep the 3,047
     provenance-free hydration records in their separate bounded-recovery track.
   - Plan an updated-code managed restart/Compose transition after inspecting
     durable jobs, leases, queues and broker health. Do not blindly SIGCONT old
     processes; paused processes do not reload fixes.
   - Re-run release acceptance and explicitly resolve/accept historical coverage,
     freshness and infrastructure limitations. Only then finalize documentation
     and the wiki. Commit/push/publication remain separately gated.

**Gate 1 implemented and rehearsed locally (2026-11-03 UTC).**
The [capture/rehearsal CLI](../scripts/stage_graph_repair.py) has only `capture`,
`verify` and `rehearse` operations, with no live repair/promotion operation.
`GraphBuildJob.stage()` now exports a typed candidate without publication;
ordinary job builds retain their publication behavior. Providers live in the
existing worker composition root, preserving lightweight API/submission imports.
See the [artifact and command contract](OPERATIONS_RUNBOOK.md#sealed-graph-repair-rehearsal).

The sealed real capture contains 12,621 source records, exactly 1,824 Congress
114 repairs (1,322 House/502 Senate), raw pointers, physical metadata, field
diffs, version preconditions and six retained CSVs. A different-cluster rehearsal
produced **116,450 voting edges across Congresses 113-119**, including **48,655**
with searchable Congress 114 evidence. It verified unchanged staged pointers,
full source content, export counts/scores, exact original source/pointer
restoration and owned-index cleanup. No unexplained source differences occurred.
Candidate files and the acceptance report persist outside the repository.

Acceptance includes tampered/missing/symlinked input rejection, duplicate/
inconsistent IDs, capture bounds, identity/metadata mismatches, pointer drift,
same-cluster rejection, injected staging failure, source/pointer concurrency
conflicts and rollback with a previously absent pointer. The two-cluster test is
wired into CI with a second bounded Elasticsearch service. This adds explicit
safety tooling, not a code-reduction claim; tests are counted separately.
Verification: **587 selected Python regressions, 44 real-store acceptance
cases and 67 frontend tests**, with clean scoped Ruff/Pyright, unchanged generated
API contracts and a successful frontend build. Deterministic documentation
generation/link checks pass, including tracked worktree deletions. The only
frontend build notice is the existing large-chunk advisory.
At gate 1 closeout, no live source, mapping, alias or pointer changes were made,
and no workers resumed. The operator subsequently approved gate 2. Its
version/topology/backup/resource checks must be repeated immediately before
an approved write; the capture is frozen evidence, not continuing freshness.

**Gate 2 completed (2026-11-03 UTC).**
The [source-repair CLI](../scripts/repair_graph_sources.py) first backed up all
**1,148,223 physical graph documents**, including historical versions, to a
sealed 1,116,363,857-byte local before-image. Every document/ID/count was restored
and verified with the original field mapping on a fresh owned index on a
different cluster, then that index was removed. Source versions, aliases,
pointers, cluster health and budgets were revalidated before live writes.

Exactly the eight approved mapping paths were added and are searchable with
their declared types. Exactly **1,824 Congress 114 source documents** were
replaced using sequence/primary-term preconditions: **1,322 House and 502 Senate**.
All **12,621** scoped source bodies now match the approved originals plus
repairs; the other **10,797** records retain their original versions/content.
Every acknowledged write has a fsynced receipt. Complete graph before-image/
version verification passed after repair; graph document writes were **zero**,
and active pointers/aliases remain unchanged.

Application counters are exactly **1,824 indexes, zero index failures and zero
deletes**. All **19** original worker processes remain suspended and the
pre-existing staged deployment blob is unchanged. Cluster health remains yellow
because of unavailable replicas, with no unavailable primaries; this is not a
replica-durability certificate. The sealed plan, raw backup, per-write receipts
and successful application report persist outside the repository.

Verification: **587 Python regressions and 55 real-store cases** passed,
including partial rejection, lost responses, interrupted rollback/resumption,
concurrent version conflicts, changed backup/pointers, same-cluster refusal and
capture bounds. All **67 frontend tests**, unchanged API contract generation
and the frontend production build passed (existing large-chunk advisory only).
Scoped Ruff/Pyright and documentation generation/link checks pass.
Production Python is **33,908 lines** versus the reproducible gate-one
closeout count of **33,202 (+706)**; this is safety/execution tooling rather than
a reduction increment, and test code is separate.

**Gate 3 completed (2026-11-03 UTC).**
The [voting-only promotion CLI](../scripts/promote_voting_graph.py) installs
create-only edges without publication, seals their exact bodies/versions and
requires measured real API/browser acceptance. Its `accept` operation validates
both passing viewport results and their embedded typed API responses against
the exact staged version, member and Congress 114 availability. Publication
revalidates every source/history/candidate precondition and uses the original
raw voting pointer's sequence/primary-term CAS. An acknowledged-pointer receipt
supports exact raw pointer rollback without pruning; unknown responses never
establish rollback ownership.

The live voting pointer now selects
`20261103T091601Z-4b9d26b3167844a790a5f1aded61143f`, serving **116,450 edges**
over explicit Congress **113-119** scope, including **48,655** searchable
Congress 114 edges. All **1,148,223** original physical graph documents were
verified with only the intended voting pointer replacement; historical edge
sources/versions, sibling pointers, aliases and all **12,621** scoped source
bodies/versions remain unchanged from the successful source repair.
The physical graph now has **1,264,673** documents. Real API and desktop/narrow
browser checks passed before and after publication; topic analysis correctly
remains unknown.

The exact gate-three delta is **116,451 successful indexes** (116,450 edges and
one voting pointer), **zero failures and zero deletes**. Cumulative application
counters including gate two are **118,275/0/0**. All 19 original processes remain
held; no live rollback, pruning, additional signal publication or worker restart
was performed. Sealed staging, measured acceptance, pointer receipt and
successful publication reports persist outside the repository.

Verification: **587 Python regressions, 71 isolated real-store cases, 67 frontend
tests, 42 mocked browser cases and four real browser cases** pass. Scoped
Ruff/Pyright, contracts, production frontend builds and deterministic
documentation checks pass. Production Python is **34,666 lines**, versus
**33,908** at gate-two closeout (**+758**); this adds bounded safety tooling, not
a code-reduction claim. Test Python is counted separately (**19,529 lines**).

**Gate 4 closeout (2026-11-03):** the user approved a controlled Compose cutover,
not full acquisition/analytics scheduling. Verified backups cover 198,359 files,
99,044 archive SQLite databases and the 628,077-row ledger. All old native
registrations/processes are retired; current-code API/UI and one bounded
index/maintenance worker are managed by Compose. Acquisition, analytics
publication, Beat and automatic retention scheduling remain off. Scoped release
acceptance passed; see the [dated evidence and limitations](OPERATIONS_RUNBOOK.md#controlled-cutover-acceptance).
R03's broader historical/freshness/source-authority work is **not** globally
closed. Collaboration/topic promotion, pruning, broader worker roles, sustained
unattended operation, commit/push and wiki publication remain separate gates.

Final verification includes **593 configured Python regressions, 93 isolated
real-store cases, five production-image/broker cases, 67 frontend tests, 42
mocked browser cases and two actual managed desktop/narrow browser cases**.
Exact sealed sources, graph history/candidate versions and pointers survived
the managed restart. Updated diagrams pass syntax/extension preview and rendered
edge/node/label geometry checks. Full generated references/wiki checks pass;
lightweight wiki checks also run with Node absent from `PATH`.

Application Python (`cdm` + `scripts`, tracked/nonignored existing files) remains
**34,666 lines**, unchanged from gate three. Documentation/release tooling
(`tools`) is **836 lines**, reported separately; test Python is **19,635 lines**.
This gate reduces active runtime roles/control paths, not application line count.

**Publication finalization (2026-11-03):** commit/push and separate wiki
publication are now user-approved. The full regression suite exposed a missing
`hydration_assessment` mapping declaration; it is now explicitly source-only,
preserving API evidence and the existing derived searchable status. Mapping
audits are included in CI rather than relying solely on the narrower release
selector. This changes the declared mapping artifact, not live indices/data.
Final offline validation passes **883 tests**, with **144 external/integration
opt-ins skipped**; those skips are not a claim of upstream acceptance. The
separately executed isolated release gates remain recorded above.
The first remote CI run exposed a Compose CLI portability issue in the test
harness: overriding `PWD` did not also change its actual working directory.
Rendering now runs from the isolated project directory, retaining exact mount
assertions and reporting observed mounts on failure; runtime topology is unchanged.

**Acceptance:**

- Fixtures cover correction/removal, sparse-after-rich input, equal/newer/older
  source versions and canonical-ID collisions.
- Each supported resource/Congress has explicit `complete`, `partial`,
  `unavailable`, `not_applicable` or failed disposition, with stage counts and
  reasons. Expected counts are documented as authoritative or estimated.
- A successful job does not silently imply complete hydration/indexing.
- Migration starts with a read-only collision/field/alias inventory, a bounded
  shadow projection and comparison; no source/archive deletion is prerequisite.

<a id="r04"></a>
### R04 - Complete analysis publication and safe experiments

**Initial finding (before the implemented publication changes):** the legacy
topic writer indexed versioned rows in bulk and readers chose the newest
timestamp, not a complete/published marker. Capped runs shared the ordinary
namespace unless paired with dry-run, whose check followed fitting/cache writes.
The current execution boundary is [TopicTrainingJob](../cdm/topics/training.py);
the historical finding is not its present publication contract.

**Risk:** partially written or deliberately sampled results can become the
"latest" model even if the build later fails. A preview is not read-only today.
No live corpus corruption was reproduced in this assessment.

**Target/work:** use an immutable run manifest plus explicit validated publication,
reusing the existing graph pointer concept rather than introducing another
registry service. Readers use the published version, not "largest timestamp".
Keep experimental/sample output separate. Make cache-writing preview behavior
explicit and opt-in where it could affect the shared serving cache.

**Acceptance:**

- Inject failure after the first successful result batch: readers still see the
  prior published model.
- Publish only after all required kinds/counts and corpus scope pass validation.
- Capped and experimental runs cannot replace a production pointer accidentally.
- Preview mode states and tests exactly which writes/external calls are allowed.
- A publish operation can roll back to the previous compatible complete run.

<a id="r05"></a>
### R05 - One durable lifecycle for acquisition and analytics

**Initial finding (before durable analytics consolidation):** the ledger had
no analytics kinds. Removed topic/graph/perspective launchers used separate
check-then-spawn, PID and JSON status paths; atomic status-file replacement did
not make concurrent admission atomic. Current submission and execution use
[AnalyticsJobs](../cdm/jobs/analytics.py) and
[AnalyticsJobRunner](../cdm/workers/analytics_runner.py).

**Impact/risk:** duplicated lifecycle policies, host-local observability and
different recovery behavior. Existing single-process duplicate-start tests do
not prove safe concurrent admission across API processes.

**Target/work:** routes/CLIs/schedules submit typed named jobs to the durable
control plane; workers own execution. Reuse existing lifecycle/idempotency
primitives, adding analytics payloads and resource-specific queues/limits.
A worker may supervise a heavy subprocess when isolation is needed, but the
subprocess is not a second authority for job state.

**Acceptance:**

- Concurrent identical submissions produce one logical active job.
- Status survives API/worker restart and is visible from every supported API
  instance; orphaned execution has an explicit recovery disposition.
- CLI, admin and schedule paths use the same validated payload and lifecycle.
- Existing queued job payloads/task names remain compatible during migration.
- CPU/GPU/memory limits, cancellation and stage progress are specified for
  long jobs rather than inherited accidentally from short task defaults.

<a id="r06"></a>
### R06 - Exact lineage and reference-aware retention

**Initial finding (before explicit lineage/retention changes):** graph pointers
lacked source-model versions, health inferred drift from timestamps, and removed
topic cleanup kept newest observed versions through asynchronous deletion.
Graph signals had separate publication/retention rules. Current boundaries are
[GraphVersionPointer](../cdm/graph/models.py),
[GraphBuildJob](../cdm/graph/job.py) and the read-only
[RetirementReporter](../cdm/topics/retirement.py).

**Impact:** model age is not exact input lineage, and independently retained
outputs need not describe the same corpus/model. Asynchronous cleanup request
success is not deletion completion.

**Target/work:** store source model/run ID, corpus scope/fingerprint or watermark,
code/config/model identity and build status in run manifests.
Pin each reader/build to its inputs. Prune only unreferenced eligible versions,
tracking asynchronous deletion completion/errors.
Independent graph-signal publication may remain valid if the API exposes it;
do not force a global transaction without a product need.

**Acceptance:**

- A graph/perspective response can identify its exact source model and Congress
  scope; freshness uses lineage rather than timestamp ordering alone.
- A published dependent run prevents deletion of its required artifacts.
- Interrupted cleanup is resumable and does not report uncompleted deletes as
  verified completion.
- Embedding model/dimension changes have a compatible namespace/migration plan;
  a preview or alternate-model run cannot silently invalidate serving vectors.

<a id="r07"></a>
### R07 - Offline, single-source contracts

**Verified:** [package scripts](../frontend/app/package.json#L6) fetch OpenAPI
from a running API during `predev` and `prebuild`; the
[bill wrapper](../frontend/app/src/api/bills.ts#L4) still declares response
shapes separately from [generated contracts](../frontend/app/src/shared/contracts/api.ts#L1).
The historical plan correctly wanted one source of truth, but live-server
generation did not enforce adoption.

**Target/work:** export OpenAPI deterministically without live infrastructure,
generate/check a committed artifact, and reference generated response schemas
from handwritten request wrappers. Keep request-building helpers; do not add
a custom API framework or runtime validation library by default.

**Acceptance:** a clean frontend build works without a running API; schema
generation is deterministic; CI detects stale generated output; duplicate
wrapper-owned response interfaces are retired without changing response shapes.
Query parameters/enums/nullability remain aligned with backend validation.

<a id="r08"></a>
### R08 - Trustworthy errors, readiness and partial-data states

**Verified:** [health](../cdm/backend/app.py#L22) is liveness-only.
[Bill detail](../cdm/backend/services/bill_service.py#L80) lacks the same
explicit missing-record policy as other routes.
[HTTP helpers](../frontend/app/src/api/client.ts) discard server error detail.
Optional sections can fall back to empty/null values, while
[search](../cdm/backend/services/search_service.py) can return partial results.

**Target/work:** retain a cheap liveness endpoint; define bounded dependency
readiness separately from data coverage/freshness. Use a small typed error
policy and explicit partial/unavailable metadata where it changes interpretation.
The UI must not call API liveness "ingest online" or label dependency failure
as zero records.

**Acceptance:** fixture-backed route/UI tests distinguish missing entity,
invalid input, dependency outage, empty source results, optional unavailable
analysis and stale published analysis. Appropriate responses use consistent
404/422/409/503 semantics and useful safe error detail.
Optional LLM fallback remains possible, with recorded `label_source`/fallback
reason instead of an indistinguishable success label.

**Implementation update:** the HTTP/readiness and explicit analytics-state
slices are implemented, followed by recorded label provenance for topics,
metasubjects, and perspective clusters. Shared typed metadata distinguishes
accepted LLM replies, deterministic fallbacks, overrides, and unknown legacy
origins. Carried names preserve their origin; known optional model failures do
not block publication, but invalid label coverage does. Detail views expose the
origin and safe fallback category. Regression coverage includes offline/wire
contracts, read-only previews, real-index/HTTP round trips, and browser fixtures.
These are incremental implementation results, not a live-data coverage claim.
The next bounded slice is R09 measurement and stable, bounded read semantics.

<a id="r09"></a>
### R09 - Query budgets, stable ordering and honest search

**Verified:** [bill listing](../cdm/backend/services/bill_service.py#L51) eagerly
materializes voted-bill IDs into a `terms` query for `has_votes`.
It uses offset paging and update-date sorting.
[Member activity](../cdm/backend/services/member_service.py#L308) fetches
`min(page * limit, 10_000)` hits **per source**, then merges/slices; with the
current bill/amendment sources that can be 20,000 hits for one request.
Search concatenates entity groups before applying the final limit; it is not
a single global relevance ordering.

**Target/work:** declare stable sort/tie-break keys, maximum supported depth
and truncation behavior. Use cursor/search-after paging where justified, or
reject unsupported deep pages explicitly. Measure voted-bill ID set size and
latency before choosing a cached, indexed or incrementally maintained filter.
Make grouped versus globally ranked search an explicit product contract.

**Acceptance:** largest-supported-scope fixtures assert bounded requests,
payload sizes and deterministic ties using sortable keyword IDs, not an
unsupported `_id` sort. No deep page silently looks empty because an internal
cap was reached. Baseline latency/memory is measured before selecting and
enforcing numeric budgets; caching is not added as a substitute for correctness.

**Implemented, incremental:** the user chose a 10,000-match offset window,
grouped search with a per-type limit, a complete-or-reject read-time voted-bill
join, and activity ordering matching its displayed date. Shared injected read
configuration validates depth before queries. Lists retain true totals and expose
page bounds/cutoff metadata; keyword IDs break ties. One multi-index activity
query replaces prefix fetching and Python merging. Vote aggregations reject
omitted buckets (422) and approximate/incomplete responses (503); the existing
20,000-bucket-per-source join remains, without a cache or new index. Frontend
controls honor the returned bounds, explain grouped results, surface activity
errors, and discard stale activity responses.

**Measured evidence:** an isolated one-CPU/1-GiB Elasticsearch fixture used 10,001 bills,
10,001 amendments, 25,001 voted-bill IDs, and 100 members. Activity page 100
(limit 100), with all required item fields and actual typed normalization:

| Observation | Before | Implemented |
| --- | ---: | ---: |
| Search requests / fetched hits | 2 / 20,000 | 1 / 100 |
| Serialized search-response bytes | 5,564,799 | 29,027 |
| Traced Python peak bytes | 43,735,468 | 217,905 |
| Warm elapsed observation | 947 ms | 83 ms |

These are synthetic observations, not production latency or memory guarantees.
The previously silent empty deep page is now rejected before any query.
The oversized vote fixture is rejected, not reported as 20,000 complete IDs.
Search limit 20 now returns 20 members and 20 bills instead of starving bills.
Real-index regression fixtures cover the exact 20,000-bucket boundary, oversized
scopes, displayed-date fallbacks, missing dates, stable ties, projections, HTTP
contracts, and preservation of seeded source records. Broad documentation/wiki
regeneration remains deferred; the next bounded roadmap slice is R10.

**Validation and size:** 155 targeted Python cases, including five real-index
integration cases, passed with user warnings treated as errors; 15 frontend
cases, contract freshness/type assertions, the production build, Ruff/import
placement, and core Pylance checks passed. Browser fixtures checked all three
pagination cutoffs, actionable errors, grouped results, and late activity replies.
The activity regression also enforces 100 fetched hits and a search-response
payload below 50,000 bytes for its fixed fixture. Net handwritten production
change is **+287 Python / +1 frontend lines**; generated contracts add 28.
This slice grows explicit validation/contracts rather than claiming net deletion.

<a id="r10"></a>
### R10 - Reproducible UI investigations and one request convention

**Verified:** [BillsPage](../frontend/app/src/pages/BillsPage.tsx#L15) already
uses URL parameters and guards stale responses. Preserve that working behavior.
[MemberSearchPage](../frontend/app/src/pages/MemberSearchPage.tsx#L19) also has
a cancellation guard, but keeps filters/page locally.
[SearchPage](../frontend/app/src/pages/SearchPage.tsx#L23) keeps query/types/limit
in local state and fetches on submit; its disabled submit button reduces
concurrent submissions, but is not a shared request-state convention.

**Target/work:** finish typed URL serialization/restoration for investigation
state, and standardize loading/error/empty/partial behavior. Reuse or extract
the existing sound request pattern; do not automatically introduce a global
store, query-cache framework or rewrite every effect.

**Acceptance:** refresh, direct links, back/forward and copied URLs reproduce
member/search/bill filter state. Stale completions cannot overwrite the active
request. Critical paths are keyboard-usable and tested on narrow screens.
Adopt actual Radix Themes unless D6 explicitly approves a redesign.

**Implemented, incremental:** typed URL codecs now own applied bill/member/search
filters and paging. Local state holds only unsubmitted drafts; navigation restores
the URL's controls and results. Filtering resets page 1, paging keeps filters, and
resubmitting the same canonical URL retries without duplicating history. Existing
subject links, non-default party values, and all valid per-type search limits
remain representable. Malformed URL state is explicit and prevents dependency
reads instead of silently querying defaults.

The existing analytics hook is now the shared `useRead`, with idle support for an
unsubmitted search. Three separate request implementations were removed; existing
analytics callers only changed the hook name. Request identity rejects late
successes/failures, including navigation back to idle. Radix controls were retained;
wrapping the header/navigation fixed measured mobile horizontal overflow.

**Validation and size:** 65 frontend cases (50 new URL-codec regressions), strict
TypeScript checks, contract freshness, and the production build passed. Isolated
browser fixtures verified direct links, refresh, back/forward, unchanged-URL
retries, invalid-URL reads making zero API calls, empty versus unavailable states,
late success/failure isolation, and keyboard form/selector/checkbox/paging actions.
At 320- and 390-pixel viewport widths, the tested pages' document width matched
the viewport. Production frontend is **+77 handwritten lines**; Python and
generated contracts are unchanged. No dependency, cache, live data, or deployment
change was introduced. Broad documentation/wiki regeneration remains deferred.

<a id="r11"></a>
### R11 - Automated architectural acceptance

**Assessment baseline:** the repository initially had no CI workflow or frontend
test command. The existing [contracts workflow](../.github/workflows/contracts.yml)
now checks focused Python regressions, schema freshness, Node/TypeScript tests,
and the production frontend build. New URL-codec cases run through that existing
test command. Browser journeys were initially fixture-validated only in the
editor; the incremental persistent gate below now extends this same workflow.
Existing test counts do not by themselves establish deployment or cross-store
crash correctness.

**Target/work:** add a small automated baseline, then attach each refactor's
failure tests. Start with existing runners; add browser tooling only for the
critical user journeys it must protect.

**Acceptance:**

- CI checks Ruff, focused/unit Python tests, generated schema/documentation
  consistency, frontend type/build and representative HTTP contracts.
- Fixture-backed browser tests cover state -> member, member -> bill, query URL
  restoration, and unavailable/partial states without spending API budget.
- Controlled integration tests exercise mixed bulk results, source/archive
  handoff interruption, stream trimming/reclaim, duplicate jobs, missing targets,
  alias cutover/rollback and failed model publication.
- Image/resource smoke and queue-routing tests gate production release.
- Restore/recovery and sustained-operation acceptance run separately on an owned
  test environment; unit pass counts are not substituted for those gates.

**Implemented increment: persistent browser gate.** Added Playwright as a
development-only dependency and extended the existing contracts workflow, not a
second CI baseline. Typed fixture journeys run against an owned production
preview in desktop and 320-pixel Chromium. They cover state/member/bill
navigation, optional-analysis/activity failures, URL restoration and history,
same-URL retry, server page bounds, invalid URLs making zero data reads,
keyboard controls, narrow layout, and held late success/failure responses.
Unexpected API/external traffic is aborted and fails the gate; guard tests also
prove that same-origin fetches cannot fall through to a successful SPA page.
No live source/API budget is consumed.

The gate exposed and fixed a member party history-restoration reset: keep
URL-restored options available while the draft changes, and remove the duplicate
Independent option. No production abstraction, service, or runtime dependency
was added. Handwritten frontend is **-1 line** (5,037); Python remains 31,345
and generated contracts 3,767. The remaining additions are testing, CI, and docs.

**Validation:** 32 browser cases passed twice locally (64 executions, no retries),
including guard failure-path assertions; browser types and the production build
passed. All 65 frontend cases, contract freshness, and 10 documentation-tooling
cases also passed. The workflow retains failure traces/screenshots/reports for seven days.
This configures CI but does not claim an observed cloud run. Broad
documentation/wiki regeneration remains deferred.

**Still open:** CI Ruff/documentation consistency, controlled cross-store crash
and replay scenarios, release image/resource/queue gates, and separate restore/
sustained-operation acceptance. This browser increment does not close all R11
acceptance criteria.

**Audit/editor follow-up:** resolved all nine reported npm findings without
suppressions or dependency-source patches. Updated Vite/router/source-map
dependencies, replaced the blocked Redocly-based generator with pinned Hey API
type-only generation, and tested compatible color/YAML overrides. The user
approved the generator replacement and Node 22.18+ tooling requirement; CI and
both frontend Docker builds now use Node 22 and lockfile-based installs. Full
dependency audits now gate CI.

The browser project is referenced from the root TypeScript solution, fixing the
editor's missing `process` diagnostic without redundant Node typings. Generated
response aliases and operation query guarantees remain checked. Deterministic
generation tests now also cover required defaults, nullable/read-only fields,
closed enums, references, and malformed-input failure without output changes.

**Follow-up evidence:** a clean Node 22/npm 10 install and full audit passed with
**zero vulnerabilities**, including development dependencies. All 67 frontend
cases, contract freshness, types, and the production build passed; 34 browser
cases passed twice (68 executions), including new map/delegation coverage.
VS Code reports no error for the Playwright configuration. Handwritten frontend
is **-1 additional line** (5,036); generated contracts shrink from 3,767 to 1,813
lines with no runtime client added. Python is unchanged. Image builds and cloud
CI execution are not claimed; the broader acceptance gates above remain open.

**Implemented increment: controlled pipeline acceptance.** Added five real-service
cases around the existing `StreamIndexer` and `IndexJobRunner`, with typed
synthetic bills and temporary SQLite archives/ledgers. A real Elasticsearch
ingest-pipeline rejection proves mixed-success bulk behavior: one document is
written, both contributing owners fail, and neither pending entry is acknowledged.
Redis pending IDs are aged without sleeps; a fresh indexer reclaims both and
retries safely without duplicate canonical documents.

The remaining cases construct the interrupted state after durable archive commit
but before publication, trimmed pending bodies, and loss of a fixture-owned
stream, then execute real runner recovery. They also cover duplicate terminal job
delivery and incomplete archives refusing success. They do not interrupt a live
source fetcher or simulate an OS process kill, Redis server crash, or power loss.

Extended the same workflow with bounded disposable Redis/Elasticsearch services
and a 30-minute job limit. Reused the existing SQLite admission/recovery/retry,
canonical projection/missing-target, topic CAS/rollback, graph publication,
perspective rejection/source-preservation, and real-index query-budget suites.
The node's 8 MiB HTTP limit matches the oversized perspective test; that case is
not silently skipped. Ruff gates the new Python acceptance module; UserWarnings
fail the selected Python suites. No production code, runtime dependency, cache,
or service topology was added.

See the [runbook](OPERATIONS_RUNBOOK.md#controlled-pipeline-acceptance) for exact
commands, ownership/cleanup rules, and the tested failure boundaries.
Production remains **31,345 Python / 5,036 handwritten frontend / 1,813 generated
contract lines**, unchanged by this increment.

**Validation:** all **36 selected real-service cases passed with no skips** against
owned Elasticsearch 9.3.1/Redis services with the same memory/CPU caps and 8 MiB
HTTP limit used by CI. All **217 selected contract/recovery Python cases** passed
with UserWarnings treated as errors. Scoped Ruff, formatting, Python syntax,
Pylance diagnostics, workflow YAML/selector/HTTP-limit checks, and all 10
documentation-tooling cases passed. Fixture indexes and Redis keys were empty
afterward; only the owned test containers/volumes were removed. The existing
staged worker configuration was preserved unchanged.

**Still open after this increment:** repository-wide Ruff/generated-documentation
consistency, production alias cutover/rollback, release image/resource/queue
smoke, genuine crash/restore and sustained-operation acceptance. Cloud CI
execution and deployment are not claimed.

**Implemented increment: image and queue-routing release smoke.** The user chose
a manual pre-release gate rather than rebuilding the NLP image on every push/PR.
Extended the same workflow with a dependent, manual-only image job and retained
deployment/routing unit checks in the normal gate. A small locked `release` group
runs the host test driver without installing training packages; runtime package
versions and sources remain unchanged.

Built both actual production images locally. The image fixture uses an owned
internal Docker network, no published ports or source mounts, temporary broker
credentials, and enforced CPU/memory caps. Checks exercise the default API command
with a nondefault `PORT`, typed health and dependency-unavailable readiness,
packaged mappings, nginx SPA/assets/404 behavior, real AMQP envelopes for every
job kind, and singleton prefork worker/task/queue discovery. Envelopes are consumed
before worker startup, so no congressional source or analysis task is executed.
Both Compose consumer configurations and configurable immediate/delayed dispatch
are covered by the focused unit gate.

The build exposed a duplicate uv installer cache. Added `--no-cache` to the
existing frozen/no-dev install and a runtime absence check. Local ARM64 Docker
reported backend image size **21.27 GB -> 11.30 GB**, approximately **47% smaller**;
the production frontend is approximately **78.6 MB**. These are local image
measurements, not cloud startup/throughput or peak-memory benchmarks. Training
dependencies, including GPU libraries, remain an explicit R12 concern.

No application Python/frontend code or production worker configuration changed.
Production line totals remain **31,345 / 5,036 / 1,813**. See the
[release runbook](OPERATIONS_RUNBOOK.md#release-image-and-routing-acceptance)
for reproduction, caps, cleanup, and the precise limits of the gate.

**Validation:** all three final image/broker cases passed using only the isolated
release dependency group; the preceding final-image run also passed. All **249
focused contract/recovery/deployment/documentation cases** passed with
UserWarnings treated as errors, including 22 deployment/routing cases. Scoped
Ruff/formatting, Python syntax, Pylance diagnostics, manual-workflow YAML/selectors,
lock freshness, and unchanged locked package versions/sources were verified.
The host release environment contains no training packages. Fixture cleanup
removed its containers/volumes/network; the pre-existing staged worker blob was
preserved.

**Still open:** repository-wide Ruff/generated-documentation consistency, actual
production alias cutover/rollback, full-topology/resource-load acceptance,
genuine crash/restore, and sustained-operation acceptance. The manual cloud job
has not been observed; no image is published and no deployment is authorized.

**Implemented increment: recovery acceptance with a net code reduction.** Reused
the existing pipeline fixture for a spawned writer that commits a ledger claim,
archive records, and progress, then waits with a live WAL. SQLite's backup API
captures both stores; the test SIGKILLs the writer, preserves the newer original
files, restores snapshots to the payloads' original paths, and executes the real
recovery service and index runner. It verifies restored progress, terminal rows,
exact dispatch, two replayed records, attempt counts, and duplicate skipping.
Only worker-liveness/queue-depth probes and dispatch transport are injected;
the ledger, archives, Redis lock, and search writes are real.

Rather than adding production backup/recovery infrastructure, consolidated five
existing ledger transitions behind one typed SQLAlchemy transaction boundary.
All guards and window/timestamp/error semantics remain explicit and unchanged.
Thirty characterization cases passed before the extraction; they now also
protect unrelated rows, with an additional failed-window-write rollback case.
This removes **46 net production Python lines: 31,345 -> 31,299**. Handwritten
frontend remains 5,036 and generated contracts 1,813. Test code grows separately:
31 lifecycle/atomicity cases and one crash/restore case were added.

The existing CI selectors now include these checks and related ledger,
heartbeat, worker-task, and documentation tests. **315 focused Python cases and
37 real-store cases passed with no skips**, with UserWarnings treated as errors.
Scoped Ruff/formatting and Pylance checks passed. The runbook now uses the SQLite
backup API instead of a live main-file copy and preserves old WAL/SHM files
before restoring a verified snapshot. The exact documented recipes also passed
a disposable SQLite check, including live-WAL capture, refusing an existing
snapshot target, and preserving previous sidecars. Python syntax checks passed.
Fixture indexes/Redis keys were empty afterward; only owned test containers and
volumes were removed, and the staged worker blob was preserved unchanged.

This tests process loss after committed writes, not power-loss durability,
mid-source-fetch Celery termination, broker restart/redelivery, Elasticsearch/
model snapshot restore, or a full-system disaster-recovery drill. Those remain
operational acceptance work; they must not be inferred from these counts.
Larger production/dependency reductions should now proceed through R12/R13,
without indefinitely expanding the test-infrastructure layer.

<a id="r12"></a>
### R12 - Lightweight reads and targeted domain organization

**Initial finding:** the shared [Container](../cdm/container.py#L1) imported both serving
and analysis-building collaborators; [dependencies](../pyproject.toml#L10)
install training/NLP packages unconditionally. One local fresh-process import
of `cdm.backend.app` took **13.56 seconds** and loaded NumPy, SciPy,
scikit-learn, PyTorch, spaCy, BERTopic and Sentence Transformers.
This is one local observation, not a cloud cold-start benchmark.

**Target/work:** separate lightweight query DTOs/read composition from training
construction at module boundaries, with explicit dependency injection and
optional dependency groups/images where worthwhile. No lazy-import workaround.
Move topic orchestration out of generic `utils` into a coherent domain only
when touching that code; keep compatibility imports during migration.

Typed settings/model boundaries already exist. Finish annotation, configuration
and Pydantic consistency in changed modules, rather than a blanket rewrite of
every helper or an extra abstraction for each query. Simple application classes
should own orchestration; avoid generic repositories/service locators.

**Acceptance:** API-only imports do not import training-only packages; query
normalization behavior is preserved; API and analysis images each pass their
own smoke tests. Measure import/startup time, image size and memory before/after
under the same conditions. Changed Python code has no new Ruff/Pydantic/type
issues.

**Implemented locally:** the existing `Container` now owns reads and durable
submission; the existing `WorkerContainer` owns analysis construction. No new
composition framework or lazy imports were introduced. Four single-use
metasubject factory wrappers were removed and graph/perspective builds share
one stateless topic-model reader. Source normalization and publication/job
policies are unchanged. Production Python under tracked/non-ignored `cdm` and
`scripts` fell **31,299 -> 31,276 (-23 lines)**; tests are counted separately.

BERTopic/Sentence Transformers moved into the `analysis` dependency group.
Normal `uv sync` still includes `dev` and `analysis`. NumPy/PyYAML are explicit
base dependencies; all **134 locked package versions and sources are unchanged**.
The user selected a compatible rollout: the full `analysis` Docker target
remains last/default; `--target api` opts into serving without training packages.
Existing image tags, deployment wiring and live services were not changed.

Both images retain spaCy, its pinned English model and NumPy because query
lemmatization is real serving behavior. The API-only image has no installed or
loaded BERTopic, Sentence Transformers, SciPy, scikit-learn or PyTorch.
In a full environment, spaCy's optional integrations still import PyTorch;
this is not hidden with import hooks or lazy-import workarounds.

Local Docker measurements used the same ARM64 base digest, no network,
1 CPU/1,536 MiB, and three fresh-container Python imports per image:

| Runtime | Image bytes | Median API import | Median import-only peak RSS |
| --- | ---: | ---: | ---: |
| Before this increment, full image | 11,304,345,833 | 17.317 s | 1,099.1 MiB |
| Opt-in API target | 2,031,314,879 | 2.194 s | 128.2 MiB |
| Default full analysis target | 11,304,375,316 | 3.710 s | 604.4 MiB |

The opt-in API image is **82.0% smaller**. The full image has not shrunk in this
increment; its capabilities are retained. These are local import measurements,
not cloud cold starts, throughput, request latency or serving peak-memory SLAs.
RSS is captured before loading the spaCy model for the first normalized query.
All nine measurements produced identical OpenAPI hashes and real normalization
outputs, including punctuation/case and empty input.

**Validation:** **352 focused Python/documentation cases**, four isolated
production-image/broker cases, and an additional default-full-image API
health/readiness smoke passed. The manual release gate now builds/checks both
Python targets and nginx; the normal gate adds fresh-process read/submission
import guards and related composition/training tests. Scoped Ruff/format and
Python syntax checks passed. With the Pylance client unavailable, standalone
Pyright **1.1.414** checked all ten changed Python files with **zero errors or
warnings**. No cloud workflow run, deployment, live training or source-data
mutation was performed. Broader domain moves and generated-reference/wiki
refresh remain separate work.

<a id="r13"></a>
### R13 - Consolidate policies, not safeguards

**Verified:** [task recovery](../cdm/workers/tasks.py),
[stream recovery](../cdm/ingest/redis_stream.py#L63),
[batch indexing](../cdm/store/batch_indexing.py#L131) and archive replay have
different state responsibilities. Whole-buffer late acknowledgement protects
against ambiguous partial bulk results; successful writes can be redelivered.
The YAML has **21 mapping families**, which is not itself a problem or proof
that each family should be populated.

**Target/work:**

- Document one recovery decision table and ownership for broker delivery,
  running-job heartbeat, stream pending state and archive replay.
- Retain whole-batch late acknowledgement initially; add source-correlated
  per-item diagnostics and explicit permanent-failure disposition/quarantine.
  Consider per-item acknowledgement only if measured replay cost justifies it.
- Benchmark optional archive-batch references as the sole record handoff.
  Do not remove streams before proving crash/replay/completeness equivalence.
- Keep only indexes/relationship projections justified by actual queries.
  Do not populate unused bridge schemas or build the old annotation/chunk stack
  merely to match an inventory diagram.

**Acceptance:** fault injection at each handoff has an explicit recovery owner,
no unaccounted source records and the same final logical projection after replay.
Permanent rejected records remain visible as failures/partial coverage.
Any transport/index removal reduces measured operational burden and preserves
backpressure, shared rate limits, replay and rollback.

**Implemented, bounded consolidation:** bulk rejection now raises at the shared
`bulk_upsert` boundary. Five caller-specific error policies were removed; all
returned rejected item identities/details are retained rather than only three.
Successful return dictionaries, write destinations/projection semantics and
whole-buffer late acknowledgement are unchanged. Reconciliation cannot write a
new "completed" report after a rejected write. No extra recovery/quarantine store
or framework was added. The existing FAILED ledger plus pending entries and
source archive remain the explicit permanent-failure disposition.

A characterization reproduced false completion when one streamed record was
replayed from an incomplete one-record archive against an expected count of two.
The fallback now requires its full snapshot count independently. Unit and real
store regressions cover overlap, missing/complete archives, all rejected IDs,
permanent batched failures, no automatic retry, and retained source records.

The [recovery ownership table](OPERATIONS_RUNBOOK.md#recovery-ownership) identifies
broker, ledger/liveness, queued redispatch, pending entry and archive owners.
The same real-store fixture compared 100 synthetic records via stream versus
archive fallback: 0.249/0.214 seconds, 19,660/1,016 retained Redis bytes in one
local warmed-normalization run. Both produced identical preserved records.
This archive route still creates an empty Redis consumer group. It is not proof
of a Redis-free handoff, load/backpressure equivalence or mid-write crash safety.
**Decision: retain Redis Streams**, rate coordination and all recovery layers;
no transport/index removal is justified by this small measurement.

**Validation:** 362 focused Python/documentation cases and 41 isolated real-store
cases passed, with no integration skips. Scoped Ruff and Pyright passed with no
type warnings/errors. Production Python is **31,276 -> 31,267 (-9 lines)**,
including formatting; added tests are separate. CI retains these checks.
R15 is next in the agreed order. Full-system release acceptance and final
generated docs/wiki remain later gates; no deployment or source deletion occurred.

<a id="r14"></a>
### R14 - Reconcile analytics goals before expanding them

**Verified:** [topic training](../scripts/train_topic_model.py#L1) implements
discovery BERTopic; [metasubjects](../cdm/utils/metasubjects.py) group centroids,
not reviewed taxonomy concepts. [Graph models](../cdm/graph/models.py#L86)
contain a smaller evidence surface than the old graph plan proposed.
The [Ollama client](../cdm/utils/ollama_client.py#L29) is the implemented provider;
[Vertex IAM grants](../infra/terraform/iam.tf#L18) do not implement a provider.

**Target/work:** keep source subjects, discovery topics, metasubject similarity,
party contrasts, collaboration and voting agreement explicitly distinct.
Use CRS classifications for stable browsing where sufficient. Do not present
cluster membership/cosine similarity as calibrated confidence, member belief,
ideology or support for policy.

The old controlled multilabel taxonomy, review workflow and evidence spans are
**not** completed by BERTopic; retain them as conditional product work under D4.
Likewise, graph overview, co-defection evidence and additional filters are
feature decisions, not reasons to build a graph database or replace the current
bounded neighborhood approach.

**Acceptance:** each user-facing analysis exposes scope, input/source version,
method, meaningful support counts and limitations. A stable-taxonomy feature,
if selected, has reviewed definitions/hard negatives, evidence and held-out
evaluation before production rollout. Optional generated labels identify their
provider/fallback. A cloud rollout works with deterministic labels if no LLM
provider has been enabled.

<a id="r15"></a>
### R15 - One supported operational/configuration surface

**Assessment baseline:** Make, native service scripts, development Compose and
GCP Compose encoded different process/queue configurations. The old stack
helper stopped processes by name patterns. Typed application configuration
already existed; this increment does not introduce another configuration manager.

**Target/work:** designate the supported development and production entry points,
keep wrappers thin, and validate capabilities against a small explicit manifest
or tests rather than duplicating more shell policy.
One process manager owns a service per environment. Stop only known owned
processes; preserve volumes during routine restart.

**Implemented and verified:** the user selected Compose as the sole managed
local stack. [Make](../Makefile) and the thin [shell wrapper](../scripts/stack.sh)
share startup/status/restart/shutdown paths; the native installer is removed.
Startup refuses loaded legacy labels or retained plists rather than
uninstalling/switching live services. The
[manual retirement procedure](OPERATIONS_RUNBOOK.md#retiring-native-agents)
verifies ownership and preserves registrations.

[Development Compose](../docker-compose.fullstack.yml) now shares Python
configuration, consumes every configurable queue, gates workers on API
readiness, supervises exits, and persists the ledger/archives and Beat schedule.
Mounting the checkout at its original absolute path preserves queued native
archive references without rewriting payloads. Frozen dependencies are installed
at build time rather than into a contended environment at service startup.
Infrastructure gains restart and broker/Redis health checks. Routine shutdown
does not delete volumes or match native processes.

Verification: **379 focused tests passed**, including offline real-Compose
rendering, actual Make execution through isolated CLI stubs, prerequisite errors,
legacy-registration guards and the exact documented migration on fake plists.
**Four actual development-image cases passed** against an isolated broker:
API/default command/readiness failure, frontend, prefork routing/registration,
and API process-exit/automatic restart with the exact ledger row preserved.
The API-only training-boundary case is deliberately excluded from this full
development-image run; R12 separately verified that production boundary.
Ruff and selected Pyright/Pylance checks are clean.

The two shell files plus Make shrink **407 -> 187 lines (-220)**; production
Python remains **31,267 lines**, with test additions counted separately.
At that implementation gate, no live agents were stopped, stack migrated, source data removed or GCP topology
changed. Existing staged worker configuration remains unchanged. Mac sleep,
Docker-engine startup, unhealthy-but-running processes, Linux host routing,
full-load operation and cloud cutover remain explicit release/operations limits,
not outcomes inferred from configuration checks.

**Dated operations follow-through (2026-11-03):** the approved Gate 4 controlled
cutover has now retired native agents and migrated the actual API/UI plus a
bounded index/maintenance worker to Compose. Profiles and slim API/full worker
images make inactive capabilities explicit. The retained Redis snapshot is
restored under a measured 1280 MiB limit. Actual managed-browser and production
image/broker acceptance pass; the full optional topology exceeds this Docker VM's
measured budget and was not enabled. R15's local managed-path transition is
complete within that scope; full-load/cloud/unattended acceptance is not.

**Acceptance:** documented startup/status/restart paths agree with actual queue
consumers and state locations; missing prerequisites fail clearly; shutdown
does not match another checkout's processes. Effective non-secret settings and
provenance can be inspected without logging credentials. Backup/restore steps
are tested on an isolated fixture before operational use.

<a id="r16"></a>
### R16 - Keep documentation maintenance proportional

**Initial finding:** the [documentation builder](../tools/build_documentation.py)
generated the source catalogue and wiki together; source generation also invokes
the [TypeScript extractor](../tools/build_frontend_reference.mjs).
An ordinary wiki preparation therefore required installed frontend
TypeScript dependencies even if no symbols changed.

**Implemented (2026-11-03):** explicit `--wiki-only --wiki <directory>` skips
source extraction/visual regeneration while retaining canonical link validation
and deterministic wiki generation/checking. It rejects a missing output path.
Tests prove that source/visual generation is not called, stale prose fails the
check, and regeneration restores determinism. The default full build/check is
unchanged and remains required for source/diagram edits. No new platform or
automatic publication was added.

**Target/work:** keep narrative docs/this roadmap primary and exhaustive symbol
catalogues navigational. If the coupled workflow is burdensome, separate explicit
source-reference generation from lightweight wiki preparation/checking.
Retain deterministic generation and link checks; do not replace these tools
with a documentation platform or auto-publishing service without a need.

**Acceptance:** a prose-only plan/wiki update does not require a live API or
scientific stack; source catalogues still have an explicit stale-output check.
One canonical roadmap is discoverable from the README, docs home and historical
frontend plan. Remote wiki publication remains a separate approved operation.

## Plan crosswalk

### Tracked frontend implementation plan

The [original plan](../frontend/WEB_APP_IMPLEMENTATION_PLAN.md) remains useful
for user stories. Its scaffold API examples, module layout, checkboxes and
"next task" are historical specifications, not a current implementation report.

| Original area | Current disposition | Continue with |
|---|---|---|
| Phase 0: API/React shells, settings, contracts | Implemented; response-type adoption incomplete; live-server generation adds build coupling | R07, R11, R12 |
| UI selection: shadcn + Radix Primitives | Diverged: actual implementation uses Radix Themes. Do not rebuild it solely to complete the original checkbox | D6, R10 |
| Phase 1: states/members | Routes, pages, filters and timelines exist; live coverage, missing-term semantics and complete story acceptance need verification | R03, R08, R10, R11 |
| Phase 2: bills/activity/search | Implemented in part; filter/sort scope, member/search URL restoration, grouped ranking and paging budgets remain incomplete or underspecified | R08, R09, R10 |
| Phase 3: offline topics | Existing versioned discovery/metasubject/graph/perspective implementations make "not built" stale; stable reviewed classification/evidence goals remain different work | R04, R06, D4, R14 |
| Phase 4: admin/accessibility/freshness | Admin UI exists, but local execution/status is not distributed job control; a route does not establish accessibility or data freshness | R01, R05, R08, R10 |
| Phase 5: tests/caching/rate limiting | Python service tests exist; no tracked CI workflow/frontend test script was found. Caching/rate limits require workload and deployment decisions, not a blanket checkbox | R09, R11 |
| Product principle: aggregates link to evidence | Partially supported; each analytical feature still needs scoped support/coverage and aggregate-to-record acceptance | R03, R06, R08, R14 |

### Local engineering and specialist plans

The ignored `planning` directory contains local historical notes. Relevant
intentions were reviewed and summarized here so this plan remains self-contained;
those local files are **not publication dependencies or current acceptance
evidence**, and must not be added to Git as part of this work.

| Reviewed plan | Current disposition and recommendation |
|---|---|
| Engineering `PLAN.md` (September) | Resource/spec/storage milestones broadly exist. The "1:1 mirror" vision, old script names and deferred M6 cross-linking need a scoped acceptance contract, not restoration of a deleted generic resolver. Use D3/R03/R13. |
| `FULL_DATA_INGEST_IMPLEMENTATION_PLAN.md` | GovInfo acquisition, normalization, manifests and replay exist. Treat historical proof-run counts as dated; unify replay output and demonstrate coverage before cutover (R02/R03). |
| `OPENSEARCH_DATA_MODEL_PLAN.md` | Target inventory/strict mapping/bridge and analysis proposals are not the current contract. Shipped service is Elasticsearch; current YAML has 21 families with `dynamic: false`. Keep only query-justified projections (R03/R13), not inventory parity. |
| `SELF_DRIVEN_PIPELINE_PLAN.md` | Batched indexing and recovery exist. Reject the missing-target-to-live fallback as a future target; fail closed instead. Retain durability and simplify recovery ownership (R02/R05/R13). |
| `OPERATIONS_HARDENING_PLAN.md` | Health/recovery implementation is useful; sustained unattended operation and restore acceptance remain separate from historical completion labels (R01/R08/R11/R15). |
| `INGEST_FINISH_INDEX_CLEANUP_PLAN.md` | Dated queue/cleanup instructions are incident context, not a current cleanup authorization. Re-inventory and preserve replay evidence until acceptance (R03/R11/R15). |
| `TOPIC_ANALYSIS_IMPLEMENTATION_PLAN.md` | The proposed reviewed hierarchical/multilabel taxonomy was not implemented by discovery clustering. Preserve the distinction; decide whether that product is needed before implementing its extra classifiers/indices/review stack (D4/R14). |
| `TOPIC_CLEANUP_PLAN.md` | Embedding cache, parent bill text, metasubjects, naming and retention exist. Recorded corpus counts/coverage are historical; publication, experiments, lineage and safe retention still need hardening (R04/R06). |
| `MEMBER_TOPIC_GRAPH_PLAN.md` | Collaboration/voting/topic edges, version pointers, API and neighborhood UI exist despite "next" labels. Exact model lineage, some proposed evidence/overview features and full operational acceptance remain open (R06/R11/R14). |
| `GCP_DEPLOYMENT_PLAN.md` | Terraform/images exist, but local notes' "not applied" statement is not current deployment proof. Source confirms missing image resource, consumer/control-plane gaps. Vertex is optional pending D7, not a reason to block basic deployment indefinitely (R01/R05/R12). |

## Delivery sequence and migration safeguards

**Current agreed order:** R13 -> R15 -> R03 -> release acceptance -> final
documentation/reference/wiki refresh. Keep directly related docs accurate during
each increment, but defer the broad generated-reference/wiki finalization until
acceptance. Remote publication and deployment remain separate approvals.

### Wave 0 - Baselines and explicit decisions

Resolve D1-D4 for the intended installation. Capture source revision, supported
resources/Congresses, resolved aliases, queued job destinations, immutable
archive availability, mapping versions and currently published analytical runs.
Measure duplicate delivery, query cost, import/startup time and recovery workload.
Do not infer production counts from old notes or test fixtures.

Start R11 automation with the existing tests. Create a small deterministic
multi-source bill/vote/member corpus usable by every later migration test.

### Wave 1 - Correctness and deployment gates

Implement R01, R02 and R04 as separately testable changes. Add their failure
fixtures before relying on staging/replay or new model publication.
Define R03 policy before rewriting existing documents.

**Exit:** self-contained images; no implicit live writes from staging jobs;
equivalent canonical live/replay output; incomplete/sample analysis cannot
replace a published production model.

### Wave 2 - One control plane and trustworthy contracts

Implement R05 and R07; add R08 error/status semantics. Move existing entry points
behind compatibility adapters rather than deleting working scripts/task names.
Implement R06 manifests/retention with existing published runs imported or
marked `legacy/unknown`, not assigned fabricated lineage.

**Exit:** one logical job per request across processes; consistent observable
states; reproducible offline frontend build; published outputs have explicit
provenance and safe rollback.

### Wave 3 - User journeys and bounded read paths

Complete R09/R10 alongside R11 contract/browser acceptance.
Preserve working Bills URL behavior and existing stale-response guards.
Add only measured indexes/caches needed to meet chosen budgets.

**Exit:** state -> member -> bill and search investigations are reproducible,
bounded and honest about missing/partial/stale results.

### Wave 4 - Consolidation and selected product work

Address R12/R13/R15/R16 in small, outcome-measured changes. Decide R14 feature
scope before building a supervised taxonomy, additional graph evidence, a new
LLM provider or extra indices.

**Exit:** fewer independent lifecycle/config/projection policies, lighter reads
and a tested operational path, without losing replayability or existing
investigation features.

### Rules for every migration

1. Preserve unrelated work and existing queued payload compatibility.
2. Add characterization/failure tests before changing behavior.
3. Inventory and shadow-compare before changing document identity/merge rules.
4. Use bounded canaries and explicit destinations; never delete archives to
   "fix" a retry.
5. Keep the prior alias/published run for rollback. Pause destructive retention
   while its referenced data is part of a migration.
6. Record expected versus observed outcomes and exceptions, not just row counts.
7. Retire compatibility paths only after queue drain, acceptance and rollback
   verification.
8. Update reference docs, this plan, README and changelog with the change.

## Evidence and validation record

During this review:

- Read current source and the tracked frontend plus relevant local plans.
- Ran the focused analytics/launcher baseline:

  ```bash
  uv run pytest -q tests/test_graph_runner.py tests/test_graph_health.py \
    tests/test_topic_training.py tests/test_perspective_launcher.py \
    tests/test_embedding_cache.py tests/test_metasubjects.py tests/test_perspectives.py
  ```

  **Result:** 36 passed. These tests do not establish concurrent launch safety,
  atomic model publication or live deployment correctness.
- Measured one fresh-process API import: 13.56 seconds with the scientific
  packages listed in R12 loaded. No cold-start SLA is inferred from this sample.
- Verified image COPY/resource-path and configured queue mismatches statically.
  Did not build/apply Terraform, start replacement workers, mutate indexes,
  replay production archives, inspect credentials, or certify live coverage.
- Documentation/link/wiki checks accompany this plan update. No application
  behavior or deployment configuration was changed.

### Work-record template

For each completed or investigated item, record:

```text
Finding ID:
Decision and rationale:
Source revision and scope:
Change / intentionally unchanged behavior:
Tests and measured before/after results:
Data migration / rollback evidence:
Remaining risks and next step:
Status: open | in progress | blocked | validated
```

Do not label an item validated until its relevant acceptance criteria above are
met. Findings should be closed by evidence or an explicit accepted tradeoff,
not by adding more architecture.
