# Engineering Notes: Holistic Architecture Review

Snapshot of a full-stack review of Congress Tracker (backend, data collection, ingest/workers,
frontend, and the still-missing analysis/NLP layer). Intended as a living reference for module
boundaries, known gaps, and recommended follow-ups — not a changelog.

## 1. Module map (what each top-level package is actually for)

| Package | Role |
|---|---|
| `cdm/data_collection/` | Low-level "SDK" for Congress.gov: `CDGClient` (HTTP + auth + rate limiting), `endpoint_registry`/`specs/` (typed endpoint definitions), `id_strategy`/`id_utils` (deterministic ID derivation), `utils.resolve_pagination` (pagination-cursor normalization). No orchestration, no persistence. |
| `cdm/ingest/` | Orchestration built *on top of* `data_collection`: `runner.py`/`pipeline.py` (checkpointed, rate-limited multi-page fetch loops), `checkpoint.py` (resumable offsets), `archive.py` (durable JSONL archives), `redis_stream.py` (publish to the ingest→index handoff stream), `govinfo.py` (a second, independent acquisition path — GovInfo bulk ZIP/XML downloads — not the REST API), `reconciliation.py` (replay archived GovInfo records into a staging index for diffing against live-ingested data). |
| `cdm/workers/` | Celery task definitions and scheduling glue; dispatches ingest/GovInfo/reconciliation/index jobs, tracks them via `cdm/jobs/store.py`. |
| `cdm/store/` | OpenSearch-facing persistence: `client.py`/`opensearch.py` (connection + index CRUD), `indexer.py` (`to_document()` — the untyped translation boundary from ingest records to OpenSearch documents), `index_manager.py`, `redis_indexing.py` (the consumer side of the stream handoff), `mapping_validation.py`. |
| `cdm/models/` | Pydantic domain models mirroring the Congress.gov API response shapes (bills, members, committees, etc.). Used by `data_collection` and `ingest` only. |
| `cdm/contracts/` | Separate Pydantic request/response schemas for the FastAPI backend. Used by `cdm/backend/` only. **Zero import overlap with `cdm/models`** — confirmed via repo-wide grep. |
| `cdm/backend/` | FastAPI app; `services/` (`bill_service`, `member_service`, `search_service`, `state_service`, `admin_service`) read directly from OpenSearch (and, for `admin_service`, directly from the jobs SQLite DB) and hand-build `contracts` objects from raw `_source` dicts. |
| `cdm/services/generative.py` | Unused OpenAI client wrapper stub — zero callers anywhere in the codebase. Left over from an earlier idea, likely the intended seed for the topic/NLP module (see §3). |
| `frontend/app/` | React/Vite/TypeScript SPA consuming the FastAPI backend. |

**Verdict on "is `data_collection` vs `ingest` legacy duplication?"** No — they are a clean
SDK-vs-orchestration split, not overlapping. The confusion is understandable because there was
genuinely dead code inside `data_collection` (deleted this pass, see §4) that made the boundary
look muddier than it is. Worth a one-line module docstring in each package's `__init__.py`
making the split explicit, since it's not obvious from directory names alone.

## 2. `cdm/models` vs `cdm/contracts` — intentional but under-documented boundary

- `cdm.models.*` = canonical *ingest-time* domain models validated against the live Congress.gov
  API shape.
- `cdm.contracts.api` = *read-time* API response schemas for the frontend, describing a
  flattened/denormalized OpenSearch document shape (which itself is produced by
  `cdm/store/indexer.py::to_document()`, an untyped `dict`-in/`dict`-out function).
- These are legitimately different shapes for different purposes (ingest fidelity vs. UI-friendly
  read models), so merging them isn't automatically correct. But the *translation boundary*
  (`to_document()`) is untyped, which means drift between what ingest produces and what
  `contracts` expects can only be caught by integration tests, not the type checker.
- **Recommendation (needs a design decision, not auto-refactored here):** either (a) explicitly
  document this as an intentional read/write model split, or (b) introduce a typed intermediate
  model for `to_document()`'s output so the OpenSearch document shape is itself a checked
  contract. Option (b) is a bigger lift and should be scoped as its own task if pursued.

## 3. Missing analysis / NLP module — scoped but unbuilt

The gap is real, and the pieces for it already exist as placeholders:

- `cdm/services/generative.py` — dead OpenAI wrapper, no callers.
- `frontend/app/src/pages/TopicsPage.tsx` / `TopicDetailPage.tsx` — hardcoded `SAMPLE_TOPICS`
  mock data with explicit "will be populated from backend NLP pipelines" placeholder text.
- `TOPIC_ANALYSIS_IMPLEMENTATION_PLAN.md` (root) — already contains a full taxonomy/architecture
  design for this feature (chunking, annotation, aggregation).
