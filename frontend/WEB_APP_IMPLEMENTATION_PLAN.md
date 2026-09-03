# Congress Tracker Web App Implementation Plan

## Objective
Build a scaffolded web application where users can:
- Browse US states.
- Open a state page and view linked representative timelines split by chamber (House vs Senate) by Congress.
- Open member profile pages.
- Prepare for downstream features: recent bill activity and NLP-driven topic association.

## Product User Stories

These stories define the user jobs the frontend must support. They are grouped
by the page where the user takes action, not by backend implementation order.

### Cross-Application Stories

- As an analyst, I want every visible count, label, and date to identify its
  Congress, time range, and source context so that I can interpret it correctly.
- As a voter, I want clear paths from a state to its delegation, from a member
  to their legislation, and from a bill to its sponsors so that I can follow a
  question across records.
- As a researcher, I want to distinguish current data, historical data, and
  unavailable data so that an empty result is not mistaken for zero activity.
- As a data scientist, I want stable URLs, typed filters, pagination, and
  reproducible query parameters so that I can cite and repeat an investigation.
- As any user, I want loading, empty, error, and stale-data states to be
  explicit so that the interface never presents placeholders as facts.

### Home / Orientation

- As a new user, I want to understand the available paths through states,
  members, bills, topics, and search so that I can choose the right starting
  point.
- As a returning analyst, I want a prominent global search and links to current
  congressional data so that I can resume an investigation quickly.

### States Directory (`/states`)

- As an analyst and voter, I want to browse all states and territories by name
  and abbreviation so that I can find a jurisdiction quickly.
- As an analyst, I want the map and directory to use real state data rather than
  fabricated counts so that previews are trustworthy.
- As a voter, I want to select a state from either the map or a compact list so
  that the interaction works with a mouse, keyboard, touch device, or screen
  reader.
- As an analyst, I want to see a concise current delegation summary on state
  hover or selection so that I can compare jurisdictions before opening one.

### State Detail (`/states/:stateCode`)

- As an analyst and voter, I want to know who represents my state in the House
  and Senate for a selected Congress so that I can identify my representatives.
- As a voter, I want at-large and district-based House seats to be labeled so
  that I understand how my state is represented.
- As an analyst, I want to move across Congresses and filter a date range so
  that I can study delegation changes over time.
- As an analyst, I want to open a member directly from a timeline row so that I
  can continue from a jurisdiction question to a person-level investigation.
- As a researcher, I want the page to explain missing seats or missing terms so
  that incomplete source data is distinguishable from no representation.

### Member Directory (`/members`)

- As an analyst and voter, I want to search members by name, state, district,
  party, chamber, or Bioguide ID so that I can find a person even when I do not
  know their exact name.
- As a data scientist, I want filterable, paginated member results with stable
  sorting so that thousands of records remain usable and comparable.
- As a voter, I want each result to show current state, chamber, district, and
  party so that I can identify the correct member before opening the profile.

### Member Profile (`/members/:bioguideId`)

- As an analyst and voter, I want a canonical profile with name, party, state,
  chamber, district, current term, and Bioguide ID so that I can verify identity.
- As an analyst, I want to see a member's complete chamber and state history so
  that I can understand career progression and incumbency changes.
- As an analyst and voter, I want to know what legislation the member sponsors,
  introduces, co-sponsors, supports, and votes for so that I can evaluate their
  record.
- As an analyst, I want activity grouped by type, Congress, and time period so
  that aggregate patterns are visible before I inspect individual bills.
- As a data scientist, I want every aggregate to link to its underlying bill or
  vote records so that I can audit the calculation.
- As a data scientist, I want a topic distribution, word cloud, and tag cloud
  with representative phrases and source bills so that issue concentration is
  visible at a glance and explainable on inspection.

### Bills Directory (`/bills`)

- As an analyst, I want a compact, server-side paginated table of bills so that
  thousands of records do not become an unscannable card grid.
- As an analyst, I want to filter bills by Congress, chamber, type, date, policy
  area, sponsor, and status so that I can isolate a meaningful working set.
