# Engineering Guidelines

## Code style

- Professional, strongly typed, object-oriented Python (3.13). Behavior lives in classes with clear single responsibilities; avoid loose module-level functions that pass dicts around.
- Use Pydantic models for every structured value: CSV rows, API payloads, OpenSearch documents, job payloads, config. Validate at the boundary and keep typed models inside.
- Avoid string-keyed dicts. Model fields as typed attributes, and use `StrEnum` for closed sets of values (chambers, parties, positions, kinds). Dicts are fine only when keyed by an enum or a typed identifier.
- Keep string literals to a minimum: constants, enum members, and Pydantic field aliases replace magic strings. Serialize at the edge with `model_dump(mode="json")`.
- Full type annotations on all signatures, including return types; no bare `Any` where a concrete type or Protocol exists.
- Prefer SQLAlchemy Core/ORM expressions over raw SQL strings.
- One-line comments only, and only for what the code cannot show.

## Applying this guidance

These rules apply to new and modified code. Do not rewrite legacy modules just to conform; migrate them when they are otherwise being changed.

## Reference implementation

`cdm/ingest/voteview.py` is the pattern to follow: enums, Pydantic row and document models, a generic typed reader, and small collaborating classes.

## Workflow

- Tests: `uv run pytest -q`.
- Do not commit `planning/`, `models/`, `data/`, `logs/`, or one-off local scripts.
- Ask before pushing.
