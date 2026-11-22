# Congress Tracker documentation

Welcome to the Congress Tracker technical documentation. These pages explain
how legislative records are collected, indexed into Elasticsearch, analyzed
with NLP and graph models, and served through FastAPI and React.

These repository files are the **canonical documentation**; the
[GitHub wiki](https://github.com/hbeychaner/usa-congress-monitor/wiki) is
generated automatically from this directory.

By default, the local Docker Compose stack runs the web UI, the FastAPI
backend, Elasticsearch, RabbitMQ, Redis, and one indexing/maintenance worker.
Data acquisition, machine-learning analytics, and scheduled refresh jobs are
opt-in profiles described in
[configuration and deployment](guides/configuration-and-deployment.md).

## Start here

| Your question | Read |
|---|---|
| How do I install and run the app locally? | [Getting started](../README.md#quick-start) |
| How do the services and databases fit together? | [Architecture](architecture.md) |
| Can I view system and data-flow diagrams? | [Visual atlas: C4, data flow, relationships, and request sequence](reference/visuals.md) |
| What data models and identifiers are used? | [Data structures](reference/data-models.md) |
| How are records stored and searched in Elasticsearch? | [Indexing and storage reference](reference/indexing.md) |
| How do we collect data from Congress.gov, GovInfo, and Voteview? | [Ingestion guide](guides/ingestion.md) |
| How do topics, party perspectives, and member graphs work? | [Analytics guide](guides/analytics.md) |
| Which frontend pages call which API endpoints? | [API and frontend reference](reference/api-and-frontend.md) |
| Where is a specific class, function, or field defined? | [Generated source symbol index](reference/symbols/README.md) |
| How do I configure settings, run tests, or deploy? | [Configuration and deployment](guides/configuration-and-deployment.md) |
| How do I troubleshoot jobs, restart services, or back up data? | [Operations runbook](OPERATIONS_RUNBOOK.md) |
| How do I update docs and regenerate diagrams/symbol tables? | [Documentation maintenance](CONTRIBUTING.md) |

### Suggested reading paths

- **New user:** [Getting started](../README.md#quick-start) →
  [Using the app](../README.md#using-the-app) →
  [Ingestion guide](guides/ingestion.md) when you want to import data.
- **Developer onboarding:** [Architecture](architecture.md) →
  [Visual atlas](reference/visuals.md) →
  [Data structures](reference/data-models.md) →
  [API and frontend reference](reference/api-and-frontend.md).
- **Data & ML engineer:** [Data structures](reference/data-models.md) →
  [Indexing reference](reference/indexing.md) →
  [Analytics guide](guides/analytics.md) →
  [Source symbol index](reference/symbols/README.md).
- **Operator:** [Quick start](../README.md#quick-start) →
  [Configuration and deployment](guides/configuration-and-deployment.md) →
  [Operations runbook](OPERATIONS_RUNBOOK.md).

## How the system works in 6 steps

1. **External sources:** Congress.gov and GovInfo provide bills, summaries,
   text, committees, and communications; Voteview provides historical roll-call
   votes and member positions.
2. **Job tracking & task delivery:** SQLite records durable job state and
   stores raw downloaded archives for local replay. RabbitMQ delivers Celery
   tasks to workers.
3. **Stream handoff:** Acquisition workers write normalized records to Redis
   Streams; indexing workers consume those streams and bulk-write projections
   into Elasticsearch.
4. **Canonical bill documents:** Records from multiple sources (Congress.gov
   API, GovInfo bulk XML, and Statutes at Large) merge onto canonical bill IDs
   (`bill:<congress>:<type>:<number>`), with full text stored directly on the
   bill document.
5. **Search & analytics store:** Elasticsearch serves both core entity
   projections (bills, members, committees, votes) and derived analytics
   (embeddings, BERTopic clusters, party perspectives, and member graphs).
6. **Typed API & web UI:** FastAPI validates queries and returns typed Pydantic
   response contracts; the React/TypeScript frontend renders them.

## Reference files in this folder

| Reference | Description |
|---|---|
| [Mapping definitions](opensearch_mappings.yaml) | Elasticsearch index mapping definitions loaded at runtime |
| [Generated endpoint specifications](generated_endpoint_specs.json) | Captured Congress.gov endpoint catalog; runtime specs live in [cdm/data_collection/specs](../cdm/data_collection/specs) |
| [Original upstream endpoint docs](original) | Reference snapshots of Congress.gov API documentation |
| [Original OpenAPI JSON](original/swagger.json) / [YAML](original/swagger.yaml) | Congress.gov upstream OpenAPI snapshots |
| [Frontend style guide](../frontend/STYLE_GUIDE.md) | UI conventions and layout guidelines |

## Building visuals and the wiki

The [visual atlas](reference/visuals.md) and
[source symbol index](reference/symbols/README.md) are generated from the
`.mmd` diagram files in [diagrams/](diagrams) (plus
[worker-architecture.mmd](../worker-architecture.mmd)) and the codebase AST:

```bash
uv run python tools/build_documentation.py --wiki documentation/wiki
uv run python tools/build_documentation.py --check --wiki documentation/wiki
```
