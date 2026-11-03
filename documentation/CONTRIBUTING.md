# Maintaining documentation and preparing the wiki

[Documentation home](README.md)

## Single source of truth

Edit repository documentation. Do not independently edit the wiki or generated
reference pages. The wiki is a reproducible publication copy with rewritten
links and its own navigation.

| Content | Edit here |
|---|---|
| Architecture and explanations | Markdown chapters under `documentation` |
| Diagram geometry and labels | `.mmd` files under `documentation/diagrams` and root `worker-architecture.mmd` |
| Symbol signatures and field types | Python/TypeScript source, then regenerate |
| Search field types and analysis | Mapping definitions and owning store code, then update the indexing chapter |
| Upstream endpoint behavior | Runtime endpoint specs; original snapshots remain provenance |
| Wiki navigation/link conversion | [Documentation builder](../tools/build_documentation.py) |

## Regenerate and validate

The generator statically parses Python using `ast` and TypeScript using the
project's installed TypeScript compiler. It does not import the application,
read `.env`, connect to databases, or call an LLM.

```bash
# Initial prerequisites, if not already installed:
uv sync --all-extras
npm --prefix frontend/app ci

# After code or diagram changes:
uv run python tools/build_documentation.py

# Check deterministic generated content, local files and source line links:
uv run python tools/build_documentation.py --check

# Focused tooling tests:
uv run pytest -q tests/unit/test_documentation.py
uv run --with ruff ruff check tools/build_documentation.py tests/unit/test_documentation.py
```

Normal `uv sync` retains the full `dev` and `analysis` groups. To work on serving
without installing training packages, keep a separate environment and retain
the group selection on subsequent `uv run` commands:

```bash
UV_PROJECT_ENVIRONMENT=tmp/api-env uv sync --frozen --no-default-groups
UV_PROJECT_ENVIRONMENT=tmp/api-env uv run --frozen --no-default-groups \
  uvicorn cdm.backend.app:app --host 127.0.0.1 --port 8000
```

This still installs spaCy/its model and NumPy for existing search behavior.
Worker execution requires the `analysis` group; the normal developer/test
environment includes it. Submission CLIs do not construct training jobs.

The generated [symbol index](reference/symbols/README.md) covers declarations,
including private helpers, rather than claiming every declaration is public API.
Python class attributes are shown as declared, not as fully resolved inherited
Pydantic schemas. Enum values, serializers, validators and computed fields must
be read in source. Frontend names are syntax declarations, not inferred call
relationships. Use the narrative chapters to understand responsibilities.

The builder checks local Markdown file targets and `#L<number>` source-line
bounds. It does not verify remote URLs, semantic heading anchors, live index
state, or runtime contracts. A successful build is not sufficient evidence for
a behavioral claim.

### Diagram validation

1. Update the editable `.mmd` source.
2. Validate it with the Mermaid extension's `mermaid-diagram-validator`.
3. Render it using `mermaid-diagram-preview`, passing the existing document URI.
4. Regenerate the visual atlas and wiki so embedded diagrams match the source.
5. Check diagrams against code responsibilities and acknowledgement ordering.

Inspect rendered geometry, not syntax alone: no connector may pass through an
unrelated node or hide another relationship's label. The routed C4 views avoid
the native renderer's straight-line overlaps. Check the actual SVG paths and
label bounds again after adding nodes or relationships.

Do not use the Mermaid AI repair command without discussing credit usage.
Do not manually regenerate diagrams managed by Mermaid Chart Sync; use its
review workflow if an `id` frontmatter field is present.

## Prepare the local wiki

```bash
uv run python tools/build_documentation.py --wiki documentation/wiki
uv run python tools/build_documentation.py --check --wiki documentation/wiki
```

For a **prose-only** edit with already-current source/visual references:

```bash
uv run --frozen --no-default-groups python tools/build_documentation.py \
  --wiki-only --wiki documentation/wiki
uv run --frozen --no-default-groups python tools/build_documentation.py \
  --wiki-only --check --wiki documentation/wiki
```

This mode validates canonical links and generates/checks the wiki without
source inventory, TypeScript/Node, diagram regeneration, scientific imports,
environment files or a live API. It requires `--wiki`. Pydantic must still be
installed. It deliberately does **not** certify symbol/diagram freshness: run
the full commands above after code or `.mmd` changes and before publication.
Use a separate no-default-groups environment if preserving a full developer
environment; group selection can change installed dependencies.

The ignored `documentation/wiki` directory contains:

- `Home.md`: documentation landing page and reading paths;
- `_Sidebar.md`: stable understanding/operations navigation;
- `_Footer.md`: canonical-source reminder;
- flat page filenames such as `reference-indexing.md` and `guides-ingestion.md`;
- source-reference pages per package and a rendered Mermaid atlas.

The wiki publishes current implementation and operating reference only: the
documentation home, architecture, runbook, maintenance guide, and chapters under
`guides/` and `reference/`. Root-level plans, incident reports and other internal
records are not published. Keep their repository copies for provenance.
Repository-only historical sections inside an otherwise current chapter use
paired `<!-- wiki:repository-only:start -->` and
`<!-- wiki:repository-only:end -->` markers on their own lines. The builder
omits those sections from the wiki and rejects unmatched or nested markers.

Internal chapter links become wiki page links. Source, diagram, mapping,
upstream snapshot and other non-wiki links become absolute GitHub repository
links, preserving source-line anchors.
The default source ref is `main`; pass `--source-ref <branch-or-tag>` when the
published source should refer to a different revision. Use the same ref on
generation and `--check`. Source links will not resolve remotely until that
revision and its docs are pushed.

The builder refuses unmanaged/obsolete Markdown pages in an existing output
directory instead of silently publishing stale content. Inspect those named
files and move or remove only the confirmed obsolete generated pages before
regenerating. Never point `--wiki` at the canonical documentation directory.

## Publishing the wiki

**No publication is performed as part of local preparation.** Review the
local pages, commit/push the canonical repository documentation, and obtain
approval before changing the remote wiki.

When approved:

1. Enable the repository's GitHub Wiki if needed. Create its first page in the
   GitHub UI if the wiki Git repository does not yet exist.
2. Clone `https://github.com/hbeychaner/usa-congress-monitor.wiki.git` into a
   separate directory, not into the canonical documentation tree.
3. Review any existing wiki-only content before replacing anything. Preserve or
   deliberately reconcile it; do not overwrite an established wiki blindly.
4. Regenerate a fresh local wiki for the source revision being published.
5. Copy the reviewed generated pages into the wiki checkout and inspect its Git
   diff, including sidebar/footer links and Mermaid rendering.
6. Commit with the required contributor attribution and make a plain push.
   Never force-push.
7. Verify the remote wiki home, sidebar, source links and diagram rendering.

GitHub Wiki is a separate Git repository: pushing the application repository
does not publish the wiki. This workflow deliberately avoids an automatic
deployment token or write-enabled CI action.

## Update discipline

When changing a subsystem, update its narrative chapter and source reference
together. Update the root README and changelog for user-visible documentation
changes. Keep dated incident reports clearly historical.

Before asserting that a field is indexed, inspect the mapping **and** the
projection/writer. Before asserting a relationship, check the actual identifier
construction and query. Before asserting a retry guarantee, check the failure
path and the checkpoint/acknowledgement order. Do not copy stale claims from
upstream snapshots or old planning documents into current architecture pages.
