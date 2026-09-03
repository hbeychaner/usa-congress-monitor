# Ingest Checklist

> Historical smoke-test notes are retained below for reference. New ingestion
> should use the durable queue commands in `README.md` and
> `documentation/README.md`; they write compressed SQLite archives and support
> automatic retry and resume. Do not use the old JSON/JSONL output examples for
> new runs.

Instructions
- Run the ingest for each resource one at a time using the existing `scripts/ingest.py`.
- We use `--max-pages 2` and `--max 500` to limit scope.
- Use `--items` and `--pause-on-error` so we stop on any item fetch error.
- Example command:

```bash
source $(conda info --base)/etc/profile.d/conda.sh && conda activate congress && export PYTHONPATH=./ && \
  python3 scripts/ingest.py --outdir tmp_ingest/<resource> --resource <resource> --items --max-pages 2 --max 500 --pause-on-error
```

Recent changes
 - `scripts/ingest.py` now exposes a typed `Resource` enum and an `IngestRunner` class.
 - The CLI's `--resource` flag accepts only the enum values; valid resource names include:
   `amendment`, `bill`, `bound_congressional_record`, `committee`, `committee_report`, `congress`, `crsreport`, `daily_congressional_record`, `hearing`, `house_communication`, `house_requirement`, `house_vote`, `law`, `member`, `nomination`, `treaty`.
 - The top-level function `fetch_and_save_all()` is a thin compatibility wrapper that delegates to `IngestRunner` — you can also instantiate `IngestRunner` directly from Python for stronger typing and programmatic control.

**IdStrategy typing**
- Endpoint specs now use a typed `IdStrategy` model available as `EndpointSpec.IdStrategy` (declared in `cdm/models/endpoint_spec.py`).
- When adding or generating specs, prefer constructing `IdStrategy(...)` instances rather than raw dicts; the ingestion helper `apply_id_strategy()` accepts either the typed model or legacy mappings, but typed models improve safety and tooling.
- Verification step when adding a new endpoint: ensure `spec.id_strategy` is either `None` or an `EndpointSpec.IdStrategy` instance and test that `apply_id_strategy()` yields a `reference_id` and `id` as expected for at least one sample record.


Checklist (do one resource at a time)

 - [x] amendment (resource: `amendment`)
  - Instructions: run ingest into `tmp_ingest/amendment` (use `--save-raw --pause-on-error` while developing).
  - Findings: limited ingest (--max 20 --max-pages 2) completed and wrote `tmp_ingest/amendment/items.json` (20 items); `tmp_ingest/amendment/list.json` and `raw_list.json` are present (saved during list phase).
  - Actions taken:
    - Updated models to coerce `number` → `int`, replace `amended_treaty` with `amended_bill` (alias `amendedBill`), add `links`, and support `countIncludingWithdrawnCosponsors` on cosponsor envelopes.
    - Recoerced `tmp_ingest/amendment/raw_items.json` using updated `Amendment` model to regenerate `items.json` (no failures for the recent run).
    - Verified deterministic id population via `model.build_id()` and presence of canonical fields in processed items.