- As a researcher, I want full-text search across bill title, identifier,
  sponsor, policy area, and subjects so that I can find relevant legislation by
  concept as well as exact ID.
- As a data scientist, I want sortable columns and URL-addressable filters so
  that result sets can be compared, shared, and reproduced.
- As any user, I want result counts, active-filter visibility, and explicit empty
  states so that I know what the table does and does not contain.

### Bill Detail (`/bills/:billId`)

- As an analyst, I want the bill identity, Congress, chamber, dates, status, and
  latest action together so that I can establish the record's context quickly.
- As an analyst and voter, I want sponsors, cosponsors, committees, summaries,
  subjects, amendments, votes, laws, and text versions linked or counted so that
  I can follow the bill's legislative history.
- As a researcher, I want individual actions and source dates shown in order so
  that I can reconstruct what happened and when.
- As a data scientist, I want raw-source provenance and stable record links so
  that I can validate derived summaries.

### Global Search (`/search`)

- As any user, I want one search box across members, states, and bills so that I
  can begin with the question I have rather than the data model I know.
- As an analyst, I want to restrict search to one or more record types so that
  results stay focused.
- As a researcher, I want result type, title, subtitle, relevance context, and
  direct links so that I can triage results efficiently.
- As a data scientist, I want the query, selected types, limit, and result count
  reflected in the interface and URL so that searches are reproducible.

### Topics Directory and Detail (`/topics`, `/topics/:topicLabel`)

- As a data scientist, I want to see the most prevalent topics across members
  and bills so that I can identify issue areas worth investigating.
- As an analyst, I want topic size, confidence, trend, and coverage metadata so
  that I can distinguish a strong signal from a sparse or uncertain one.
- As a data scientist, I want a topic detail view with representative phrases,
  tagged members, supporting bills, and provenance so that topic assignments are
  explainable rather than opaque labels.
- As an analyst, I want to pivot from a topic to a member, bill, state, or
  Congress so that I can compare how an issue appears across the record.

### Ingest Administration (`/admin/ingest`)

- As an operator, I want to see ingest job status, stage, progress, failures,
  and last update time so that I can tell whether user-facing data is current.
- As an operator, I want links from an ingest failure to its resource and scope
  so that I can diagnose incomplete pages without searching logs blindly.
- As an operator, I want retry and recovery actions to be explicit and
  idempotent so that an operational action cannot create duplicate records.

## Product Acceptance Principles

- No fabricated names, counts, confidence values, or activity may appear in a
  production page. Fixtures belong in tests and are visibly labeled in the
  style guide only.
- Aggregate views must provide a path to the records behind the aggregate.
- Large collections use server-side filtering, sorting, and pagination; the
  browser must not load an entire resource to render a directory.
- Every page has designed loading, empty, error, and unavailable-data states.
- Filters that materially change a result set should be encoded in the URL.
- All data displays must remain usable at desktop and mobile widths and support
  keyboard navigation and semantic labels.

This plan is implementation-focused and checkable so we can execute it incrementally.

## Technology Decision
Chosen stack: React frontend + FastAPI backend.

Why this stack:
- React is fast to scaffold and easy to iterate for navigation-heavy UIs.
- FastAPI fits your Python data pipeline ecosystem and keeps data logic server-side.
- Backend-first architecture prevents data shaping and heavy computation from leaking into the frontend.

## UI Library Decision Matrix (Free and Open-Source Only)

All candidates below are verified free/open-source (MIT) with public docs and examples.

