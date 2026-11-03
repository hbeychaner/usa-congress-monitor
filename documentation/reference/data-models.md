# Data models and persisted records

This chapter describes the structures actually accepted, produced, and stored by
the application. A model field is not necessarily a searchable index field:
Pydantic validation, archive serialization, document transformation, and search
mappings are separate boundaries. See [indexing](indexing.md) for searchable
fields and [ingestion](../guides/ingestion.md) for acquisition and replay.
The [model symbol index](symbols/models.md) lists individual declarations;
this chapter explains their boundaries and relationships.

## Model organization and serialization

The concrete Congress API models live in
[`bills.py`](../../cdm/models/bills.py),
[`people.py`](../../cdm/models/people.py),
[`other_models.py`](../../cdm/models/other_models.py), and
[`shared.py`](../../cdm/models/shared.py).
The domain modules `legislation`, `committees`, `communications`, `nominations`,
`people_lists`, `records`, `reports`, `taxonomy`, and `identifiers` re-export
selected definitions; they are not independent persistence schemas.

Most API inputs use camelCase aliases, while ingest normally emits
`model_dump(mode="json", exclude_none=True)`, using Python field names unless
the model itself names a field differently. Dates and URLs become JSON values.
Do not assume all legacy fields are snake_case: list models include `recordType`,
and `BillTextResponse`/`BillRelatedBillsResponse` retain API collection names.
Nor do all models share one extra-field policy: many use Pydantic's default,
while committee-print and committee-meeting detail models allow extra fields.

### Shared value models

| Model | Meaning and important fields |
|---|---|
| `EntityBase` | Optional `id` and `build_id()` identity heuristics; used by many, but not all, item/list models. |
| `Format` | Text representation `type` and HTTP `url`; not the fetched content. |
| `Activity` | Committee activity `name` and `date`. |
| `CountUrl` | Deferred relationship: `count`, `url`, optional `count_including_withdrawn_cosponsors`. It does not mean the relationship has been expanded. |
| `Title` | `title`, `title_type`, `title_type_code`, `update_date`, and bill-text version code/name. |
| `SourceSystem` | Action source `name` and numeric `code` (default `-1`). |
| `Note` | One `text` value; the client normalizes several upstream note shapes to this list-compatible form. |

[`CDGClient.coerce_records()`](../../cdm/data_collection/client.py) validates
records, fills IDs where possible, applies an optional endpoint ID strategy, and
warns about unprocessed upstream fields. A validation failure invokes the
quarantine callback, if supplied, and then raises; it is not automatically
silently skipped. The field-coverage check catches its own `ValueError`, so the
strict-field-check setting is not a reliable rejection barrier in this method.

## Legislation and bill detail families

### Bill identity, content, and relationships

[`Bill`](../../cdm/models/bills.py) represents an item-level bill. Its identity
is `congress`, lowercased `type`, and `number`, canonically
`bill:{congress}:{type}:{number}`. `number` is string-valued in the model; it is
not interchangeable with a public/private law number.

Core fields include `title`, `introduced_date`, `origin_chamber`,
`origin_chamber_code`, `latest_action`, `update_date`,
`update_date_including_text`, `constitutional_authority_statement_text`, `url`,
`policy_area`, `sponsors`, `laws`, and `notes`.

The expanded collections are `actions`, `amendments`, `committees`,
`cosponsors`, `related_bills`, `subjects`, `summaries`, `text_versions`, and
`titles`. Several collection fields can also contain a `CountUrl` envelope.
An envelope preserves a link/count, not the related objects themselves.
`full_text` holds extracted text; it is distinct from `text_versions`, whose
formats describe where published representations can be fetched.

`detail_hydration` is a dictionary of per-endpoint completeness observations:
each value contains `page_count`, `expected_count`, `fetched_count`, `state`,
and `complete`; versioned detail evidence also records a reason and optional
expected/fetched active co-sponsorship counts. Overall co-sponsor counts include
withdrawn episodes; subject counts include a nonempty policy-area row once,
alongside distinct legislative subjects. They are not unique active-member or
legislative-subject-only counts. The keys used by hydration include `relatedBills` and
`textVersions`, rather than the normalized model attribute names.
The YAML mapping's flat `detail_hydration` object does not declare those
per-endpoint keys, so these observations are available in `_source` but are not
automatically searchable at their actual paths.
Related-bill totals measure nested relationships, not unique related bills.
Optional `fetched_record_count` preserves the separate top-level object count;
older evidence omitting it remains readable but is not newly recertified.

