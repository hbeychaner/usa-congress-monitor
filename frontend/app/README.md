# Frontend (Radix Themes + React)

This is the Congress Tracker web application.

## Stack
- React + TypeScript + Vite
- [`@radix-ui/themes`](https://www.radix-ui.com/themes/docs/overview/getting-started) — `Theme` provider wired in `src/main.tsx` (`accentColor="teal"`, `radius="large"`). The app shell and every routed page are migrated to Themes components (`Flex`, `Card`, `Table`, `TextField`, `Select`, `Badge`, `Progress`, `DataList`, `Callout`, etc.) — see "Radix Themes migration" below for what was converted and the follow-up items.
- Backend API calls to FastAPI (`/api/v1/*`)

## Routes
- `/` home
- `/admin/ingest` ingest job/coverage admin dashboard
- `/states` states directory
- `/states/:stateCode` state timeline detail
- `/members` member search
- `/members/:bioguideId` member profile
- `/bills` bill activity list
- `/bills/:billId` bill detail
- `/topics` topic explorer (currently mock data — see `planning/TOPIC_ANALYSIS_IMPLEMENTATION_PLAN.md`)
- `/topics/:topicLabel` topic detail
- `/search` backend-backed global search

## Local Run
1. Install Node.js 20+ and npm.
2. Copy `.env.example` to `.env` and adjust API URL if needed.
3. Run backend:

```bash
make backend-api
```

4. In another shell, run frontend:

```bash
make frontend-dev
```

## Radix Themes migration

**Status:** completed 2026-09-05. `Theme` provider, `AppShell`, and every
routed page are converted to Radix Themes components. `StyleGuidePage.tsx`
was deleted (it was unrouted and unreferenced). `src/styles/globals.css` was
trimmed from ~1,100 lines to ~260, keeping only the genuinely bespoke CSS
(the state map via `react-simple-maps`, the vertical delegation timeline
connector lines/party dots, and the shared shell/typography tokens).

The app previously used only the raw `@radix-ui/react-navigation-menu`
primitive plus ~1,100 lines of hand-rolled CSS in `src/styles/globals.css`
(custom cards, chips, timeline, portrait-header patterns). `@radix-ui/themes`
is now used throughout for cards, tables, forms, badges, and progress bars,
which is exactly the "cut down on boilerplate" win — Themes ships the design
tokens (`--accent-9`, spacing scale, radius scale) so `globals.css` now only
keeps truly bespoke patterns (the vertical timeline, the map).

Relevant references:
- Radix Themes docs/playground: https://www.radix-ui.com/themes/docs/overview/getting-started
- Radix Themes component gallery: https://www.radix-ui.com/themes/docs/components/callout (use the left nav for the full component list — `Card`, `Table`, `DataList`, `Tabs`, `TextField`, `Badge`, `Dialog`, `Select` are the ones most applicable here)
- Vercel's Radix UI template gallery (https://vercel.com/templates/radix-ui) is mostly Next.js **AI-chatbot** starters and isn't a direct fit, but two templates were useful layout references for this app:
  - "Next.js Book Inventory" (search/filter/pagination over a list) — https://vercel.com/templates/next.js/next-book-inventory — used as the layout model for `BillsPage`, `MemberSearchPage`, and `SearchPage`'s list+filter UI.
  - "Natural Language Postgres" (query input → structured results) — https://vercel.com/templates/next.js/natural-language-postgres — used as the layout reference for `SearchPage`'s query/result pattern.
- [shadcn/ui](https://ui.shadcn.com) is also Radix-primitive-based and worth skimming for table/filter/detail-page composition patterns, even though this project uses Themes' pre-styled components rather than shadcn's copy-in component source.

### Completed conversions

All pages were converted from hand-rolled `className` markup to Radix Themes
components, keeping existing data-fetching hooks/logic untouched. Legacy CSS
that no longer had any consumer was deleted from `globals.css` as each page
was finished.

- [x] `HomePage.tsx` — `Grid` + `Card` (`asChild` wrapping `Link`) for the
      destination cards.
- [x] `TopicsPage.tsx` / `TopicDetailPage.tsx` — `Grid`/`Card` for topic tiles;
      `Progress` replaces the old `.topic-bar` fill divs.
- [x] `MemberSearchPage.tsx` — `TextField` for the query input, `Select` for
      chamber/party filters (`"all"` sentinel value), `Table` for results,
      `Button`/`Flex` pagination.
- [x] `StatesPage.tsx` / `StateDetailPage.tsx` — kept the existing
      `react-simple-maps` map component as-is (Themes has no map primitive);
      the hover/preview panel and stat panels are now `Card`; timeline filter
      inputs use `TextField.Root`. The per-Congress delegation timeline
      (`.timeline-lane`/`.timeline-card`/`.party-dot*`) intentionally stays
      bespoke CSS — Themes has no vertical-timeline-with-connector primitive.
- [x] `MemberProfilePage.tsx` — `Avatar` (with initial fallback) replaces the
      raw `<img onError>` portrait pattern, `Badge` for party/district/term
      chips, `Progress` for the topic-weight bars (same pattern as
      `TopicsPage`), `Card` for section panels.
- [x] `BillsPage.tsx` — same `TextField`/`Select`/`Table`/`Button` pagination
      pattern as `MemberSearchPage.tsx`.
- [x] `BillDetailPage.tsx` — two-column `Grid` layout, `Card` per section,
      `DataList` for the bill-record/available-records metadata lists.
      Revisit with `Tabs` once more bill detail fields exist (see
      `planning/FULL_DATA_INGEST_IMPLEMENTATION_PLAN.md`).
- [x] `SearchPage.tsx` — `TextField` for the query, `Button variant="soft"`
      toggle group standing in for a "chip" filter (Radix Themes has no
      dedicated `ToggleGroup` in `@radix-ui/themes`), `Select` for the result
      limit, `Card` for grouped results — modeled after the "Natural Language
      Postgres" template's query-then-results layout.
- [x] `AdminIngestPage.tsx` — `Progress` for the 3 pipeline bars, `Badge` for
      the readiness/job-status pills, `Card` for the stat/metric panels,
      `Table` for the per-job list with a `Select` status filter, `Callout`
      for the top-level error state.
- [x] `StyleGuidePage.tsx` — deleted. It was unrouted (not present in
      `routing/routes.tsx`) and had zero remaining references anywhere in the
      codebase.
- [x] `globals.css` cleanup — removed all page-wrapper/card/panel/table/form
      classes that no longer had any `className` consumer. Kept: CSS custom
      properties, `.app-shell`/`.topbar`/`.brand`/`.content` (shell layout),
      `.chip` (still used inline in `StateDetailPage`'s congress-range chip),
      `.timeline-lane`/`.timeline-item`/`.timeline-card*`/`.party-dot*`
      (vertical delegation timeline), `.congress-grid`/`.congress-column`/
      `.chamber-section` (timeline layout), and `.map-layout`/`.map-panel`/
      `.usa-map`/`.map-state` (react-simple-maps styling).

### Follow-up items (not done in this pass)
- Every converted page currently uses Radix `Heading` for its page title and
  section headings without an explicit `as="h2"`/`as="h3"` prop. Radix's
  `Heading` renders an `<h1>` by default regardless of `size`, so most pages
  now render multiple `<h1>` elements, which is a heading-hierarchy/a11y
  regression worth fixing in a follow-up pass (set `as="h2"`/`as="h3"` on the
  section-level `Heading`s so each page has exactly one `<h1>`).
- Re-run `npm run build` and check the CSS bundle size — importing
  `@radix-ui/themes/styles.css` still pulls in the full color-scale set
  (~698 KB unminified after this pass); Radix's docs cover restricting to
  specific color scales if bundle size becomes a concern.

## Notes
- All data shaping is backend-owned.
- Frontend only renders typed API responses and manages UI state.

