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

The managed stack keeps job history in a Docker volume. Existing installations
must follow the [ledger migration and recovery guidance](documentation/OPERATIONS_RUNBOOK.md#live-sqlite-operating-boundary)
before switching from the older checkout-mounted database.

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
The full acquisition queue has finished: 10,451 records now have complete detail
conditionally published, including 9,028 primary full texts. The two previously
oversized laws are recovered. One additional resolution now serves its available
full text and all 99 original cosponsors from official GovInfo metadata, including
the correctly identified Lincoln Chafee. Its failing Congress API collection
remains honestly marked partial; later sponsorship episodes are not inferred.
All 12,969 captured versions remain retained; the serving record contains one
selected primary body. Exact source/version/API checks preserve all 371,366
original document versions and all 10,449 previously accepted enrichments.
For 487 records, revision ordering is unresolved: a retained
source-listed representative is published without claiming it is the latest.
Acquisition timestamps, including cache replays, do not certify source freshness.
See the [current coverage and freshness boundaries](documentation/OPERATIONS_RUNBOOK.md#current-operating-posture)
for the verified current-Congress catch-up; acquisition is not whole-field
freshness certification.
Expanded-corpus analytics are accepted: 109,726 inputs, 892 visible topics and
707 Congress/topic perspective results, including 19 stability-passing splits,
with current graph/model lineage and actual API/browser checks.
The fixed [implementation closeout](documentation/IMPLEMENTATION_PLAN.md#fixed-local-release-closeout)
is finished with explicit content/freshness and full-recovery blockers, not a
complete historical-data or disaster-recovery certification.
The genuine uninterrupted observation **passed** from **2026-11-07 01:54:45 UTC**
to **2026-11-08 01:54:46 UTC**: **86,400.149 seconds**, **432,000 offered and
completed reads**, **zero read failures**, and **p95 0.343 seconds**, below the
2-second objective. All **1,440 timed indexing jobs/28,800 records** passed;
the 480 stress and two warm jobs are separate from the qualifying day.
All **1,922 jobs, exact retained archives and zero-pending acknowledgements**
are reconciled, all **628,082 original ledger rows** and **371,366 original
document versions** are unchanged, and the accepted enrichment/model/graph/
perspective data still pass exact readback and current HTTP contracts.
Only the owned test index and acknowledged test streams were retired.
The original worker had no restart/OOM, and all **4,319 resource samples**
preserved the original floors and allocations.

The indexing worker shares its warmed CPU NLP model and frozen parent heap
across prefork children while continuing GC for new task objects.
Its operational composition excludes unrelated analytics imports; analytics
implementations register before fork only for analytics-queue consumers,
preserving their original routing/name/limits. Search normalization uses
serialized memory zones without changing model identity or the text cap.
Operational Compose services now also use the `api` image target; only the
analytics worker installs the `analysis` dependency group. An independently
verified operational image is **2.03 GB instead of 11.30 GB**, about **82% smaller**,
and runs task imports and NLP without Torch/NVIDIA dependencies. Existing
containers require an explicit rebuild/recreation to pick up image changes.
See [lemmatization and cache ownership](documentation/reference/indexing.md#lemmatization).
Failed attempts remain retained and contribute no qualifying time.
Actual existing-service interruption recovered queued indexing in 77 seconds
without changing the original worker allocation or protected records. The
25-index/vector/ledger backup is retained. Every index's contents, all 3,244,277
documents/vectors and the closed ledger have now been restored and exactly
verified across preserved 20-index and five-index phases. This does not pass
the 15-minute recovery objective or certify full-system/off-host restoration.
See the [recovery boundaries](documentation/OPERATIONS_RUNBOOK.md#backup-and-actual-recovery-boundaries).
A private dated Google Drive snapshot now protects **25 current indices /
3,622,617 documents**, published models and retained public source archives.
All **170 payload files / 5,026,339,543 bytes** passed actual cloud-download
SHA-256 checks; a bounded restore exactly verified **936 documents**, including
250 nonempty vectors. All five model files, 1,531,866 logical source records,
49,249 raw source files and 112 official PDFs were downloaded and read.
See the [dated data-only backup procedure](documentation/OPERATIONS_RUNBOOK.md#independent-dated-data-only-backups)
for the verified scope, exclusions and recovery steps. This is independent
data storage with a local restore check, not full-system or separate-host failover.
For a private external-drive backup of operational state, see the
[portable local backup guidance](documentation/OPERATIONS_RUNBOOK.md#portable-local-operational-backup).
The current model's five files were actually restored and hash-verified.
A later host/container SQLite-view incident was recovered without losing any
protected original jobs, but exceeded 15 minutes. Keep live ledger operations
inside Docker; see the [SQLite operating boundary](documentation/OPERATIONS_RUNBOOK.md#live-sqlite-operating-boundary).
Older Congress.gov text links can encode the Congress in the URL path rather
than the filename; recovery validates the complete identity before downloading.
Historical law recovery also verifies older act headings and page-header
citations, using source-sealed local OCR when a PDF's text layer is damaged.

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

Frontend dependency audits remain enforced. The pinned glob-matcher remediation
and bounded regression checks are documented under
[testing and contracts](documentation/guides/configuration-and-deployment.md#testing-and-contracts).

## Learn more

- [Documentation home](documentation/README.md) and
  [published wiki](https://github.com/hbeychaner/usa-congress-monitor/wiki).
- [Configuration and deployment](documentation/guides/configuration-and-deployment.md).
- [Data collection and replay](documentation/guides/ingestion.md).
- [Architecture and visual guides](documentation/reference/visuals.md).
- [Analytics guide](documentation/guides/analytics.md).
- [Development and validation](documentation/guides/configuration-and-deployment.md#testing-and-contracts).
- [Changelog](CHANGELOG.md).