`Bill.add_bill_details()` fetches nine related endpoints and fills normalized
collections and text. All nine collections, including committees, validate
before assignment to the original bill. The versioned `HydrationAssessment`
is source-only; the derived root status is searchable. A complete assessment
certifies those retrievals, not global historical, text or freshness coverage.

| Supporting model | Important fields and relationship |
|---|---|
| `BillMetadata` | Lightweight bill/reference shape: congress/type/number/title/URL, introduced date, latest action, relationship details, chamber, update dates. Its ID builder uses bill identity. |
| `BillListItem` | Sparse list shape with bill identity/title/latest action/chamber/update dates; `recordType="congress-bills"`. Endpoint specs determine which list model is actually used. |
| `LatestAction`, `BillLatestAction` | Action date and text; the list variant permits sparse data. |
| `Action` | Date/code/text/type, `source_system`, committees, action time, and `recorded_votes`. |
| `RecordedVote` | Roll number, chamber, congress, date, session number, and source URL; a reference, not a member-position table. |
| `RelationshipDetail` | `identified_by` and relationship `type` on a related bill reference. |
| `TextVersion`, `BillTextResponse` | Publication date/type/formats and an API text-version response envelope with pagination/request data. |
| `Summary` | `action_date`, `action_desc`, `text`, `version_code`; embedded bill summary content. |
| `PolicyArea`, `LegislativeSubject`, `Subjects` | Named CRS policy area and legislative subjects, with update dates where modeled. |
| `LawMetadata` | Law `number` plus `law_type`; nested enactment metadata associated with a bill. |
| `Law` | `Bill` subclass adding `is_law=True`, not a separate search-index family. |
| `LawListItem`, `LawEntry` | Bill-like law-list result and its law number/type entries. Retain the bill number separately from `laws[].number`. |

`BillActionsResponse`, `BillAmendmentsResponse`, `BillCommitteesResponse`,
`BillCosponsorsResponse`, `BillRelatedBillsResponse`, `BillSubjectsResponse`,
`BillSummariesResponse`, and `BillTitlesResponse` describe paginated API
relationship envelopes, not independent index documents.

### Amendments and treaties

[`Amendment`](../../cdm/models/bills.py) contains congress/type/number,
description, purpose, latest action, update date, sponsors/cosponsors, actions,
text versions, submitted/proposed dates, chamber, amended bill, links, and
full text. `on_behalf_of_sponsor` and `behalf_type` describe introduction on
another member's behalf. `AmendmentMetadata` and `AmendmentListItem` are sparse
references/list records; `AmendmentLatestAction` also includes action time.
The amendment ID builder uses the `amendment:` prefix for complete identity.

`Treaty` models congress received/considered, treaty number/suffix, countries
or parties, transmitted/in-force/update dates, index terms, parts, related
documents, resolution text, topic, titles, and legacy numbering.
`TreatyListItem` is the lighter received/considered congress, number, parts,
suffix, topic, dates, and URL shape. Do not equate `congress_received` with the
bill-style `congress` attribute.

Enums in this family include `BillType`, `LawType`, `ChamberCode`,
`IdentifyingEntity`, and `BehalfType`. Chamber enums are not globally uniform:
API people use `House`/`Senate`, while Voteview uses `house`/`senate`.

## Committees, publications, communications, and records