- [x] bill (resource: `bill`)
  - Instructions: run ingest into `tmp_ingest/bill`.
  - Findings: `tmp_ingest/bill/list.json` and `tmp_ingest/bill/items.json` contain 1000 records (list paginated to 4 pages originally; full items fetched up to 1000).
  - Action taken: Bill ingest previously executed and verified; model coercion for `notes` updated and test added. Marking as checked.
  - Ensure API top-level fields (`relatedBills`, `textVersions`) are preserved and represented by our models; validate id/url population and field-coverage enforcement.

  Issues Discovered
  - Raw item payloads sometimes omit explicit `id`/`url` and wrap the real payload under a `bill` envelope.
  - API uses camelCase keys (`relatedBills`, `textVersions`) while models used snake_case (`related_bills`, `text_versions`), causing Pydantic to drop fields.
  - Some sub-endpoints return a Count+URL object (CountUrl) instead of a list; code assumed only list shapes.
  - Existing ingest flow did not persist per-item raw payloads; this made debugging harder.

  Actions Taken
  - Added robust parsing in `cdm/models/bills.py`:
    - `Bill.add_bill_details()` now accepts either a `CountUrl` dict (with `count`+`url`) or a list for `relatedBills` and `textVersions`.
    - Field aliases added to accept camelCase API keys (`alias="relatedBills"` and `alias="textVersions"`) so Pydantic populates `related_bills` and `text_versions` fields properly.
  - Added unit test `tests/unit/test_bills_relatedbills.py` to verify CountUrl/list parsing behavior.
  - Enhanced ingestion/debugging flow:
    - `scripts/ingest.py` supports `--save-raw` to save per-item raw payloads into `tmp_ingest/<resource>/raw_items.json`.
    - Captured a 1,000-item sample to `tmp_ingest/bill/raw_items.json` for analysis.
  - Performed re-coercion of saved raw payloads (ad-hoc) to validate model output and ensure fields are preserved; produced `tmp_ingest/bill/items_recoerced.json` during investigation.
  - Removed temporary helper scripts used only for investigation to keep repo tidy.

  Files Modified / Added
  - Modified: `cdm/models/bills.py` — added CountUrl handling and field aliases for `relatedBills`/`textVersions`.
  - Modified: `cdm/data_collection/client.py` — (existing) has a field-coverage check that raised on unprocessed fields; that behavior helped surface missing fields.
  - Added: `tests/unit/test_bills_relatedbills.py` — unit test for parsing shapes.
  - Added/Used (temporary): `tmp/scripts/inspect_related.py`, `tmp/scripts/recoerce_bill_raw.py` (both later deleted after use).
  - Artifacts produced: `tmp_ingest/bill/raw_items.json`, `tmp_ingest/bill/items.json`, `tmp_ingest/bill/items_recoerced.json`.

  Verification Performed
  - Ran focused unit test: `pytest tests/unit/test_bills_relatedbills.py` — passed.
  - Ran full test suite: `pytest` — all tests passed (36 passed, 0 failed).
  - Performed a small smoke ingest (5 items) into `tmp_ingest/bill` and a larger sample (up to 1,000 items) into `tmp_ingest/bill` with `--save-raw`.
  - Programmatically compared `raw_items.json` and `items.json` for all 1,000 items — no discrepancies found for presence/counts of `relatedBills`/`textVersions` vs `related_bills`/`text_versions`.

  Notes & Rationale
  - We preserved the API's CountUrl shape when present (as `CountUrl` model) rather than always expanding to empty lists. This keeps the ingest lightweight and lets callers decide whether to follow the `url` to fetch details.
  - Field-coverage checks (controlled by `CONGRESS_STRICT_FIELD_CHECK` in `settings.py`) remain useful to surface other unprocessed API fields early; we left strict mode enabled during triage.

  Decision
  - Marked **Bill** resource as complete: models updated, tests added, artifacts captured and verified.

- [x] bound_congressional_record (resource: `bound_congressional_record`)
  - Instructions: run ingest into `tmp_ingest/bound_congressional_record`.
  - Findings: `tmp_ingest/bound_congressional_record/list.json` saved with 500 entries (max-pages=2).
  - Action taken: Resumed ingest and fetched items; `tmp_ingest/bound_congressional_record/items.json` now contains 500 items. Marking as complete for the limited run.

- [x] committee (resource: `committee`)
  - Instructions: run ingest into `tmp_ingest/committee`.
  - Findings: Full ingest completed. `tmp_ingest/committee/list.json` saved with 818 entries (full pagination). Item fetching produced `tmp_ingest/committee/raw_items.json` (818 raw envelopes) and `tmp_ingest/committee/items.json` (817 coerced items after dedupe during fetch).
  - Action taken: Ingest executed successfully (full run) and artifacts saved under `tmp_ingest/committee` (list.json, raw_list.json, raw_items.json, items.json). Models updated to accept CountUrl envelopes for `bills`, `communications`, `nominations`, and `reports`. Programmatic comparison between raw and coerced items found no dropped top-level fields; verification complete. Marking as checked.

