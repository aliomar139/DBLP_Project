# DBLP Research Intelligence Platform — Comprehensive Specification & Context

> **Purpose of this document**: This specification provides a complete, self-contained overview of the DBLP Research Intelligence platform. It contains everything an AI assistant or engineer needs to visualize, understand, analyze, and build upon the existing system without needing prior context.

---

## 1. Executive Summary & Purpose

The **DBLP Research Intelligence Platform** is a high-performance web dashboard and analytical engine built over the entire **DBLP Computer Science Bibliography**. 

The dataset contains:
- **8,738,331** indexed publications (dating from 1936 through 2027)
- **4,301,538** unique researchers
- **21,224** publication venues (conferences, journals, repositories)
- **32,498,462** co-authorship collaboration edges (derived from all paper co-authorships)

The platform enables computer science researchers, department heads, and bibliometricians to:
1. Explore macro-trends in computer science over the last 8 decades (1950s–2020s).
2. Inspect individual researcher trajectories, career spans, venue preferences, and collaboration networks.
3. Track publication venue volume, momentum, and researcher concentration.
4. Discover rising researchers and emerging venues using statistical growth models.
5. Interact with large-scale force-directed co-authorship graphs (up to 500 nodes).
6. Read live data-driven insights on team size evolution and scientific partnerships.

---

## 2. Architecture & Technology Stack

```
                                 ┌─────────────────────────────────────────┐
                                 │       React + Vite Frontend (SPA)       │
                                 │  (History API, Recharts, D3 Force Sim)   │
                                 └────────────────────┬────────────────────┘
                                                      │ HTTP / REST (JSON)
                                                      ▼
                                 ┌─────────────────────────────────────────┐
                                 │          FastAPI Backend Engine         │
                                 │ (Pydantic v2 Models, LRU Query Caching, │
                                 │      Single-Flight Worker Locks)        │
                                 └────────────────────┬────────────────────┘
                                                      │ Read-Only SQL (duckdb)
                                                      ▼
                                 ┌─────────────────────────────────────────┐
                                 │       DuckDB Database (Local File)      │
                                 │           `database/dblp.duckdb`        │
                                 │  (8.7M papers, 32.5M ties, pre-agg stats│
                                 └─────────────────────────────────────────┘
```

### Backend Architecture
- **Framework**: Python 3.12 + FastAPI + Uvicorn.
- **Database**: Local DuckDB database file at `database/dblp.duckdb` (read-only connections, no writes).
- **Concurrency & Safety**:
  - In-process **single-flight lock** serializes heavy analytical queries per worker to prevent memory spikes on multi-million row scans.
  - Read-only database connection barrier rejects any modifying statements (`INSERT`, `UPDATE`, `DROP`).
  - Strict **45-second query timeout** interrupts runaway queries.
- **Caching**: In-memory LRU cache (128 entries per process, 10-minute TTL) caches SQL results keyed by SQL string + bound parameter tuples. Cold queries run in 50ms–2.2s; warm queries respond in < 5ms.
- **Validation**: Strict Pydantic v2 schemas in `backend/app/schemas/models.py`.

### Frontend Architecture
- **Framework**: React 18+ with TypeScript, bundled with Vite.
- **Routing**: Zero external router dependencies; uses clean native HTML5 History API (`pushState`, `popstate`) with lazy-loaded route components (`React.lazy`, `Suspense`).
- **Data Visualization**:
  - **Recharts**: Composed charts, dual-axis volume/growth lines, donut breakdowns, multi-line evolution charts, and bar charts.
  - **D3.js (v7)**: Force-directed network simulations (`d3-force`, `d3-zoom`, `d3-selection`) for collaboration graph exploration.
- **Design System & Styling**:
  - Plain additive CSS (`tokens.css` and `intelligence.css`) using modern CSS variables, OKLCH color spaces, and an 8pt spatial grid.
  - Anti-AI-slop philosophy (inspired by Hallmark & Apple HIG): No generic pastel blobs, no fake metrics, honest labels, high visual hierarchy, roman headings, and dense tabular scanability.

