# Indexing, mappings, and delivery guarantees

The executable mapping source is
[`documentation/opensearch_mappings.yaml`](../opensearch_mappings.yaml), loaded
by [`load_definitions()`](../../cdm/store/index_manager.py). Its introductory
comments are historical: there are **21** logical definitions, not 17.
The runtime also creates analytical indices outside this YAML.
For individual declarations, use the [store](symbols/store.md) and
[worker](symbols/workers.md) symbol indexes.

The [shipped deployment](../../README.md) runs self-managed Elasticsearch 9.
The project retains OpenSearch in filenames and many APIs, but uses the Python
`elasticsearch.Elasticsearch` client and its bulk helpers.
[`ElasticClientFactory`](../../cdm/store/client.py) constructs
`Elasticsearch(url, api_key=...)` from injected configuration; it does not set
the compatibility header described in an older `IndexManager` docstring.
Historical names are not evidence of an OpenSearch deployment, and OpenSearch
is not a verified drop-in replacement. Dense-vector/kNN APIs in particular
require actual server compatibility.

## Resource routing and names

[`resource_target()`](../../cdm/store/opensearch.py) maps resources to logical
indices and mandatory discriminators:

| Resource | Logical target | Discriminator added to each transformed record |
|---|---|---|
| `bill` | `legislation` | `source_type="bill"` |
| `bill_text` | `legislation` | `source_type="bill_text"` |
| `law` | `legislation` | `source_type="law"` |
| `house_communication` / `senate_communication` | `communication` | `chamber="House"` / `"Senate"` |
| `bound_congressional_record` / `daily_congressional_record` | `congressional_record` | `record_subtype="bound"` / `"daily"` |
| `congress` | `congress_ref` | None |
| Other resource names | Same logical name | None |
| `summaries` | Rejected | Summaries are embedded in legislation; direct indexing raises. |

`index_name()` prefixes `congress-` and converts underscores to hyphens:
`committee_meeting` becomes `congress-committee-meeting`.
`read_alias()` and `write_alias()` append `-read` and `-write`.
Default bulk writes use the write alias; an explicit `target_index` bypasses
that alias. A declared logical mapping is not proof of a populated index.

## Complete YAML family catalog

All definitions have root `dynamic: false` and one replica. Shard counts below
come from the YAML, not a recommendation for any particular deployment.
Common `id`, URL, and record-type fields are keyword unless noted.
Date mappings generally accept `strict_date_optional_time||yyyy-MM-dd`.
Text fields and their keyword/lemma multi-fields are explicitly declared;
not every string is full-text searchable and not every text field has every
multi-field.

| Logical family | Shards | Declared searchable content and important joins |
|---|---:|---|
| `legislation` | 3 | Bill/law/text source discriminator; congress/type/bill_type/number/version/reference ID; titles/full text, sponsors/cosponsors, normalized relationships, subjects, summaries, enactment metadata, dates and provenance. Details below. |
| `amendment` | 2 | Congress/number, `amendment_type`; `amended_bill_id`, congress/type/number components; sponsor ID/name and sponsor/cosponsor ID arrays; description/purpose; submitted/update dates. |
| `communication` | 2 | Chamber, congress, numeric number, `communication_type_code`, searchable type name, update date. |
| `committee` | 1 | `system_code`, name, chamber/type code; flattened parent name/code/URL and subcommittee-code array; update date. |
| `committee_meeting` | 2 | Integer event ID, congress, chamber, update date. Rich detail fields are not all mapped. |
| `committee_print` | 1 | Congress/chamber/integer jacket number/update date. |
| `committee_report` | 1 | Congress/chamber/citation/update date. |
| `congressional_record` | 2 | Bound/daily subtype, reference ID, congress/volume/session/issue number, issue/update dates. |
| `hearing` | 2 | Congress/chamber/integer jacket number/number/update date. |
| `house_vote` | 2 | Clerk source URL, congress/session/roll-call number, long identifier, vote type/result, legislation type/number/ID, amendment type/number/author, start/update dates. |
| `member` | 1 | Bioguide ID, searchable name, state/party name/district/image URL, nested terms, update date. |
| `district` | 1 | State code/district number and `geometry: geo_shape`; identity joins map reads to district metadata. |
| `nomination` | 1 | Congress/number/part/citation, description/organization, civilian flag, received/latest-action/update dates and latest-action text. |
| `treaty` | 1 | Congress received, number/suffix, searchable topic, transmitted/update dates. |
| `crsreport` | 1 | Title/status/summary/authors, nested report topics with update dates, publication date. |
| `congress_ref` | 1 | Congress number/name/year bounds, nested sessions, update date. |
| `house_requirement` | 1 | Requirement number/update date. |
| `sponsorship` | 2 | Bioguide ID ↔ legislation ID, congress, sponsorship type/original flag, member name/state/party, sponsorship/withdrawal dates. |
| `vote_position` | 3 | Bioguide ID ↔ House-vote ID and legislation ID; congress/session/roll-call, position, party/state/member name/vote date. |
| `rollcall` | 1 | Voteview congress/chamber/session/roll/clerk-roll/date, question/description/result/bill label/legislation ID; counts, party split/positions, per-position and defector Bioguide arrays. |
| `analysis_graph` | 1 | Kind/signal/graph version/build time; member/neighbor/score/shared-bill/shared-vote counts; nested per-congress graph statistics. |

