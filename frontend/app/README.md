# Frontend (Radix Themes + React)

This is the Congress Tracker web application.

## Stack
- React + TypeScript + Vite
- [`@radix-ui/themes`](https://www.radix-ui.com/themes/docs/overview/getting-started) — `Theme` provider wired in `src/main.tsx` (`accentColor="teal"`, `radius="large"`). `AppShell` (header/nav) is migrated to Themes components (`Flex`, `Box`, `Heading`, `Badge`, `Link`). Page bodies still use the original hand-rolled CSS in `src/styles/globals.css` — see "Radix Themes migration" below for the page-by-page backlog.
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

**Status:** started 2026-09-05. `Theme` provider + `AppShell` are done; page
bodies are not yet converted.

The app previously used only the raw `@radix-ui/react-navigation-menu`
primitive plus ~1,100 lines of hand-rolled CSS in `src/styles/globals.css`
(custom cards, chips, timeline, portrait-header patterns). `@radix-ui/themes`
is now installed and provides a themeable component library (`Card`, `Table`,
`TextField`, `Tabs`, `Dialog`, `Badge`, `DataList`, layout primitives) that
can replace most of that hand-rolled CSS, which is exactly the "cut down on
boilerplate" win — Themes ships the design tokens (`--accent-9`, spacing
scale, radius scale) so `globals.css` mostly only needs to keep truly
bespoke patterns (the vertical timeline, the map).

Relevant references:
- Radix Themes docs/playground: https://www.radix-ui.com/themes/docs/overview/getting-started
- Radix Themes component gallery: https://www.radix-ui.com/themes/docs/components/callout (use the left nav for the full component list — `Card`, `Table`, `DataList`, `Tabs`, `TextField`, `Badge`, `Dialog`, `Select` are the ones most applicable here)
- Vercel's Radix UI template gallery (https://vercel.com/templates/radix-ui) is mostly Next.js **AI-chatbot** starters and isn't a direct fit, but two templates are genuinely useful layout references for this app:
  - "Next.js Book Inventory" (search/filter/pagination over a list) — https://vercel.com/templates/next.js/next-book-inventory — closest match for `BillsPage`, `MemberSearchPage`, and `SearchPage`'s list+filter UI.
  - "Natural Language Postgres" (query input → structured results) — https://vercel.com/templates/next.js/natural-language-postgres — useful layout reference for `SearchPage`'s query/result pattern.
- [shadcn/ui](https://ui.shadcn.com) is also Radix-primitive-based and worth skimming for table/filter/detail-page composition patterns, even though this project uses Themes' pre-styled components rather than shadcn's copy-in component source.

### Remaining backlog (page by page)

For each page: replace the page's custom `className`-driven markup with Themes
components, keep the existing data-fetching hooks/logic untouched, and delete
the now-unused CSS rules from `globals.css` once a page no longer references
them (mirror the cleanup already done for `.health-pill*`/`.nav-list`/`.nav-link`
in this pass).

- [ ] `HomePage.tsx` — replace `.card-grid`/`.card` with Themes `Grid` + `Card`.
- [ ] `StatesPage.tsx` / `StateDetailPage.tsx` — `Table` or `DataList` for the
      delegation list; keep the existing `react-simple-maps` map component as-is
      (Themes has no map primitive).
- [ ] `MemberSearchPage.tsx` — `TextField` for the query input, `Table` for
      results; model after the "Book Inventory" template's search/filter layout.
- [ ] `MemberProfilePage.tsx` — the `.member-hero-card`/`.member-chips` pattern
      in `StyleGuidePage.tsx` maps well to Themes `Flex` + `Avatar` + `Badge`.
- [ ] `BillsPage.tsx` / `BillDetailPage.tsx` — `Table`/`DataList` for the list
      and bill metadata; `Tabs` for grouping actions/summaries/text-versions on
      the detail page once those fields exist (see
      `planning/FULL_DATA_INGEST_IMPLEMENTATION_PLAN.md`).
- [ ] `TopicsPage.tsx` / `TopicDetailPage.tsx` — currently mock data; hold off
      on a full rebuild until the backend topics API exists, but the shell
      (`Card`/`Badge` for topic chips) can be converted now.
- [ ] `SearchPage.tsx` — `TextField` + `Tabs` (by result type) + `Card`/`Table`
      results, modeled after the "Natural Language Postgres" template's
      query-then-results layout.
- [ ] `AdminIngestPage.tsx` — `Table` for job/coverage rows, `Badge` for status,
      `Callout` for failures; this page has the most tabular data and will
      benefit the most from Themes' `Table` component.
- [ ] `StyleGuidePage.tsx` — either delete (it's unrouted) or repurpose as a
      living Themes component reference once the migration above is complete.
- [ ] Once every page is converted, delete the now-fully-unused legacy pattern
      classes from `globals.css` (`.card`, `.panel`, `.chip`, `.timeline-*`,
      `.member-*`, etc.) and keep only truly bespoke CSS (map styling, the
      vertical timeline connector lines Themes has no equivalent for).
- [ ] Re-run `npm run build` and check the CSS bundle size — importing
      `@radix-ui/themes/styles.css` pulls in the full color-scale set
      (~700 KB unminified in this pass); Radix's docs cover restricting to
      specific color scales if bundle size becomes a concern.

## Notes
- All data shaping is backend-owned.
- Frontend only renders typed API responses and manages UI state.
