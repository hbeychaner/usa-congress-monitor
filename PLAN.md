# Congress Tracker — Engineering Plan

## Current Status (2026-09-04)

All 20 Congress.gov resource endpoints are implemented and tested: specs,
Pydantic models, ingest-run tests, and field coverage exist for every
resource (see `tests/unit/test_*_ingest.py`). The original migration,
resource-triage, and historical-ingest milestones described in earlier
revisions of this document are complete; that per-endpoint checklist has
been removed here to avoid duplicating information that's now embodied in
the test suite itself.

This document is now a short index pointing to the documents that carry
the current, actively-maintained plans and status:

| Document | Scope |
|---|---|
| `FULL_DATA_INGEST_IMPLEMENTATION_PLAN.md` | GovInfo bulk acquisition, normalization, and reconciliation with canonical bill metadata |
| `OPENSEARCH_DATA_MODEL_PLAN.md` | Target OpenSearch index architecture (entity, relationship, and derived-analysis indices) |
| `INGEST_FINISH_INDEX_CLEANUP_PLAN.md` | Near-term operational plan to drain ingest jobs and finish indexing |
| `OPERATIONS_HARDENING_PLAN.md` | Health checks, throughput tuning, and failure-reconciliation work |
| `TOPIC_ANALYSIS_IMPLEMENTATION_PLAN.md` | Planned topic-taxonomy/NLP feature (not started) |
| `CHANGELOG.md` | Dated log of completed work |
| `documentation/README.md` | Architecture, module layout, and operational runbook |

## Vision

Build a 1:1 mirror of all congressional data from the Congress.gov API, stored in
OpenSearch, with a clean SDK layer for retrieval and a data management layer for
ingest, enrichment, and cross-reference linking. Eventually covers all 200 years of
records; immediate priority is the last 20 years (~Congress 109–119).

## Milestone Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1 | ✅ Done | Rename `src` → `cdm`; `cdm/` skeleton |
| M2 | ✅ Done | Specs for all 20 endpoints; full test coverage |
| M3 | ✅ Done | Local bulk ingest for all 20 endpoints (`scripts/ingest_all.py`, `scripts/ingest_history.py`) |
| M4 | ✅ Done | OpenSearch mappings for all resources (`documentation/opensearch_mappings.yaml`) |
| M5 | ✅ Done | OpenSearch storage layer — index creation, bulk upsert, aliasing (`cdm/store/`) |
| M6 | ❌ Deferred | Cross-reference linking/enrichment. An earlier `cdm/links/resolver.py` stub was unused dead code and was removed; if this work is picked up again it should be redesigned against the current `cdm/store/` and `documentation/opensearch_mappings.yaml`, not restored from history. |

Ongoing work beyond the original M1–M6 scope (GovInfo bulk ingest, topic
analysis, operational hardening) is tracked in the documents listed above.
