# Congress Tracker — Engineering Plan

## Current Status (2026-08-08)

The original migration and resource-validation work is complete. The focused
historical-ingest work is also complete through configurable date parameters,
overlapping yearly windows, cross-chunk deduplication, coverage reporting, and
scope-catalog validation. These changes are exercised by the current test suite
and bounded live Congress.gov smoke tests.

The remaining work is downstream infrastructure rather than resource triage:

- Operational hardening is tracked in
  `OPERATIONS_HARDENING_PLAN.md`, beginning with a repeatable dependency and
  backlog health check while historical ingest drains.

- Checkpoint persistence exists in `cdm/ingest/checkpoint.py` and now has unit
  coverage, but it is not yet wired into the runner or historical orchestrator.
- OpenSearch index management and bulk upsert helpers exist, but they need
  integration tests against a running cluster before M5 can be called complete.
- Cross-reference linking remains unimplemented.
- The resource tables and older acceptance checkboxes below are historical
  notes; use the current test suite and `INGEST_IMPLEMENTATION_PLAN.md` as the
  authoritative status for ingest behavior.

## Vision

Build a 1:1 mirror of all congressional data from the Congress.gov API, stored in
OpenSearch, with a clean SDK layer for retrieval and a data management layer for
ingest, enrichment, and cross-reference linking. Eventually covers all 200 years of
records; immediate priority is the last 20 years (~Congress 109–119).

---

## Milestone Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1 | ✅ Done | Rename `src` → `cdm`; extract `pycongress` SDK repo; `cdm/` skeleton |
| M2 | ✅ Done | Add missing specs (committee_meeting, committee_print, summaries); 57 tests green |
| M3 | ✅ Done | Local bulk ingest — pull real data for all 20 endpoints to disk |
| M4 | 🔶 In progress | Schema design — inspect real data, define OpenSearch mappings |
| M5 | 🔶 In progress | OpenSearch storage layer — index creation, bulk upsert, aliasing |
| M6 | ❌ Not started | Cross-reference linking and enrichment pipeline |

---

## M3 — Local Bulk Ingest

**Goal:** Make it trivially easy to pull real API data for every resource and save
it locally. No schema commitment yet — the output is raw JSON on disk for inspection.
Once we have real data samples for every endpoint we can design the index mappings
with confidence (M4).

### Scope parameters

Every resource falls into one of three scope types:

| Scope type | Parameters | Resources |
|------------|-----------|-----------|
| **Date-windowed** | `fromDateTime` / `toDateTime` | amendment, bill, committee, committee_meeting, committee_print, committee_report, crsreport, daily_congressional_record, house_communication, member, nomination, senate_communication, summaries, treaty |
| **Congress-scoped** | `congress` (+ optional `chamber`) | hearing, house_vote, law |
| **Static** | none | bound_congressional_record, congress, house_requirement |

### Output layout

```
data/local/
  <resource>/
    Redis Streams      ← validated records handed to indexing
    SQLite             ← job and checkpoint metadata
    meta.json          ← run metadata (timestamp, params used, counts)
```

### Key abstractions

```
cdm/ingest/
  resource_config.py  ← ResourceConfig dataclass (scope type, date params, etc.)
  pipeline.py         ← Pipeline class: run all/subset of resources
  runner.py           ← IngestRunner (updated: date params, extra_params)

scripts/
  ingest_all.py       ← CLI: --from-date, --to-date, --congress, --resources, --outdir
```

### ResourceConfig fields

```python
@dataclass
class ResourceConfig:
    resource: Resource
    scope: Literal["date_window", "congress_scoped", "static"]
    from_date_param: str | None   # e.g. "fromDateTime"
    to_date_param: str | None     # e.g. "toDateTime"
    requires_congress: bool       # True → must pass congress number
    list_only: bool               # True → no item endpoint
    fetch_items_default: bool     # False for very large resources (bill, member)
```

### Acceptance criteria

