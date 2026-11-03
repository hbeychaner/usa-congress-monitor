# API and frontend implementation reference

This reference describes the checked-in application, not the upstream Congress.gov API.
Paths below are relative to the repository; endpoint paths are relative to `/api/v1`
unless explicitly marked otherwise. For analytical methods and rebuilds, see the
[analytics guide](../guides/analytics.md).
Exhaustive declarations and source locations are indexed in
[backend](symbols/backend.md), [contracts](symbols/contracts.md),
[frontend](symbols/frontend.md), [graph](symbols/graph.md),
[perspectives](symbols/perspectives.md), and [utils](symbols/utils.md).

## Request path and composition

1. [main.tsx](../../frontend/app/src/main.tsx) mounts React in `StrictMode`, wraps
   the application in the Radix `Theme`, and installs React Router's `BrowserRouter`.
2. [App](../../frontend/app/src/App.tsx) renders `AppShell` around `AppRoutes`.
   [AppShell](../../frontend/app/src/components/AppShell.tsx) owns navigation and
   the API health badge; pages own their feature data fetching.
3. A page calls a feature helper in [src/api](../../frontend/app/src/api).
   Helpers build query strings and delegate to `apiGet<T>` or `apiPost<T>`.
4. [client.ts](../../frontend/app/src/api/client.ts) concatenates
   `VITE_API_BASE_URL` with the supplied path; its fallback is
   `http://localhost:8000`. POST requests have no JSON body.
5. [app.py](../../cdm/backend/app.py) creates FastAPI and applies configured CORS
   origins, allowing credentials and all methods/headers.
6. [api_router](../../cdm/backend/api/router.py) mounts eleven route families
   under `/api/v1`: admin, states, members, search, bills, committees, topics,
   subjects, graph, parties, and votes.
7. [dependencies.py](../../cdm/backend/dependencies.py) defines the typed
   `Annotated[..., Depends(...)]` providers. `get_container()` is process-cached;
   providers return collaborators from [Container](../../cdm/container.py).
8. Services query indexed documents or analytical repositories and construct
   response models from [cdm.contracts.api](../../cdm/contracts/api.py).

Most route functions are synchronous and deliberately small: parameter validation
and dispatch belong there; document joins, ranking, and response construction live
in [backend/services](../../cdm/backend/services). Admin analytics builds submit
durable jobs through the container; a dedicated worker executes them.

### Health and errors

- `GET /health` is outside the versioned router and returns `{"status":"ok"}`.
  It does **not** check Elasticsearch, the database, workers, or analytical freshness.
- `GET /ready` performs a bounded Elasticsearch check with no retries.
  AppShell's API Ready/Not Ready badge follows readiness, not ingestion completeness.
- OpenAPI is exported offline for checked-in TypeScript contract generation;
  frontend startup/build does not fetch a running API.
- Interactive listing bounds are checked before dependency reads. Unsupported
  depth, oversized voted-bill filters, invalid types, and excessive query text
  produce HTTP 422 using FastAPI's standard validation-detail array.
- Known missing entities return HTTP 404. Missing indexes, dependency failures,
  timed-out searches, and failed shards return safe HTTP 503 responses, never
  success-shaped partial results. Unexpected programming errors remain HTTP 500.
- `apiGet` and `apiPost` preserve safe string/validation-array details and status
  in `ApiError`; they do not implement retries or runtime response validation.
- Network and JSON decoding errors reject the promise directly. The generic
  TypeScript cast is compile-time typing, not runtime response validation.
- No authentication dependency is installed on the checked-in admin routes.
  Do not treat the `/admin` prefix or CORS settings as access control.

## Public route families

### Cross-entity search

Source: [search routes](../../cdm/backend/api/routes/search.py) and
[SearchService](../../cdm/backend/services/search_service.py).

| Endpoint | Parameters and behavior |
| --- | --- |
| `GET /search` | Required nonempty `q` (maximum 200 characters); comma-separated `types=member,state,bill`; `limit=20`, range 1–100 **per selected type**. |

`SearchService.search` trims the query and returns no results for whitespace-only
input. Type selections are case-normalized and deduplicated; unknown types return
422 instead of silently broadening the request. An empty selection means all types.

`_state_results` matches substrings against state names/codes from `StateService`.
`search_members` boosts bioguide IDs, state codes, name prefixes, and fuzzy name
fields. `_bill_query` combines ID/number matches, title prefixes, fuzzy textual
fields, and optional lemmatized fields through `try_lemmatize_query`.

