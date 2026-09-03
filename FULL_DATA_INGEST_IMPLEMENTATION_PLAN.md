# Full Congressional Data Ingest and OpenSearch Migration Plan

## Objective

Replace the current predominantly list-level bill corpus with a complete, provenance-preserving legislative corpus and ensure every OpenSearch index can retain the full normalized record for its resource. The migration must be resumable, idempotent, observable, and reversible.

The desired end state is:

- Every supported Congress.gov resource is ingested across its documented historical coverage.
- Bills and resolutions have complete available metadata, relationships, summaries, subjects, actions, text-version metadata, and published text.
- OpenSearch contains hydrated records rather than `{count, url}` relationship envelopes where expanded data is available.
- No source fields are silently lost during model coercion or indexing.
- Sparse legacy documents are replaced or removed only after replacement documents pass validation.
- Every indexed document retains source and coverage metadata sufficient to explain what was fetched and from where.

## Non-goals

- Reconstructing data that an official source does not provide.
- Treating third-party mirrors as authoritative.
- Making every historical record have modern-era fields when the source does not contain them.
- Running an unbounded 412k-record Congress.gov API hydration before the bulk path is proven.

## Current Constraints and Risks

- `documentation/opensearch_mappings.yaml` uses `dynamic: false`; fields not explicitly mapped are not indexed.
- The `legislation` index currently has only a subset of bill detail fields.
- Existing bill documents are largely list-only and contain relationship count/URL envelopes.
- `cdm/ingest/runner.py` now calls `Bill.add_bill_details()`, but that path still requires pagination and is too expensive as the primary historical strategy.
- `cdm/store/opensearch.py::bulk_upsert()` merges documents. A merge can leave stale sparse fields unless replacement semantics or a clean staging index is used.
- Congress.gov API rate limits make API-only historical hydration impractical.
- GovInfo collections have different coverage and version conventions; missing coverage must be recorded, not interpreted as a failed fetch.
- Nested, free-form legislative records can cause OpenSearch mapping explosion if raw payloads are dynamically indexed without control.

## Source Strategy

### Source precedence

1. **GovInfo `BILLSTATUS` XML** for bulk bill and resolution metadata, actions, sponsors, cosponsors, committees, related bills, summaries, subjects, laws, votes, and text-version links.
2. **GovInfo `BILLS` XML/HTML/PDF** for the actual published text of each available bill version.
3. **GovInfo `BILLSUM` XML** as an independent summary source or fallback when a status record lacks summaries.
4. **Congress.gov API v3** for current deltas, reconciliation, records outside GovInfo bulk coverage, API-specific fields, and targeted repair of incomplete records.
5. **Third-party repositories** only as tooling, diagnostics, or comparison references. They must not replace official provenance.

### Official bulk locations

- `BILLSTATUS/{congress}/{type}/BILLSTATUS-{congress}{type}{number}.xml`
- `BILLS/{congress}/{session}/{type}/BILLS-{congress}{type}{number}{version}.xml`
- `BILLSUM/{congress}/{type}/BILLSUM-{congress}{type}{number}.xml`

Normalize GovInfo bill types (`H`, `S`, `HJRES`, `SJRES`, `HCONRES`, `SCONRES`, `HRES`, `SRES`) to the project's lowercase URL form (`hr`, `s`, `hjres`, etc.). Preserve the original package ID and version code.

### Coverage policy

- `BILLS` begins with the 103rd Congress for the supported bulk collection.
- `BILLSTATUS` begins with the 108th Congress in the released historical collection; verify actual directory availability before scheduling each Congress.
- Congress.gov API remains the fallback for older or missing official bulk coverage.
- A coverage report must distinguish `available`, `not_available`, `failed`, and `not_applicable`.

## Canonical Identity and Version Identity

### Measure identity

The canonical measure ID remains:

`bill:{congress}:{bill_type_lower}:{number}`

This is the ID used by the existing legislation index, member relationships, and bill-page routes. It must not include an introduced date or text version.

### Text-version identity

Every published version needs a stable child identity, for example:

`bill-text:{congress}:{bill_type_lower}:{number}:{version_code}`

At minimum, the parent bill document must retain an array of text-version records containing:

- version code and display name
- publication/action date
- GovInfo package ID
- XML, HTML, PDF, and source URLs when available
- text availability and extraction status
- content hash and byte size

Decide before production whether text versions are embedded in the legislation document, stored in a dedicated `bill_text` index, or both. The preferred design is a dedicated version index for large full-text payloads plus compact version metadata on the parent bill.

## Phase 1: Define the Normalized Contract

- [ ] Inventory every field in the current Pydantic models, raw fixtures, GovInfo schemas, and Congress.gov API responses.
- [ ] Create a bill field matrix with columns for source, model field, OpenSearch field, type, multiplicity, provenance, and coverage.
- [ ] Define explicit normalization for:
  - camelCase and snake_case aliases
  - Count/URL envelopes versus expanded collections
  - dates and timestamps
  - member identifiers, especially Bioguide IDs
  - committee system codes
  - law type and law number
  - GovInfo bill type and version codes
  - CDATA and embedded HTML in summaries, notes, and constitutional authority text
- [ ] Preserve source-specific values that cannot be safely normalized under a namespaced field rather than discarding them.
- [ ] Add a record-level coverage contract. A record is not `complete` merely because it has an ID; each resource declares which fields and relationships are expected for its source and Congress.
- [ ] Add model tests that compare representative raw payloads with normalized output and fail on unexpected field loss except for explicitly documented wrappers such as `request`.

### Bill completeness contract

A bill record should support, when available:

- identity, title, origin chamber, introduction date, update dates
- sponsor and on-behalf-of sponsor
- active and withdrawn cosponsors, including sponsorship dates
- committees, subcommittees, activities, and reports
- all actions, action sources, action codes, committees, votes, and links
- related bills and relationship details
- amendments and amendment references
- legislative subjects and policy area
- all summaries and summary version metadata
- all titles and title-version metadata
- all text versions and formats
- laws and enactment information
- notes and constitutional authority statement
- formatted full text where an official text format exists
- source URLs, package IDs, hashes, fetch timestamps, and coverage status

## Phase 2: Build the GovInfo Adapter

- [ ] Add a dedicated module under `cdm/data_collection` or `cdm/ingest` for GovInfo bulk discovery, download, validation, and parsing.
- [ ] Discover directory listings through the official bulk repository JSON/listing endpoint rather than guessing filenames.
- [ ] Support both individual XML files and collection ZIP downloads where practical.
- [ ] Make downloads resumable and content-addressed. Store URL, ETag/Last-Modified when available, byte size, SHA-256, and retrieval timestamp.
- [ ] Validate XML against the published schema when a schema is available; at minimum validate the root element, Congress, bill type, and bill number against the filename.
- [ ] Parse `BILLSTATUS` into the normalized parent bill model.
- [ ] Parse `BILLS` into text-version records and extracted text. Retain the original XML or a content-addressed raw artifact for reprocessing.
- [ ] Parse `BILLSUM` only when needed for missing or independently verified summaries.
- [ ] Treat malformed XML, mismatched identity, HTTP errors, and unavailable packages as explicit failures with retry state.
- [ ] Never turn a missing collection into an empty list without recording the source coverage reason.

### Required adapter tests

- [ ] Parse one introduced bill, one amended bill, one enrolled bill, and one enacted bill.
- [ ] Parse a bill with multiple sponsors/cosponsors and withdrawn cosponsors.
- [ ] Parse actions with different source systems and recorded vote links.
- [ ] Parse summaries and notes containing CDATA/HTML.
- [ ] Parse a measure with multiple text versions and formats.
- [ ] Verify filename/package identity mapping for all supported measure types.
- [ ] Verify malformed, empty, unavailable, and schema-incompatible inputs fail loudly and leave retryable artifacts.

## Phase 3: Make Congress.gov Hydration Correct and Targeted

