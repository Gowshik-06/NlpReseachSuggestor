# Frontend — Research Paper Recommendation System

React + TypeScript (Vite). Phase 0 scope only: application root, routing
foundation, a centralized API service layer, layout, loading/error states,
and a health/status page.

## Run independently (without Docker)

```bash
cd frontend
npm install
cp .env.example .env      # adjust VITE_API_BASE_URL if needed
npm run dev
```

The dev server runs at `http://localhost:3000` and expects the backend at
the URL configured in `VITE_API_BASE_URL` (default `http://localhost:8000`).

## Tests

```bash
npm run test
```

## Project layout

```
src/
├── components/   # small reusable UI pieces (e.g. StatusRow)
├── pages/        # route-level pages (HomePage)
├── layouts/      # page chrome (MainLayout)
├── services/     # centralized API client (api.ts) — no scattered fetch()
├── hooks/        # data-fetching hooks (useHealthStatus)
├── types/        # shared TypeScript types
├── utils/        # shared helpers (empty in Phase 0)
└── App.tsx       # routing root
```

The home page shows only backend/database connectivity and version info.
The actual search interface, paper cards, and recommendation UI are not
implemented yet — those belong to later phases.