- [ ] `uv run python scripts/ingest_all.py --from-date 2025-01-01 --to-date 2025-01-31 --outdir data/local` runs without error and produces populated JSON files for all date-windowed resources
- [ ] `uv run python scripts/ingest_all.py --congress 119 --resources hearing,house_vote,law --outdir data/local` covers congress-scoped resources
- [ ] `uv run python scripts/ingest_all.py --static --outdir data/local` covers bound_congressional_record, congress, house_requirement
- [ ] All 57 existing tests still pass after the runner changes

---

## Repository Structure (Current)

```
cdm/              (Congress Tracker package)
  data_collection/
    client.py
    specs/                 ← 20 endpoint specs registered
    utils.py
  models/                  ← Pydantic v2 models for all 20 resources
  config.py                ← env var config (CONGRESS_API_KEY, etc.)

cdm/                       ← Congress Data Manager and API integration
  ingest/
    runner.py              ← IngestRunner (single resource)
    pipeline.py            ← (M3) multi-resource orchestration
    resource_config.py     ← (M3) per-resource scope metadata
    checkpoint.py          ← resumable checkpoint stub
  store/
    opensearch.py          ← (M5) index management + bulk upsert
    indexer.py             ← (M5) record → OS document transform
  search/
    client.py              ← (M5) query helpers
  links/
    resolver.py            ← (M6) cross-reference enrichment

scripts/
  ingest.py               ← thin shim → cdm.ingest.runner
  ingest_all.py           ← (M3) bulk local ingest CLI
```

---

## Endpoint Coverage Plan

The Congress.gov API exposes the following top-level resources. Each must satisfy
three acceptance criteria before being marked done:

| # | Criterion | Description |
|---|-----------|-------------|
| A | **Single-record fetch** | `CDGClient` can call the item endpoint and return a validated model instance |
| B | **Incremental ingest** | `IngestRunner` (or `cdm/ingest/pipeline.py`) can ingest all records for a date window (or alternative parameter where dates are unavailable) |
| C | **Field coverage** | All fields in the Pydantic model match the API schema; required fields validated; optional fields default correctly; no silent drops |

### Status key
- ✅ Done — spec, model, ingest-run test, and field tests all pass
- 🔶 Partial — spec exists, some tests pass, gaps remain
- ❌ Not started

---

### 1. Amendment `/amendment`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `amendment_specs.py` · **Model:** `Amendment` in `bills.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch returns validated `Amendment` instance
- [ ] B – ingest-run test with `fromDateTime`/`toDateTime` window (add params to spec)
- [ ] C – audit all sub-endpoints: `/actions`, `/cosponsors`, `/amendments`, `/text`
- [ ] Fix: `chamber` validator deprecation warning in pydantic 2.12+ (`mode='after'` classmethod)

---

### 2. Bill `/bill`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `bill_specs.py` · **Model:** `Bill`, `BillDetail` in `bills.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch for all bill types (hr, s, hjres, sres, hconres, sconres, hres, sjres)
- [ ] B – ingest-run test with date window; handle `updateDateIncludingText` vs `updateDate` distinction
- [ ] C – audit all sub-endpoints: `/actions`, `/amendments`, `/committees`, `/cosponsors`, `/relatedBills`, `/subjects`, `/summaries`, `/text`, `/titles`
- [ ] C – `BillActionsResponse`, `BillAmendmentsResponse` etc. must roundtrip without pydantic `default_factory` warnings

---

### 3. Bill Summaries `/summaries`

**Date param:** `fromDateTime` / `toDateTime` (**required** — defaults to last 24h)  
**Spec files:** none currently · **Model:** `Summary` in `bills.py`  
**Status:** ❌ Not started

Tasks:
- [ ] A – add `summaries_list_spec` and `summaries_item_spec`
- [ ] B – ingest-run test; this endpoint **requires** a date window for full coverage
- [ ] C – model `SummaryItem`: `actionDate`, `actionDesc`, `text`, `updateDate`, `versionCode`

---

### 4. Congress `/congress`