| Option | Best fit for this project | Tradeoffs | Docs | Examples | License |
|---|---|---|---|---|---|
| Mantine | Fast scaffold with strong app-shell/navigation primitives and modern defaults. | Smaller ecosystem than MUI, but broad core coverage. | https://mantine.dev/getting-started/ | https://mantine.dev/app-shell/?e=BasicAppShell | https://github.com/mantinedev/mantine/blob/master/LICENSE |
| MUI Core | Broadest component ecosystem, battle-tested for data-heavy pages and complex forms/nav. | Must avoid paid MUI X Pro/Premium features to stay strictly free. | https://mui.com/material-ui/getting-started/ | https://mui.com/material-ui/getting-started/templates/ | https://github.com/mui/material-ui/blob/master/LICENSE |
| Chakra UI | Accessibility-focused and straightforward component APIs for rapid UI composition. | Runtime styling model may be heavier than utility-first approaches. | https://chakra-ui.com/docs/get-started/installation | https://chakra-ui.com/docs/components/concepts/overview | https://github.com/chakra-ui/chakra-ui/blob/main/LICENSE |
| Ant Design | Enterprise-style data views, tables, forms, and dashboard patterns. | More opinionated visual style; can feel less custom by default. | https://ant.design/docs/react/introduce | https://ant.design/components/overview/ | https://github.com/ant-design/ant-design/blob/master/LICENSE |
| shadcn/ui + Radix | Maximum control and ownership of component code in-repo; ideal for custom brand direction. | More setup/design effort than batteries-included libraries. | https://ui.shadcn.com/docs and https://www.radix-ui.com/primitives/docs/overview/introduction | https://ui.shadcn.com/docs/components and https://www.radix-ui.com/primitives/docs/components/navigation-menu | https://github.com/shadcn-ui/ui/blob/main/LICENSE.md and https://github.com/radix-ui/primitives/blob/main/LICENSE |

### Recommendation for Initial Scaffold

- Selected: shadcn/ui + Radix Primitives (locked).
- Why selected: we prioritize long-term design control and accessibility, and we are not in a rush.
- Delivery approach: use shadcn/ui component building blocks to keep short-term implementation polished and functional while preserving Radix-level composability.

### Selection Gate Before Phase 0 Build

- [x] Pick one UI library from the matrix above and lock it before generating frontend scaffold code.
- [x] Locked choice: shadcn/ui + Radix Primitives.

### Radix Delivery Strategy (Nice and Functional Short-Term)

1. Use shadcn/ui defaults for immediate visual quality (buttons, cards, nav, dialogs, inputs).
2. Build page shell with Radix-aware navigation primitives and consistent spacing/typography tokens.
3. Keep all data fetching and shaping in backend endpoints; frontend only renders typed responses.
4. Implement minimum viable interactions first: state selection, timeline navigation, member profile navigation.
5. Delay advanced visual customization until core routes and API wiring are stable.

## Architecture Principle
All data work is backend-owned.

Frontend responsibilities:
- Route handling and rendering.
- Calling backend endpoints.
- Local UI state only (filters, pagination UI, loading states).
- Import generated shared API contract types from frontend/app/src/shared/contracts/api.ts only.

Backend responsibilities:
- Query shaping and joins.
- Timeline assembly by chamber and Congress.
- Search ranking and filtering.
- Bill activity aggregation.
- NLP/topic inference and caching.
- Define API contract models in one shared module and expose them via OpenAPI.

## Contract Source Of Truth (Required)

- Canonical model definitions live in cdm/contracts/api.py.
- Backend routes and services import from cdm/contracts/api.py for response models.
- Frontend imports model types only from frontend/app/src/shared/contracts/api.ts.
- frontend/app/src/shared/contracts/api.ts is generated from backend OpenAPI using npm run contracts:generate.
- Contract generation is enforced in frontend predev and prebuild scripts.
- Container stack provides OPENAPI_URL=http://backend:8000/openapi.json so generation works in Docker by default.

## Visual Guide
Architecture diagram: [frontend/diagrams/system-architecture.mmd](frontend/diagrams/system-architecture.mmd)
Navigation diagram: [frontend/diagrams/navigation-flow.mmd](frontend/diagrams/navigation-flow.mmd)

## Proposed Repository Layout

