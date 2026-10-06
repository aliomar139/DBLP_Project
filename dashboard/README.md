# DBLP Research Intelligence

The dashboard uses the existing FastAPI, DuckDB, React, TypeScript, Recharts and D3 stack. No database migrations, XML parsing or additional runtime dependencies are required.

## Run locally

From `C:\DBLP_Project`:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd C:\DBLP_Project\dashboard
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. API documentation: http://127.0.0.1:8000/docs.

`VITE_API_URL` overrides the frontend API origin. `DBLP_DB_PATH` overrides the backend database file, which is always opened read-only. Its default remains `database/dblp.duckdb`.

## Pages

- `/`: publication history, dataset metrics, leading researchers and venues, publication types.
- `/trends`: decade explorer and annual publication/growth comparison.
- `/authors`: paginated, sortable rising researcher rankings.
- `/authors/:id`: career history, venues, collaborators and mini network.
- `/venues`: paginated, sortable venue growth rankings.
- `/venues/:id`: venue history and leading researchers.
- `/network?author=:id`: researcher-centered network with strength, node count and year filters.
- `/insights`: observations calculated from DuckDB.

Use the header search to find a researcher or venue. Tab/arrow keys navigate search results; Escape dismisses them. Graph nodes support keyboard profile navigation; the accompanying table supports recentering. Timeline charts offer a data table and a draggable time range.

## Checks

From the project root:

```powershell
.\venv\Scripts\python.exe -m compileall -q backend/app backend/tests
.\venv\Scripts\python.exe -m unittest discover -s backend/tests -v
.\venv\Scripts\python.exe -m backend.tests.smoke_live
```

The unit suite creates a tiny temporary database under `backend/tests`, then removes it. It never writes to the production database. The optional smoke suite uses the configured production database read-only and prints cold/warm timings and response sizes.

From `dashboard`:

```powershell
npm run typecheck
npm run build
npm run preview -- --host 127.0.0.1
```

For deployment, configure the web server to fall back to `index.html` for frontend paths, so direct profile URLs work. API routes must remain routed to FastAPI. CORS allows local Vite development and preview origins; configure explicit origins for other deployments. The local analytics service is not an authenticated public API.

See [IMPLEMENTATION.md](../IMPLEMENTATION.md) for the feature checklist, file inventory, API contracts, database queries, methodology, performance measurements and verification limits.
