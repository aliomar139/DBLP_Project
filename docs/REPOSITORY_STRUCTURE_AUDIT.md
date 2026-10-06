# Repository Structure Audit and Cleanup Record

Audit and cleanup date: 2026-10-06

## Changes applied

Root-level operational scripts and project documents are now grouped by purpose. `tokens.css` is under the dashboard source styles and the app entry point imports it from there. The benchmark runner anchors its backend import to the repository root so moving it under `scripts/` does not break the `backend` package import. Documentation references were updated.

The raw DBLP XML was deleted after verifying the compressed archive's adjacent MD5 checksum. The compressed archive remains at `data/compressed/dblp.xml.gz`. Sixteen stale assistant run logs were removed. No project Python bytecode caches were present outside the virtual environment. The DuckDB database and FAISS/SQLite search index remain in place.

## Current organization

```text
.
├── backend/                         Python API, services, schemas, tests
├── dashboard/                       React + TypeScript application
│   └── src/styles/tokens.css        Dashboard design tokens
├── data/                            Source schema, compressed archive, fixtures
├── database/                        Active DuckDB, cache, manifests, indexes
├── docs/
│   ├── architecture/                Platform overview and technical report
│   ├── assistant/                   Assistant plans, reviews, progress
│   ├── operations/                  Codex handoff
│   ├── product/                     Product brief
│   └── prompts/                     Agentic RAG migration prompt
├── reports/assistant/               Durable assistant evaluations and results
├── scripts/                         Ingestion, indexing, evaluation, operations
│   ├── run_benchmark.py
│   └── start_gpu_server.bat
└── README.md
```

## Architecture recommendations

- Keep `backend/` and `dashboard/` as separate deployable application areas. Keep their dependency manifests close to each application.
- Keep `data/` for input snapshots, schema, and small fixtures. Keep `database/` for the active query database and derived indexes while consumers use these stable paths.
- Avoid a broad `storage/` move for now. If outputs become configurable, consider a later `artifacts/` root for rebuildable databases and indexes, with a manifest describing source version and build procedure. Migrate only after path configuration is centralized and verified.
- Keep reproducible tools in `scripts/`. Keep durable benchmark findings in `reports/`; keep transient logs out of that tree unless intentionally retained under a dated run directory.
- Keep project documentation in `docs/` by topic, with `README.md` as the root entry point. Link plans/reviews to results instead of copying evaluation conclusions across files.

## Follow-up opportunities

`reports/` currently mixes multiple result types and has assistant-specific results in `reports/assistant/`. A later documentation-only pass could establish `reports/benchmarks/` and `reports/runs/<run-id>/`, then update links. No result files were moved because report references and their intended retention need review together.

`start_gpu_server.bat` contains machine-specific absolute paths for a local llama server and model. It is now correctly categorized as an operational helper, but should be parameterized before sharing with other machines.

## Verification

The benchmark script was syntax-checked without running its live model queries. A dashboard production build is still to be confirmed; Vite's esbuild config step failed with `spawn EPERM` in the restricted environment.
