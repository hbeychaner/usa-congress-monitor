# Frontend Scaffold (Radix + React)

This is a Phase 0 scaffold for the Congress Tracker web application.

## Stack
- React + TypeScript + Vite
- Radix NavigationMenu primitive
- Backend API calls to FastAPI (`/api/v1/*`)

## Routes
- `/` home
- `/states` states list
- `/states/:stateCode` state timeline detail
- `/members/:bioguideId` member profile
- `/search` backend-backed search scaffold

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

## Notes
- All data shaping is backend-owned.
- Frontend only renders typed API responses and manages UI state.