**Date param:** none (static list; 119 records total)  
**Spec files:** `congress_specs.py` · **Model:** `Congress` in `people.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch by congress number
- [ ] B – full list ingest (single page, no date filter); already passes test
- [ ] C – `sessions` array: `startDate`, `endDate`, `number`, `type`, `chamber`

---

### 5. Member `/member`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `member_specs.py` · **Model:** `Member` in `people.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch by bioguide ID
- [ ] B – ingest-run test with date window; cover `/member/{bioguideId}/sponsored-legislation` and `/member/{bioguideId}/cosponsored-legislation` (currently missing specs: `sponsorship_list`, `cosponsorship_list`)
- [ ] C – `terms`, `partyHistory`, `addressInformation`, `depiction`

---

### 6. Committee `/committee`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `committee_specs.py` · **Model:** `Committee` in `bills.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch by chamber + committee code
- [ ] B – ingest-run test; cover `/committee/{chamber}/{committeeCode}/bills`, `/reports`, `/nominations`, `/houseCommunication`, `/senateCommunication`
- [ ] C – `subcommittees`, `history`, `activities`

---

### 7. Committee Report `/committee-report`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `committee_report_specs.py` · **Model:** (in `other_models.py` or `bills.py`)  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch
- [ ] B – ingest-run test
- [ ] C – `associatedBill`, `associatedTreaties`, `text` sub-endpoint

---

### 8. Committee Meeting `/committee-meeting`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** none currently · **Model:** none  
**Status:** ❌ Not started

Tasks:
- [ ] A – add `committee_meeting_specs.py`; model `CommitteeMeeting`
- [ ] B – ingest-run test with date window
- [ ] C – `witness`, `date`, `location`, `meetingType`, `committees`

---

### 9. Committee Print `/committee-print`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** none currently · **Model:** none  
**Status:** ❌ Not started

Tasks:
- [ ] A – add `committee_print_specs.py`; model `CommitteePrint`
- [ ] B – ingest-run test
- [ ] C – `citation`, `congress`, `number`, `text` sub-endpoint

---

### 10. Hearing `/hearing`

**Date param:** none (filter by congress + chamber)  
**Spec files:** `hearing_specs.py` · **Model:** `Hearing` in `bills.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch by congress/chamber/jacketNumber
- [ ] B – ingest-run test; parameterise by congress range for historical coverage
- [ ] C – `formats`, `dates`, `committees`, `associatedMeeting`

---

### 11. House Vote (Roll Call) `/house-vote`

**Date param:** `startDate` / `updateDate` available on list  
**Spec files:** `house_vote_specs.py` · **Model:** `HouseVote` in `other_models.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch by congress/session/rollNumber
- [ ] B – ingest-run test with congress/session loop for historical coverage
- [ ] C – `voteQuestion`, `voteResult`, `voteType`, `votes` array with member breakdowns

---

### 12. House Communication `/house-communication`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `communication_specs.py` · **Model:** `HouseCommunication` in `other_models.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch by congress/communicationType/number
- [ ] B – ingest-run test
- [ ] C – `communicationType`, `congress`, `number`, `committees`, `abstract`

---

### 13. Senate Communication `/senate-communication`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `communication_specs.py` · **Model:** `SenateCommunication` in `other_models.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch
- [ ] B – ingest-run test
- [ ] C – same fields as House Communication; validate `communicationType` enum differences

---

### 14. House Requirement `/house-requirement`

**Date param:** none (filter by number/type)  
**Spec files:** `house_requirement_specs.py` · **Model:** `HouseRequirement` in `other_models.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch
- [ ] B – full list ingest (no date filter; paginate all)
- [ ] C – `type`, `frequency`, `legalAuthority`, `activeRecord`, `matchingCommunications` sub-endpoint

---

### 15. Nomination `/nomination`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `nomination_specs.py` · **Model:** `Nomination` in `other_models.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch by congress/number
- [ ] B – ingest-run test with date window
- [ ] C – `nominees` sub-endpoint (currently missing spec); `committees`, `hearings`, `actions`

---

### 16. Treaty `/treaty`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `treaty_specs.py` · **Model:** `Treaty` in `bills.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch by congress/treatyNumber (and suffix variant)
- [ ] B – ingest-run test
- [ ] C – `countriesParties`, `indexTerms`, `relatedDocs`, `parts` sub-endpoint, `actions`

---

### 17. Law `/law`