```text
cdm/
  contracts/
    api.py
  backend/
    __init__.py
    app.py
    api/
      routes/
        states.py
        members.py
        bills.py
        search.py
        topics.py
      schemas/
        states.py
        members.py
        bills.py
        search.py
        topics.py
    services/
      state_service.py
      member_service.py
      bill_activity_service.py
      search_service.py
      topic_service.py
      timeline_service.py
    repositories/
      state_repository.py
      member_repository.py
      bill_repository.py
      search_repository.py
    core/
      config.py
      deps.py
      exceptions.py
frontend/
  app/
    src/
      shared/
        contracts/
          api.ts
      pages/
        HomePage.tsx
        StatesPage.tsx
        StateDetailPage.tsx
        MemberProfilePage.tsx
        SearchPage.tsx
      components/
        StateGrid.tsx
        TimelineLane.tsx
        MemberCard.tsx
        SearchBar.tsx
      api/
        client.ts
        states.ts
        members.ts
        search.ts
      routing/
        routes.tsx
```

## Page and Navigation Plan

The navigation should follow the user's investigation flow: orient, choose a
jurisdiction or person, inspect records, then pivot through connected evidence.
Directories are data tables or searchable lists; detail pages prioritize a
verified identity and links to the underlying records.

### 1) States Directory
Route: /states

- Displays real states and enabled territories in a searchable directory beside
  an accessible map.
- Map and directory selection navigate to /states/:stateCode.
- Shows current delegation counts only when backed by a defined Congress and
  source response.
- Supports keyboard focus, hover/selection detail, loading, and unavailable
  geography states.

### 2) State Detail
Route: /states/:stateCode

- Header: state name, abbreviation, current Congress, and data freshness.
- Compact delegation summary for House and Senate, followed by two linked
  timeline lanes grouped by Congress.
- Timeline interactions:
  - Select a Congress or range.
  - See district or at-large labels where available.
  - Click a member row to open the profile.
  - Explain missing terms or seats as unavailable data rather than zero facts.

### 3) Member Profile
Route: /members/:bioguideId

- Verified identity header: name, portrait, party, current chamber/state,
  district, current term, Bioguide ID, and source link.
- Chamber and state history timeline.
- Filterable activity tables for sponsored, introduced, co-sponsored, supported,
  and voted legislation, grouped by Congress and date.
- Topic profile with distribution chart, word cloud/tag cloud, representative
  phrases, confidence, and links to supporting bills.

### 4) Global Search
Route: /search

- Single search UX for members, states, and bills with URL-addressable query and
  type filters.
- Backend decides ranking and result typing.
- UI shows grouped, paginated result sections with type badges, subtitles, and
  direct links.

### 5) Member Directory
Route: /members

- Server-side searchable and filterable member table.
- Columns: name, party, state, chamber, district, current term, and updated
  date.
- Row click navigates to the canonical member profile.

### 6) Bills Directory
Route: /bills

- Server-side table with query, Congress, chamber, type, date, policy area,
  sponsor, and status filters.
- Compact rows show bill identifier, title, Congress, chamber, status, and last
  updated date.
- URL state, result count, clear filters, pagination, sorting, and empty states
  are required.

### 7) Bill Detail
Route: /bills/:billId

- Identity and latest-action header with Congress.gov source link.
- Evidence-oriented sections for sponsors, cosponsors, committees, subjects,
  summaries, amendments, votes, laws, text versions, and provenance.
- Every related count links to a filtered record view when that endpoint exists.

### 8) Topics
Routes: /topics and /topics/:topicLabel

- Topic directory is a real aggregate table, not hard-coded sample cards.
- Topic detail presents prevalence, confidence, trend, representative phrases,
  members, bills, Congress coverage, and provenance.
- Topic labels link to member, bill, state, and Congress pivots.

### 9) Ingest Administration
Route: /admin/ingest

- Operational dashboard for resource, scope, stage, progress, failures, and
  freshness.
- Recovery controls are visible only to authorized operators and report the
  resulting job identity and state.

## API Contract (Scaffold Version)

### States
- GET /api/v1/states
  - Returns list of states with code and displayName.
- GET /api/v1/states/{state_code}
  - Returns state metadata.
- GET /api/v1/states/{state_code}/timeline?from_congress=...&to_congress=...
  - Returns chamber-separated timeline buckets and member references.

### Members
- GET /api/v1/members/{bioguide_id}
  - Returns canonical member profile.