---

## 3. Database Schema Overview

The DuckDB database consists of core normalized tables and pre-computed analytical views:

| Table Name | Description | Key Columns |
| :--- | :--- | :--- |
| `publications` | All indexed research papers | `publication_id` (BIGINT), `year` (INT), `venue_id` (BIGINT), `type` (VARCHAR: article, inproceedings, book, etc.) |
| `authors` | Researcher identity | `author_id` (BIGINT), `name` (VARCHAR) |
| `venues` | Venues, journals, proceedings | `venue_id` (BIGINT), `name` (VARCHAR) |
| `publication_authors` | Authorship bridge table | `publication_id` (BIGINT), `author_id` (BIGINT) |
| `author_collaboration` | Canonical co-authorship pairs | `author1_id` (BIGINT), `author2_id` (BIGINT), `weight` (BIGINT: shared paper count) |
| `author_stats` | Pre-aggregated author totals | `author_id` (BIGINT), `name` (VARCHAR), `publication_count` (BIGINT) |
| `venue_stats` | Pre-aggregated venue totals | `name` (VARCHAR), `publication_count` (BIGINT) |
| `publication_year_stats` | Annual paper counts | `year` (INTEGER), `publication_count` (BIGINT) |
| `dashboard_summary` | Global summary stats | `total_publications`, `total_authors`, `total_venues`, `first_year`, `last_year` |

---

## 4. Frontend Page-by-Page Visual & Functional Specification

### 4.1. Global Shell & Navigation
- **Top Header**:
  - Brand identity: `DBLP / Research Intelligence` with distinct monogram badge.
  - **Unified Search Bar (`SearchBar.tsx`)**:
    - Debounced (300ms) input with live search popover.
    - Full keyboard navigation (`ArrowDown`, `ArrowUp`, `Enter`, `Escape`).
    - Groups results by **Researchers** and **Venues** with total paper counts.
    - Clicks smoothly route to `/authors/{id}` or `/venues/{id}` without page reloads.
  - Mobile hamburger toggle for smaller viewports.
- **Sticky Sidebar**:
  - Sticky vertical flex navigation (`/`, `/trends`, `/authors`, `/venues`, `/network`, `/insights`).
  - Active route highlighting with directional indicators (`↗`).
  - Anchored footer note: *"A field guide to computer science research · DBLP indexed records"*.

---

### 4.2. Overview Page (`/`)
*Route Component: `Overview.tsx`*

1. **Top Metric Cards Strip**:
   - `8.7M` Total Publications
   - `4.3M` Computer Science Researchers
   - `21.2K` Publication Venues
   - `1936–2027` Active Historical Span (92 active publication years)
   - `3.44` Average Authors per Paper
2. **Main Historical Trajectory Chart (`PublicationGrowthCombinedChart`)**:
   - Dual-axis interactive chart:
     - Left axis: Annual publication volume (clean line).
     - Right axis: Year-over-Year (YoY) growth percentage (bar chart).
   - View mode toggle: `Combined`, `Volume Only`, `Growth % Only`.
   - Recharts interactive Brush slider at bottom to zoom into specific eras (e.g., 1990–2025).
3. **Publication Format Intelligence**:
   - Left: `PublicationTypeDonutChart` showing distribution across `article` (journals), `inproceedings` (conferences), `book`, and others.
   - Right: `PublicationTypeTimelineChart` showing the evolution of publication types from 1970 to 2025.
4. **Generational Shift (Decades Explorer)**:
   - Covers 8 continuous decades: **1950s through 2020s**.
   - Interactive segmented toggle switches the bar chart data between:
     - *Papers* (publication volume)
     - *Researchers* (distinct active authors)
     - *Team Size* (mean authors per paper)
   - Data table displaying exact decade figures, distinct venues, and YoY decade growth.

---

### 4.3. Research Trends Page (`/trends`)
*Route Component: `ResearchTrends.tsx`*

1. **Collaboration Evolution Multi-Metric Chart**:
   - Tracks the historical rise of team science: average authors per paper over time, alongside the proportion of solo vs. multi-authored works.