**Date param:** by congress + law type  
**Spec files:** `law_specs.py` · **Model:** delegates to `Bill`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch; currently uses bill fallback (5xx from `/law` item endpoint)
- [ ] B – ingest-run test; iterate by congress number for historical coverage
- [ ] C – verify `lawNumber`, `lawType` (pub/priv) round-trip

---

### 18. Bound Congressional Record `/bound-congressional-record`

**Date param:** none (filter by year/month/day)  
**Spec files:** `bound_congressional_record_specs.py` · **Model:** `BoundCongressionalRecord` in `other_models.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch
- [ ] B – ingest-run test; iterate by year range for historical coverage
- [ ] C – `sections`, `dailyDigest`, `pagination` sub-endpoints

---

### 19. Daily Congressional Record `/daily-congressional-record`

**Date param:** by volume/issue number  
**Spec files:** `daily_congressional_record_specs.py` · **Model:** in `other_models.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch
- [ ] B – ingest-run test
- [ ] C – `fullIssue`, `articles`, `sections`

---

### 20. CRS Report `/crsreport`

**Date param:** `fromDateTime` / `toDateTime` on list  
**Spec files:** `crsreport_specs.py` · **Model:** `CRSReport` in `other_models.py`  
**Status:** 🔶 Partial

Tasks:
- [ ] A – confirm item fetch by report number
- [ ] B – ingest-run test with date window
- [ ] C – `formats` (PDF/HTML links), `topics`, `relatedBills`, `authors`

---

## CDM — Ingest Pipeline Design

### Phase 1 — Single-resource incremental ingest (priority)

```
cdm/ingest/runner.py          ← current IngestRunner, generalised
cdm/ingest/checkpoint.py      ← JSON-file checkpoint (offset + last_processed_id)
cdm/ingest/pipeline.py        ← orchestrates runner per resource, handles ordering
```

Each resource gets:
1. A `ResourceConfig` (spec refs, model class, index name, date param name)
2. A checkpoint file in `~/.congress_tracker/checkpoints/<resource>.json`
3. Idempotent upsert into OpenSearch (doc ID = canonical `id` from model)

### Phase 2 — Bulk historical backfill

- Iterate congress numbers 109–119 (or wider) for congress-scoped endpoints
- Iterate date windows in 30-day chunks for `fromDateTime`/`toDateTime` endpoints
- Rate-limited to 5 000 requests/hour (Congress.gov API limit)
- Resumable: checkpoint stores `(congress, offset)` or `(date_window_end, offset)`

### Phase 3 — Cross-reference linking

Entities reference each other by URL. The linker resolves these to internal ids:

| Source field | Target resource |
|---|---|
| `Bill.sponsors[].bioguideId` | `Member` |
| `Bill.committees[].url` | `Committee` |
| `Bill.laws[].number` | `Law` |
| `Amendment.amendedBill.url` | `Bill` |
| `Nomination.nominees[].url` | `Member` |
| `HouseVote.votes[].member.bioguideId` | `Member` |

`cdm/links/resolver.py` runs as a post-ingest enrichment step, adding `_links` to
each OS document without mutating the raw canonical model.

---

## OpenSearch Index Design

One index per resource. Mapping strategy: **dynamic: strict** on known fields,
**dynamic: false** on `_raw` sub-object (preserves full payload without polluting
mappings).

```
congress-amendment
congress-bill
congress-bill-summary
congress-committee
congress-committee-meeting
congress-committee-print
congress-committee-report
congress-congress
congress-crsreport
congress-daily-congressional-record
congress-hearing
congress-house-communication
congress-house-requirement
congress-house-vote
congress-law          ← alias over congress-bill filtered by law type
congress-member
congress-nomination
congress-senate-communication
congress-treaty
```

Index lifecycle:
- **Write alias**: `congress-<resource>-write` → always points to current index
- **Read alias**: `congress-<resource>` → supports zero-downtime reindex

---

## Test Strategy

### Unit tests (currently in `tests/unit/`)

Per-endpoint pattern (already established):
1. `test_<resource>_ingest.py` — ingest-run test with canned responses
2. `test_<resource>_models.py` — Pydantic model field coverage
3. Redis Stream records and SQLite job/checkpoint metadata