- [ ] Make every detail collection in `Bill.add_bill_details()` pagination-aware.
- [ ] Follow the returned pagination metadata until all pages are consumed, with a request limit and retry policy.
- [ ] Record expected count, fetched count, page count, and completeness for every collection.
- [ ] Distinguish an intentionally empty collection from a failed collection and from an unexpanded Count/URL envelope.
- [ ] Fetch API details only for:
  - current or recently updated measures
  - records outside GovInfo bulk coverage
  - records whose bulk/API reconciliation fails
  - records requested by a user or repair job
- [ ] Keep the existing compatibility behavior for fake/test item objects.
- [ ] Add a bounded repair queue rather than embedding unlimited retries in the item fetch path.

### Hydration metadata

Add normalized metadata such as:

- `hydration_status`: `complete`, `partial`, `failed`, `not_available`, or `list_only`
- `hydrated_at`
- `hydration_sources`
- `hydrated_relationships`
- `relationship_counts_expected`
- `relationship_counts_fetched`
- `hydration_errors`
- `source_updated_at`
- `raw_artifact_hash`

These fields must be queryable and must be included in audit reports.

## Phase 4: Expand OpenSearch Mappings

### Mapping principles

- [ ] Keep stable, high-value fields explicitly mapped and typed.
- [ ] Add all normalized bill detail fields to `legislation`.
- [ ] Add all normalized fields required by the other resource models to their target indices, including nested collections and source metadata.
- [ ] Use `nested` for arrays where relationships between fields in the same array item matter, such as actions, cosponsors, summaries, text versions, committees, and related bills.
- [ ] Use `keyword` for identifiers, codes, URLs, package IDs, and exact categories.
- [ ] Use `date` with the repository's existing strict date format for dates and timestamps.
- [ ] Use `text` plus `.keyword` and `.lemma` only for fields intended for search.
- [ ] Use `flattened` or an `enabled: false` raw object for unpredictable source payloads rather than dynamically mapping arbitrary nested keys.
- [ ] Preserve the full raw record in `_source` under `_raw` when configured, even when selected raw fields are not indexed.
- [ ] Add mapping validation that reports unknown normalized fields and raw-field counts; do not silently treat `dynamic: false` as successful full indexing.

### Legislation mapping additions

The legislation mapping should explicitly cover, as applicable:

- `introduced_date`, `update_date_including_text`, and source timestamps
- sponsor and on-behalf-of sponsor objects or normalized IDs
- `cosponsors` with Bioguide ID, name, sponsorship date, original-cosponsor flag, and withdrawal date
- `actions` with dates, text, type, action code, source system, committees, votes, and links
- `committees` and subcommittees with system codes, names, chambers, types, activities, and reports
- `related_bills` with measure identity and relationship details
- `amendments` with identity, description, purpose, and latest action
- `subjects`, `policy_area`, and primary/other subject terms
- `summaries` with version code, action description/date, update date, chamber, and text
- `titles` with title type, chamber, version code, and text
- `text_versions` with version identity, dates, formats, package IDs, and status
- `full_text` or a dedicated text-index reference, plus extraction metadata
- `notes`, `constitutional_authority_statement_text`, and `laws`
- `source`, `source_urls`, `source_package_ids`, `coverage`, and hydration metadata

### Other indices

Perform the same field-contract audit for:

- amendment
- communication
- committee
- committee meeting
- committee print
- committee report
- congressional record
- hearing
- house vote
- member
- nomination
- treaty
- congress reference
- house requirement
- sponsorship
- vote position

For each index, explicitly decide whether large raw content belongs in the primary index, a dedicated content index, or durable SQLite/object storage with a searchable reference. The decision must never result in silently dropping the source record.

### OpenSearch versioning

- [ ] Update `documentation/opensearch_mappings.yaml` as the versioned mapping source.
- [x] Add mapping version metadata to index mappings and require it during staging validation.
- [x] Use `IndexManager.create_versioned()` to create new staging indices.
- [ ] Do not rely on an in-place mapping update for fields whose type, nestedness, analyzer, or object structure changes.
- [ ] Confirm shard/replica sizing and refresh settings for the expected full corpus before the bulk load.
- [x] Add a mapping smoke test that indexes representative fully hydrated documents for every target index and reads them back.