- [x] congress (resource: `congress`)
  - Instructions: run ingest into `tmp_ingest/congress`.
  - Findings: `tmp_ingest/congress/list.json` saved with 119 entries (API returned 119 congress records). `tmp_ingest/congress/items.json` saved with 119 items after fetching; no failures.
  - Action taken: Ingest executed successfully for limited run; outputs saved to `tmp_ingest/congress` (list.json, raw_list.json, items.json). Marking as checked.

- [x] daily_congressional_record (resource: `daily_congressional_record`)
  - Instructions: run ingest into `tmp_ingest/daily_congressional_record`.
  - Verification: Limited run completed; artifacts saved and verified.
    - `tmp_ingest/daily_congressional_record/list.json` — 500 entries
    - `tmp_ingest/daily_congressional_record/raw_items.json` — 500 raw item payloads
    - `tmp_ingest/daily_congressional_record/items.json` — 500 processed items (ids now populated)
  - Action taken: saved artifacts with `--save-raw`; no immediate field-mapping discrepancies noted in a cursory parity check.
  - Post-run action: ensured processed items include deterministic `id` values by updating `scripts/recoerce_daily_congressional_record_raw.py` to apply `build_id()` when present and fall back to `canonical_id()`; reprocessed saved raw payloads and verified `items.json` contains ids like `daily-congressional-record:<volume>:<issue>`.

- [x] crsreport (resource: `crsreport`)
  - Instructions: run ingest into `tmp_ingest/crsreport`.
  - Findings: `tmp_ingest/crsreport/list.json`, `raw_list.json`, and `items.json` were written during a limited run (max-pages=2 / max=500).
  - Action taken: Limited ingest executed and items saved to `tmp_ingest/crsreport`.
  - Findings (verified):
    - `tmp_ingest/crsreport/list.json` — 500 entries
    - `tmp_ingest/crsreport/raw_list.json` — 500 entries
    - `tmp_ingest/crsreport/raw_items.json` — 500 raw item payloads
    - `tmp_ingest/crsreport/items.json` — 500 processed items
  - Action taken: Limited ingest executed with `--save-raw`; artifacts saved under `tmp_ingest/crsreport` (list.json, raw_list.json, raw_items.json, items.json). Models patched to accept `publishDate` alias so `publish_date` populates correctly. Marking as checked.

  - Post-run action: reprocessed saved raw payloads into `tmp_ingest/crsreport/items.json` using `scripts/recoerce_crsreport_raw.py` so the updated model normalization (including `publishDate` -> `publish_date`) applied to existing artifacts. Recoercion completed and `items.json` was rewritten with coerced values.

