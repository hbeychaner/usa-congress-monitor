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
Bill reads include legacy law projections with valid canonical bill identities,
without changing their stored classification or downloading them again.
Exact canonical bill-ID searches use direct identity lookup rather than NLP.
Controlled local replay uses create-only writes; ordinary ingestion still uses
the merge behavior described in the ingestion guide.
Replayed list metadata makes records available for browsing; it does not fetch
missing summaries, relationships or full text.
The coverage goal remains full detail and full text wherever available, including
enrichment of existing records when specific content is missing.
On a bill's Text tab, "Enacted public law text" or "Enacted private law text"
identifies verified law text, not an earlier bill draft. PDF source links remain
available separately; a source link alone does not mean text has been indexed.
Publisher transcriptions can contain OCR errors; consult the linked facsimile.
Historical law downloads are matched to their bill identities before publication.
A PDF marked "partial facsimile" contains only part of the law, even when the
indexed text is complete.
Complete detail retrieval does not guarantee full-text availability.
Collection counts or links alone do not prove detail completeness.
Completeness describes an individual bill, not whether a whole Congress has
been collected.
Reconcile official catalog identities against search before missing-only
recovery; matching collection totals alone do not establish identity coverage.
The reconciled Congress 93-119 roster's 10,452 missing identities have now been
created from retained catalog metadata without changing existing records.
The full acquisition queue has finished: 10,449 records now have complete detail
conditionally published, including 9,026 primary full texts. All 12,956 captured
versions remain retained; the serving record contains one selected primary body.
Exact source/version/API checks pass for every published record, and all 371,366
original document versions are preserved. Three source/detail cases remain unresolved.
Those are two law PDFs above the unchanged download bound and one repeatedly
failing API record. For 487 records, revision ordering is unresolved: a retained
source-listed representative is published without claiming it is the latest.
Acquisition timestamps, including cache replays, do not certify source freshness.
Congress 119 has 19,832 records without document-level source-check timestamps.
Expanded-corpus analytics are accepted: 109,726 inputs, 892 visible topics and
707 Congress/topic perspective results, including 19 stability-passing splits,
with current graph/model lineage and actual API/browser checks.
Broader historical coverage, full recovery acceptance and the genuine 24-hour
observation remain open; this is not release completion.
The latest observation failed after 5,882 seconds when the original worker
was OOM-killed; no failed interval counts toward the required day.
Search normalization now serializes spaCy memory zones and uses one text per
inference microbatch without changing the model or existing text cap.
See [lemmatization and cache ownership](documentation/reference/indexing.md#lemmatization).
The replacement continuous observation began November 6 at 21:03 UTC; it
cannot qualify before the same time on November 7.
Actual existing-service interruption recovered queued indexing in 77 seconds
without changing the original worker allocation or protected records. The
25-index/vector/ledger backup is retained, but full restoration stopped at its
resource guard after two complete indices and part of legislation; it did not
pass. See the [recovery boundaries](documentation/OPERATIONS_RUNBOOK.md#backup-and-actual-recovery-boundaries).
The current model's five files were actually restored and hash-verified.
A later host/container SQLite-view incident was recovered without losing any
protected original jobs, but exceeded 15 minutes. Keep live ledger operations
inside Docker; see the [SQLite operating boundary](documentation/OPERATIONS_RUNBOOK.md#live-sqlite-operating-boundary).
Older Congress.gov text links can encode the Congress in the URL path rather
than the filename; recovery validates the complete identity before downloading.
Historical law recovery also verifies older act headings and page-header
citations, using source-sealed local OCR when a PDF's text layer is damaged.

## Everyday commands

Run these from the repository root:

```bash
make stack-status   # Check running services
curl --fail http://127.0.0.1:8000/ready  # Check API dependency readiness
make stack-logs     # Follow application logs; Ctrl+C stops following
make down           # Stop the stack while preserving stored data
make up             # Start it again
```

Do not run the legacy native `make status` or `make health-check` against the
live Docker-mounted SQLite ledger. Native and container access diverged during
actual operation; full diagnostic scripts also have unqualified memory use for
large ledgers. Use the runbook's Docker-side checks instead.

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
Health warnings about failed jobs describe ingestion history, not automated
test failures. Repairing some bills does not clear a job for an entire scope.

## Learn more

- [Documentation home](documentation/README.md) and
  [published wiki](https://github.com/hbeychaner/usa-congress-monitor/wiki).
- [Configuration and deployment](documentation/guides/configuration-and-deployment.md).
- [Data collection and replay](documentation/guides/ingestion.md).
- [Architecture and visual guides](documentation/reference/visuals.md).
- [Analytics guide](documentation/guides/analytics.md).
- [Development and validation](documentation/guides/configuration-and-deployment.md#testing-and-contracts).
- [Changelog](CHANGELOG.md).