## Phase 5: Durable Bulk Ingest and Reconciliation

### Acquisition and archive

- [x] Add a durable job type for GovInfo bulk collections with Congress, session, measure type, collection, and version as idempotency dimensions.
- [x] Store raw XML and download manifests under a dedicated archive path or content-addressed store.
- [x] Record each package's retrieval result in SQLite with status, checksum, parser version, and last attempt.
- [x] Support resume by package and by collection directory.
- [x] Separate download, parse, normalize, validate, and index stages so a parser fix does not redownload the corpus.

### Normalization and merge rules

- [ ] Normalize GovInfo and Congress.gov records into the same parent bill contract.
- [x] Merge by canonical measure ID, never by title or URL text.
- [x] Use field-level source precedence:
  - GovInfo for published text and bulk status fields.
  - Congress.gov for canonical API relationship collections and API-only fields.
  - Newer source update timestamps win when the field semantics are equivalent.
- [ ] Do not replace a nonempty expanded collection with a Count/URL envelope.
- [ ] Do not replace a complete collection with an empty collection caused by a failed request.
- [x] Preserve disagreements in reconciliation diagnostics and retain both source references until resolved.
- [ ] Rebuild derived sponsorship and member-activity bridge records after parent legislation is complete.

### Indexing semantics

- [x] Add a replacement/upsert mode that writes the complete normalized document, not only a partial merge.
- [ ] Ensure a failed partial document cannot overwrite a previously complete document.
- [ ] Use bulk result checking and retry only failed operations.
- [ ] Route documents with invalid IDs, invalid dates, mapping conflicts, or incomplete required fields to a quarantine stream.
- [ ] Acknowledge Redis entries only after successful indexing and durable failure recording.

## Phase 6: Populate a Staging Corpus

- [x] Run a bounded proof of concept for the 118th Congress: one House bill, one Senate bill, and one resolution.
- [x] Compare normalized results against Congress.gov API responses for the same measures.
- [x] Measure relationship collection completeness and field parity before scaling.
- [x] Load the selected proof-of-concept documents into a versioned `legislation` staging index.
- [x] Verify that full text, nested relationships, and source metadata survive an OpenSearch round trip.
- [ ] Expand to one complete Congress and compare document counts, package counts, and coverage reports.
- [x] Add a corpus coverage report that compares discovered packages with durable manifests and distinguishes pending, failed, and unavailable packages.
- [ ] Expand to the full supported historical range only after the one-Congress acceptance gates pass.
- [ ] Populate all non-bill resources through the same staged-index process, using their existing scope catalog and checkpoints.

## Phase 7: Remove Sparse Legacy Records Safely

Sparse records must not be deleted before a replacement exists.

- [ ] Define a sparse-record query using `hydration_status`, relationship envelope shape, missing text-version fields, and missing source coverage metadata.
- [ ] Export the IDs and checksums of sparse legacy records before migration.
- [ ] Load replacement documents into staging using the same canonical IDs.
- [ ] Verify replacement count and ID-set coverage against the export.
- [ ] Verify that every replacement bill meets the applicable completeness contract or has an explicit `not_available`/`partial` reason.
- [ ] Verify zero unexpected Count/URL envelopes for fields declared bulk-expandable.
- [ ] Verify zero mapping failures and zero unacknowledged bulk failures.
- [ ] Atomically switch read and write aliases from the old index to the validated staging index.
- [ ] Retain the old physical index for a defined rollback window.
- [ ] Delete the old index only after production read checks and reconciliation reports pass.
- [ ] Do not use an in-place delete-by-query as the primary migration mechanism; it is not atomic and makes rollback difficult.

## Phase 8: Rebuild Derived Relationships

- [ ] Rebuild `sponsorship` from complete sponsor/cosponsor collections.
- [ ] Rebuild member recent activity from canonical parent bill IDs.
- [ ] Recompute sponsor and cosponsor Bioguide ID arrays on every legislation document.
- [ ] Rebuild vote-position relationships from complete vote records and official roll-call sources.
- [ ] Validate bidirectional queries:
  - member -> sponsored bills
  - member -> cosponsored bills
  - bill -> sponsors
  - bill -> cosponsors
  - bill -> related bills
  - bill -> amendments