| Family and source | Important data and join keys |
|---|---|
| `Committee`, `CommitteeMetadata`, `CommitteeListItem` in [bills](../../cdm/models/bills.py) / [other models](../../cdm/models/other_models.py) | `system_code` is the stable committee relationship key; name, chamber, type, URL, activities, subcommittees, history/current status, parent, website, and count/URL relationships describe the body. List records additionally expose `committee_type_code`. |
| `CommitteeMeeting`, `CommitteeMeetingListItem` | `event_id`, congress, chamber, URL/update date; detail adds title/name/status/date, committees, continuations, location, and videos. `event_id` is not a bill number. |
| `CommitteePrint`, `CommitteePrintListItem` | `jacket_number`, congress/chamber/URL/update date; detail also has citation, title/number, committee name, print date, committees, associated bills, and text. |
| `CommitteeReport`, `CommitteeReportListItem` | Citation and URL identify the publication; list records can include `cmte_rpt_id`, congress, chamber, type, number, and part. Detail has committee name/report date/type. |
| `Hearing`, `HearingListItem` | Jacket number, congress/chamber/number/part, URL and update date; detail includes title, citation, dates/formats, associated meeting, committees, and library identifier. |
| `HouseCommunication`, `HouseCommunicationListItem` | Congress/number/chamber, communication type, abstract, committees, congressional-record date, rulemaking flag, report nature, session, date, URL, subject, sender, and recipient; the list uses `CommunicationTypeInfo`. |
| `SenateCommunication`, `SenateCommunicationListItem` | Detail is a smaller type/date/URL/subject/sender/recipient shape; list carries congress/number/chamber/type/update date. Source shapes need not be symmetric between chambers. |
| `HouseRequirement`, `HouseRequirementListItem` | Detail type/description/date/URL versus list requirement number/update date/URL. |
| `CRSReport`, `CRSReportListItem`, `Topic` | Report title, publication date/version/content type/status/URL; detail adds summary/authors/topics. The detail normalizer accommodates a raw publication-date value. A report topic is not a BERTopic topic assignment. |

[`DailyCongressionalRecordIssue`](../../cdm/models/other_models.py) holds
congress, issue date/number, session, update date, URL, volume, and `full_issue`.
`FullIssue` holds articles, entire-issue entries, and sections.
`EntireIssueEntry` is part/type/URL; `DailySection` is page bounds/name/text.
The daily issue ID builder prefers
`daily-congressional-record:{volume}:{issue_number}`.

`BoundCongressionalRecordListItem` holds date, volume, congress/session,
update date, sections, daily digest, URL, and `reference_id`. Its normalization
accepts alternative bound-record shapes and can construct a URL from date.
`Section` carries start/end pages, title, and ordinal.
The ID builder distinguishes page-bounded sections when sufficient bounds
exist; `reference_id` points at the underlying issue.
The date-based base ID is `bound-congressional-record:{year}:{month}:{day}`,
with optional `:{start_page}:{end_page}`.
`CongressionalRecordIssue` is a separate generic issue shape with source ID,
links, publication date, session, and volume.

These are publication/issue references unless content has actually been
expanded. The default ingest policy does not hydrate bound/daily records.

## People, Congress metadata, nominations, and House votes

[`Member`](../../cdm/models/people.py) is keyed by `bioguide_id`, producing
`member:{bioguide_id}` through `EntityBase`. It includes first/full/last/middle
names, party, state/district, URL, depiction, address, website, leadership,
birth/death years, current-member status, honorific/direct/inverted names,
member type/state code, update date, and sponsored/cosponsored count/URL links.
Its nested `PartyHistoryItem`, `PreviousName`, and `MemberTermFull` preserve
historical affiliation, name variants, and service periods.

`Depiction` carries attribution/image URL, and `MemberAddress` contact fields.
`Sponsor` extends the member shape with sponsorship/withdrawal metadata;
the Python withdrawal field is spelled `sponsorship_withrawn_date`, with
upstream alias `sponsorshipWithdrawnDate`.
`SponsorRef` is a deliberately small optional Bioguide/name/state/URL
reference, also accepting non-person sponsors without a Bioguide ID.
`MemberListItem`, `MemberDepiction`,
`MemberTerms`, and `MemberTermItem` preserve the lighter list response,
including the `terms.item` wrapper. A full member is not automatically
flattened into the YAML member mapping's `name`, `party_name`, and `image_url`.

`Congress` has number/name/URL/update date, start/end year, and `Session`
entries (chamber, number, type, start/end dates). `CongressMetadata` permits
sparse versions of those fields. This is reference data, not a legislature's
bill membership list.