- `OPENSEARCH_DATA_MODEL_PLAN.md` — already specifies the planned `analysis_chunk` /
  `analysis_annotation` / `analysis_aggregate` indices.

**Recommendation:** this is a well-scoped, planned-but-not-started feature rather than an
oversight. Next implementation steps (not done in this pass): a `cdm/backend/api/topics.py`
route + `topic_service.py`, the three OpenSearch indices per the data model plan, a real chunking
job in the ingest/worker pipeline, and a `frontend/app/src/api/topics.ts` client replacing the
mock data. The `system-architecture.mmd` diagram now marks this module explicitly as "planned,
not implemented" instead of depicting it as already wired up.

## 4. Dead code / dependency cleanup completed this pass

- Removed empty leftover packages `cdm/links/` and `cdm/search/` (real modules already deleted
  in an earlier pass; only blank `__init__.py` files remained).
- Rewrote `cdm/data_collection/utils.py`, removing ~10 unused functions including a
  Selenium-based PDF downloader (`download_pdf`) — this was the *only* reason `selenium` and
  `chromedriver-py` were project dependencies.
- Removed 10 confirmed-unused top-level dependencies (`selenium`, `chromedriver-py`, `streamlit`,
  `streamlit_agraph`, `smolagents`, `PyPDF2`, `plotly`, `aio-pika`, `aiohttp`,
  `dataclasses-json`) from `pyproject.toml`/`requirements.txt`/`uv.yaml`, and regenerated
  `uv.lock`, dropping ~40 transitive packages (numpy, pandas, pillow, networkx, pyarrow, rich,
  typer, watchdog, trio, tornado, etc.).
- Fixed a stale `documentation/README.md` section ("Using Endpoint Helpers") that referenced
  entirely fictional/removed APIs (`get_members_list`, `gather_members`, `CongressDataType`,
  `gather_paginated_metadata`) with an accurate example using the real
  `get_spec()` / `request_for_spec()` pattern.
- `scripts/` cleanup — see §5.
- `.mmd` diagram accuracy — see §6.

## 5. `scripts/` folder decisions

- **Deleted** `scripts/bulk_ingest.py`, `scripts/requirements_to_uv.py` — confirmed dead/
  superseded (zero references from tests, docs, or other code; `requirements_to_uv.py` was a
  one-time migration script whose output (`uv.yaml`) already exists and is now marked historical).
- **Moved** `scripts/find_missing_docstrings.py` → `tools/find_missing_docstrings.py` — dev
  tooling, not an operational/ingest script; now sits alongside `tools/swagger_to_endpoint_specs.py`.
- **Kept as-is** (confirmed actively used/documented/tested): `scripts/create_indices.py`,
  `scripts/ingest_all.py`, `scripts/ingest_history.py`, `scripts/ingest.py`,
  `scripts/migrate_jsonl_to_sqlite.py` (imported by `tests/unit/test_list_cache.py` and
  documented in the root README — nearly flagged for deletion incorrectly, caught by grep before
  acting), `scripts/queue_full_ingest.py`, `scripts/submit_ingest.py`.

## 6. Diagram accuracy

- `worker-architecture.mmd` — was accurate for ingest/indexing but omitted the GovInfo bulk
  acquisition and reconciliation pipeline entirely, even though it's a live second ingestion path
  sharing the same job ledger and search store. Added `GovInfo Bulk Acquisition`, `Reconciliation`,
  and `GovInfo Archive` containers with their relationships.
- `frontend/diagrams/system-architecture.mmd` — was **fully fictional**: described a non-existent
  NLP service, a Postgres read-model store, and an API-facing Redis cache, none of which exist.
  Rewritten to reflect the real shape: FastAPI → `bill/member/search/state/admin` services →
  OpenSearch only (no cache, no Postgres); `admin_service` reads the job ledger directly (no
  queue in the read path); the NLP/topic module is shown explicitly as "planned, not implemented";
  the ingest/indexing pipeline (including GovInfo) is shown as a separate offline process feeding
  the same OpenSearch store.
- `frontend/diagrams/navigation-flow.mmd` — was missing the `/admin/ingest`, `/bills`,
  `/bills/:billId`, and `/topics` routes entirely, and treated global member search as reachable
  only via state detail. Rewritten to match `frontend/app/src/routing/routes.tsx` exactly.

## 7. Other findings (not yet fixed — flagging for follow-up)

- `cdm/backend/app.py` sets `allow_origins=["*"]` together with `allow_credentials=True` in its
  CORS middleware. This combination is invalid per the CORS spec in most browsers (wildcard origin
  is ignored/rejected when credentials are allowed) and is a real security smell even where it
  "works" — should be narrowed to the actual frontend origin(s), especially before any production
  deployment.