- [x] daily_congressional_record (resource: `daily_congressional_record`)
  - Instructions: run ingest into `tmp_ingest/daily_congressional_record`.
  - Findings: `tmp_ingest/daily_congressional_record/list.json`, `raw_list.json`, and `items.json` were written; limited run completed successfully under strict checks.
  - Action taken: Limited ingest executed and items saved to `tmp_ingest/daily_congressional_record`.
  - Post-run action: added an `issue` envelope field to the `DailyCongressionalRecordIssue` model and reprocessed saved raw payloads using `scripts/recoerce_daily_congressional_record_raw.py` so the original `issue` envelope is preserved in `items.json`.
  - Decision: the `request` envelope is intentionally ignored and not modeled; any `request` metadata remains available only in `raw_items.json` for forensics.

 - [x] hearing (resource: `hearing`)
  - Instructions: run ingest into `tmp_ingest/hearing`.
  - Findings:
    - `tmp_ingest/hearing/list.json` — 500 entries
    - `tmp_ingest/hearing/raw_items.json` — 500 raw item payloads
    - `tmp_ingest/hearing/items.json` — 500 processed items (reprocessed after model fixes)
    - Parity comparison (`scripts/compare_raw_proc.py`) reports top missing key: `request` (500) — intentional (forensics preserved in raw).
  - Action taken:
    - Updated `cdm/models/bills.py`:`Hearing` model to preserve the original `hearing` envelope when recoercing, and to populate convenience fields from the envelope.
    - Made `Hearing` envelope extraction robust: accept either `committee` or `committees` shapes for `committee_name`, accept `dates`/`date`/`hearingDate` for `hearing_date`, and preserve the original envelope when records are unwrapped.
    - Normalized nested committee IDs so both `systemCode` and `system_code` are available; updated `Committee` normalization to populate `system_code` when `systemCode` exists and to accept either key.
    - Reprocessed `tmp_ingest/hearing/raw_items.json` with `scripts/recoerce_hearing_raw.py` to regenerate `tmp_ingest/hearing/items.json` with the new model behavior.
    - Verified parity: only `request` is missing from processed items (intentionally ignored per current decision).
  - Decision: preserve the `hearing` envelope in the processed model (keeps forensic data available in `items.json`) and continue to ignore `request` (remains in `raw_items.json`).
    - Added `Hearing.build_id()` to generate deterministic ids like `hearing:{congress}:{jacketNumber}` (includes `:partN` when `part` present). Example id produced during re-coercion: `hearing:119:61167`.

 - [x] house_communication (resource: `house_communication`)
  - Instructions: run ingest into `tmp_ingest/house_communication`.
  - Findings:
    - `tmp_ingest/house_communication/list.json` — 500 entries
    - `tmp_ingest/house_communication/raw_items.json` — 500 raw item payloads
    - `tmp_ingest/house_communication/items.json` — 500 processed items (reprocessed after model additions)
    - Parity comparison (`scripts/compare_raw_proc.py`) reports top missing keys: `houseCommunication` (500) and `request` (500).
  - Action taken:
    - Ran ingest with `--save-raw` and `--pause-on-error`; saved list/raw_list/raw_items/items.
    - Updated `cdm/models/other_models.py`:`HouseCommunication` to parse and preserve key fields (`abstract`, `committees`, `communicationType`, `congressionalRecordDate`, `isRulemaking`, `reportNature`, `sessionNumber`, `updateDate`) while flattening the envelope into model fields.
    - Reprocessed `tmp_ingest/house_communication/raw_items.json` with `scripts/recoerce_house_communication_raw.py` and verified processed items include the requested fields.
    - Post-run verification: compared `tmp_ingest/house_communication/raw_items.json` -> `tmp_ingest/house_communication/items.json` and confirmed preserved envelope fields (e.g., `abstract`, `committees`, `communicationType`) are present in processed items; `request` remains forensic-only in `raw_items.json`.
  - Decision: keep the flattened shape (do not preserve the `houseCommunication` envelope in `items.json`); continue to treat `request` as forensic-only (available in `raw_items.json`).

 - [x] house_requirement (resource: `house_requirement`)
  - Instructions: run ingest into `tmp_ingest/house_requirement`.
  - Findings:
    - Limited fixture ingest validates 500 raw item envelopes and 500 processed items.
    - The `houseRequirement` envelope is flattened into typed `HouseRequirement` fields; `request` metadata remains raw-only for forensics.
  - Action taken:
    - Verified the restored raw fixtures with `tests/unit/test_house_requirement_ingest.py`.
    - Parity review found no missing payload fields beyond the intentional `houseRequirement` envelope and raw-only `request` metadata.

 - [x] house_vote (resource: `house_vote`)
  - Instructions: run ingest into `tmp_ingest/house_vote`.
  - Findings:
    - `tmp_ingest/house_vote/list.json` — 500 entries (limited run: `--max-pages 2 --max 500`).
    - `tmp_ingest/house_vote/raw_items.json` — 500 raw item payloads (saved with `--save-raw`).
    - `tmp_ingest/house_vote/items.json` — 500 processed items (reprocessed/validated after model fixes).
    - Parity comparison (`scripts/compare_raw_proc.py`) results: `total_raw=500 total_proc=500 compared=500` with top missing top-level keys `houseRollCallVote` and `request` (500 each) — these wrappers are intentionally flattened in processed items; `request` remains forensic-only in `raw_items.json`.
    - Model-level normalization verified: candidate-style `votePartyTotal` lists are detected and preserved under `vote_candidate_total` in processed items where applicable. Unit tests covering candidate-style and aggregated `votePartyTotal` shapes pass.
  - Action taken:
    - Added typed vote submodels and a `@model_validator(mode="before")` on `HouseRollCallVoteListItem` to normalize `voteQuestion` shapes, aggregate party totals, and detect/move candidate-style totals into `vote_candidate_total`.
    - Updated/ran `scripts/recoerce_house_vote_raw.py` during development to re-coerce existing `raw_items.json` and produced `tmp_ingest/house_vote/items.json` (500 items).
    - Executed a staging ingest into `tmp_ingest/house_vote_staging` with `--save-raw`; ran `scripts/compare_raw_proc.py` on staging artifacts — parity verified as above.
    - Decision: keep processed items flattened (do not preserve the `houseRollCallVote` envelope), but preserve candidate-style totals under `vote_candidate_total` so nonstandard vote shapes (e.g., Speaker elections) remain available for downstream consumers.
    - Next step (recommended): remove ad-hoc recoercion scripts from `scripts/` once CI confirms tests and staging parity, and optionally add lightweight logging/metrics to record frequency of candidate-style detections during live ingest.

 - [x] law (resource: `law`)
  - Instructions: run ingest into `tmp_ingest/law` (use `--congress <n>`; `--save-raw --pause-on-error` while developing).
  - Findings (attempted run, congress=119):
    - List phase succeeded: `tmp_ingest/law/list.json` saved (79 entries).
    - Item-phase failed on first item: 500 Server Error for `https://api.congress.gov/v3/law/119/pub/44` — ingest paused per `--pause-on-error` and no items were fetched.
    - Artifacts present after abort: `tmp_ingest/law/list.json`, `tmp_ingest/law/raw_list.json` (no `raw_items.json` or `items.json` produced in this run).
  - Action taken: recorded failing URL and aborted the paused run; preserved list artifacts for targeted retries.
  - Debug fetch result:
    - Performed targeted fetch for `/law/119/pub/44` and saved response to `tmp_ingest/law/debug_pub_44.json`.
    - Server returned JSON error: `"bill_details() takes 1 positional argument but 5 were given (TypeError)"` — indicates a server-side implementation error on the Congress API for this law item.
  - Next steps:
    - Option A: re-run ingest without `--pause-on-error` so the runner continues past transient 500s (good for broad smoke runs).
    - Option B: skip this specific law item (server bug) and continue ingest; record the failing URL for support reporting.
    - Option C: open a short issue/report to the API owners including the failing URL and the debug response body; retry after vendor fixes.
  - Status: complete — list-only ingest; items are derived from existing `bill` records
  - Replay & artifacts:
    - Replayed all list-item URLs and saved responses to `tmp_ingest/law/replay_bodies/` with a summary CSV at `tmp_ingest/law/replay_results.csv`.
    - Observed consistent 500 responses from `/law/119/pub/<n>` for many items; fallback to corresponding `/bill/{congress}/{type}/{number}` succeeded for all items during the ingest run.
  - Workaround:
    - The ingest runner already attempts a bill fallback when law item requests return 5xx; given the vendor-side error, treat the fallback as the operational workaround until the API is fixed.
    - Recommendation: keep the existing fallback behavior and include `ISSUES/law-api-500.md` in reports to the API owners if you plan to escalate.

