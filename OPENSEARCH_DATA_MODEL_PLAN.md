# OpenSearch Data Model and Cleanup Plan

Status: planning only. This document defines the target shape before any
destructive index cleanup or schema implementation begins.

## Decisions

The target deployment will have **21 logical indices** behind versioned read
and write aliases:

- **16 entity indices**: canonical Congress.gov records.
- **2 relationship indices**: explicit many-to-many edges between entities.
- **3 derived analysis indices**: search chunks, NLP annotations, and
  precomputed dashboard facts.

The current mapping file defines **18 indices**, not 17: 16 entity indices and
the two relationship indices. The current definitions are the starting point,
not proof that the live indices have the final shape.

OpenSearch remains a searchable projection. SQLite archives remain the source
of truth for ingestion and replay. Derived analysis can always be regenerated
from canonical documents and must never be the only copy of source data.

## Target Index Inventory

### Entity indices

| Index | Documents | Required identity | Main use |
|---|---|---|---|
| `legislation` | Bills, resolutions, and laws | `id`, `source_type`, `congress`, `bill_type`, `number` | Legislative search, timelines, status |
| `amendment` | Amendments | `id`, `congress`, `amendment_type`, `number` | Amendment lookup and bill relationships |
| `communication` | House and Senate communications | `id`, `chamber`, `congress`, `number` | Communication search and filtering |
| `committee` | Committees and subcommittees | `id`, `system_code`, `chamber` | Committee navigation and hierarchy |
| `committee_meeting` | Committee meetings | `id`, `event_id`, `congress` | Calendar and event search |
| `committee_print` | Committee prints | `id`, `congress`, `jacket_number` | Publication search |
| `committee_report` | Committee reports | `id`, `congress`, `citation` | Report search and bill references |
| `congressional_record` | Bound and daily records | `id`, `record_subtype`, `reference_id` | Proceedings and issue search |
| `hearing` | Hearings | `id`, `congress`, `jacket_number`, `number` | Hearing search and schedules |
| `house_vote` | House roll-call votes | `id`, `congress`, `session_number`, `roll_call_number` | Vote lookup and vote analytics |
| `member` | Members of Congress | `id`, `bioguide_id` | People search and member profiles |
| `nomination` | Nominations | `id`, `congress`, `number`, `part_number` | Nomination search and status |
| `treaty` | Treaties | `id`, `congress_received`, `number`, `suffix` | Treaty search |
| `crsreport` | CRS reports | `id`, `title`, `publish_date` | Research report search |
| `congress_ref` | Congress metadata | `id`, `number` | Reference navigation and filters |
| `house_requirement` | House requirements | `id`, `number` | Reference lookup |

Shared entity fields:

- `id`: immutable canonical application ID and OpenSearch document ID.
- `record_type`: source model discriminator where applicable.
- `url`: canonical Congress.gov URL.
- `congress`: integer when the source has a Congress scope.
- `update_date`: source update timestamp, mapped as a date.
- `ingested_at`: pipeline timestamp, mapped as a date.
- `schema_version`: integer mapping/transform contract version.
- `source_type`, `chamber`, or `record_subtype`: required discriminators for
  consolidated indices.
- `_raw`: optional source payload retained only where replay or audit requires
  it; it is not indexed for general search.

The mappings will use `dynamic: strict` after the migration validation gate.
Text fields will use an explicit `text` plus `.keyword` multifield. Searchable
long text will also have a purpose-built analysis representation rather than
unbounded nested fields in entity documents.

### Relationship indices

#### `sponsorship`

One document per member-to-legislation edge:

```text
id                  = sponsorship:{member_id}:{legislation_id}:{type}
bioguide_id         keyword, required
legislation_id      keyword, required
congress            integer
sponsorship_type    keyword (sponsor | cosponsor)
is_original_cosponsor boolean
sponsorship_date    date
withdrawal_date     date, nullable
member_name         keyword/display copy
member_state        keyword
member_party        keyword
schema_version      integer
```

#### `vote_position`

One document per member-to-house-vote edge:

```text
id                  = vote-position:{house_vote_id}:{member_id}
bioguide_id         keyword, required
house_vote_id       keyword, required
legislation_id      keyword, nullable
congress            integer
session_number      integer
roll_call_number    integer
position            keyword (Yea | Nay | Present | Not Voting)
party               keyword
state               keyword
vote_date           date
schema_version      integer
```

Relationships are resolved by application queries. OpenSearch is not treated
as a relational join engine: first resolve IDs or aggregate edges, then fetch
entity documents with `terms` queries or a bounded second request.

### Derived analysis indices

These indices are replaceable projections. Every document carries
`source_id`, `source_index`, `analysis_version`, `model_id`, and `generated_at`.

#### `analysis_chunk`

Searchable passages extracted from legislation, reports, records, hearings,
and communications:

```text
id                  = chunk:{source_index}:{source_id}:{ordinal}
source_id           keyword
source_index        keyword
ordinal             integer
text                text + keyword where appropriate
text_lemma          text, analyzer-specific
title               text + keyword
congress            integer
dates               date array where applicable
analysis_version    integer
```

Use this index for full-text and semantic retrieval. Keep chunks bounded and
store the canonical source ID so a result can be hydrated from the entity
index. Do not duplicate complete source documents here.

#### `analysis_annotation`

Versioned NLP output for a source document or chunk:

```text
id                  = annotation:{source_id}:{analysis_version}:{model_id}
source_id           keyword
source_index        keyword
chunk_id            keyword, nullable
analysis_version    integer
model_id            keyword
language            keyword
topics              keyword array
entities            nested objects: {type, value, normalized_id, confidence}
claims              nested objects: {subject_id, predicate, object_id, confidence}
sentiment           object: {label, score}, nullable
generated_at        date
```

Annotations are additive and replaceable. Low-confidence output remains
available for review but is excluded from high-confidence dashboard metrics.

#### `analysis_aggregate`

Dashboard-ready facts at a declared grain:

```text
id                  = aggregate:{metric}:{grain}:{bucket}:{filter_hash}
metric              keyword
grain               keyword (day | month | congress | member | committee)
bucket              keyword/date
filter_hash         keyword
value               double
dimensions          flattened keyword object
source_watermark    date
analysis_version    integer
generated_at        date
```

Aggregates are for fast dashboard reads, not authoritative history. Each row
must identify the source watermark and analysis version so stale metrics are
visible and reproducible.

## Connections

The application-level graph is:

```text
congress_ref
  -> entity.congress

member <- sponsorship -> legislation
member <- vote_position -> house_vote -> legislation
amendment -> legislation (amended_bill_id)
committee_meeting / committee_print / committee_report / hearing -> committee
legislation <- analysis_chunk <- analysis_annotation
all searchable entities -> analysis_aggregate (by source watermark)
```

Reference fields must be stored as canonical IDs, not display names. A missing
target is a visible data-quality state, not a reason to invent a placeholder
document. Relationship and annotation documents should be upserted
idempotently and retain their source IDs for replay.

## Query Strategy

### Entity and navigation queries

1. Resolve user input with a type-aware `multi_match`, exact ID boosts, and
   `match_phrase` on titles/names.
2. Apply filters with `term`/`terms` for Congress, chamber, party, source type,
   and status; use `range` for dates.
3. Return only required fields with `_source` includes.
4. Use `search_after` for deep pagination. Do not use large `from` offsets.
5. Fetch related entities in a second bounded request using IDs from a
   relationship aggregation.

### Relationship queries

- Member profile: query `sponsorship` or `vote_position` by `bioguide_id`,
  aggregate or sort by date, then fetch legislation or votes by ID.
- Bill profile: query edges by `legislation_id`, then fetch members by
  `bioguide_id`.
- Vote analysis: filter `vote_position` by `house_vote_id`, aggregate
  `position`, `party`, and `state`, then join the small result set to members.

### NLP retrieval

Use a two-stage path:

1. Candidate retrieval from `analysis_chunk` using BM25, exact filters, and
   optionally vector kNN once embeddings are available.
2. Fetch annotations from `analysis_annotation`, apply confidence and model
   version filters, then hydrate the source entity for display.

NLP must not run synchronously in dashboard requests. A queued analysis job
  reads canonical documents, writes versioned chunks/annotations, and updates
  aggregates only after successful bulk writes.

## Cleanup and Migration Gate

No live index is deleted as part of this planning change. Before cleanup:

1. Freeze the target mapping YAML and assign `schema_version` values.
2. Query the cluster for every physical index, alias, document count, mapping,
   settings, and creation date. Include indices not present in YAML.
3. Classify each physical index as `keep`, `reindex`, `archive`, or `delete`.
4. Snapshot or export every index classified as `reindex`, `archive`, or
   `delete`; record the snapshot ID and document count in the migration log.
5. Compare live mappings to the target mapping. Any unexpected field,
   incompatible type, missing discriminator, or wrong alias blocks deletion.
6. Create versioned target indices, for example
   `congress-legislation-v2`, and populate them by deterministic transforms.
7. Validate representative documents, counts, required IDs, relationship
   referential integrity, query behavior, and dashboard aggregate parity.
8. Atomically move read/write aliases to the validated target indices.
9. Keep the old physical indices read-only through the rollback retention
   period. Delete them only after the retention window and a second health
   check.

An index may be deleted immediately only when it is not in the target
  inventory, has no live alias, has zero documents or a verified export, and is
  explicitly listed in a reviewed deletion manifest. `indices.delete` must
  remain confirmation-gated and must never accept a broad wildcard.

## Implementation Order

1. Add a versioned target mapping contract and a checked-in inventory test.
2. Add mapping inspection, diff, snapshot/export, and deletion-manifest
   tooling in dry-run mode.
3. Create v2 entity and relationship indices; reindex and validate canonical
   documents.
4. Switch aliases only after query and referential-integrity tests pass.
5. Add `analysis_chunk`, `analysis_annotation`, and `analysis_aggregate` as
   independently rebuildable projections.
6. Add the two-stage search/NLP service and dashboard aggregate reads.
7. Delete obsolete physical indices after the rollback retention period.

## Acceptance Criteria

- Exactly 21 target logical indices are defined and documented.
- Every write uses a write alias; every read uses a read alias.
- No production mapping relies on accidental dynamic fields.
- Every entity and relationship document has a stable ID and schema version.
- Relationship queries can resolve member, legislation, committee, and vote
  connections without scanning unrelated indices.
- NLP output is versioned, traceable to a source ID, and regenerable.
- Dashboard metrics expose their source watermark and analysis version.
- Cleanup is dry-run auditable, snapshot-backed, alias-aware, and rollbackable.
- The full mapping, transform, query, migration, and integration test suites
  pass before destructive deletion is enabled.