Results are grouped state-first, then member, then bill, with `ordering="grouped"`.
There is no final global slice or cross-type relevance score: a limit of 20 can
return 20 members **and** 20 bills. Member/bill groups use relevance followed by
canonical keyword `id` for deterministic ties and narrow source projections.
Failure of any requested dependency rejects the response.

### Interactive browsing window

[QueryReadConfig](../../cdm/config/query_reads.py) supplies one injected policy
for bill/member lists, member activity, and search. Listing responses retain the
true `total` and include `max_result_window`, `max_page`, and `window_limited`.
The default window is **10,000 matches**, not 10,000 rows rendered at once.
Pages contain at most 100 records; `page * limit` must not exceed the window.
`max_page` also respects the actual total and whole pages fitting that window.
With a page size that does not divide 10,000, a trailing incomplete window is
not navigable; `window_limited` still reports hidden matches.

The UI follows server page bounds, displays a refine-filters notice when limited,
and does not leave old rows presented as successful results after a failed read.
Ordering is deterministic for unchanged data; offset browsing is not a snapshot
and does not guarantee unchanged page boundaries while records are updated.
No cursor service, query cache, or new index was introduced.

### Members

Source: [member routes](../../cdm/backend/api/routes/members.py),
[MemberService](../../cdm/backend/services/member_service.py), and
[frontend member helpers](../../frontend/app/src/api/members.ts).

| Endpoint | Purpose and query parameters |
| --- | --- |
| `GET /members` | Filter by `query`, `state`, `chamber`, `party`; `page>=1`; `limit=50`, range 10–100. |
| `GET /members/{bioguide_id}` | Core profile and recent bill activity; topics are fetched separately; explicit missing-member 404. |
| `GET /members/{bioguide_id}/activity` | Merged linked-document activity; comma-separated `types`; `page>=1`; `limit=25`, range 5–100. |
| `GET /members/{bioguide_id}/topics` | Discovered topic weights/trends and CRS subject/policy-area weights. |
| `GET /members/{bioguide_id}/similar` | `signal=collaboration`, also `voting` or `topic`; optional `congress>=1`; `limit=10`, range 1–50. |

`list_members` queries the member read alias with pagination and filters; chamber
short names are expanded to source chamber names. `get_profile` uppercases the ID,
searches canonical/fallback IDs, and picks the richest matching source record.
`_member_detail` and `_expand_terms` adapt stored term shapes to API models.

`list_activity` makes one multi-index query with `from`/`size`, fetching at most
the requested page rather than each source's entire prefix. Supported types are
`bill,amendment`; duplicates are removed and unknown types return 422. Bill
source-type filtering excludes laws; amendment selection uses its read alias.
A runtime date matches the displayed chronology: latest action for bills,
submission for amendments, falling back to update date. Missing dates sort last;
keyword `id` breaks ties. Filter aggregations provide exact per-type counts.
Activity failures remain visible without replacing the available core profile.

`get_summaries` uses `mget` against canonical `member:{bioguide_id}` documents.
Graph endpoints omit neighbors whose canonical summary cannot be loaded.
`GraphService.similar` retrieves precomputed edges, not a live graph rebuild.

### Bills and semantic neighbors

Source: [bill routes](../../cdm/backend/api/routes/bills.py),
[BillService](../../cdm/backend/services/bill_service.py),
[BillVoteIndex](../../cdm/backend/services/bill_vote_index.py), and
[SimilarBillService](../../cdm/backend/services/similar_bill_service.py).

| Endpoint | Purpose and query parameters |
| --- | --- |
| `GET /bills/recent` | `page>=1`, `limit=50` (10–100), optional `query`, `congress` (1–200), `bill_type`, `chamber=House|Senate`, `subject`, and `has_votes=false`. |
| `GET /bills/{bill_id}` | Stored bill details, relationships, and available full text. |
| `GET /bills/{bill_id}/votes` | De-duplicated bill vote summaries across two source families. |
| `GET /bills/{bill_id}/topics` | Latest-model non-outlier assignments, labels, and probabilities. |
| `GET /bills/{bill_id}/similar` | Cached-embedding nearest neighbors; `limit=10`, range 1–50. |