- GET /api/v1/members/{bioguide_id}/activity?window=90d
  - Returns proposed/supported/voted bill summaries.
- GET /api/v1/members/{bioguide_id}/topics
  - Returns topic distribution labels and scores.

### Search
- GET /api/v1/search?q=...&types=member,state,bill&limit=20
  - Returns typed blended results with backend relevance score.

### Bills
- GET /api/v1/bills/recent?chamber=...&congress=...&limit=...&page=...
- GET /api/v1/bills/{bill_id}

### Additional Read Models Required By The Stories
- GET /api/v1/members?query=...&state=...&chamber=...&party=...&page=...
- GET /api/v1/members/{id}/activity?activity_type=...&congress=...&page=...
- GET /api/v1/members/{id}/topics
- GET /api/v1/topics?query=...&congress=...&page=...
- GET /api/v1/topics/{topic_label}
- GET /api/v1/admin/ingest-progress?resource=...&job_id=...

All collection endpoints return a total, page, limit, and stable sort metadata;
detail endpoints include provenance and source links where available.

## Data Model Expectations (Backend)

Core read models:
- state(code, name)
- member(bioguide_id, display_name, party, current_state)
- member_term(member_id, congress, chamber, state, district, start_date, end_date)
- bill(bill_id, congress, introduced_date, title, summary)
- bill_member_activity(member_id, bill_id, activity_type, activity_date)
- member_topic_profile(member_id, topic_label, weight, updated_at)

Notes:
- Keep ingest-normalized raw artifacts out of direct frontend contracts.
- Add explicit response schemas in FastAPI to avoid accidental field drift.

## Search Design

Phase 1 (scaffold):
- Name/identifier exact and prefix matching.
- Optional OpenSearch-backed lookup for members/bills.

Phase 2:
- Weighted ranking signals:
  - Exact ID match > name match > fuzzy match.
  - Recency boost for bill activity.
  - Optional popularity/office tenure signal.

Phase 3:
- Hybrid search (keyword + semantic topic vectors) for member-topic discovery.

## NLP/Topic Pipeline Plan

Phase 1 (offline batch only):
- Build per-member corpus from bill titles/summaries, sponsorship text, and vote context.
- Compute topic labels with a deterministic baseline (TF-IDF + clustering or seeded topic mapping).
- Store as member_topic_profile.

Phase 2:
- Add embedding model and semantic nearest-topic mapping.
- Recompute profiles on schedule (daily/weekly) via worker jobs.

Phase 3:
- Expose explainability fields in API:
  - top supporting phrases
  - sample bill IDs per topic

## Execution Plan and Checklists

### Phase 0: Project Scaffolding
- [x] Confirm chosen free/open-source UI component library and starter pattern.
- [ ] Initialize frontend with shadcn/ui and Radix-compatible styling foundation.
- [x] Create shared design tokens (color, spacing, typography, radius) for consistent component appearance.
- [x] Create cdm/backend FastAPI app shell and health endpoint.
- [x] Create frontend/app React shell with routing and base layout.
- [x] Add environment configs (.env example) for API base URL.
- [x] Add local run commands to Makefile.
- [x] Create centralized backend contract models in cdm/contracts/api.py.
- [x] Generate frontend shared contract types from backend OpenAPI.
- [x] Enforce contract generation during frontend dev/build.

Exit criteria:
- Frontend loads and routes between page shells with shared loading, empty,
  error, and unavailable-data states.
- Backend responds to /health and versioned API prefix.

### Phase 1: State and Member Core
- [x] Implement /states and /states/{code}/districts endpoints.
- [x] Implement /states/{code}/timeline endpoint with house/senate lanes.
- [x] Implement /members/{bioguide_id} endpoint.
- [ ] Add a real member directory endpoint and server-side member filters.
- [ ] Replace state map hover placeholders with live delegation summaries.
- [ ] Wire state and member pages to verified current and historical records.
- [ ] Add tests for active terms, at-large seats, missing data, and state pivots.

Exit criteria:
- User can click state -> Congress -> member -> verified profile end-to-end.
- No production state or member page displays fabricated values.

