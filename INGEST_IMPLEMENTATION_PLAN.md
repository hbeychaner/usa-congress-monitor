# Ingest Cycle Implementation Plan

This plan covers the functionality needed to cycle through historical Congress.gov data reliably.

## Items

- [x] 1. Honor configured date parameter names
  - Pass `ResourceConfig.from_date_param` and `to_date_param` through the pipeline into `IngestRunner`.
  - Keep the default API names for direct runner use.
  - Add regression coverage for custom date parameter names.

- [x] 2. Add boundary-safe date windows
  - Support configurable overlap between adjacent date chunks.
  - Document the inclusive/exclusive boundary behavior.
  - Keep deduplication deterministic when overlap is enabled.

- [x] 3. Deduplicate historical output
  - Define canonical-ID based deduplication across year and Congress chunks.
  - Provide a merge utility that preserves raw and processed records.
  - Report records with no usable canonical ID instead of silently dropping them.

- [x] 4. Add coverage reporting
  - Record requested date/Congress ranges, completed chunks, failures, counts, and duplicate IDs.
  - Emit a machine-readable coverage report for resumable runs.

- [x] 5. Verify static endpoint assumptions
  - Guard the catalog so static resources cannot accidentally advertise date filters.
  - Keep API behavior checks as an operational validation against live responses.

## Validation

Run the focused tests after each item, then run the full suite before marking the item complete.