2. **Team Size Distribution Breakdown**:
   - Categorizes papers into team size tiers: Solo (1 author), Small Team (2–3 authors), Medium Team (4–5 authors), Large Team (6+ authors).
3. **Leading Venues Historical Activity**:
   - Multi-line comparative timeline comparing the annual output of the top 10 computer science venues (e.g., *CoRR*, *IEEE Access*, *Lecture Notes in Computer Science*).

---

### 4.4. Researchers Intelligence Suite (`/authors`)
*Route Component: `Rankings.tsx` (kind="authors")*

A multi-tab intelligence suite with 5 specialized views:
1. **Productivity vs. Collaboration Scatter Plot (`ResearcherScatterChart`)**:
   - Plots the top 100 researchers with Total Publications on the X-axis vs. All-Time Collaborator Degree on the Y-axis.
   - Tooltips show author name, paper count, and collaborator count; clicking navigates to their profile.
2. **Most Productive Researchers**:
   - Ranked list of researchers by all-time publication volume.
3. **Most Collaborative Researchers**:
   - Ranked list of researchers by degree centrality (highest number of distinct co-authors across 32.5M edges).
4. **Longest Active Research Careers**:
   - Ranks researchers with the longest spans between their first and most recent publications (minimum 20 papers threshold).
5. **Rising Researchers (10-Year Momentum)**:
   - Statistical momentum engine comparing recent output (**2016–2025**) against all historical output prior to 2016.
   - Computes percentage growth: `(recent - historical) / historical * 100`.
   - Server-side sorting (`growth_rate`, `recent_publications`, `historical_publications`, `name`), configurable threshold (`minimum_recent`), and deterministic pagination.

---

### 4.5. Venues Intelligence Suite (`/venues`)
*Route Component: `Rankings.tsx` (kind="venues")*

A multi-tab intelligence suite with 3 specialized views:
1. **Fastest Growing Venues**:
   - 10-Year momentum ranking for publication venues, filtering by minimum recent publication volume with sortable columns and pagination.
2. **Venue Activity Heatmap (`VenueActivityHeatmap`)**:
   - Interactive Year (2005–2025) × Venue (top 12 global venues) intensity matrix.
   - Cells colored dynamically using OKLCH heat scales with tooltips displaying exact paper counts.
   - Horizontal scrolling features a sticky left column ensuring venue names remain legible at all times.
3. **Largest Publication Venues**:
   - Volume rankings of conferences and journals.

---

### 4.6. Macro & Interactive Collaboration Network (`/network`)
*Route Component: `Network.tsx`*

1. **Macro Network Intelligence Strip**:
   - Displays global dataset metrics:
     - **32,498,462** Total Collaborations
     - **4,301,538** Active Connected Researchers
     - **15.1** Average Co-authors per Researcher
     - **Peak Partnership**: Maosong Sun & Zhiyuan Liu (560 joint papers)
2. **Global Collaboration Tie Persistence**:
   - Distribution chart & table grouping all 32.5M collaboration ties into strength tiers:
     - *1 paper only* (~70% of ties)
     - *2 papers*
     - *3–5 papers*
     - *6–10 papers*
     - *11+ papers* (long-term scientific partnerships)
3. **Interactive D3 Force-Directed Network Graph (`NetworkGraph.tsx`)**:
   - Can center on any focal researcher (defaults to most prolific or query parameter `?author_id=...`).
   - Node limit selector: Supports up to **500 nodes** dynamically.
   - Minimum shared papers threshold filter: `1`, `5`, `10`, `50` papers.
   - Year range bounds: Interactively filter co-authorship ties by date range.
   - Visual encoding:
     - Center node highlighted with prominent styling.
     - Node radii scaled proportionally to total career publications.
     - Link widths scaled by joint paper weight.
   - Interactive capabilities: Drag nodes, pan, zoom, hover tooltips, click node to re-center graph, or click to open full profile.

---