### Phase 2: Bill Activity and Search
- [x] Implement bill detail and recent bill list endpoints.
- [ ] Complete the server-side bills table with date, policy, sponsor, status,
  sorting, URL state, and clear-filter controls.
- [ ] Implement member activity endpoint for sponsored, introduced,
  co-sponsored, supported, and voted records.
- [ ] Render activity as compact filterable tables with bill-level links.
- [x] Implement search endpoint with typed results.
- [ ] Add global search navigation, URL state, grouped pagination, and query
  explainability.

Exit criteria:
- Search returns actionable links to state, member, and bill pages.
- A user can move member -> bill activity -> bill detail -> sponsor/member.
- Bill and activity collections remain usable with thousands of records.

### Phase 3: NLP Topic Features
- [ ] Build offline topic profile generator job with versioned outputs.
- [ ] Implement aggregate /topics and /topics/{label} endpoints.
- [ ] Implement /members/{id}/topics endpoint.
- [ ] Render topic distribution, word cloud, tag cloud, and confidence states.
- [ ] Add representative phrases, supporting bills, and provenance metadata.
- [ ] Add member, bill, state, and Congress pivots from topic views.

Exit criteria:
- Topic views display stable, explainable associations with source coverage and
  do not imply confidence where the pipeline has no evidence.

### Phase 4: Operations and Accessibility
- [ ] Turn /admin/ingest into a real resource/job progress dashboard.
- [ ] Add freshness indicators and incomplete-data explanations to directories.
- [ ] Verify keyboard, screen-reader, focus, and mobile behavior for maps,
  tables, filters, dialogs, and timelines.
- [ ] Add URL-shareable investigation states and browser navigation coverage.

Exit criteria:
- An operator can identify and trace stale or failed data behind a user view.
- Core journeys are usable without a mouse and at mobile widths.

### Phase 5: Hardening
- [ ] Add integration tests for state timeline, member directory, member
  activity, bill filters, search, and topic endpoints.
- [ ] Add API schema contract tests.
- [ ] Add frontend e2e smoke paths for state -> member, member -> bill, and
  topic -> member/bill pivots.
- [ ] Add caching and basic rate limiting.
- [ ] Add deterministic fixture tests for aggregate-to-record drilldowns.

Exit criteria:
- Core journeys pass in CI with reproducible fixtures and no placeholder data.

## UX Data Journey (How users explore)
1. User opens the home page or global search and chooses a question.
2. User selects a state, member, bill, or topic from a directory or search result.
3. User verifies the record's identity, Congress, time range, and freshness.
4. User filters a compact table or timeline to isolate a working set.
5. User opens an individual record behind an aggregate or table row.
6. User follows links across state, member, bill, vote, and topic records.
7. User shares or revisits the URL with the same filters and scope intact.

## Non-Goals for Initial Scaffold
- Real-time streaming updates.
- Full roll-call vote analytics UI; vote records and links remain a later
  evidence surface.
- On-device NLP in browser.
- Any frontend direct DB/OpenSearch access.
- Personalized voter accounts, saved searches, and alerts.

## Risks and Mitigations
- Risk: Data shape drift from ingest models.
  - Mitigation: strict FastAPI response models and contract tests.
- Risk: Slow timeline queries at full history scale.
  - Mitigation: precomputed read models + caching.
- Risk: Topic results look unstable early.
  - Mitigation: deterministic baseline first, versioned topic pipeline.

## Immediate Next Implementation Task
Start the next implementation slice with the highest-confidence data journey:

- Replace the StatesPage placeholder hover data with a live state summary
  contract and loading/error/unavailable states.
- Add a server-side member directory and redesign MemberSearchPage as a compact
  filterable table.
- Make StateDetailPage and MemberProfilePage use current-term data explicitly,
  including at-large/district labels and source links.
- Add focused tests proving active terms such as South Dakota's 119th House seat
  are included and that missing source data is not rendered as zero.
- Then complete bill table URL state and member activity drilldowns before
  starting topic visualizations.