`list_recent` filters `source_type=bill`, sorts by descending `update_date` then
ascending canonical keyword `id`, projects only summary fields, and
attaches vote counts. `bill_type` filters the canonical ID pattern. `_subject_filter`
matches either a nested legislative subject or a policy-area name; `_text_query`
adds optional lemma search. The endpoint remains update-sorted even with text search.

`get` reads the exact trimmed bill ID, verifies `source_type`, sorts actions by
action date, and exposes available relationship arrays and relationship counts.
It does not fetch missing relationships or full text from upstream on demand.

`BillKey.parse` interprets canonical IDs such as `bill:119:hr:138`.
`BillVoteIndex.bill_ids` and `counts` aggregate linked roll calls and House votes
for filtering/count badges. Those aggregate counts are not the same operation as
the vote-detail merger's cross-source de-duplication.
The read-time join remains bounded at **20,000 buckets per vote source**.
Any omitted buckets reject `has_votes` with 422 rather than returning a partial
ID set and misleading total; approximate counts/incomplete searches return 503.
Selecting Congress narrows the aggregation; other bill filters do not narrow it
before the join. A still-oversized Congress is unsupported with this filter.

`SimilarBillService.similar` asks its injected embedding store for neighbors,
loads bill title/Congress metadata with `mget`, and returns similarity scores.
No request-time transformer encoding is performed by this service.

#### Exact bill-detail request sequence

`BillDetailPage` → handwritten `fetchBill(billId)` → handwritten
`apiGet<BillDetailResponse>` → `GET /api/v1/bills/{bill_id}` →
`bills.bill_detail` → `BillServiceDep` / `get_bill_service` →
cached `get_container()` → `Container.bill_service` →
`BillService(elastic_client, vote_index, query_reads).get(bill_id)`.
The method strips surrounding whitespace and calls client `get` on
`read_alias("bill")` (`congress-legislation-read`) with the exact ID. It maps `_source` into
`BillDetailResponse`; it does not hydrate upstream or join another index here.
Missing documents and non-bill records raise `EntityNotFoundError` and become 404;
a missing index is a dependency failure and becomes 503.

Listing takes the same provider path to `BillService.list_recent`, which searches
`read_alias("bill")` and calls `BillVoteIndex` on `read_alias("rollcall")`
(`congress-rollcall-read`) and `read_alias("house_vote")`
(`congress-house-vote-read`) for counts/filtering. These are aliases, not guaranteed
physical index targets. The bill page's additional
`fetchBillVotes` and `fetchBillTopics` calls are separate HTTP requests dispatched
to `VoteServiceDep` and `TopicServiceDep`, not joins inside `BillService.get`.

### Votes

Source: [vote routes](../../cdm/backend/api/routes/votes.py),
[VoteService](../../cdm/backend/services/vote_service.py), and
[VoteBreakdownService](../../cdm/backend/services/vote_breakdown_service.py).

| Endpoint | Behavior |
| --- | --- |
| `GET /votes/{vote_id}/breakdown` | Read a `rollcall` document and group members by party and position; missing roll call gives 404. |

`VoteService.for_bill` queries the `rollcall` and `house_vote` aliases, with a
default per-source limit of 100. It de-duplicates on chamber, Congress, session,
and roll number. For House roll calls it uses `clerk_roll_number`, not Voteview's
roll number. Congress.gov House records win ties while retaining the matched
`rollcall_id`, allowing the browser to request an individual-member breakdown.

Breakdowns use `yea_ids`, `nay_ids`, `present_ids`, and `not_voting_ids`.
`_members` joins display names, states, and party labels from the member index.
Unmatched people remain visible under `other` with the ID as their name.
This is not a historical party-affiliation reconstruction.

### States and districts

Source: [state routes](../../cdm/backend/api/routes/states.py) and
[StateService](../../cdm/backend/services/state_service.py).

| Endpoint | Behavior |
| --- | --- |
| `GET /states` | States represented in loaded member records, mapped through the local state-name table. |
| `GET /states/{state_code}/timeline` | House/Senate term groups; optional `from_congress` and `to_congress`. |
| `GET /states/{state_code}/districts` | GeoJSON FeatureCollection from district documents. |

`get_timeline` derives Congress numbers from term years, de-duplicates terms, and
groups members by Congress. Open-ended terms use the current UTC year; displayed
party labels come from the member record. This is a year-based approximation,
not an exact service-date or district-boundary history.

