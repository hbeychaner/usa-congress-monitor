# Congress Tracker frontend

React, TypeScript and Vite application backed by FastAPI under `/api/v1`.
Use the repository [quick start](../../README.md#quick-start) for the managed
local deployment, including search, broker, workers and native Ollama.

## Structure and UI

[`AppRoutes`](src/routing/routes.tsx) selects pages.
[`main.tsx`](src/main.tsx) installs the Radix Themes provider.
Pages use Radix cards, tables, forms, badges and progress components;
[`globals.css`](src/styles/globals.css) owns application layout, map and
delegation-timeline styling. See the [style guide](../STYLE_GUIDE.md).

Feature helpers call the API through generated response contracts. The frontend
owns presentation, URL/filter state and browser graph layout; backend services
own data shaping, source interpretation and persisted analysis.
Analysis availability and request errors are displayed explicitly.

## Routes

| Path | Page |
|---|---|
| `/` | Home |
| `/admin/ingest` | Durable jobs, ingestion progress and build controls |
| `/states` | States directory |
| `/states/:stateCode` | Delegation timeline |
| `/members` | Member search |
| `/members/:bioguideId` | Member profile |
| `/graph` | Member/topic graph |
| `/bills` | Legislation list |
| `/bills/:billId` | Bill detail |
| `/committees/:systemCode` | Committee detail |
| `/topics` | Published topic explorer |
| `/topics/:topicId` | Topic detail |
| `/parties` | Party perspectives |
| `/search` | Global search |

## Isolated foreground development

Do not run foreground API/workers alongside their managed copies.
Use Node.js 22 and install the locked frontend dependencies:

```sh
cd frontend/app
npm ci
```

From the repository root, start the API and frontend in separate terminals:

```sh
make backend-api
make frontend-dev
```

Set `VITE_API_BASE_URL` in the frontend environment when using a nondefault API
origin. The API must allow the corresponding browser origin.

## Contracts and validation

From `frontend/app`:

```sh
npm run contracts:generate
npm run contracts:check
npm run build
npm run audit
```

Contract generation exports the Python API schema offline and writes
[`api.ts`](src/shared/contracts/api.ts); check mode does not rewrite it.
Normal frontend builds do not need a running API or regenerate the contracts.
See the [API/frontend reference](../../documentation/reference/api-and-frontend.md)
for hooks, endpoints, browser tests, error handling and publication lineage.
