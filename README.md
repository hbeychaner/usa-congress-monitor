# Congress Tracker

Congress Tracker is a local web application and data toolkit for exploring U.S.
congressional legislation, members, committees, and roll-call votes. Search
bills, read summaries and full text, inspect sponsorships and voting records,
and explore topic clusters, party perspectives, and member relationship graphs
once analytics are built.

---

## Quick start

### 1. Install the prerequisites

- [Git](https://git-scm.com/)
- Python 3.13+ and [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Docker with Compose v2 (Docker Desktop on macOS)
- [Ollama](https://ollama.com/) installed natively on your host machine for
  generating human-readable topic labels. Pull the configured model once:
  ```bash
  ollama pull llama3.1
  ```
- A [Congress.gov API key](https://api.congress.gov/sign-up/) if you plan to
  fetch new records from Congress.gov (browsing already indexed data does not
  require a key).

> **Resource requirements:** Give Docker at least **8 GiB of memory** and keep
> at least **8 GiB of free disk space** on your host. Startup automatically
> checks available memory and disk space before launching containers.

### 2. Set up a fresh checkout

```bash
git clone https://github.com/hbeychaner/usa-congress-monitor.git
cd usa-congress-monitor
uv sync --all-extras
make local
```

`make local` creates your local `.env` file and starts the background
infrastructure (Elasticsearch, Redis, and RabbitMQ). If you plan to collect
data from Congress.gov, add your `CONGRESS_API_KEY` to `.env`.

Next, generate a local Elasticsearch API key once and start the application stack:

```bash
make es-api-key
make up
```

On subsequent runs, `make up` is all you need. It verifies that your native
Ollama server and label model are reachable, starts the containers, and mounts
the durable job ledger volume. See the
[SQLite operating boundary](documentation/OPERATIONS_RUNBOOK.md#live-sqlite-operating-boundary)
before inspecting or backing up the job database.

### 3. Open the app

- **Web app:** <http://localhost:5173>
- **API documentation (OpenAPI):** <http://localhost:8000/docs>

All backend endpoints live under `/api/v1`.

---

## Using the app

- **Bills & Search:** Find legislation by keyword, Congress, chamber, subject,
  or vote activity. Open any bill to read its summaries, actions, sponsors,
  related bills, and full text.
- **Members & States:** Browse members by state, chamber, or party and review
  their legislative sponsorship and voting history.
- **Topics, Parties & Graph:** Explore BERTopic subject clusters, party
  framing comparisons, and member collaboration/voting networks. If an analysis
  view shows a "Not Built" banner, run the corresponding analytics build from
  the CLI or Admin page.
- **Admin:** Monitor background ingestion and indexing jobs and trigger
  rebuilds.

### Loading data into a fresh installation

A fresh installation starts with an empty search index—starting the app does
not automatically download historical data or train machine-learning models. By
default, `make up` runs the web UI, the FastAPI backend, and one lightweight
indexing/maintenance worker.

When you are ready to load legislative records:
1. Follow the [ingestion guide](documentation/guides/ingestion.md) and prefer
   bulk GovInfo ZIP packages (`scripts/queue_govinfo_bulk.py`) and Voteview CSVs
   (`scripts/ingest_votes.py`) for full Congress backfills, using the
   Congress.gov API for bounded date windows or non-bulk resources.
2. Review the [worker profiles and capacity requirements](documentation/guides/configuration-and-deployment.md#managed-stack-compose)
   to enable the `acquisition` or `analytics` Docker Compose profiles when
   running collection or training jobs.

> **Notes on legislative data:**
> - Bill pages show how much detail has been fetched (`complete`, `partial`, or
>   `unknown`). A bill can be searchable by title and summary even before its
>   full text or all related sub-collections are downloaded.
> - On a bill's **Text** tab, *"Enacted public law text"* or *"Enacted private
>   law text"* indicates verified statute text rather than an earlier bill
>   draft. Linked source PDFs remain available alongside indexed text.

---

## Everyday commands

Run these commands from the repository root:

```bash
make stack-status                         # Show running Docker containers
curl --fail http://127.0.0.1:8000/ready   # Verify API and Elasticsearch readiness
make status                               # Print indexed document counts and job summary
make worker-monitor                       # Show active ingestion progress
make stack-logs                           # Follow container logs (Ctrl+C to exit)
make down                                 # Stop containers while preserving data volumes
make up                                   # Start the default stack
```

To enable the opt-in daily bill refresh scheduler alongside the default stack,
run:

```bash
make up STACK_PROFILES=operations,scheduler
```

See the [refresh policy](documentation/guides/ingestion.md#scope-and-item-fetch-policy)
and [supported operational entry points](documentation/guides/configuration-and-deployment.md#supported-operational-entry-points)
for data collection, analytics training, and maintenance commands.

If startup refuses to launch due to resource limits, run `make stack-capacity`
and see the [configuration guide](documentation/guides/configuration-and-deployment.md).
For troubleshooting failed jobs, restarts, or backups, consult the
[operations runbook](documentation/OPERATIONS_RUNBOOK.md) and the
[analytics retention policy](documentation/guides/analytics.md#6-rebuilds-retention-and-operational-checks).

---

## Learn more

- [Documentation home](documentation/README.md) and
  [published wiki](https://github.com/hbeychaner/usa-congress-monitor/wiki)
- [Architecture overview](documentation/architecture.md) and
  [visual diagrams](documentation/reference/visuals.md)
- [Configuration and deployment](documentation/guides/configuration-and-deployment.md)
  (including [testing and contracts](documentation/guides/configuration-and-deployment.md#testing-and-contracts))
- [Data collection and replay](documentation/guides/ingestion.md)
- [Analytics guide](documentation/guides/analytics.md)
- [Changelog](CHANGELOG.md)
- [Security policy](.github/SECURITY.md)