`_member_records` loads at most 10,000 documents. `_fetch_districts` loads up to
100 features for a state; `get_districts` caches the result in the service instance.
The districts response is a dictionary rather than a dedicated Pydantic response
model. Unknown state codes do not have a dedicated 404 branch.

### Committees

Source: [committee route](../../cdm/backend/api/routes/committees.py) and
[CommitteeService](../../cdm/backend/services/committee_service.py).

`GET /committees/{system_code}` accepts `page>=1` and `limit=50` (10–100).
`detail` queries nested
committee/subcommittee entries on **bills**, then `_entry` extracts matching
activities, names, chamber, and committee type. It is not a comprehensive committee
directory, membership service, or meeting/report search. With no matches the
response can use the supplied code as its name and contain an empty bill list.

### Topics, metasubjects, and CRS subjects

Source: [topic routes](../../cdm/backend/api/routes/topics.py),
[subject routes](../../cdm/backend/api/routes/subjects.py),
[TopicService](../../cdm/backend/services/topic_service.py), and
[SubjectService](../../cdm/backend/services/subject_service.py).

| Endpoint | Behavior |
| --- | --- |
| `GET /topics` | Latest-model non-outlier topic summaries, largest first. |
| `GET /topics/trends` | Largest topics' saved time series; `size=8`, clamped to 1–25. |
| `GET /topics/metasubjects` | Broad groups in the latest model. |
| `GET /topics/metasubjects/trends` | Saved quarterly group counts. |
| `GET /topics/metasubjects/{metasubject_id}` | Group, constituent topics, trend, and related groups; explicit 404. |
| `GET /topics/{topic_id}` | Topic, related topics, trend, highest-probability bills; `bills=20`, clamped to 1–200; explicit 404. |
| `GET /subjects` | CRS legislative-subject/policy-area aggregations; optional `congress` (1–200); `size=100` (10–500). |
| `GET /subjects/policy-area-trends` | Annual policy-area counts; `size=10` (1–32); optional `start_year` (1900–2100). |

`latest_model_version` selects the newest stored topic by `trained_at`.
`topic_summaries` prefers stored labels, then de-duplicated keywords, then a name
fallback. `related_topics` and related metasubjects use centroid cosine similarity.
`get_member_topics` joins up to 5,000 sponsored/cosponsored bills to assignments
and produces quarterly counts; CRS aggregates remain a separate source of labels.

Missing analysis indexes/models produce empty list responses or `None` for detail.
`TopicService._search` catches `NotFoundError`, not every connection failure.
CRS subjects are upstream annotations; discovered topics and metasubjects are
derived analytical output. They must not be presented as interchangeable taxonomies.

### Graph and party analysis

Source: [graph routes](../../cdm/backend/api/routes/graph.py),
[party routes](../../cdm/backend/api/routes/parties.py), and the
[analytics guide](../guides/analytics.md).

| Endpoint | Behavior |
| --- | --- |
| `GET /graph/neighborhood` | Repeated `member` query parameters, 1–5 seeds; blended member graph with optional topic/subject/metasubject overlays. |
| `GET /graph/topic-neighborhood` | Required `kind=topic|metasubject|subject` and `key`; sponsor-ranked members around a subject center. |
| `GET /parties` | Optional `congress`; otherwise choose newest available perspective Congress; party rankings and bilateral topics. |
| `GET /parties/topics/{topic_id}` | Required `congress`; persisted topic contrast and gated perspectives; explicit missing-analysis 404. |

Both graph routes accept collaboration/voting/topic weights (each 0–1; defaults
1/0.6/0.3), optional Congress, repeated party groups, chamber, and `limit=15` (1–50).
The member route also accepts `include_topics`, `include_subjects`, and
`include_metasubjects`, with respective per-member caps of 1–8 (default 3).

[NeighborhoodService](../../cdm/backend/services/neighborhood_service.py) scales,
blends, filters, and joins stored signal edges. Its limit is per seed, not a global
maximum node count. Seeds with loaded summaries remain even if neighbor filters
exclude their party/chamber. [TopicNeighborhoodService](../../cdm/backend/services/topic_neighborhood_service.py)
selects sponsors with at least two matching bills, then attaches member links.
[PartyService](../../cdm/backend/services/party_service.py) reads saved analyses;
failed-quality cluster splits are hidden while other contrast evidence remains.

