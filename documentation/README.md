# Congress Tracker documentation

Understand how source records become searchable bills, member activity, votes,
topics, and graphs. These repository pages are the **canonical documentation**.
The [GitHub wiki](https://github.com/hbeychaner/usa-congress-monitor/wiki) is a
publication target, not a second editing location.

The managed local stack serves the API/UI and one index/maintenance worker.
Additional acquisition, analytics and scheduler roles require explicit profile
selection and capacity admission. See [configuration and deployment](guides/configuration-and-deployment.md)
for the supported topology and resource checks.

## Start here

| Your question | Read |
|---|---|
| How do I install and start using the app? | [Getting started](../README.md#quick-start) |
| What runs, and why are there several databases? | [Architecture](architecture.md) |
| Can I see the system rather than just read about it? | [Visual atlas: C4, data flow, relationships, and request sequence](reference/visuals.md) |
| What are the records, identifiers, fields, and relationships? | [Data structures](reference/data-models.md) |
| Where does each record go, and what can be searched? | [Indexing and storage reference](reference/indexing.md) |
| How are records fetched, retried, replayed, and refreshed? | [Ingestion guide](guides/ingestion.md) |
| What do topics, perspectives, similarity, and graph edges mean? | [Analytics guide](guides/analytics.md) |
| Which page calls which endpoint and service? | [API and frontend reference](reference/api-and-frontend.md) |
| Which class, function, or field implements this? | [Generated source symbol index](reference/symbols/README.md) |
| How do I configure, run, test, or deploy it? | [Configuration and deployment](guides/configuration-and-deployment.md) |
| How do I recover failed jobs or restore state? | [Operations runbook](OPERATIONS_RUNBOOK.md) |
| How do I update the docs and prepare the wiki? | [Documentation maintenance](CONTRIBUTING.md) |

### Suggested reading paths

- **First-time user:** [getting started](../README.md#quick-start) ->
  [using the app](../README.md#using-the-app). Read the ingestion guide when
  you are ready to collect data.
- **System reader:** architecture -> visual atlas -> data structures ->
  ingestion -> indexing -> API and frontend.
- **Data investigator:** data structures -> indexing -> analytics -> source
  symbols for the relevant package. A diagram edge is a logical identifier
  reference, not a database-enforced foreign key.
- **Operator:** root [quick start](../README.md#quick-start) -> configuration
  and deployment -> ingestion -> operations runbook.
- **Contributor:** architecture -> subsystem guide -> exact source declaration ->
  related tests -> documentation maintenance.

## The mental model

1. Congress.gov and GovInfo supply legislative records; Voteview supplies
   additional roll calls, positions, and voting metadata.
2. SQLite owns durable job history and replayable acquisition state.
   RabbitMQ delivers work; it is not the job ledger.
3. Acquisition publishes records into Redis Streams. Indexing turns them into
   searchable projections; acknowledging a stream record is not the same as
   marking an acquisition job complete.
4. Bills from multiple sources converge on canonical bill IDs. Full text is
   stored on bill documents, not in a separate bill-text index.
5. Elasticsearch serves indexed entities and derived analysis. Python modules
   retain historical `opensearch` names; the shipped containers use
   **Elasticsearch**, not interchangeable OpenSearch binaries.
6. FastAPI exposes typed responses; React renders them. Offline analytics and
   admin-triggered builds add projections, not new authoritative source facts.

## Reference material and provenance

The prose documents source behavior, not a claim that a particular deployment
has completed all historical backfills. Check durable coverage and live health
before drawing conclusions about missing records.

| Reference | Status |
|---|---|
| [Mapping definitions](opensearch_mappings.yaml) | Executable mapping input, despite the historical filename |
| [Generated endpoint specifications](generated_endpoint_specs.json) | Captured endpoint catalogue; runtime specs live in [source](../cdm/data_collection/specs) |
| [Original upstream endpoint docs](original) | Upstream reference snapshots, not application API documentation |
| [Original OpenAPI JSON](original/swagger.json) / [YAML](original/swagger.yaml) | Congress.gov snapshots, not FastAPI's `/openapi.json` |
| [Spec comparison report](specs_swagger_report.json) | Historical comparison artifact |
| [Frontend style guide](../frontend/STYLE_GUIDE.md) | UI design conventions |

## Visuals and wiki

The [visual atlas](reference/visuals.md) embeds Mermaid diagrams for rendering
on GitHub and in the wiki. Editable `.mmd` files remain in
[diagrams](diagrams); the worker C4 container view remains at the repository
[root](../worker-architecture.mmd) for existing links.

To regenerate references and prepare a local, unpublished wiki:

```bash
uv run python tools/build_documentation.py --wiki documentation/wiki
uv run python tools/build_documentation.py --check --wiki documentation/wiki
```

The output includes `Home.md`, `_Sidebar.md`, `_Footer.md`, and flat wiki page
names with rewritten internal links. The output directory is ignored by Git.
Nothing is uploaded, committed, or pushed by these commands.