[`Nomination`](../../cdm/models/other_models.py) uses congress, nomination
number, and part number; includes citation/description/authority and received
dates/update date, nomination type/latest action, nominees, actions, hearings,
committees, position/status/URL/subjects. Its normalization accepts sparse and
alternative upstream fields. `NomineePosition` holds ordinal, nominee count,
organization, position title, introduction text, and URL.
`NominationListItem`, `NominationLatestAction`, and `NominationTypeInfo`
represent discovery data, including military/civilian flags.

`HouseRollCallVoteListItem` represents the Congress API vote source:
congress/session/roll-call number, identifier, start/update dates, vote
type/result, legislation and amendment references, party totals, vote
question/candidate totals, clerk `source_data_url`, URL, and API URL.
`VotePartyTotal` has yea/nay/present/not-voting totals; `VoteQuestion` has
question/result/required; `VoteCandidateTotal` has candidate/total.
This family is separate from Voteview rollcall documents and is not itself a
row per member vote.

`BillSummaryBill` and `BillSummaryListItem` preserve standalone summary-list
results: bill identity/reference plus summary text, action/update dates,
chamber, action description/version, and last-summary update date.
The ingest worker deliberately does not queue direct `summaries` indexing.
`RecordTypeBase` supplies legacy list record-type metadata. `Subject` is a
small name/update-date model alongside the report `Topic` fragment; neither
is a trained analytical topic or metasubject.

## IDs, references, and parameter types

[`UrlIdParser`](../../cdm/data_collection/id_utils.py) strips scheme, query,
and leading API version from a URL path, lowercases nonnumeric segments, and
joins segments with colons. Numeric segments are kept verbatim, not converted
to integers. `EntityBase.build_id()` prefers an existing ID, then member
Bioguide identity, then bill-style congress/type/number, then a generic
congress/number form, then URL identity.

[`CanonicalIdBuilder`](../../cdm/data_collection/id_utils.py) first tries a
model's builder, then its own fallback heuristics. Those fallback heuristics
are not identical to `EntityBase`: a plain Bioguide mapping can produce
`person:{id}`, and a plain explicit ID can become `id:{id}`.
The final `record:` fallback uses Python `hash()`, so it is not a durable,
cross-process content-addressed identity. Prefer a domain ID or source URL.
Archive fallback identity, by contrast, uses SHA-256 over canonical JSON.

[`IdStrategyApplier`](../../cdm/data_collection/id_strategy.py) can derive
`reference_id` from URL and append integer start/end page bounds to a base ID.
It resolves dotted paths, including numeric list indices. `unique_from` is
declared on `EndpointSpec.IdStrategy` but is not consumed by this applier.
The indexer normalizes legacy `referenceId` to `reference_id`.

### Indexed identity and relationship reference

These are application identities, not database-enforced foreign keys:

| Dataset | Document ID and joins |
|---|---|
| Bill in `congress-legislation` | Normally `bill:{congress}:{lowercase_type}:{number}`; archived introduced-date suffixes are removed before indexing. Sponsor/cosponsor arrays hold raw Bioguide IDs, joining `member.bioguide_id`, not the complete member document ID. |
| Member in `congress-member` | Normally `member:{bioguide_id}` via the model builder; Bioguide casing is retained by this builder. |
| House vote in `congress-house-vote` | Normalizer preserves an explicit ID; otherwise creates `house-rollcall-vote:{congress}:{session}:{roll}` or, without those components, `house-rollcall-vote:{identifier}`. It does not use a `house_vote:` prefix. |
| Voteview in `congress-rollcall` | `rollcall:{congress}:{house_or_senate}:{Voteview_roll_number}`; optional `legislation_id` is a canonical bill ID derived from an alphabetic type plus numeric bill label. |
| Voteview member position | No independent position-document ID: raw Bioguide IDs appear inside `yea_ids`, `nay_ids`, `present_ids`, `not_voting_ids`, and `defector_ids` on the rollcall. |
| Declared `vote_position` bridge | YAML convention `vote-pos:{congress}:{session}:{roll}:{bioguide_id}`, joining `house_vote_id`, `legislation_id`, and raw Bioguide ID; this is a declared convention, not a row emitted by the normal runners. |
| Declared `sponsorship` bridge | YAML convention `sponsor:{bioguide_id}:{legislation_id}`; likewise not automatically emitted by normal bill indexing. |