### 4.7. Research Insights Page (`/insights`)
*Route Component: `Insights.tsx`*

Presents 4 live, data-backed analytical observation cards derived from live queries:
1. **Publication Acceleration**: Compares computer science output in 2000 vs. latest completed year (dramatic exponential growth).
2. **Expanding Research Teams**: Evidence of team size expansion (mean authors per paper doubled over 25 years).
3. **Venue Concentration**: The dominant role of open repositories (e.g., CoRR/arXiv) in shaping modern dissemination.
4. **Strongest Scientific Partnership**: Highlights the dataset's top co-authorship pair (Maosong Sun & Zhiyuan Liu with 560 papers), linking straight into the network visualizer.

---

### 4.8. Researcher Profile View (`/authors/{author_id}`)
*Route Component: `AuthorProfile.tsx`*

- **Header**: Author full name, total publication count, career duration (first to latest year), active publication years, and total distinct collaborator count.
- **Career Timeline**: Bar chart showing publications per calendar year throughout their career.
- **Top 10 Publication Venues**: Ranked table of the author's primary publication outlets.
- **Top 20 Closest Collaborators**: Ranked list of co-authors with shared paper counts and direct links.
- **Mini Collaboration Network**: An embedded D3 force graph showing the researcher's immediate ego-network.

---

### 4.9. Venue Profile View (`/venues/{venue_id}`)
*Route Component: `VenueProfile.tsx`*

- **Header**: Venue full name, total indexed papers, active years, and total distinct contributing authors.
- **Historical Output**: Annual publication volume chart over the entire history and last decade.
- **Top 20 Contributing Researchers**: Ranked list of authors who have published most frequently in this venue.

---

## 5. Backend REST API Reference

All analytical endpoints are `GET`, read-only, and automatically documented in OpenAPI at `/docs`.

| Endpoint | Description | Key Parameters | Typical Latency (Warm) |
| :--- | :--- | :--- | :--- |
| `GET /api/overview` | Global database counts & metrics | None | < 3ms |
| `GET /api/search` | Unified search across authors and venues | `q` (min 2 chars), `limit` (default 6) | < 5ms |
| `GET /api/publications/timeline` | Complete yearly paper counts (zero-filled) | None | < 3ms |
| `GET /api/publications/growth` | Annual volumes + YoY growth % | None | < 3ms |
| `GET /api/publications/types` | Breakdown by publication type | None | < 3ms |
| `GET /api/publications/types/timeline` | Format evolution by year (1970–2025) | None | < 4ms |
| `GET /api/trends/decades` | 8-decade comparison (1950s–2020s) | None | < 4ms |
| `GET /api/trends/collaboration-evolution`| Authors per paper over time | None | < 5ms |
| `GET /api/trends/team-distribution` | Papers by team size tier | None | < 4ms |
| `GET /api/authors/{author_id}` | Full researcher profile + top venues/coauthors | None | < 3ms |
| `GET /api/authors/top` | Top authors by total publication volume | `limit` (default 20, max 100) | < 3ms |
| `GET /api/authors/rising` | 10-year momentum ranking | `limit`, `offset`, `minimum_recent`, `sort_by`, `order` | < 3ms |
| `GET /api/authors/collaborative` | Top authors by collaborator degree | `limit` (max 100) | < 4ms |
| `GET /api/authors/longest-active` | Longest careers (min 20 papers) | `limit` (max 100) | < 3ms |
| `GET /api/authors/productivity-scatter` | Coordinates for top 100 authors (papers vs ties) | None | < 4ms |
| `GET /api/venues/{venue_id}` | Venue profile + yearly history + top authors | None | < 4ms |
| `GET /api/venues/top` | Top venues by publication volume | `limit` (max 100) | < 3ms |
| `GET /api/venues/growth` | 10-year momentum venue ranking | `limit`, `offset`, `minimum_recent`, `sort_by`, `order` | < 3ms |
| `GET /api/venues/heatmap` | Year × Venue publication matrix | `start_year`, `end_year` | < 4ms |
| `GET /api/venues/trends` | Yearly output for top venues | `limit` (default 10) | < 5ms |
| `GET /api/collaboration` | Ego-network for D3 force simulation | `author_id`, `limit` (up to 500), `min_weight`, `start_year`, `end_year` | < 7ms |
| `GET /api/network/stats` | Macro network totals + tie distribution | None | < 3ms |
| `GET /api/insights` | 4 data-backed analytical observations | None | < 4ms |