- [x] member (resource: `member`)
  - Instructions: run ingest into `tmp_ingest/member`.
  - Findings: Limited run (`--max-pages 2 --max 20`) saved `tmp_ingest/member/list.json` (500 entries for 2 pages), `tmp_ingest/member/raw_items.json` and `tmp_ingest/member/items.json` (20 processed items for the limited run).
  - Action taken:
    - Added `MemberAddress` model and `address_information` field (alias `addressInformation`) to `cdm/models/people.py` to preserve office/contact details.
    - Added `official_website_url` (alias `officialWebsiteUrl`) and `leadership` fields to capture additional raw keys.
    - Implemented a `@model_validator(mode="after")` on `Member` to populate `id` (via `build_id()`), synthesize `url` from `bioguide_id` when missing, and copy `member_type` and `state_code` from the first `terms` entry when absent.
    - Reprocessed `tmp_ingest/member/raw_items.json` using the updated `Member` model and overwrote `tmp_ingest/member/items.json` (20 items, 0 failures). Processed items now contain non-null `id` values (e.g., `person:K000401`), `url`, `member_type`, `state_code`, and `address_information`.
    - Performed a parity scan comparing raw vs processed keys: no missing top-level keys and no unexpected nulls reported for the limited run.
  - Decision: mark `member` as checked for the limited ingest scope. Keep raw payloads in `raw_items.json` for any further forensic checks.

