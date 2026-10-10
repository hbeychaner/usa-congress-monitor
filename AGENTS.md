# Engineering Guidelines

## Code style

- Professional, strongly typed, object-oriented Python (3.13). Behavior lives in classes with clear single responsibilities; avoid loose module-level functions that pass dicts around.
- Use Pydantic models for every structured value: CSV rows, API payloads, OpenSearch documents, job payloads, config. Validate at the boundary and keep typed models inside.
- Avoid string-keyed dicts. Model fields as typed attributes, and use `StrEnum` for closed sets of values (chambers, parties, positions, kinds). Dicts are fine only when keyed by an enum or a typed identifier.
- Keep string literals to a minimum: constants, enum members, and Pydantic field aliases replace magic strings. Serialize at the edge with `model_dump(mode="json")`.
- Full type annotations on all signatures, including return types; no bare `Any` where a concrete type or Protocol exists.
- Prefer SQLAlchemy Core/ORM expressions over raw SQL strings.
- One-line comments only, and only for what the code cannot show.
- No lazy imports, and centralized configuration when contants are needed. If a constant is added or already exists in a python file and it's read as part of another task, move to a configuration class or object. 
- Prefer dependency injection anywhere possible instead of procedural code that passes parameters through multiple levels of functional depth.
- Never commit work that still has pydantic warnings or issues. Always scan for pydantic and ruff issues, and fix before committing. 
- Update the CHANGELOG, README, and other documentation if that documentation is committed to the repository before every commit. 

## Configuration and dependency injection

- Application settings live in `cdm/config` (pydantic-settings sections, `get_config()`); do not add new module-level constants to `settings.py`. Constants used by only one or two functions may stay beside them.
- Classes receive collaborators (clients, stores, config sections) through their constructors and never read config or build clients themselves.
- `cdm/container.py` (`Container`) is the composition root for scripts and workers; `cdm/backend/dependencies.py` provides FastAPI `Depends` providers. Tests inject fakes directly or override the container.
- Legacy modules still importing `settings` are migrated when they are otherwise changed.

## Applying this guidance

These rules apply to new and modified code as well as legacy modules. Rewrite legacy modules to conform; migrate them when they are otherwise being changed.

## Reference implementation

`cdm/ingest/voteview.py` is the pattern to follow: enums, Pydantic row and document models, a generic typed reader, and small collaborating classes.

## Workflow

- Tests: `uv run pytest -q`.
- Do not commit `planning/`, `models/`, `data/`, `logs/`, or one-off local scripts.
- Ask before pushing.
