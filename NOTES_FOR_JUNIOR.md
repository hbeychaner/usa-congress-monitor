# Code Review Notes

Notes from a full-repo review, written up so you can see what was wrong, why it
mattered, and how it was fixed. All items below have already been fixed and
verified (`uv run pytest tests/unit -q` → 202 passed) unless marked otherwise.

## Fixed

### 1. `cdm/store/index_manager.py` — missing cache on hot-path disk read
`load_definitions()` re-read and re-parsed `documentation/opensearch_mappings.yaml`
from disk on **every single document** validated during indexing (called via
`mapping_validation.py` for each record). Added `@lru_cache(maxsize=1)`.

Lesson: if a "pure" function is called once per item in a hot loop, check
whether its inputs ever change at runtime — if not, cache it.

### 2. `cdm/data_collection/client.py` — duplicate docstring
Leftover copy-paste duplicate docstring in `_request_with_backoff()`. Harmless,
but a code smell — cleaned up.

### 3. `cdm/data_collection/client.py` — unbounded HTTP 429 retry
5xx/connection errors were capped (`max_attempts=5`, 10s cumulative wait), but
HTTP 429 ("rate limited") responses retried **forever** — no attempt cap, with
delays growing up to 1 hour. A sustained rate-limit situation could hang a
worker indefinitely instead of failing the job so it can be retried/inspected.

Fixed: added `max_rate_limit_attempts: int = 8` — after 8 rate-limited
attempts, raises `RuntimeError` just like the other retry path does.

Lesson: when you have two different retry loops in the same function (5xx vs.
429), make sure they follow the same "give up eventually" contract. An
infinite loop is rarely the right failure mode — a bounded retry that
surfaces a clear error is almost always safer.

### 4. `cdm/jobs/store.py` — duplicated claim logic (`mark_running`/`claim_running`)
Two near-identical methods did the same atomic "claim a QUEUED job" update,
except `claim_running` forgot to update the `_INGEST_WINDOWS` coverage table.
This is exactly the kind of copy-paste that causes a real bug the *next* time
someone patches the claim logic and only touches one of the two copies.

Fixed: merged into one method, `mark_running(job_id, *, update_windows=True)`.
GovInfo bulk jobs (which have no `_INGEST_WINDOWS` row) call it with
`update_windows=False`. Updated the one call site in `cdm/workers/tasks.py`.

Lesson: if you're about to copy a method and tweak one behavior, stop and add
a parameter instead. Two copies of "almost the same logic" will drift.

### 5. `cdm/jobs/store.py` — N+1 query pattern
`stale_active()`, `stale_queued()`, `failed()`, `queued()`, and `jobs()` each
ran a `SELECT id` query, then looped calling `self.get(id)` — which opens a
**new connection per row** and does a second `SELECT`. For N jobs that's
`1 + N` round trips instead of 1.

Fixed: added a `_fetch(statement)` helper that selects full rows in a single
query and decodes the JSON payload column in Python, no per-row connections.

Lesson: watch for "get list of ids, then fetch each by id in a loop" — it's a
classic N+1 and almost always avoidable by selecting the full row up front.

### 6. `scripts/queue_full_ingest.py` — no pacing on bulk dispatch
Running this with defaults plans **2,034 jobs** (119 congresses × 8
date-windowed resources across ~237 yearly windows) and used to dispatch all
of them to Celery in one tight `for` loop with zero pacing. Not incorrect by
itself, but there was no way to queue a full historical backfill gently, and
an accidental double-run would double-dispatch everything at once.

Fixed: added `--batch-size` (default 50) and `--batch-delay` (default 2.0s)
flags — the loop now pauses briefly every `batch-size` dispatches. Set
`--batch-size 0` to disable pacing entirely if you want the old behavior.

## Deleted (dead code)

These were checked with `grep` across `cdm/`, `scripts/`, and `tests/` for any
import/usage before removal, and the full test suite was re-run after
deleting them to confirm nothing broke:

