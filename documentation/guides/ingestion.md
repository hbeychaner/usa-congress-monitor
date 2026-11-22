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

## Reconcile existing data before historical acquisition

Before launching a large historical download from Congress.gov or GovInfo,
check what is already indexed in Elasticsearch and what raw archives are
already saved on disk:

1. **Check existing bill IDs:** Compare canonical bill IDs across bill and law
   projections (`bill:<congress>:<type>:<number>`). Do not re-download a bill
   simply because its completeness badge is `unknown`.
2. **Preserve indexed records:** Leave already indexed bills untouched during
   missing-record backfills so existing GovInfo text and analytics are
   preserved.
3. **Reuse local SQLite archives first:** Central job archives and the record
   library (`records.sqlite3`) and list discovery caches
   (`bill/list_records.sqlite3`) often already contain the needed records.
4. **Distinguish list metadata from full detail:** List caches provide title,
   introduced date, and latest action, whereas full item archives include
   summaries, committees, and text versions.
5. **Write missing bills safely:** Use
   [`CreateOnlyBillWriter`](../../cdm/store/create_only.py) with a pinned
   [`CreateOnlyTarget`](../../cdm/config/create_only.py) when replaying
   missing records so existing documents are never overwritten.

See [manual serving repair safety](../OPERATIONS_RUNBOOK.md#manual-serving-repair-safety)
for targeted repairs of already indexed fields.

### Full-detail and full-text coverage

Compare actual indexed fields with retained item/detail/text payloads before
planning additional acquisition. An archived identity already being indexed does
not prove that every archived field was incorporated. Conversely, an absent
versioned assessment does not prove that the content is missing.

For each bill and required collection/text version:

1. Reuse content already indexed. Inspect nonblank stored `full_text`, actual
   expanded records and text-version formats/URLs, not only lemma existence,
   nested-row totals or unversioned `hydration_status` labels.
2. Compare retained central archives, record-library variants and staged recovery
   archives against those fields. Preserve richer indexed values and flag
   conflicting variants for semantic reconciliation; exact-value differences
   alone are not authorization to overwrite.
3. Acquire only available content absent from both indexed and usable local
   inputs. Prefer supported official bulk sources before per-item API calls.
   Scope work by exact missing fields/versions rather than re-fetching all nine
   collections for every existing identity.
4. Track indexed, locally reusable, available upstream, explicitly unavailable,
   unassessed and failed acquisition/validation separately. An empty array,
   unresolved count/URL descriptor, reserved bill number or unsupported download
   format is not interchangeable with a verified successful empty collection.
5. Rehearse preservation-aware enrichment and use frozen-version conditional
   writes with exact source/API readback. The create-only writer cannot enrich
   existing records. Retain the original failed-job history.

Availability is source- and format-specific.
[GovInfo's published bill-text collection](https://www.govinfo.gov/help/bills)
covers the 103rd Congress onward, but the currently listed
[BILLS bulk XML](https://www.govinfo.gov/bulkdata/json/BILLS/) starts at the 113th,
[BILLSTATUS bulk XML](https://www.govinfo.gov/bulkdata/json/BILLSTATUS/) at the 108th,
and [BILLSUM bulk XML](https://www.govinfo.gov/bulkdata/json/BILLSUM/) at the 113th.
Recheck discovery rather than extrapolating one collection's range to another.

Older bill records can still link to Public Law or Private Law PDFs in the
Statutes at Large. Those are available enacted-law references, not proof that
earlier bill drafts exist online. The current Congress API
[`Bill.add_full_text`](../../cdm/models/bills.py) path only retrieves
`Formatted Text`; PDF-only references are not extracted by that method.
Keep the law/bill-version distinction and source provenance when assessing or
adding another retrieval path. Neither a collection start date nor an unsupported
format establishes that text is unavailable everywhere.

### Historical enacted-law text from Statutes XML

The official [STATUTE bulk collection](https://www.govinfo.gov/bulkdata/STATUTE)
can provide structured text for enacted-law PDF references predating the BILLS
collection. Discovery is volume-level: follow the official directory to
`STATUTE-<volume>.xml`, not an assumed per-law XML filename.

[`StatutesReader`](../../cdm/ingest/statutes.py) accepts a sealed
[`StatuteVolume`](../../cdm/ingest/statutes.py) and injected
[`StatutesSettings`](../../cdm/config/statutes.py). It performs no downloading,
index writes or automatic scheduling. The adapter does not change ordinary
Congress API ingestion or register a new resource in the worker pipeline.

The reader checks the file SHA before and after a fully consumed stream, validates
the volume root/namespace/scope, and returns typed Public/Private Law records with
text, approval date, original citation, source URL and component/volume hashes.
Volume books can contain older reprints: a law's Congress and original citation
must not be inferred from its containing volume. Missing law-session metadata
remains explicitly unknown. Inline word fragments and paragraph boundaries are
preserved when extracting plain text.

Use `records()` for fail-fast reading, or `scan()` for independent accepted laws
and explicit `StatuteRejectedLaw` diagnostics. Persist every rejection; a scan
with rejected components is not complete coverage. Wrong volume headers, malformed
XML or changed file seals remain fatal rather than per-law quarantines.

Before any existing-bill enrichment, independently match the indexed law
kind/Congress/number, PDF citation volume/page and XML bill reference. Conflicting
official metadata or links must not be silently corrected or labeled unavailable.
Retain the original downloads and every unresolved reference for review.
Serving promotion remains a separate preservation-aware conditional-write gate:
preserve existing details/text, retain source/version provenance, and identify
the result as enacted-law text rather than an earlier bill draft. Staged text
alone does not make it available through the application.

[`StatuteTextEnricher`](../../cdm/ingest/statute_text.py) builds a controlled
projection using injected [`StatuteTextSettings`](../../cdm/config/statute_text.py)
and a lemmatizer. It rechecks the serving identity, indexed law and PDF evidence,
refuses nonblank text, unassessed lemmas or conflicting version codes, and changes
only text, text lemma, version code and additive source provenance. It does not
recompute hydration or touch relationships/analysis. Publication remains an
operator-controlled frozen-version write, not ordinary upsert or a worker job.

Published text uses `full_text_version_code` values such as
`public-law-95-367` or `private-law-95-138`. The existing bill-detail API exposes
both text and code; the Text tab labels these **Enacted public/private law text**.
USLM plain text is rendered literally, without HTML/entity reinterpretation.
Ordinary bill versions use their source-listed version labels.

Provenance uses `govinfo:statute` in `source_metadata`, with the original PDF
package/reference, official volume XML URL, XML component and volume SHA-256,
parser version, original citation, containing volume, law identity and approval
date. Existing source entries/package IDs/URLs are retained. The source enum
addition does not change general reconciliation authority or certify earlier
drafts, other versions, all available laws, freshness or complete bill detail.

### Independent metadata, PDF and facsimile recovery

The original indexed PDF links are not an exhaustive catalog. Official
volume-level [MODS metadata](https://www.govinfo.gov/metadata/pkg/STATUTE-90/mods.xml)
lists constituent public/private laws and their primary and secondary bills.
Read this catalog once per retained volume rather than making an API request
for every bill. Exactly one primary bill is required; secondary associations
must not be treated as enacted bills. Preserve the containing metadata package
separately from a reprinted law's original citation.

| Model or collaborator | Responsibility |
|---|---|
| [`SealedStatuteFile`](../../cdm/ingest/statutes_evidence.py) | Bind a local source to its official URL and SHA-256; reject changed bytes. |
| [`StatuteMetadataReader`](../../cdm/ingest/statutes_evidence.py) | Validate MODS law identity, primary bill, citation, date, pages and PDF URL; expose explicit rejection records. |
| [`StatutePdfReader`](../../cdm/ingest/statutes_evidence.py) | Check page count, citation and law/bill evidence; isolate the selected complete law from neighboring acts on shared pages. |
| [`StatuteOcrWitness`](../../cdm/ingest/statutes_evidence.py) | Bind on-device OCR to the source PDF and hashed page images. Recovering a damaged opening requires OCR of every PDF page. |
| [`CongressionalLawEvidence`](../../cdm/ingest/statutes_evidence.py) | Corroborate a primary bill using an exact captured Congress terminal law action when the printed bill header is wrong. |
| [`StatuteCitationReader`](../../cdm/ingest/statutes_evidence.py) | Find an exact law/start-page citation in a sealed official U.S. Code publication. |
| [`RecoveredStatuteText`](../../cdm/ingest/statutes_recovery.py) | Select corroborated XML or verified PDF/OCR text without rewriting conflicting XML. |
| [`StatuteRecoveryEnricher`](../../cdm/ingest/statutes_recovery.py) | Recheck the serving bill/evidence, use the shared text projector, and add verified missing law/PDF metadata without declaring complete detail retrieval. |
| [`LawTextProjector`](../../cdm/ingest/statute_text.py) | Keep text, lemma, enacted-law version and additive provenance together; refuse pre-existing text/rank conflicts. |

The controlled flow is **sealed catalog + XML + indexed evidence → independent
matching → bounded PDF/facsimile recovery where needed → sealed text →
fresh serving projection → owned shadow → live canary → conditional publication
→ exact source/version/API checks**. Recovery settings are injected through
[`StatuteRecoverySettings`](../../cdm/config/statute_recovery.py).
These adapters do not download, schedule jobs or write Elasticsearch themselves.
Acquisition, OCR and publication require an explicit operator-controlled
workflow; these adapters are not automatic ingestion commands.

PDF recovery requires the `historical` dependency group (`pypdf`), also included
by the normal `dev` group. A separate minimal environment can install it with
`uv sync --frozen --no-default-groups --group historical`; API-only environments
need not install the PDF parser. Native extraction is bounded to 64 MiB per PDF,
1,000 pages and 16 MiB text. Missing native page text is an explicit failure, not
silently omitted content. OCR witnesses can corroborate a native header; when
OCR supplies the text instead, every source page must be represented.
OCR evidence records the local extraction program and source page-image hashes.

HTTP 200 alone does not establish a source exists: STATUTE HTML/PDF paths
can return a GovInfo "Page Not Found" page. Check content type and PDF parsing,
not status alone. Never infer availability from an invented neighboring filename
or use fuzzy title matching to resolve a bill-number conflict.

Recovered provenance records the metadata package/component hashes, text format
(`uslm_xml`, `publisher_pdf_text_layer`, or `on_device_facsimile_ocr`), original
XML discrepancies, bill-association proof and any OCR program/page-image hashes.
Retain the sealed original downloads and OCR sidecars as well as indexed
provenance. Publisher transcriptions may contain errors; the Text tab directs
readers to the facsimile. A PDF format with `coverage: "partial"` is labeled
**PDF (partial facsimile)** rather than being presented as the whole law.

An exceptional citation disagreement needs independent evidence, not an edited
source: Public Law 94-284's complete XML begins at **90 Stat. 503**, whereas MODS
and its linked PDF begin at **508**. The official
[Code's 1976 amendment note](https://www.govinfo.gov/content/pkg/USCODE-2024-title15/html/USCODE-2024-title15-chap47-sec2051.htm)
independently corroborates page 503. The complete XML text is indexed, both page
values and the witness are retained, and the original PDF link is marked partial.
This narrow citation exception does not waive law identity, primary bill,
approval date or other matching requirements.

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
| `amendment`, `committee_report`, `congress`, `crsreport`, `hearing`, `house_communication`, `senate_communication` | Static | Default on. |
| `bound_congressional_record`, `daily_congressional_record`, `house_requirement`, `house_vote` | Static | Default off; opt in selectively (`house_vote` roll calls are covered by Voteview bulk CSVs). |
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

The existing daily scheduler also submits a current-Congress bill pass without
a date window, using `refresh_stale=True`. Discovery scans the current list;
item hydration is limited to new bills, newer source versions and unhydrated
skeletons. This catches updates older than the incremental two-day overlap.
Each day's distinct job retains its fetched records and uses the existing
shared API limiter, ledger, retry and indexing pipeline. Aware source timestamps
are compared in full, including same-day changes; date-only timestamps retain
day-level precision. Bill state includes law projections with canonical bill
identities. Coverage-gap bill jobs explicitly enable item hydration.

These are configured scheduler capabilities, not proof that acquisition is
running or that every available detail/text endpoint succeeds. The controlled
`operations` profile still excludes Beat and acquisition workers. The GovInfo
package scheduler remains discovery-only for previously unseen package jobs;
it does not perform recurring Congress API refresh.

The Compose `scheduler` profile sets `CELERY_BILL_REFRESH_ONLY=true`: Beat
publishes only the 02:00 UTC bill-refresh task to the existing maintenance
queue. The operations worker runs that acquisition serially using the existing
shared API limiter, then drains the resulting index work. It does not consume
the general ingest queue or enable retention, analytics, static, vote or GovInfo
schedules. Completed daily refresh jobs are not dispatched again. The restricted
Beat process does not import worker/NLP implementations.

After queue review and capacity admission, enable this scoped recurrence with
`make up STACK_PROFILES=operations,scheduler`. The default `operations` profile
alone still does not start Beat. Bill updates preserve an existing law
discriminator and do not erase nonempty full text with an empty fetch.

Accept a catch-up only after comparing the captured list's identities and
versions with serving state, verifying archived bodies/relationships and
checking child index jobs plus Redis pending/lag. A succeeded ingest resource
can still have logged item failures; its status alone is not acceptance.
The stale/skeleton policy is not an all-field freshness audit. In particular,
`source_checked_at` is stripped at projection, and a hydrated timestamp is
not a certificate for every listed text version. Preserve failed attempts and
source-specific pagination errors rather than stamping success or relaxing
count/identity checks.

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
* `list_records.jsonl`, accepted as a resume input when the SQLite cache is absent.

A checkpoint is usable only when its parameters match and its offset is an
integer at least `-1`; `-1` marks completed discovery. A mismatch removes the
old list caches. Page-size and sample limits are not all part of the stored
parameter context; do not interpret a checkpoint as a full run configuration.
Cache reload validates by Python field name to preserve snake_case dumps.

For each page, the runner extracts and validates list records, deduplicates
model identities, writes the list cache, then advances the atomic checkpoint.
It reports discovered count/checkpoint offset through the progress sink.
Bill metadata with an introduced date uses an augmented list identity so
entries sharing a bill key can remain distinct.

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
Archived IDs are read from resource and parent job roots; attempt
JSONL files are also accepted as resume inputs. Bill dates ending in midnight are
normalized for identity comparisons.

Bill resume also compares signatures comprising congress/type/number/title
and latest-action date/text when introduced-date variants are involved.
The stale filter compares indexed canonical bill state against list metadata:
new IDs, newer upstream update **dates** (day precision), or unhydrated
skeletons without subject/policy data need refresh. It is not a byte-level or
full-timestamp freshness check.

`_fetch_single_item()` derives item parameters and obtains the typed detail.
For bill entries with `introduced_date`, it can select the matching
version from `detailUrl` responses before coercion, then appends that date to
the archived item ID. The indexer later collapses the date suffix back to
the four-part bill identity.

### Bill hydration evidence

For bills, [`Bill.add_bill_details()`](../../cdm/models/bills.py) requests:
`actions`, `amendments`, `committees`, `cosponsors`, `relatedbills`, `subjects`,
`summaries`, `text`, and `titles`.
[`BillDetailFetcher`](../../cdm/contracts/hydration.py) follows pagination,
detects cycles/changing totals/conflicting identities, enforces the page bound,
and validates response shapes. Expected counts must match source-counted
entries exactly. A valid exhausted pagination protocol can establish retrieval
completeness when no count is supplied; this is not authoritative global coverage.
Nonzero count/URL envelopes remain incomplete; authoritative zero is explicit
empty evidence. Object-shaped subjects preserve policy area and expand
`legislativeSubjects`; a missing list is not an empty list.

Counts follow actual endpoint semantics, not just array lengths. Pagination
accepts `count` and `total`, rejects contradictory totals
and detects changes between pages. Co-sponsors are identified by member identity
**and sponsorship date**: withdrawing and later rejoining is two preserved
episodes, not a conflicting duplicate person. Contradictions within the same
episode still fail. `countIncludingWithdrawnCosponsors` is the overall expected
row count; `count` is the separate active count. Optional `expected_active_count`
and `fetched_active_count` retain that distinction in detail evidence, and both
must agree before completeness. Subject pagination includes a nonempty policy
area as one row alongside distinct legislative subjects, counted once even when
repeated across pages. Neither counter is a distinct-member/support score.
Related-bill pagination counts nested `relationshipDetails` rows, not
unique bill objects: one bill can carry both an identical-bill and a procedural
relationship. Repeated grouped bills on different pages do not multiply links.
Repeated anonymous nested rows are preserved in the returned relationship list;
`fetched_relationship_count` separately counts distinct relationships within
each related bill. Multiplicity does not prove separate real-world links.
Missing relationship lists remain incomplete; conflicting bill metadata still
fails. `fetched_record_count` separately reports distinct top-level records
(legislative subjects for the object-shaped subjects response), while
`fetched_count` reports the endpoint's source-counted entries.
Text-version pagination also counts source rows, including exact anonymous
duplicates. The normalized version list remains distinct so a repeated version
is downloaded only once. `repeated_text_versions` preserves each repeated body
and its occurrence count; raw counts, distinct counts and multiplicities must
reconcile before completeness. This does not waive missing or conflicting rows.
For actions, the source count measures returned rows, including identical
anonymous bodies. `fetched_count` retains that row count, while normalized
`actions` and `fetched_record_count` remain distinct. `repeated_actions` stores
each repeated anonymous body and its occurrence count in source-only evidence;
it does not assert multiple distinct real-world events. Repeated explicit
IDs/URLs cannot satisfy completeness, and contradictory explicit identities,
changing counts, pagination cycles and missing/excess rows remain failures or
partial evidence. Other collections keep their endpoint-specific distinct
count rules.

All nine relationship updates, including committees, validate before the original
bill mutates. Partial responses preserve existing richer arrays.
By default, `add_bill_details()` then calls `add_full_text()` automatically.
For explicitly separate acquisition, call
`add_bill_details(client, fetch_full_text=False)` or construct
`IngestRunner(..., fetch_bill_text=False)`. This opt-in path still validates all
nine detail collections, including text-version listings, and preserves existing
text and version metadata without making the public text request. It does not
certify text-body coverage or change ordinary CLI/worker defaults. A separate
downloader must fetch available bodies, preserve version evidence and surface
failures; use an unauthenticated public-download session rather than forwarding
the Congress API session's credential to a text host.
`add_full_text()` retrieves formatted text, rejects unsuccessful HTTP
responses and empty bodies, and cannot establish historical/text completeness.
Bill and amendment network failures raise `FullTextDownloadError` (a
`RuntimeError` subtype) with the original request exception as their explicit
cause. The shared failure classifier uses that cause: connection/timeouts and
HTTP 429/5xx are transient; HTTP 4xx other than 429, parsing/empty-text errors
and missing network causes are not. Generic `RuntimeError` wrappers do not gain
network retry classification. This preserves existing retry limits and
full-text validation rather than treating failed downloads as empty success.

Enacted-law entries in a bill's text-version list use `PLAW` or `STATUTE` URLs,
not necessarily a `BILLS` draft URL. Do not assign a draft version/rank by
guessing from those links. Match the acquired bill-law relationship against
official XML primary-bill references or independently validated MODS/PDF
evidence. Historical PDF headings can use `102d` or `103d` as well as modern
ordinal spellings; the heading Congress must agree with the law identity.
Older facsimiles instead use an `AN ACT` or `JOINT RESOLUTION` opening,
sometimes preceded by an enactment date, without repeating the Congress.
Require that complete legislative opening, not a running page header or a
fragment starting mid-act. Older page headers can print the page before the
volume or place the volume at the left and page at the right of a law/date
banner. Match the exact page, volume and Congress against independent MODS
metadata; a date's day/year is not a page number. A running header can name an
adjacent law sharing that page, so identify and bound the selected act separately.
Preserve adjacent-law boundaries and explicit partial-facsimile/OCR failures.
When the text layer is damaged, retain source-sealed local OCR witnesses and
page-image digests; reconstructing a missing opening requires every PDF page.
The `-2`/`-3` suffix in a granule filename distinguishes granules sharing a
page; it is not part of the numeric Statutes citation. Independently match
the primary bill and law identity before selecting the canonical MODS PDF;
retain discrepancies with the originally listed source URL.
If a whole-volume XML exceeds the response bound, keep that bound and use a
bounded independently verified law source instead; the large representation
does not establish that the law's text is unavailable.

Historical draft links can instead use
`/{congress}/bills/{measure}{number}/BILLS-{measure}{number}{version}.htm`.
The filename alone does not establish the Congress. Controlled recovery validates
the official HTTPS host, Congress path, both measure/number occurrences and
version code, then requires a nonblank preformatted bill body. Some official
historical bodies use rich HTML rather than `<pre>`; controlled recovery
accepts those only after independently matching Congress and bill headings,
removing script/style content and retaining the complete extracted body.
Do not rewrite
these links into a guessed modern package URL or treat nonblank error-page text
as a successful bill download. Retained successful API responses can be reused
after payload-digest validation; cache replay must consume no network attempts.

### Retained versions, primary text and source freshness

Controlled missing-record enrichment keeps the complete captured version set in
sealed acquisition archives. `text_versions` in the serving document contains
version metadata and source links; `full_text` contains one selected primary
body, not an array of every captured body. The text tab exposes those links and
labels the primary version without asserting that it is always the latest.

Selection prefers independently verified enacted law, then a single distinct
body. Complete source publication dates can establish a unique latest body;
otherwise a unique highest rank is used only when every candidate has a known
rank. Ties, missing dates and incomparable versions remain explicit. A retained
source-listed representative may be published with an unresolved-order
disposition; no rank is invented and no other captured body is discarded.
These selection dispositions remain in the sealed publication evidence.
An empty version listing means only that the source listed no versions.

Acquisition, hydration assessment and upstream source-check times are different.
Cached response replay can finish a new acquisition without contacting upstream.
Controlled enrichment retains its acquisition-supplied time in
`source_metadata[].acquisition_completed_at`, including timestamps preserved
on resume, and records the lack of freshness evidence separately. It does not
derive `source_checked_at` or a whole-document snapshot version from that time.
Do not use file age, successful replay or an assessment timestamp to certify
current document freshness.

The runner and indexer derive `hydration_status` from the versioned
`HydrationAssessment`, never from successful return alone. The assessment records
source, assessment time, per-detail counts/state/reasons and the scoped status.
`complete` requires all nine complete details; `partial` has assessed unresolved
details; `unknown` has no certified retrieval evidence. Unversioned root labels
and detail reports alone are not proof. Only an actual assessment supplies the
hydration timestamp/source markers. The assessment is retained in `_source`,
not added as searchable mappings; the existing root status remains searchable.

Bill detail API responses expose `hydration`; the UI warns for unknown/partial
without hiding source records; an absent field is unknown. Corrupt versioned proof fails validation rather than silently becoming
complete. GovInfo BILLSTATUS v3 and BILLSUM v2 normalization emit source-specific
unknown API assessments in new immutable snapshots; existing snapshots are not
rewritten. Full text, other sources, freshness, and resource/history coverage
remain independent obligations.
Optional count fields do not recertify an assessment when absent.

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
It can construct measure/text package descriptors, construct measure-type bulk
`.zip` archive descriptors (`collection_zip_package()`), probe availability, or
enumerate official JSON directories with HTML-listing fallback.
When `prefer_zip=True` is passed to `list_congress_packages()`, `BILLSTATUS`,
`BILLSUM`, and `BILLS` are discovered as per-measure-type `.zip` archives
(`BILLSTATUS-119-hr.zip`, `BILLSUM-119-hr.zip`, `BILLS-119-1-hr.zip` — 32
requests per Congress instead of ~50,000+ individual XML requests).
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
`extract_zip()` safely validates extraction paths when a `.zip` package is
processed by `GovInfoPackageRunner`.

The downloader cache is not proof that upstream never changed: a local
matching `complete` record can short-circuit network revalidation.
The package runner later records `parsed` state in SQLite; JSON and SQLite
manifests are separate writes. Parser-version fields document interpretation,
not a global automatic cache-invalidation system.

### XML adapters and worker stages

[`GovInfoPackageRunner`](../../cdm/workers/govinfo_runner.py) claims a package,
downloads it, chooses an adapter, marks the manifest parsed, archives the
normalized record(s) using **package ID** within an immutable artifact/parser/check
snapshot directory, publishes them to the job's Redis stream, creates
an index job with `expected_count` matching the parsed record count (1 for
single XML packages, or the constituent XML count for bulk `.zip` archives),
and marks acquisition succeeded.
Its index payload includes source attempt so re-parsing does not collide
with another source attempt's index job.
The index job points to that snapshot only; retained snapshots and package
archives remain immutable. Cached reparsing reuses the actual HTTP fetch time,
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

[`reconcile_govinfo_bulk.py`](../../scripts/reconcile_govinfo_bulk.py)
provides read-only archive previews and explicit durable staging replay. A
source/parser repair still requires its own approved scope and evidence;
staging replay is not a replacement for rerunning a changed XML adapter.
Archives preserve their first payload; immutable snapshots bind artifact,
parser and check identity. A parser change requires a distinct parser version.

[`BillReconciler`](../../cdm/ingest/reconciliation.py) groups canonical parent
bill identities, including archive introduction-date suffixes. Conflicting
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
writes. Values without completeness proof are retained/unioned with conflict
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
strips snapshot/check controls; archive evidence and staging
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