## Administrative routes

Source: [admin routes](../../cdm/backend/api/routes/admin.py) and
[AdminService](../../cdm/backend/services/admin_service.py).

| Endpoint | Method | Responsibility |
| --- | --- | --- |
| `/admin/topic-training` | GET / POST | Read status / launch topic-training script. |
| `/admin/member-graph` | GET / POST | Read status / launch graph rebuild script. |
| `/admin/perspectives` | GET / POST | Read status / launch all-topic current-Congress perspective rebuild. |
| `/admin/ingest-progress` | GET | Ledger-backed active-job progress, heartbeat activity, rates, ETA, and backfill totals. |
| `/admin/ingest-snapshot` | GET | GovInfo/job/staging readiness snapshot, currently specific to Congress 118. |
| `/admin/system-status` | GET | Search connectivity, selected alias document counts, job counts, generation timestamp. |

POST starts are not completed-build acknowledgments: inspect returned state,
`started`, later status, and logs. File-based PID checks prevent a second launch
when the recorded process is still alive; this is not a distributed lock.
The snapshot's `ready_for_cutover` is a code-defined heuristic, not data validation.
System status enumerates a fixed subset of aliases, not every index family.

## Actual browser routes and page responsibilities

Source of truth: [AppRoutes](../../frontend/app/src/routing/routes.tsx).

| Browser route | Page and implementation responsibility |
| --- | --- |
| `/` | [HomePage](../../frontend/app/src/pages/HomePage.tsx): landing/navigation content. |
| `/admin/ingest` | [AdminIngestPage](../../frontend/app/src/pages/AdminIngestPage.tsx): progress, infrastructure status, topic/graph/perspective build cards. |
| `/states` | [StatesPage](../../frontend/app/src/pages/StatesPage.tsx): state listing/map entry point. |
| `/states/:stateCode` | [StateDetailPage](../../frontend/app/src/pages/StateDetailPage.tsx): member timelines and Congress range. |
| `/members` | [MemberSearchPage](../../frontend/app/src/pages/MemberSearchPage.tsx): filtered, paginated member listing. |
| `/members/:bioguideId` | [MemberProfilePage](../../frontend/app/src/pages/MemberProfilePage.tsx): profile, activity, topics, subjects, graph entry. |
| `/graph` | [MemberGraphPage](../../frontend/app/src/pages/MemberGraphPage.tsx): member/topic-centered graph exploration. |
| `/bills` | [BillsPage](../../frontend/app/src/pages/BillsPage.tsx): filtered recent bills, vote-only selection, pagination. |
| `/bills/:billId` | [BillDetailPage](../../frontend/app/src/pages/BillDetailPage.tsx): bill relationships/text, votes, topics, similar bills. |
| `/committees/:systemCode` | [CommitteeDetailPage](../../frontend/app/src/pages/CommitteeDetailPage.tsx): matching bill referral activities. |
| `/topics` | [TopicsPage](../../frontend/app/src/pages/TopicsPage.tsx): topics, groups, CRS aggregates, and trend charts. |
| `/topics/:topicId` | [TopicDetailPage](../../frontend/app/src/pages/TopicDetailPage.tsx): trend, representative bills, related topics. |
| `/parties` | [PartiesPage](../../frontend/app/src/pages/PartiesPage.tsx): Congress-selected rankings, bilateral evidence, selected-topic contrast. |
| `/search` | [SearchPage](../../frontend/app/src/pages/SearchPage.tsx): cross-entity query and result navigation. |

Unknown browser paths redirect to `/` with replacement. There are no separate
browser routes for a vote detail, subject detail, metasubject detail, committee
directory, or party-topic detail; those features are embedded in existing pages.

### Shareable browse/search state

Applied state is the URL, not a second local filter store. Draft edits are applied
on form submission; changing filters resets listing pages to 1. Paging keeps the
applied filters. Refresh, direct/copied links, and browser back/forward restore
both controls and results.

| Page | URL parameters |
| --- | --- |
| `/bills` | `query`, `congress`, `chamber`, `bill_type`, `subject`, `has_votes`, `page` |
| `/members` | `query`, `state`, `chamber`, `party`, `page` |
| `/search` | `q`, comma-separated `types`, `limit` (per type) |

