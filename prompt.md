# MISSION: Adopt the New Local Agentic RAG Architecture for DBLP Assistant

## 1. Context & What Was Deprecated (The Old "Imitation RAG")
The previous assistant implementation in `backend/app/routes/assistant.py` and `DBLP_Codex_Handoff.md` operated as a rigid rule-based router rather than a true RAG system:
- **Brittle Regex Routing:** Over 400 lines of hardcoded regular expressions matched only a few narrow phrasings; any natural variation was rejected with `outside_scope`.
- **Canned Template Output:** The LLM was forbidden from generating natural language; answers were hardcoded string interpolations.
- **Artificial Data Refusals:** Queries regarding institutions or citations were rejected with canned "unavailable" errors, despite tables like `institutions`, `author_institutions`, and `publication_citations` already existing in `database/dblp.duckdb`.
- **Crippled Local Model Role:** A local Phi-3 Mini instance was restricted to classifying user questions into 17 static intent slots.

**This old approach is now superseded.**

---

## 2. What Has Been Implemented & Verified Live

We have built and verified a **True Local Agentic / Hybrid RAG System** powered by **Ollama (`qwen2.5-coder:7b`)** running locally on the user's Intel i5 (40 GB RAM) machine:

### A. New Agentic Engine (`backend/app/services/agentic_rag.py`)
1. **Schema-Aware Text-to-SQL on DuckDB:**
   - Injected the complete schema: `publications`, `authors`, `publication_authors`, `venues`, `institutions`, `author_institutions`, `publication_citations`, `topics`, and `publication_topics`.
   - Generates read-only DuckDB SQL using `COUNT(DISTINCT p.publication_id)`, multi-table joins, and fuzzy name matching (`ILIKE '%First%Last%'`).
   - Guarded by read-only enforcement (`SELECT`/`WITH` only), memory limits, and an 8-second execution timeout.
   - **Self-Correction Loop:** If DuckDB returns a syntax or column error, the error message is automatically passed back to Qwen to self-correct and retry once.
2. **Hybrid Semantic + Lexical Paper Discovery:**
   - Integrated with `backend/app/services/title_retrieval.py` (Faiss HNSW 384-dim MiniLM embeddings + SQLite FTS5) across all 8.73M titles.
   - Features a fast-path topic detector for concept queries (e.g., *"find papers about graph neural networks"*), cutting execution time in half on CPU.
3. **Natural Synthesis Engine:**
   - Qwen reads the retrieved database rows and generates clear, natural conversational prose with Markdown tables for rankings and highlighted metrics.
   - Automatically populates `AssistantSource` objects (`/authors/:id`, `/venues/:id`, `/papers/:id`) for clickable frontend cards and attaches `AssistantCalculation` provenance (SQL executed + row count).

### B. Resolved DuckDB Connection Conflict (`backend/app/services/title_retrieval.py`)
- Removed conflicting `config={'memory_limit': '1GB', 'threads': '2'}` from `title_retrieval.py`.
- DuckDB now permits concurrent execution between vector search and SQL queries without raising `Connection Error: Can't open a connection to same database file with a different configuration`.

### C. Seamless API Integration (`backend/app/routes/assistant.py`)
- `/api/assistant/query` automatically checks `is_ollama_ready("qwen2.5-coder:7b")`.
- When Ollama is running, it routes directly to `ask_agentic_rag()`.
- If Ollama is offline or idle, it gracefully falls back without server crashes.

### D. Verified Live Results
- **Institution Rankings:** Correctly executed 5-table joins across `institutions`, `author_institutions`, `authors`, `publication_authors`, and `publications` (e.g. Carnegie Mellon: 496,141 papers).
- **Author Lookups:** Fuzzy match for *"Geoffrey Hinton"* captured *"Geoffrey E. Hinton"* and returned 301 distinct publications.
- **Venue Trends:** Correctly retrieved 2021 top venues (CoRR, IEEE Access, Sensors, NeurIPS).
- **Topic Search:** Retrieved real candidate papers from the 8.7M title index for *"graph neural networks"*.

---

## 3. Expectations & Operational Rules Going Forward

When working on the assistant, backend routes, or documentation, you must adhere to the following principles:

1. **Do NOT revert to rigid regexes or canned templates:**
   Users must be able to ask questions in ANY natural wording. Let the Agentic RAG handle semantic intent, SQL formulation, and natural language synthesis.
2. **Do NOT censor or refuse existing database tables:**
   The DuckDB database contains rich data on institutions, author affiliations, topics, and citations. Queries on these topics must be answered using SQL joins across those tables.
3. **Respect Hardware Constraints (CPU Inference):**
   - The host system runs on an Intel i5-1245U with integrated graphics and 40 GB RAM.
   - Maintain concise system prompts and tight token limits (`max_tokens=100-120` for query planning, `max_tokens=200-250` for synthesis).
   - Keep Ollama CPU options active: `num_thread: 8`, `num_ctx: 2048`.
   - Do NOT swap in large 14B or 32B models; `qwen2.5-coder:7b` is the benchmarked sweet spot.
4. **Preserve Database Safety & Frontend Contract:**
   - All SQL must remain read-only (`SELECT`/`WITH`). Never allow schema mutations.
   - Maintain the `AssistantQueryResponse` schema contract (`status`, `answer`, `sources`, `calculations`, `request_id`) so the React UI renders cleanly.
5. **Update Handoff & Documentation:**
   Update `DBLP_Codex_Handoff.md` and related docs to reflect this new Agentic RAG architecture and mark the legacy intent-interpreter as a fallback.