- **`cdm/data_collection/collector.py`** — `collect_with_details`,
  `collect_paginated_list`, `retry_call`: zero usages anywhere except a stale
  documentation example (which referenced modules — `data_types.py`,
  `endpoints/bill.py` — that don't even exist anymore). Superseded by the
  current pipeline (`cdm/ingest/pipeline.py` + `cdm/ingest/runner.py`).
  Updated `documentation/README.md` to point at the current architecture
  instead of the removed example.
- **`cdm/links/resolver.py`** — `resolve_bill_ref`/`resolve_member_ref`: zero
  usages anywhere. Also had a latent bug worth knowing about even though the
  code is gone: `record.get("latestAction", {}).get("bill")` will raise
  `AttributeError` if `latestAction` is present but explicitly `None`, because
  `dict.get(key, default)` only returns `default` when the *key is missing*,
  not when the value is `None`. If you ever write similar chained `.get()`
  calls, guard each step explicitly (`(record.get("latestAction") or {}).get("bill")`).
- **`cdm/search/client.py`** — a one-function OpenSearch query wrapper, never
  imported anywhere.

**Important correction:** `cdm/ingest/checkpoint.py` was flagged in an earlier
review pass as dead code and was briefly deleted during this cleanup — but it
turned out to be a false positive. It's actually used by
`scripts/ingest_history.py` (`checkpoint.load()` / `checkpoint.save()`), just
via an import style (`from cdm.ingest import checkpoint`) that an earlier
`grep` search didn't match. It was restored and is **not** dead code. Lesson
for both of us: when checking "is this used anywhere," search for the module
name in bare-import form too (`import x`, `from pkg import x`), not just
`from pkg.x import ...` / `pkg.x.` patterns.

## Also fixed in this pass

- **`cdm/backend/api/schemas/` was an orphaned package.** `ruff check .`
  flagged unused imports in `members.py`/`search.py`/`states.py` — each file
  was *only* `from cdm.contracts.api import SomeType` with nothing else, and
  a repo-wide `grep` found zero code importing from these modules by name or
  reference. Deleted the whole package. Lesson: run `ruff check .` on a
  schedule (or in CI) — it catches this kind of orphaned-module rot for free.
- **Test suite was slow (3 minutes) for a boring reason.** The Congress.gov
  client throttles itself to ~5000 req/hour (`_rate_limit_interval = 3600/5000
  ≈ 0.72s`) via a real `time.sleep()` call before every request. Ingest
  fixture tests mock the HTTP layer (`_request_with_backoff`) but not the
  rate limiter, so each test that simulated fetching ~19 item details paid
  ~19 × 0.72s ≈ 13.8s in *real* wall-clock sleep — 13 such tests dominated
  the 183s suite runtime. Added `tests/unit/conftest.py` with an autouse
  fixture that no-ops `cdm.data_collection.client.time.sleep` for all unit
  tests (tests that specifically assert on sleep durations override it
  locally, which takes precedence). Suite now runs in ~3s. Lesson: if a test
  suite is mysteriously slow, `pytest --durations=25` shows you exactly which
  tests to look at — don't guess.
- **`Documentation/` vs `documentation/` case mismatch.** Git had this
  directory tracked as `Documentation` (capital D), but every reference in
  the codebase (`cdm/store/index_manager.py`'s OpenSearch mappings path,
  `tools/swagger_to_endpoint_specs.py`) used lowercase `documentation`. macOS
  and Windows filesystems are case-insensitive by default, so this worked
  fine locally and hid the bug — but a checkout on a case-sensitive Linux
  filesystem (CI runners, Docker containers, most servers) would create a
  directory literally named `Documentation`, and every one of those lowercase
  path references would fail to find the file. Fixed by renaming the
  git-tracked directory to lowercase (`git mv` through a temp name, since a
  direct case-only rename doesn't register on a case-insensitive filesystem).
  Lesson: don't trust that a path "just works" because it works on your
  machine — macOS/Windows case-insensitivity hides a whole class of bugs
  that only show up in production.

## Flagged, not changed (needs a product/design decision)

- **`elastic-start-local` secrets**: while reviewing `.env` output in the
  terminal this session, the `ELASTIC_API_KEY` value was printed in full (in
  addition to the `OPENAI_API_KEY` flagged earlier). Recommend rotating both
  if you haven't already — neither was committed to git, but both leaked to
  terminal scrollback/session history.
- **`bulk_upsert()` painless merge script** (`cdm/store/redis_indexing.py`) —
  for the "bill" resource, list-valued fields are merged by unbounded append
  on every re-ingest. Not urgent, but if a bill gets re-ingested many times
  over its lifecycle, some array fields could grow indefinitely. Worth a cap
  or dedup step if this becomes a real problem.
- **Makefile/Docker parity**: native `make worker-index` runs with
  `--concurrency=4`, but `docker-compose.fullstack.yml`'s `worker-index`
  service uses `--concurrency=2`. Probably fine, but worth reconciling so
  local dev and the containerized stack behave the same way.