For example, `/bills?subject=Health&congress=119&has_votes=true&page=2`
retains the existing subject-link behavior while restoring the other filters.
`/search?q=health&types=member,bill&limit=100` restores both selected groups.
Listing page size remains 50. Default page 1, all search types, search limit 20,
and inactive/empty filters are omitted from generated URLs.

[queryState.ts](../../frontend/app/src/shared/queryState.ts) owns the typed
codecs and explicit URL-boundary errors; [useQueryForm](../../frontend/app/src/hooks/useQueryForm.ts)
owns draft synchronization and history updates. Invalid numeric values, closed
selections, or repeated supported parameters display an alert and block the read,
rather than silently querying fallback filters. Correct the URL or explicitly
submit the corrected controls. Free-text validation and supported server depth
remain API responsibilities. Reapplying the same canonical URL retries the read
without inserting a duplicate history entry.

[useRead](../../frontend/app/src/hooks/useRead.ts) is the existing analytics read
hook generalized by name and with an idle (`null`) request. Lists and search now
share its request-identity guard: new requests immediately hide previous data;
late successes/failures cannot overwrite the active state. A query-less search
is idle, not an empty result or a loading request. Failed reads show an error,
not zero-result success. Existing optional-analysis callers keep their behavior.
No query-cache library or global state store was added.

Native forms, labeled inputs, pressed-state type buttons, and Radix selectors
remain keyboard operable. Navigation wraps on narrow screens rather than
expanding the page width; result tables retain their internal horizontal scroll.
The member party selector keeps the URL-restored historical party in its option
list while drafts change, avoiding a native-select reset during history
restoration. Standard parties, including Independent, appear only once.

`MemberGraphPage` persists member seeds in repeated `member` URL parameters.
Topic mode uses `view=topics`, `kind`, and `key`; weights and display filters are
local React state. [MemberGraphView](../../frontend/app/src/components/MemberGraphView.tsx)
constructs an undirected Graphology graph, runs ForceAtlas2 layout, optionally
colors Louvain communities, and renders/interacts through Sigma. Layout/community
coloring are browser-side visualization calculations, not persisted analytical truth.

Bill-detail vote/topic requests can fail without replacing the main bill response.
Member-profile topics/activity and TopicsPage's auxiliary subject/trend requests
also have independent fallbacks. Optional analysis being absent is therefore not
proof that the main page or the backend has no data. Admin progress polls every
10 seconds and system status every 60 seconds; build cards poll their own status.

## Contracts, generation, and serving

- [contracts/api.py](../../cdm/contracts/api.py) holds Pydantic families such as
  `MemberProfileResponse`, `BillDetailResponse`, `NeighborhoodResponse`,
  `TopicDetailResponse`, `VoteBreakdownResponse`, and administrative snapshots.
    Graph-build models additionally live in [jobs/analytics.py](../../cdm/jobs/analytics.py);
  party analysis embeds models from [perspectives/models.py](../../cdm/perspectives/models.py).
- [package.json](../../frontend/app/package.json) runs pinned `@hey-api/openapi-ts` in
  `contracts:generate` through the offline [generator](../../frontend/app/scripts/generate-contracts.mjs),
  writing [shared/contracts/api.ts](../../frontend/app/src/shared/contracts/api.ts).
- Run `npm run contracts:generate` from `frontend/app` after changing contracts;
  `npm run contracts:check` checks freshness without writing. Export uses Python,
  not a running API or `OPENAPI_URL`. Browser-time `VITE_API_BASE_URL` remains the
  API origin for actual application reads.
- Generated response aliases are the shared browser contract. These compile-time
  types do not provide runtime JSON validation. Helpers retain their public alias
  names and use generated named types (`Contracts.BillsResponse`), not the old
  generator's `components['schemas']` map. Operation request/response types are
  generated too; compile-time tests verify query enums and numeric parameters.
- Generation enables only the TypeScript plugin: no SDK, HTTP client, or runtime
  enums. It generates into an owned temporary directory before comparing or
  writing the single checked-in module, and always cleans up. Check mode never
  rewrites stale output; malformed input/exporter failures exit unsuccessfully.
  Required defaults, nullable fields, read-only fields, references, and closed
  enums are covered by generator regressions. Repetitive generated comments are
  disabled; field descriptions remain in the OpenAPI export and source models.
- `npm run build` runs `tsc -b` and `vite build`. Normal frontend startup/build is
  Node-only and does not regenerate or fetch a schema.