- [ ] Ensure bridge rebuilds are idempotent and do not retain rows for deleted or quarantined parent records.

## Phase 9: Incremental Operation After Backfill

- [ ] Run a scheduled GovInfo `BILLSTATUS` refresh for current and recently changed Congresses.
- [ ] Refresh new and changed `BILLS` text packages using directory modification metadata and content hashes.
- [ ] Use Congress.gov list endpoints sorted by update date for an incremental repair/reconciliation queue.
- [ ] Hydrate only changed or incomplete API records, with the shared rate limiter.
- [ ] Re-run reconciliation when a bill's status, text version, sponsor, cosponsor, or committee set changes.
- [ ] Keep parser and mapping versions in the job ledger so historical records can be reprocessed deterministically.
- [ ] Emit daily coverage metrics and alert when complete records regress to partial or list-only status.

## Validation and Acceptance Gates

### Functional gates

- [ ] Focused model and parser tests pass.
- [ ] Pagination tests prove all pages are consumed and counts are compared.
- [ ] XML/package identity tests pass for all measure types.
- [ ] OpenSearch round-trip tests preserve nested fields and full text.
- [ ] Every target index accepts a representative full record without mapping errors.
- [ ] Bill pages render actions, sponsors, cosponsors, committees, subjects, summaries, text versions, and full text when source data exists.

### Corpus gates

- [ ] Expected package counts reconcile with downloaded and parsed package counts.
- [ ] Every scheduled scope has a coverage result.
- [ ] Every indexed document has a canonical ID and source metadata.
- [ ] No record classified `complete` has unexpanded relationship envelopes for expandable collections.
- [ ] No record classified `complete` has a parser, mapping, or indexing error.
- [ ] Replacement staging index has the expected ID set and no unexpected duplicate IDs.
- [ ] Full-text availability and extraction success are reported separately from bill metadata completeness.

### Operational gates

- [ ] Jobs resume after process termination without duplicating documents.
- [ ] Failed downloads and failed bulk operations are retryable and visible.
- [ ] Quarantined records are queryable and reprocessable.
- [ ] Alias cutover is atomic and rollback is tested.
- [ ] Old sparse index remains available through the rollback window.
- [ ] OpenSearch health, disk usage, rejected bulk requests, refresh latency, and mapping conflicts are monitored.

## Rollback Procedure

1. Stop new writes to the affected logical index.
2. Confirm the old physical index still exists and its aliases are known.
3. Use `IndexManager.switch_aliases_to_versioned()` or an equivalent atomic alias update to restore the old index.
4. Preserve failed staging documents, manifests, and reconciliation reports for diagnosis.
5. Fix the parser, model, mapping, or indexing defect.
6. Create a new staging index version and repeat validation; never mutate the failed staging index into an undocumented state.

## Suggested Execution Sequence

1. Implement and test the GovInfo directory/download proof of concept.
2. Implement `BILLSTATUS` and `BILLS` normalization for one Congress and measure type.
3. Add complete bill mappings and raw/provenance metadata.
4. Make API relationship hydration pagination-aware.
5. Populate and validate a versioned legislation staging index.
6. Rebuild sponsorship and member activity from validated legislation.
7. Expand the bulk adapter across bill types and Congresses.
8. Audit and expand mappings for all other indices.
9. Populate all staged indices and run corpus acceptance gates.
10. Atomically switch aliases, retire sparse records after the rollback window, and enable incremental refresh.

## Deliverables

- GovInfo bulk downloader, manifest, parser, and normalized adapter.
- Expanded bill and all-resource OpenSearch mappings.
- Mapping/version migration command and staging-index validation reports.
- Pagination-aware targeted API hydration and repair queue.
- Complete-corpus coverage and reconciliation reports.
- Sparse-record export, replacement validation, alias cutover, and rollback runbook.
- Focused parser, model, mapping, integration, and end-to-end bill-page tests.
