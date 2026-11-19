# Congress Tracker

Explore U.S. congressional bills, members, committees and votes in a local web
app. Search legislation, read bill summaries and available full text, and follow
sponsors and legislative activity. Topics, similarity and relationship graphs
are available when their analysis has been built and published.

## Quick start

### 1. Install the prerequisites

- [Git](https://git-scm.com/).
- Python 3.13+ and [uv](https://docs.astral.sh/uv/getting-started/installation/).
- Docker with Compose v2; use Docker Desktop on macOS.
- [Ollama](https://ollama.com/) installed natively for readable topic labels.
  Install the configured model once with `ollama pull llama3.1` (or the model
  selected by `OLLAMA_MODEL` in `.env`).
- A [Congress.gov API key](https://api.congress.gov/sign-up/) if you plan to
  collect Congress.gov data. Browsing existing data does not require this key.

The default services need roughly 8 GiB of Docker memory. Keep at least 8 GiB of
host disk free for the runtime, with additional space for images, dependencies
and data. Startup checks capacity and refuses an undersized configuration.
Maintain the free-disk reserve while long jobs run, not only at startup.
The API watches only application Python for hot reload, not the retained-data
tree or the entire checkout.

### 2. Set up a fresh checkout

```bash
git clone https://github.com/hbeychaner/usa-congress-monitor.git
cd usa-congress-monitor
uv sync --all-extras
make local
```

`make local` creates your local `.env` file and starts Elasticsearch, Redis and
RabbitMQ. If collecting Congress.gov data, set `CONGRESS_API_KEY` in `.env`.
Keep credentials private; do not commit this file.

Create the application's local search credential once, then start the app:

```bash
make es-api-key
make up
```

For an already configured checkout, use `make up`; you do not need to recreate
credentials each time.
Startup reuses or starts native Ollama, checks that the label model is installed,
and verifies access from the application container. It does not automatically
download models or regenerate labels already stored in the index.

The managed stack keeps job history in a Docker volume. Read the
[SQLite operating boundary](documentation/OPERATIONS_RUNBOOK.md#live-sqlite-operating-boundary)
before inspecting or restoring the ledger.

### 3. Open the app

- **Web app:** <http://localhost:5173>
- **API documentation:** <http://localhost:8000/docs>

Use the `localhost` addresses above so the browser origin matches the default
configuration.
API routes use the `/api/v1` prefix; the API documentation lists the endpoints.

## Using the app

- **Bills / Search:** find legislation and open its summaries, actions, available
  text, sponsors and related records.
- **Members / States:** explore members and their indexed legislative activity.
- **Topics / Parties / Graph:** explore published analysis. An unavailable
  analysis message means that result has not been built and published.
- **Admin:** inspect durable jobs and available administrative controls.

**A fresh installation has no legislative data.** Starting the app does not
download history or train models. The default stack runs the web app, API and
one indexing/maintenance worker; acquisition, analytics and scheduling are off.

To load data, follow the [ingestion guide](documentation/guides/ingestion.md)
and review the [worker profiles and capacity requirements](documentation/guides/configuration-and-deployment.md#managed-stack-compose)
before enabling acquisition. Submitting a job alone does not start its worker.
Begin with a bounded scope rather than a full-history backfill.
If you already have retained downloads, check which records are indexed first
and reuse local data for missing records before downloading them again.

Data availability varies by source and scope. Bill pages distinguish unknown,
partial and complete detail-retrieval evidence; missing text or analysis does
not necessarily mean the bill itself is missing.
Missing completeness evidence alone is not a reason to re-ingest a record.
Bill reads include bill and law projections with valid canonical identities.
On a bill's Text tab, "Enacted public law text" or "Enacted private law text"
identifies verified law text, not an earlier bill draft. PDF source links remain
available separately; a source link alone does not mean text has been indexed.
Publisher transcriptions can contain OCR errors; consult the linked facsimile.
A PDF marked "partial facsimile" contains only part of the law, even when the
indexed text is complete.
Complete detail retrieval does not guarantee full-text availability.
Collection counts or links alone do not prove detail completeness.
Completeness describes an individual bill, not whether a whole Congress has
been collected.

## Everyday commands

Recurring bill refresh reuses the existing ingest pipeline; see the
[refresh policy](documentation/guides/ingestion.md#scope-and-item-fetch-policy).
The controlled operations profile does not automatically enable acquisition
or scheduling. To retain the opt-in daily bill refresh on startup, use
`make up STACK_PROFILES=operations,scheduler`; plain `make up` does not retain
the scheduler profile.

Run these from the repository root:

```bash
make stack-status   # Check running services
curl --fail http://127.0.0.1:8000/ready  # Check API dependency readiness
make stack-logs     # Follow application logs; Ctrl+C stops following
make down           # Stop the stack while preserving stored data
make up             # Start it again
```

`make status` fetches the API's indexed counts and durable job summary;
`make worker-monitor` fetches current ingestion progress. `make health-check`
checks API/search readiness, not broker/worker health, ledger integrity or
corpus completeness. These commands do not open the live ledger on the host.
Use `API_URL=http://host:port` to target another owned deployment.
See the [supported entry points](documentation/guides/configuration-and-deployment.md#supported-operational-entry-points)
for setup, collection, analytics, and guarded recovery commands.

If startup is refused, run `make stack-capacity` and consult the
[configuration guide](documentation/guides/configuration-and-deployment.md).
Do not start extra workers manually to bypass a capacity refusal.
If the app reports API Not Ready, check service status and health first.
Keep the Mac awake while running long collection or validation jobs; elapsed
time across sleep is not evidence of continuous operation.
For failed jobs, restarts or backups, use the
[operations runbook](documentation/OPERATIONS_RUNBOOK.md).
Inspect a failed analysis job and resolve any reported capacity warning before
resubmitting it; an analysis failure does not mean the underlying legislation
needs downloading again.
Successful analytics builds enqueue separate verified cleanup jobs, retaining the served model
and one predecessor. See the [analytics retention policy](documentation/guides/analytics.md#6-rebuilds-retention-and-operational-checks);
downloaded base models and source data are not removed.
Failed training and preview runs do not remove working models; cleanup refuses
uncertain serving state.
Health warnings about failed jobs describe ingestion history, not automated
test failures. Repairing some bills does not clear a job for an entire scope.

## Learn more

- [Documentation home](documentation/README.md) and
  [published wiki](https://github.com/hbeychaner/usa-congress-monitor/wiki).
- [Configuration and deployment](documentation/guides/configuration-and-deployment.md).
- [Data collection and replay](documentation/guides/ingestion.md).
- [Architecture and visual guides](documentation/reference/visuals.md).
- [Analytics guide](documentation/guides/analytics.md).
- [Development and validation](documentation/guides/configuration-and-deployment.md#testing-and-contracts):
  local checks and hosted CI.
- [Changelog](CHANGELOG.md).