- [x] nomination (resource: `nomination`)
  - Instructions: run ingest into `tmp_ingest/nomination` (use `--save-raw --pause-on-error` while developing).
  - Findings:
    - Early item-phase failures (IndexError) due to unexpected response envelope shapes (responses contain `nomination` + `request`).
    - Raw payloads are inconsistent: some items include `nominees`, `latestAction`, `actions`, `committees`, `hearings`, `position`, `nominee`; others omit these and only contain top-level dates/number/citation.
    - Many repeated identical item params observed at list phase; deduping occurs during fetch.
  - Action taken:
    - Spec: set item `unwrap_key` to `"nomination"` and ensure runtime param extraction (`extract_from_url_segment`) maps nomination number/congress.
    - Models (`cdm/models/other_models.py`): added `NomineePosition`, extended nomination detail model, added `NominationDetail` and restored a minimal `Nomination` for other endpoints.
    - Ingest script: added defensive check when `--save-raw` produces no coerced item instances to raise a clear ValueError with response keys.
    - Added `scripts/debug_fetch_nomination.py` to fetch and save a single raw nomination for inspection.
  - Artifacts produced (sample run, 1 page / 100 items):
    - `tmp_ingest/nomination/list.json`, `tmp_ingest/nomination/raw_list.json`, `tmp_ingest/nomination/raw_items.json`, `tmp_ingest/nomination/items.json`.
  - Next steps completed:
    - Scanned raw payloads and added aliases/validators to the model to preserve camelCase keys and derive convenience fields.
    - Recoerced saved raw payloads and verified processed items contain deterministic ids and derived `position`, `nominee`, and `date` where available.
  - Status: complete
  - Instructions: run ingest into `tmp_ingest/nomination` (use `--save-raw --pause-on-error` while developing).
  - Findings:
    - Early item-phase failures (IndexError) due to unexpected response envelope shapes (responses contain `nomination` + `request`).
    - Raw payloads are inconsistent: some items include `nominees`, `latestAction`, `actions`, `committees`, `hearings`, `position`, `nominee`; others omit these and only contain top-level dates/number/citation.
    - Many repeated identical item params observed at list phase; deduping occurs during fetch.
  - Action taken:
    - Spec: set item `unwrap_key` to `"nomination"` and ensure runtime param extraction (`extract_from_url_segment`) maps nomination number/congress.
    - Models (`cdm/models/other_models.py`):
      - Added `NomineePosition` model and extended `Nomination` to include `number`, `part_number`, `nomination_type`, `latest_action`, `nominees`, `actions`, `hearings`, `committees`, and `subjects`.
      - Made convenience fields `nominee`, `position`, and `date` optional and added a `@model_validator(mode="before")` to copy camelCase aliases into snake_case and derive `date`/`position`/`nominee` from embedded data when present.
      - Allowed CountUrl-like envelopes for embedded list resources (actions/hearings/committees).
    - Ingest script: added defensive check when `--save-raw` produces no coerced item instances to raise a clear ValueError with response keys.
    - Added `scripts/debug_fetch_nomination.py` to fetch and save a single raw nomination for inspection.
  - Artifacts produced (sample run, 1 page / 100 items):
    - `tmp_ingest/nomination/list.json`, `tmp_ingest/nomination/raw_list.json`, `tmp_ingest/nomination/raw_items.json`, `tmp_ingest/nomination/items.json`.
  - Verification completed:
    - Validated all 100 restored nomination item fixtures through `Nomination` with zero validation failures.
    - Added partition-aware canonical IDs in the form `nomination:<congress>:<number>:part<partNumber>`.
    - Retained list-phase deduplication as an optimization opportunity; it does not block resource correctness.
  - Status: complete

 - [x] senate_communication (resource: `senate_communication`)
  - Instructions: run ingest into `tmp_ingest/senate_communication`.
  - Findings:
    - `tmp_ingest/senate_communication/list.json` — 500 entries
    - `tmp_ingest/senate_communication/raw_items.json` — 500 raw item payloads
    - `tmp_ingest/senate_communication/items.json` — 500 processed items (reprocessed after model additions)
    - Parity check: `communication_type` present in processed items; `communicationType` (camelCase) removed from final output.
  - Action taken:
    - Updated `cdm/models/other_models.py`:`SenateCommunication` to type `committees` as `List[Committee]`, accept `communicationType` via alias into `communication_type`, normalize envelope fields, and implement `build_id()` that produces ids like `senate-communication:{congress}:{communication_type.code}:{number}` with safe fallbacks.
    - Recoerced saved raw payloads using `tools/recoerce_and_write_items.py` to regenerate `tmp_ingest/senate_communication/items.json` and verified deterministic ids (example: `senate-communication:119:ec:3033`).
    - Removed the earlier note about being unable to run network ingest here — local re-coercion and model changes completed the parity work.
  - Suggested command (if you want a fresh networked run in your env):