`sponsorship` and `vote_position` are declared bridge schemas. The normal
Congress ingest/index runners do not derive their rows from bill or clerk
payloads. Do not infer automatic bridge population from YAML comments.
The maintained bill-member backfill instead writes relationship ID arrays
onto bill documents:
[`backfill_bill_member_links.py`](../../scripts/backfill_bill_member_links.py).
Voteview writes aggregate rollcall documents, not `vote_position` rows.

### Legislation object layout

The searchable nested collections are `actions`, `amendments`, `cosponsors`,
`committees`, `related_bills`, `titles`, `text_versions`, `notes`, `laws`, and
`summaries`. Their declared properties are:

* Actions: date/code/type/text/time and source-system name/code.
* Amendments: ID/congress/number/type/description/purpose/URL.
* Cosponsors: Bioguide ID, full/first/last names, sponsorship date.
* Committees: system code/name/chamber/type/URL, activities, subcommittees and
  subcommittee activities.
* Related bills: ID/congress/number/type/title/URL.
* Titles: type/title/text/chamber/version code.
* Text versions: type/date/formats/package ID/source URL.
* Notes: text/type. Laws: number/law type.
* Summaries: version code/action description/current chamber/action date/
  last-summary update date/text.

`subjects` is an object containing a policy-area object and nested
`legislative_subjects` (name). `sponsors` is an ordinary object mapping,
including Bioguide ID/name/party/state/district, not a nested mapping.
Top-level `policy_area` is an object with name.
`latest_action` contains date/time/text; separate flattened
`latest_action_date` and `latest_action_text` also exist in the mapping.
`cbo_cost_estimates` and `text_versions.formats` have `enabled: false`.
Raw `full_text` has `index: false`; its injected `full_text_lemma` sibling is
the searchable normalized field. The declared `.lemma` multi-field also
exists, but it does not store a separate input value.

Provenance includes hydration status/time/sources/relationships/errors,
source-updated timestamp, artifact hash, source URL/package arrays, and
`source_metadata` (collection/package ID/URL/source).
`detail_hydration` declares a flat completeness object, although the bill
model currently emits a dictionary keyed by endpoint name.
The versioned `hydration_assessment` is explicitly `object, enabled: false`:
validated evidence remains in `_source` for the API, without dynamically indexing
endpoint keys or duplicating searchable status fields. Queries use the existing
`hydration_status` keyword, which the projection derives from that assessment;
legacy labels alone do not prove completeness.
Searchable enactment fields include `is_enacted`, `law_number`, `law_type`,
and nested `laws`; a `Law.is_law` model attribute alone does not populate them.

### Other nested fields and source-only values

Member `terms` map chamber/start year/end year. Congress-reference `sessions`
map chamber/number/type/start/end date. CRS report `topics` map topic/update
date. Graph `by_congress` maps congress, member/neighbor sponsored counts,
co-signed/shared/agreed vote and split-vote counts, and score.
Rollcall `party_positions` is `object, enabled: false`.

With `dynamic: false`, undeclared fields remain in `_source` but receive no
search mapping; they are not discarded from the stored source. This includes
many rich item-model fields, `_resource`, and optionally `_raw`.
An `enabled: false` object is likewise retained but not parsed/indexed.
These settings do not turn malformed values for declared mapped fields into
valid data: server-side type parsing can still reject a write.
Use nested queries where a mapped nested collection's per-element association
matters; ordinary object arrays do not preserve nested query isolation.

## Document construction is intentionally limited

[`to_document()`](../../cdm/store/indexer.py) performs these operations:

1. Copy the record and overlay resource routing discriminators.
2. Overlay optional ingest metadata.
3. If ID is absent, derive it from URL; reject records with neither.
4. Normalize `referenceId`/`reference_id` to string `reference_id`.
5. For bills and amendments, derive sponsor/cosponsor Bioguide ID arrays from
   list-valued relationship objects using either Bioguide field spelling.
6. For bills, strip an introduced-date suffix from the canonical bill ID.
   Convert a single `source_metadata` dictionary to a list and derive source
   package/URL arrays from that entry.