**Gap:** resources without ingest-run tests yet:
- `committee-meeting`, `committee-print`, `summaries`, `crsreport` (item-level gaps)

### Integration tests (`tests/integration/`)

Skipped unless `CONGRESS_INTEGRATION=1` env var is set. Each test:
1. Calls the live API with `max_pages=1`, `max_items=3`
2. Asserts response parses without validation errors
3. Does NOT write to OpenSearch (read-only)

Add `conftest.py` fixture: `live_client` (reads `CONGRESS_API_KEY` from env or skips).

### OpenSearch tests (`tests/integration/test_opensearch_*.py`)

Skipped unless `OPENSEARCH_INTEGRATION=1` is set. Tests:
1. Index creation with correct mappings
2. Bulk upsert idempotency (upsert same doc twice → count stays 1)
3. Cross-reference link resolution

---

## Milestone Checklist

### M1 — Clean foundation (immediate)
- [ ] Rename `src` → `cdm` (single PR, mechanical)
- [ ] Create `cdm/` skeleton with `__init__.py` stubs
- [ ] Move `scripts/ingest.py` → `cdm/ingest/runner.py`; update imports
- [ ] 56/56 tests green under `uv run pytest` ✅ (already done)

### M2 — Missing endpoint coverage
- [ ] Add specs + models for: `committee-meeting`, `committee-print`, `summaries`
- [ ] Add `sponsorship_list` and `cosponsorship_list` specs (member sub-endpoints)
- [ ] Add `nominees` sub-endpoint spec for nominations
- [ ] Ingest-run tests for all 20 resources (currently 16 of 20 covered)

### M3 — CDM ingest pipeline
- [ ] `cdm/ingest/checkpoint.py` — offset + last id, atomic JSON write
- [ ] `cdm/ingest/pipeline.py` — multi-resource orchestration, rate limiter
- [ ] `cdm/store/opensearch.py` — index create/update, bulk upsert helper
- [ ] `cdm/store/indexer.py` — model → OS doc transform
- [ ] `make ingest-all` target in Makefile

### M4 — Historical backfill (last 20 years, Congress 109–119)
- [ ] Congress-scoped resources: iterate 109–119
- [ ] Date-windowed resources: iterate in 90-day chunks from 2005-01-01 to now
- [ ] Record counts logged per resource; compare against Congress.gov totals
- [ ] Resumable on failure (checkpoint per resource)

### M5 — Cross-reference linking
- [ ] `cdm/links/resolver.py`
- [ ] Post-ingest enrichment job: adds `_links` to OS docs
- [ ] Bi-directional: `bill → member` and `member._bills → [bill_id, ...]`

### M6 — Full historical coverage (all records)
- [ ] Extend backfill to Congress 1–108
- [ ] Handle data gaps / API coverage holes per `coverage-dates` page
- [ ] Audit record counts against known totals

---

## Known Issues / Technical Debt

| Item | Location | Note |
|---|---|---|
| `@model_validator(mode='after')` classmethod deprecation | `people.py:432`, `bills.py:1040` | Pydantic 2.12 warning; must convert to instance method before Pydantic 3.0 |
| Law item endpoint returns 5xx | `law_specs.py` | Workaround: use bill fallback. Monitor for fix from LoC. |
| `uv.yaml` (custom format) | repo root | Superseded by `pyproject.toml`; can be deleted |
| `scripts/requirements_to_uv.py` | scripts/ | No longer needed; can be removed after M1 |
| Selenium / chromedriver dep in requirements | `pyproject.toml` | Only used for scraping; consider moving to an optional extra |

---

## Quick Reference

```bash
# Setup
brew install uv
make uv-sync             # creates .venv from pyproject.toml

# Local OpenSearch
make local               # starts elasticsearch + kibana + rabbitmq via docker compose
make local-down          # tears down + removes volumes

# Tests
make uv-test             # PYTHONPATH=. uv run pytest -q
uv run pytest -k bill    # run only bill-related tests

# Future
make ingest-all          # (M3) run full pipeline
```