The House-vote normalizer is in
[`HouseRollCallVoteListItem`](../../cdm/models/other_models.py).
The [bill-vote lookup](../../cdm/backend/services/bill_vote_index.py) joins
House records using congress, uppercase `legislation_type`, and numeric
`legislation_number`; `to_document()` does not synthesize their mapped
`legislation_id`. Voteview instead writes `legislation_id` directly.
[VoteService](../../cdm/backend/services/vote_service.py) de-duplicates sources
using chamber/congress/session/roll, substituting **Clerk** roll number for
Voteview House records. Voteview's own roll number remains part of its ID.
The declared bridge position labels (`Yea`, `Nay`, `Present`, `Not Voting`)
are not the same spelling as Voteview's lowercase position enum.

[`identifiers.py`](../../cdm/models/identifiers.py) exports parameter wrappers
for event/jacket/volume/issue/requirement/report/bill/law/amendment/
communication/nomination/treaty numbers, treaty suffix, ordinal, and district,
plus `CommitteeCode`, `ReportType`, `CommunicationType`, and `StateCode`.
These constrain endpoint inputs; `District` here is a number wrapper, not the
GeoJSON district search document.

The [district importer](../../scripts/ingest_district_boundaries.py) writes
`district:119:{state_code}:{district}` with state code, integer district,
and source GeoJSON geometry. It reads the Census `CD119` attribute, skips
nonnumeric values, and does not generalize its schema to arbitrary Congresses.

[`EndpointSpec`](../../cdm/models/endpoint_spec.py) holds endpoint name,
method, path template, parameter specs, pagination, data/unwrap keys, response
model, ID strategy, and optional builder name. `ParamSpec` records location,
required/default/source-field/URL extraction metadata and `SchemaSpec`.
`PaginationSpec` describes offset/page/cursor parameter names and limits.
Validation checks required parameters and basic numeric types; it is not a
general JSON Schema validator.

## Job ledger and transport payloads

[`JobPayload`](../../cdm/jobs/payloads.py) ignores unknown fields and
`to_json()` excludes unset fields. Explicit defaults versus omitted defaults
can therefore affect serialized job identity.

| Payload | Contract |
|---|---|
| `IngestPayload` | Output root, resources/date window/congress, item-fetch controls, pagination/concurrency, indexing/raw flags, stale refresh, durable record retention, and schedule mode/date/week. |
| `IndexPayload` | Stream/resource/batch size/raw flag/group/expected count/archive root; optional target index, replacement, source attempt, and part. Batch compatibility compares resource, target, replace, and preserve-raw only. |
| `GovInfoPackagePayload` | Collection/congress/measure type/package ID/URL/session/version, output root, optional target and replacement flag. |
| `GovInfoBatchPayload` | List of independently durable package-job IDs. |
| `ReconcilePayload` | Archive root, target index, report path, and preserve-raw flag. |

[`JobStore`](../../cdm/jobs/store.py) uses SQLite through SQLAlchemy:

* `jobs`: primary `id`, kind, unique `idempotency_key`, JSON-text payload,
  status, attempts, last error, created/updated/started/finished timestamps.
* `ingest_windows`: composite `(job_id, resource)` key; date bounds/congress,
  status/fetch-items, discovered/hydrated/target counts, checkpoint offset,
  start/progress/completion timestamps, and last error. These are coverage
  observations, not proof that every expected search document exists.

Kinds are ingest, index, GovInfo package/batch, and reconciliation. Statuses
are queued/running/retrying/succeeded/failed/cancelled; coverage stages are
discovery/hydration. `JobRow`, `CoverageRow`, and `PrunedJob` are TypedDicts,
not Pydantic models. WAL mode, connection timeouts, and file locks coordinate
ledger operations. Retention preserves coverage history after removing jobs.

[`JobSubmitter.job_id()`](../../cdm/workers/dispatch.py) uses
`{kind}:{first_24_hex_of_sha256(sorted_compact_payload_json)}`.
`JobStore.create()` uses the supplied idempotency key as the job ID and
insert-if-absent semantics; it does not overwrite an existing payload.
`create_govinfo_bulk_job()` also offers a package-derived `govinfo:` key,
distinct from generic payload-hash submission.