7. Preserve `_raw` only if both `preserve_raw=True` and a separate
   `raw_record` argument are supplied.
8. Populate mapping-declared lemma siblings and default `_resource`.

It does **not** generally flatten members, committees, communications,
nominations, or latest actions into every flattened YAML field. It does not
join standalone summary-list records into legislation at index time, nor
populate bridge documents or rename `recordType` to `record_type`.
A mapped field can therefore be empty even while
a corresponding nested API value survives in `_source`.
Stream/archive index callers do not supply `raw_record`, so their
`preserve_raw=True` flag alone does not reconstruct original API payloads.

### Lemmatization

[`load_definitions()`](../../cdm/store/index_manager.py) recursively injects
real `{field}_lemma` siblings wherever a text mapping declares a `.lemma`
multi-field. Siblings use the whitespace analyzer; the original multi-field
cannot hold a different spaCy-generated value.
`lemma_field_paths()` caches paths, and `to_document()` traverses nested
objects/lists and calls
[`lemmatize_texts()`](../../cdm/utils/lemmatize.py) on nonblank strings.
The raw field remains intact. A failed/missing enrichment should not be
mistaken for a server analyzer generating the sibling automatically.

## Upsert and replacement semantics

[`bulk_upsert()`](../../cdm/store/opensearch.py) materializes input documents,
skips missing IDs, and sends actions through the Elasticsearch bulk helper
with `raise_on_error=False`. The result reports successful actions, whether
errors occurred, skipped missing IDs, and at most three error details.
An empty action set returns success with zero updates; successful action
count is not automatically equal to input count.

| Mode/resource | Actual write |
|---|---|
| `replace=True`, any resource | Full `_op_type="index"` replacement at the document's own ID. No resource-specific merge or parent-text action. |
| Default `bill` | Scripted upsert with special nonempty merging. |
| Default `bill_text` | Scripted update of canonical parent bill; no standalone child write. |
| Default other resources | Partial `doc` update with `doc_as_upsert=True`. |

Bill merge ignores nulls, empty strings, and empty incoming lists. Nonempty
lists are unioned using full-value equality; an existing scalar becomes a
list if a list arrives. Incoming/existing maps merge shallowly using
`putAll`; other nonempty scalars overwrite. This is not a recursive merge,
a deletion protocol, or a semantic deduplication by member/action identity.
Removing a cosponsor upstream does not remove its old list entry this way.
All update actions request eight retries on version conflicts.

### Published text selection

`bill_text_parent_action()` requires congress/type/number and nonempty text.
It targets `bill:{congress}:{type}:{number}`, fills missing identity metadata,
and replaces text only if no full text exists or the existing ranked text
has rank less than or equal to the incoming rank.

| Version codes | Rank |
|---|---:|
| `ih`, `is`, unrecognized/absent code | 0 |
| `rh`, `rs`, `rds`, `rcs`, `pcs` | 1 |
| `eh`, `es`, `eas` | 2 |
| `enr` | 3 |

Equal-rank arrival can overwrite text. Existing unranked full text, such as
API-hydrated text, is protected from this parent merge. Stored selection fields
are `full_text_version_code` and `full_text_version_rank`; text and lemma
change together. This does not impose priority on later ordinary bill merges.

The reconciliation replay uses replacement mode for parent **and** text
records. It therefore stores `bill-text:...` child documents, rather than
running this parent-text selection step. Those are different storage modes,
not interchangeable ways of replaying published text.

Controlled historical law-text publication is a separate parent-only operation.
[`StatuteTextEnricher`](../../cdm/ingest/statute_text.py) fills blank text and its
lemma while preserving existing details, hydration, analysis and law/PDF evidence.
It adds `govinfo:statute` provenance and `public-law-<congress>-<number>` or
`private-law-<congress>-<number>` version codes, not a bill-draft rank or synthetic
`bill-text:` child. These unranked full texts retain the existing protection from
GovInfo parent-text replacement above. Publication uses frozen-version conditional
writes and exact source/version/API checks, not additive upsert. Existing mapping
fields suffice; extra component/volume hashes remain in stored source metadata.

## Validation and index lifecycle

[`audit_document()`](../../cdm/store/mapping_validation.py) reports top-level
unmapped fields (except `_resource`/`_raw`) and discriminator mismatches.
`validate_document()` rejects only missing/truthy-ID failure or discriminator
mismatch, while also requiring a mapping definition to exist.
It does not recursively validate mapped field types, reject unmapped fields,
or compare the live cluster mapping. Server bulk errors remain significant.

[`IndexManager`](../../cdm/store/index_manager.py) provides:

* `create()`/`create_all()`: create canonical physical indices from YAML and
  ensure aliases; existing indices are not remapped automatically.
* `ensure_aliases()`: add missing read/write aliases only; existing aliases
  are never moved by this method.