```bash
source $(conda info --base)/etc/profile.d/conda.sh
conda activate congress
export PYTHONPATH=./
python3 scripts/ingest.py --outdir tmp_ingest/senate_communication --resource senate_communication --items --max-pages 2 --max 500 --save-raw --pause-on-error
```

- [x] treaty (resource: `treaty`)
  - Instructions: run ingest into `tmp_ingest/treaty`.
  - Findings: limited run previously failed due to enveloped item responses (`{"treaty": [ ... ]}`) and `treatyNumber` typed as int in some payloads.
  - Action taken:
    - Added `unwrap_key="treaty"` to `cdm/data_collection/specs/treaty_specs.py` so client unwraps the list-wrapped envelope automatically.
    - Implemented strongly-typed `Treaty` model in `cdm/models/bills.py` with nested types: `CountryParty`, `IndexTerm`, `RelatedDoc`, `TreatyParts` and full typed fields (`actions`, `congress_received`, `countries_parties`, `index_terms`, `titles`, `transmitted_date`, `update_date`, etc.).
    - Coerced `treatyNumber` to `str` in a model pre-validator to handle int/string inconsistencies.
    - Updated recoercion helper `tools/recoerce_and_write_items.py` to unwrap list-wrapped envelopes and to emit snake_case `reference_id` (previously `referenceId`).
    - Recoerced `tmp_ingest/treaty/raw_items.json` and wrote `tmp_ingest/treaty/items.json` (500 items; failures=0) — processed items now include the typed fields and `reference_id`.