## Archives, library, and GovInfo manifests

[`SQLiteRecordArchive`](../../cdm/ingest/archive.py) writes
`records.sqlite3`, table `records(resource, record_id, payload)`, with composite
primary key and zlib-compressed JSON BLOB. Writes are insert-or-ignore:
the first payload for an archive key wins, across attempts.
`JsonlRecordArchive` is a compatibility alias for this class, not a current
JSONL writer. A bill's introduced-date suffix can distinguish archived versions
that eventually collapse to one canonical search ID.

`LatestRecordArchive` uses the same layout but replaces payload on conflict.
[`RecordLibrary.archive(label)`](../../cdm/ingest/record_library.py) locates it
outside job directories. The ingest worker chooses `congress-{number}` or
`all`, and writes only when `retain_records=True`. This is a latest-record
library, not immutable source history.

`SQLiteListCache` uses `records(page_offset, record_id, payload)` in a separate
list database, deduplicating within page offsets and revalidating cached model
dumps by field name on load. `SQLiteQuarantineArchive` uses
`quarantined_records(failure_id, resource, record_id, source_url, payload,
error, captured_at)` in `quarantine.sqlite3`. Its failure key hashes resource,
stable record identity, and error; repeated same-key failures keep the first
compressed raw payload.

[`GovInfoPackage`](../../cdm/ingest/govinfo.py) is a frozen dataclass with
package ID/collection/congress/measure type/URL/session/version code.
`GovInfoCoverage` adds availability status/check time/error.
`GovInfoManifestStore` has `govinfo_packages`, keyed by
`(collection, congress, measure_type, package_id)`, with URL/session/version,
status/path/byte count/SHA-256/ETag/last-modified/fetched-at/parser-version/error.
The downloader also maintains `manifest.json`; neither is the job ledger.

## Stream, Voteview, and analytical documents

[`StreamEntry`](../../cdm/ingest/redis_stream.py) contains resource, JSON
record, and optional ingest metadata. Redis stores `resource` directly and
record/metadata as JSON strings in `congress:ingest:{job_id}:{resource}`.
Redis entry IDs are delivery IDs, not canonical document IDs. Repeated
publication is possible; indexing uses document identity for convergence.

[`voteview.py`](../../cdm/ingest/voteview.py) defines validated `MemberRow`,
`RollCallRow`, and `VoteRow` CSV boundaries, immutable `Member`/`CsvFile`,
and a generic `CsvReader`. `RollCallDocument` is keyed by
`rollcall:{congress}:{lowercase_chamber}:{roll_number}` and links a parseable
bill label to `legislation_id`. Its serialized position arrays contain raw
Bioguide IDs, not `member:` document IDs. Computed yea/nay counts, party
majorities, split flag, and defector IDs accompany the vote metadata.
The internal enum-keyed `positions` dictionary is excluded from serialization.

[`EmbeddingRecord`](../../cdm/store/embedding_store.py) contains document ID,
model, content hash, float vector, and embedding timestamp; `SimilarDocument`
and `PruneReport` describe search/prune results.
`IndexOutcome` in [batch indexing](../../cdm/store/batch_indexing.py) reports
indexed delivery count, batches, pending entries, stream length, status, and
optional archive replay count, not a search-index unique-document count.
[`JobResult`](../../cdm/workers/results.py) is a Pydantic task-return envelope
with optional job/status/skipped/cancelled/deferred/index-job/resource/batch
fields and allowed runner-specific extras. `RecoveryResult` and
`RetentionResult` in [maintenance](../../cdm/workers/maintenance.py) summarize
recovered IDs and pruned jobs/streams/archives/bytes/protected references.

Analytical persistence is intentionally separate from API models:
[topic rows](../../cdm/utils/topic_records.py),
[perspective models](../../cdm/perspectives/models.py),
[graph models](../../cdm/graph/models.py), and
[metasubject models](../../cdm/utils/metasubjects.py) describe derived results.
[Repositories](indexing.md#analytical-storage-outside-the-resource-mappings)
use model/build versions and kind discriminators to store/read them.
Manual names use append-only `OverrideVersion` records, where null names are
tombstones rather than deletion of history.
