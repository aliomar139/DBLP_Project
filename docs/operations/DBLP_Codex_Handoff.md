# DBLP Research Assistant — Chat Handoff

Repository: `C:\DBLP_Project`.

## Current assistant architecture

- Backend: FastAPI. Frontend: React/TypeScript/Vite. Query endpoint: `/api/assistant/query`.
- The primary path is `backend/app/services/agentic_rag.py`, using local Ollama model `qwen2.5-coder:7b`. The model plans read-only DuckDB queries or hybrid title searches, then writes a concise answer grounded in returned evidence.
- SQL execution uses a read-only DuckDB connection, permits only one `SELECT`/`WITH` statement, caps returned rows, applies memory/thread settings, and interrupts after eight seconds. Failed SQL gets one model correction attempt.
- Ollama requests use CPU options `num_thread=8`, `num_ctx=2048`. Planning and synthesis token limits are 120 and 230 respectively.
- The response preserves `status`, `answer`, `sources`, `calculations`, and `request_id`; recognized authors, venues, papers, and topics include dashboard links. SQL and result row counts are attached as calculation provenance.
- If the configured Ollama model is unavailable or the agentic call fails, `/api/assistant/query` falls back to the older deterministic bounded tools and Phi-3 Mini intent interpreter. That path remains useful offline but supports a narrower set of phrasings and data operations.

## Evidence and safety

- DuckDB is the canonical source at `database/dblp.duckdb`; the verified title index is `database/indexes/dblp-title-v2` and covers 8,738,331 titles.
- The agentic planner is schema-aware for publications, authors, authorship, venues, institutions and affiliations, citations, and topic tables. Do not reintroduce canned refusals for tables that exist in the active database.
- Title retrieval returns candidate bibliographic records. Titles alone do not establish methods, findings, or paper contents.
- Never remove read-only execution safeguards or expose model-generated SQL without validation. Continue to attach structured sources and calculations to answers.
- Avoid describing the system as universally accurate. The live examples recorded by the project owner are spot checks, not a broad held-out quality evaluation.

## Current limitations and verification

- Ollama must be installed, running, and have `qwen2.5-coder:7b` available for the primary path. Otherwise the API uses the bounded legacy fallback.
- The fallback interpreter and agentic planner have different capabilities; the fallback must not be described as the primary assistant.
- Whole-request latency, answer grounding across a reviewed set, multi-user load, and behavior when Ollama is idle remain evaluation areas. Do not claim these are established without fresh measurements.
- `scripts/test_agentic_rag.py` contains the agentic smoke harness. Run only when explicitly requested; do not treat earlier live spot checks as a fresh test run.

## Important files

- `backend/app/routes/assistant.py` — primary/fallback dispatch and response contract.
- `backend/app/services/agentic_rag.py` — Ollama planning, guarded SQL execution, title retrieval, and answer synthesis.
- `backend/app/services/local_query_interpreter.py` — legacy Phi-3 Mini intent interpreter used by the offline fallback.
- `backend/app/services/assistant_tools.py` — fixed, bounded legacy evidence tools.
- `backend/app/services/title_retrieval.py` — local semantic and SQLite FTS title retrieval.
- `docs/assistant/progress.md` — implementation milestones and evaluation notes.