---

## 6. Design System & Styling Tokens

The visual style is governed by `tokens.css` and `intelligence.css`. It embodies an **editorial academic aesthetic** with high data density:

- **Typography**:
  - Display/Headings: Clean sans-serif system stack (`Inter`, `-apple-system`, `BlinkMacSystemFont`, `Segoe UI`, `sans-serif`) with strict roman posture (no italicized headers).
  - Data / Metrics: Monospace font stack (`JetBrains Mono`, `ui-monospace`, `Consolas`, `monospace`) for numbers, table cells, and IDs.
- **Color Palette (OKLCH)**:
  - Background: Soft neutral paper tones (`var(--surface)` / `var(--panel)`).
  - Lines / Borders: Subtle hairlines (`var(--line)`).
  - Accent / Primary: Academic deep indigo/navy (`var(--accent)`).
  - Secondary Accents: Emerald green for growth positive, muted rose for baseline negatives.
- **Component States**:
  - Standardized 8-state interactive support (`default`, `hover`, `focus-visible`, `active`, `disabled`, `loading`, `error`, `success`).

---

## 7. How to Run & Verify the Project

### Running the Backend
From `c:\DBLP_Project`:
```powershell
$env:PYTHONPATH="."
.\venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Running the Frontend
From `c:\DBLP_Project\dashboard`:
```powershell
npm run dev
# Dashboard launches at http://localhost:5173
```

### Running the Test Suite
- **Unit Tests (deterministic fixture)**:
  ```powershell
  $env:PYTHONPATH="."
  .\venv\Scripts\python.exe -m unittest backend/tests/test_api.py
  # Result: 23 passing tests
  ```
- **Live Smoke Tests (8.7M production DB)**:
  ```powershell
  $env:PYTHONPATH=".;backend"
  .\venv\Scripts\python.exe backend/tests/smoke_live.py
  # Result: 22 endpoints passing
  ```
- **Frontend Typecheck & Production Build**:
  ```powershell
  cd dashboard
  npm run typecheck
  npm run build
  # Result: 0 TypeScript errors, clean Vite production bundle
  ```

---

## 8. Current Limitations & Concrete Improvement Opportunities

For any future AI assistant or developer looking to enhance this platform, here are high-value areas ready for expansion:

1. **Individual Paper Search & Details (Highest Priority)**:
   - *Current state*: The global search bar (`SearchBar.tsx`) notes *"Paper search is planned"* and only returns authors and venues.
   - *Enhancement*: Add a `publications` search endpoint (`/api/publications/search?q=...`) and a paper detail modal / view showing title, year, venue, authors, and external DOI/DBLP links.
2. **Community Detection & Cluster Coloring in Network Graph**:
   - *Current state*: All co-author nodes share a uniform color scheme (scaled only by size and center focus).
   - *Enhancement*: Compute community clusters (e.g. Louvain modularity or connected sub-components) on the backend or in D3, coloring co-authors by research sub-groups.
3. **Graph & Table Export Capabilities**:
   - *Current state*: Visuals and data tables can only be viewed in the browser.
   - *Enhancement*: Add "Export to CSV" buttons on ranking tables and "Export SVG / PNG" buttons on the D3 network and Recharts figures.
4. **Dark Mode / Theme Toggle**:
   - *Current state*: Single light editorial theme.
   - *Enhancement*: Implement a theme switcher utilizing CSS custom property overrides (e.g., dark slate/navy theme).
5. **Mobile Navigation Drawer & Breakpoint Verification**:
   - *Current state*: Responsive CSS exists, but visual verification on real mobile viewports (320px–414px) has not been tested with automated browser tools.

