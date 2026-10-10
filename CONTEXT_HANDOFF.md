# DBLP Project: Session Handoff

Use this note to continue work in a new session. Read it first, then check `git status` before editing.

## Project at a glance

- **Purpose:** Local research discovery and analytics over about 8.7 million DBLP publication records.
- **Backend:** FastAPI in `backend/`.
- **Frontend:** React, TypeScript, and Vite in `dashboard/`.
- **Canonical data:** DuckDB at `database/dblp.duckdb` (local file; ignored by Git).
- **Main progress report:** [`RAG_PROGRESS_REPORT.md`](RAG_PROGRESS_REPORT.md). It has the current benchmark details and plain-language model guide.

## Current retrieval setup

- **Semantic title search:** MiniLM embeddings with Faiss HNSW. It finds titles with related meaning or wording.
- **Keyword title search:** Tantivy with BM25 is active. SQLite FTS5 remains as a fallback.
- **Combined results:** Reciprocal-rank fusion merges the two ranked lists. Candidate records are checked against canonical DuckDB before returning them.
- **Scope limit:** Search indexes titles, not full paper text. It cannot retrieve methods or findings missing from a title.
- **Local runtime:** Retrieval dependencies and model files are under `.work/rag-benchmark/`. The Tantivy index is under `database/indexes/dblp-title-v2/`. Both are local generated assets and ignored by Git.

## Latest retrieval results

- The 50-question DBLP-QA benchmark using Tantivy is saved at `reports/assistant/dblp-qa-tantivy-v1.json`.
- The saved FTS5 baseline is `reports/dblp_qa_retrieval_results.json`.
- Both runs returned the same target rank for all 50 questions: Recall@1 **0.18**, Recall@3 **0.20**, Recall@5 **0.22**, MRR@3 **0.1867**, and MRR@5 **0.1917**.
- Run times were measured separately: Tantivy averaged about **802 ms** (p95 **1,016 ms**); FTS5 averaged about **1,733 ms** (p95 **3,046 ms**). Treat this timing comparison as directional.
- In a paired 12-query development probe, both engines hit 11/12 targets at rank 8. Tantivy reduced mean full retrieval time from 1,273 ms to 753 ms. This is a small development set, not a held-out quality result.

## Answer models

- The configured primary route uses Groq Cloud with `qwen/qwen3.8-27b` when credentials are available.
- `qwen2.5-coder:7b` through Ollama is the configured local fallback. A successful live benchmark has not been recorded.
- Phi-3 Mini belongs to a legacy offline intent route; deterministic code executes its bounded query choices.
- RAGScholar model results (Mistral-7B, Phi-4, TinyLlama-1.1B, and FLAN-T5) are paper-reported comparison results, not models in this app's active answer route.
- Do not claim answer accuracy from retrieval scores or the two-prompt smoke run. The evidence and limits are documented in the progress report.

## Useful files

- `backend/app/services/title_retrieval.py` — semantic and keyword title retrieval.
- `backend/app/services/agentic_rag.py` — answer planning and synthesis.
- `backend/app/routes/assistant.py` — assistant API dispatch.
- `scripts/build_tantivy_title_index.py` — build the Tantivy title index.
- `scripts/evaluate_dblp_qa.py` — run the DBLP-QA retrieval evaluation.
- `scripts/requirements-retrieval-benchmark.txt` — isolated retrieval benchmark dependencies.
- `RAG_PROGRESS_REPORT.md` — full progress, definitions, and results.

## Next useful step

Review retrieval against a larger, user-checked question set. Include both questions answerable from titles and questions that require abstracts. Keep answer-quality evaluation separate from retrieval metrics.

## Large and private files

`.gitignore` excludes local databases, indexes, caches, model/runtime files, archives, JSONL datasets, and the root files `collaborations.txt` and `com-dblp.ungraph.txt`. Git ignore rules do not remove files already committed. Check `git status --ignored --short` if a large local file still appears.

Keep `.env` and API credentials private. Do not add large source data or generated indexes to commits.

## Working tree note

At handoff time, the repository already had a mix of modified and untracked project files. Review `git status` and preserve the user's existing work; do not reset, clean, or discard files as a shortcut.