Notes
- We will stop immediately when `--pause-on-error` pauses due to an exception; inspect `tmp_ingest/<resource>/items_partial_on_error.json` for partial results.
- Update this file after each run with Findings and Action taken, and check the box when complete.

**Operational Notes**
- **Environment:** activate the `congress` conda env and set `PYTHONPATH=./` before running the ingest command. Example:

```bash
source $(conda info --base)/etc/profile.d/conda.sh
conda activate congress
export PYTHONPATH=./
```

- **API Key:** the CLI will prefer `--api-key` when supplied; otherwise `scripts/ingest.py` reads `settings.CONGRESS_API_KEY`. Ensure your `.env` or environment provides the key or pass `--api-key` explicitly.

- **Client (`CDGClient`) notes:** avoid adding per-endpoint special-casing in the client where spec- or model-level fixes suffice. The client contains helpers for pagination and `coerce_records` (used minimally for `notes` coercion); prefer adjusting `cdm/data_collection/specs/*` and models in `cdm/models/` for envelope/shape issues.

- **Runner & CLI notes:**
  - The `--resource` CLI argument is now validated against the `Resource` enum; use one of the names listed above. The previous string-based usage remains supported, but the enum provides strong typing when calling from Python.
  - For programmatic use, prefer `from scripts.ingest import IngestRunner, Resource` and instantiate `IngestRunner(outdir=Path("tmp_ingest/bill"), resource=Resource.BILL, fetch_items=True).run()`.

- **Specs:** endpoint specs live in `cdm/data_collection/specs/`. Key patterns used during triage:
  - `ParamSpec.source_field` must match the list-record key (snake_case) or use `extract_from_url_segment` to derive values from the list `url`.
  - Use `unwrap_key` when item responses are wrapped in an envelope (e.g., `{ "committee": { ... } }`).

- **Models:** when the API returns inconsistent shapes, prefer model-level normalizers (e.g., `@model_validator(mode="before")`) to derive missing human-friendly fields. Recent fixes:
  - `cdm/models/bills.py`: `Bill.notes` normalization and `Committee` subcommittee normalization (fill `chamber`/`type`/`systemCode`/`url` from parent when missing).

**Interruption & Recovery**
- `--pause-on-error` writes
  - `tmp_ingest/<resource>/list.json` — saved paginated list (ids/urls)
  - `tmp_ingest/<resource>/raw_list.json` — raw response pages
  - `tmp_ingest/<resource>/items_partial_on_error.json` — items fetched so far when paused
  - When a run finishes, `tmp_ingest/<resource>/items.json` is written with fetched items.

- To resume after fixing code: re-run the exact ingest command for that resource (same `--outdir` and flags). If you only changed models/specs, rerun will start fresh but re-use saved artifacts if you want to avoid repeating list fetches (you can inspect `scripts/ingest.py` options).

- Quick inspection tips:
  - Inspect the failing record in `tmp_ingest/<resource>/items_partial_on_error.json` to see the API shape.
  - Inspect `tmp_ingest/<resource>/raw_list.json` to confirm `systemCode` vs `system_code` and whether the item response is enveloped.
  - Use `scripts/debug_fetch_bill.py` or similar small scripts to reproduce a single-record fetch.

**When to change what**
- If the list record keys differ from item-record keys, prefer fixing the `ParamSpec` (in `cdm/data_collection/specs/*`) to map the runtime param correctly.
- If the item payload uses an envelope or nested `history` for human-friendly values, add a short `@model_validator(mode="before")` in the model to normalize the shape rather than broad client enrichment.
- Use client-side coercion only for minor, local normalizations that are impractical to represent in specs or models (document such changes clearly in this file).

**Logging & Repro**
- Ingest logs are printed to stdout and use the project logger; save terminal output when debugging intermittent network/API issues.
- When reporting an issue, include the failing resource, the `tmp_ingest/<resource>/raw_list.json` snippet for that id, and the exception stack trace.