* `update()`/`update_all()`: apply mappings, not shard/replica settings.
* `create_versioned()`: create `congress-{family}-v{version}` without aliases.
* `reindex_to_versioned()`: copy from canonical physical source, synchronously,
  and fail if the server reindex response contains failures.
* `validate_versioned()`: compare normalized mappings/version metadata, source
  and target counts, absence of target aliases, and up to three sampled
  `_id`/source-ID matches.
* `switch_aliases_to_versioned()`: validate then atomically remove both aliases
  from the canonical source and add them to staging.
* `delete(confirm=True)`: explicitly destructive physical-index deletion.
* `status()`/`audit()`: physical-index presence/count/mapping observations.

Mappings receive `_meta.mapping_version="2026-09-01.1"` at creation/update.
Staging validation is count/mapping/sample validation, not a full content
diff. Its source is the canonical physical name, not whichever index an alias
currently targets; the switching helper also assumes that canonical source.
Do not assume it implements arbitrary repeated rolling migrations.

## Redis consumption, acknowledgment, and replay

[`RedisRecordStream`](../../cdm/ingest/redis_stream.py) creates consumer
groups from `0-0`, claims pending entries idle for at least 60 seconds via
`XAUTOCLAIM`, then reads fresh `>` entries. It decodes payloads to
`StreamEntry`. Streams use approximate max-length trimming (default one
million entries); acknowledging does not delete stream entries.

[`StreamIndexer`](../../cdm/store/batch_indexing.py) can share bulk requests
across compatible jobs. It constructs and validates documents before buffering,
flushes at the configured shared document threshold, and acknowledges entry
IDs **only after the whole bulk result reports no errors**.
A partial bulk failure may already have written some documents, but all
contributors to that buffer are failed and their entries remain pending.
Re-delivery can repeat already-successful actions.

Decode/transform/validation exceptions fail the owning stream job and do not
acknowledge the offending batch. Earlier buffered valid entries may still be
flushed; stream processing is not transactional. An acknowledgment failure
after a successful bulk also permits repeat delivery.
Recently pending entries can remain unavailable until the idle threshold.

[`IndexJobRunner`](../../cdm/workers/index_runner.py) rejects outcomes with
nonzero pending count. If a job supplies `expected_count` and the current
indexed delivery count is lower, `ArchiveReplayer` reads
`archive_root/records.sqlite3`, transforms/validates records, and replays all
records of that resource in batches. It checks indexed-plus-replayed count,
not unique-document equivalence. Jobs without an expected count do not get
this missing-stream completeness fallback.

Partial ingest index jobs include source attempt/part for ledger identity and
usually omit expected count. Compatible jobs can drain the same stream; their
counts are per invocation, not globally partitioned record counts.
If an explicit staging index is missing, live stream indexing falls back to
the normal write alias with a warning. Archive replay still uses the payload's
target index; do not assume both paths resolve targets identically.

## Analytical storage outside the resource mappings

[`EmbeddingStore`](../../cdm/store/embedding_store.py) receives its index
name, model, and batch size through construction. It creates model keyword,
unindexed content hash, embedding date, and an indexed cosine `dense_vector`
of the supplied dimension. `_id` is the canonical document ID; source excludes
the `doc_id` field. Cache freshness hashes `model + NUL + text`.
Pruning removes vectors outside the retained ID set or from another model.
kNN similarity excludes the queried document and requests ten times as many
candidates as results. This index is not created by YAML `create_all()`.

Topic/metasubject/perspective repositories also receive configured index names.
[`MetasubjectRepository`](../../cdm/store/metasubject_repository.py) produces
`metasubject:{model_version}:{id}` and
`metasubject_over_time:{model_version}:{ordinal}` documents; its newest-model
read sorts by training timestamp and examines at most 200 hits.
Its additional mappings include assignment metadata/topic IDs and unindexed
centroid arrays.

[`PerspectiveRepository`](../../cdm/store/perspective_repository.py) stores
`party_topic:{model_version}:{congress}:{topic_id}`. `replace()` removes that
Congress's prior party-topic documents before bulk writing; this is not an
atomic swap. Large nested party-bill/term/bilateral/perspective payloads are
stored as disabled objects. Reads sort by build time, select the first hit's
model version, and return matching hits within a 10,000-document scan.

[`MetasubjectOverrideStore`](../../cdm/store/metasubject_override_store.py)
creates its own integer-ID/version, keyword-name, date mapping. New edits use
`{metasubject_id}:{version}`, `op_type="create"`, and `refresh="wait_for"`.
History is append-only; clearing appends a null-name tombstone. Current names
come from the latest version per ID within a 10,000-record history read.
These repositories do not establish universal retention, unlimited paging,
or transactional consistency across all analytical datasets.