- [vite.config.ts](../../frontend/app/vite.config.ts) serves development on port
  5173 and defines no API proxy. Browser requests use the configured API origin.
- [nginx.conf](../../frontend/app/nginx.conf) serves production static assets on
  8080, gives assets immutable caching, and falls back to `index.html` for SPA
  routes. It does not configure a reverse proxy for `/api`.

### Browser acceptance gate

From `frontend/app` using Node 22.18+, after `npm ci`:

```bash
npx playwright install chromium
npm run audit
npm run test:browser
# Optional repeat check; retries remain disabled:
npm run test:browser -- --repeat-each=2
```

The [configuration](../../frontend/app/playwright.config.ts) type-checks through
the npm command, builds production assets, and owns a strict-port loopback preview
on port 4175. An existing listener is not reused. Tests run Chromium at 1280x900
and 320x740 with two workers, no retries, and service workers blocked.

[Typed fixtures](../../frontend/app/tests/browser/fixtures.ts) use generated
response schemas. Only declared API responses and same-origin application
documents/assets are allowed. Unknown API calls, same-origin fetch fallthrough,
and external requests are aborted and fail the test; dedicated
[guard regressions](../../frontend/app/tests/browser/network-guard.spec.ts)
verify that failure path. Uncaught page errors also fail journeys.

The [journeys](../../frontend/app/tests/browser/journeys.spec.ts) cover:

- state -> member -> bill links, and core records surviving optional-analysis
  and activity outages; the map journey also renders synthetic geometry and
  opens its delegation, fulfilling the map asset locally rather than using a CDN;
- direct query URLs, reload, back/forward, historical parties, custom search
  limits, page resets, and same-URL retries without duplicate history;
- real keyboard form/selector/checkbox/paging actions and document-width bounds;
- idle versus empty search, explicit 422/503 failures without empty/partial
  success, and server-advertised browsing limits;
- held responses released after a newer read or navigation to idle, proving
  late success/failure isolation without fixed sleeps.

The existing [contracts workflow](../../.github/workflows/contracts.yml) installs
Chromium with Linux dependencies and runs this gate after unit/contract checks.
The browser command includes the production build, replacing the separate CI
build step rather than building twice. Failures retain traces/screenshots and
an HTML report in ignored `test-results`/`playwright-report` directories; CI
uploads them for seven days. Inspect a downloaded trace with
`npx playwright show-trace <trace.zip>`.

These are browser-contract fixtures, not a live backend, search-index, image,
queue-recovery, or deployment acceptance test. Those controlled integration and
release gates are separate checks.
The same workflow now runs a separate
[controlled pipeline gate](../OPERATIONS_RUNBOOK.md#controlled-pipeline-acceptance)
against disposable Redis/Elasticsearch, including the real-index query-budget
regressions. Browser fixtures do not substitute for those checks or the remaining
release/restore gates.

### Dependency and editor configuration

The root [TypeScript solution](../../frontend/app/tsconfig.json) references the
app, Node/Vite, and browser projects. This makes VS Code discover
[playwright.config.ts](../../frontend/app/playwright.config.ts) through
[tsconfig.browser.json](../../frontend/app/tsconfig.browser.json), including its
Node types; adding another `@types/node` installation is not the fix.

CI audits **all** dependencies, including development tooling, with
`npm run audit` (`npm audit --audit-level=low`). There are no audit suppressions
or dependency-source patches. Node 22 is used in CI and both frontend Docker
builds, and both images install the committed lockfile with `npm ci`.

Two explicit overrides bridge upstream dependency ranges:

- `d3-color` 3.1.0 replaces the vulnerable v2 in the map's D3 dependency chain.
  Its ESM color/interpolation behavior is tested through that actual chain and
  the production map bundle.
- The new generator's `@hey-api/json-schema-ref-parser` uses patched `js-yaml`
  4.3.2, staying within YAML's existing major API.

Keep the generator pinned to its exact version because its pre-1.0 releases can
change output. Reassess overrides on upgrades and remove them when upstream
ranges resolve patched compatible versions without them. The generator migration
removes the old Redocly/minimatch/brace-expansion chain rather than forcing an
incompatible minimatch API into it.

When diagnosing a page, trace its feature helper, the concrete route, the
dependency provider, and service method before interpreting an empty panel.
Analytical freshness, source coverage, and build success are separate questions.
