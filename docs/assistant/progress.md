# Hybrid RAG implementation status

## 2026-10-03: Agentic RAG is the primary API path

`/api/assistant/query` now dispatches to the local Ollama Agentic RAG service
when `qwen2.5-coder:7b` is available. The deterministic bounded routes and
Phi-3 Mini interpreter remain an offline/error fallback. Agentic Ollama calls
use the CPU settings `num_thread=8`, `num_ctx=2048`, with 120 planning tokens
and 230 synthesis tokens. Generated SQL is screened as a single `SELECT`/`WITH`
statement, external file/source reader functions are rejected, and DuckDB is
opened read-only.

This integration and documentation update has not been tested in this pass.
Prior live spot checks described by the project owner are not a substitute for
a reviewed end-to-end evaluation; latency, grounding, and concurrency remain to
be measured. See `../operations/DBLP_Codex_Handoff.md` for the current architecture summary.

## 2026-10-01: schema-aware natural-language query path

Added a local-model planner that can express general read-only retrieval and
aggregation requests over the trusted publication, author, venue, and authorship
tables. It emits a bounded JSON query plan, which application code validates,
compiles to parameterized SQL, and executes through the existing read-only query
service. The assistant then drafts an answer from returned rows and attaches that
query result as calculation evidence. Title-discovery plans use the verified
semantic and SQLite FTS sidecar. The existing deterministic routes and fixed-intent
interpreter remain fallbacks.

The dashboard prompt now invites free-form questions. This code change has not been
tested or evaluated in this pass; broad paraphrase coverage, plan accuracy, answer
grounding, and latency remain unmeasured. The query surface deliberately excludes
untrusted generated tables and data absent from DBLP bibliographic records.

The repaired database is now the single canonical source at
`database/dblp.duckdb`. It contains decoded author names and rebuilt title-based
classification/count tables. See `candidate-extension-review.md` and the v2
verification reports for current results. The earlier milestone notes below
describe the original implementation baseline.

## Current continuation status (2026-09-28)

The user approved repaired v2 as the application's DBLP source after review. It
fixes title fidelity and author-name decoding, rebuilds title-based project
summaries, and preserves all publication IDs, author IDs, and authorship links.
It now occupies the canonical `database/dblp.duckdb` path; the old and
intermediate database copies have been removed. The full-title index is verified
against it and now serves bounded assistant paper-discovery requests.

Milestone 3 is complete for the repaired canonical database: a versioned SQLite FTS5
and 384-dimensional local MiniLM/Faiss HNSW scalar-8 sidecar covers all 8,738,331
nonempty titles. Independent verification matched every ordered publication ID
and every title to the canonical database; Faiss, ID map, and keyword rows each
contain 8,738,331 records. There are zero empty-title exclusions in this repaired
database. Its fingerprint stayed unchanged during promotion. Runtime checks the
approved database fingerprint and index coverage before loading the sidecar.
Every candidate ID is reloaded from the canonical read-only DuckDB before it is
returned as an assistant source.

The final resumed builder pass processed its 204,800 new vectors in 1,699 seconds,
while also replaying 8.53 million saved IDs to reconstruct the complete keyword
index. The final builder-reported peak was 9.93 GiB. Final artifacts are about
7.26 GB (5.73 GB Faiss plus 1.52 GB SQLite); peak temporary disk usage was not
captured. The separate verifier completed in 29.8 seconds. A 12-query development
probe set hit its exact title targets at 10/10 for both retrieval modes and its
paraphrase targets at 12/12 semantic, 10/12 lexical, and 11/12 hybrid. All returned
candidate IDs were valid. This is a small development set, not held-out quality
evidence. The earlier lexical benchmark took 4.21 s mean and 6.61 s p95.

The assistant now routes explicit paper-discovery questions through the full
local semantic and SQLite FTS index, merges at most 50 candidates from each
retriever, and validates returned records against the canonical DBLP tables. A
12-item development run retrieved 11/12 expected records in the top eight. The
retrieval-only mean was 2.00 s and p95 2.45 s after warmup; runtime initialization
including the full database fingerprint check took 7.11 s. Peak process working
set was 6.53 GiB. One end-to-end API smoke case returned HTTP 200 in 1.86 s with
the expected paper citation and structured claim validation. These are small
development measurements, not the reviewed-set answer evaluation or a claim
that the 10-second ready-service p95 target has been established.

On 2026-09-28, Phi-3 Mini was connected as a fallback question interpreter after
a 20/20 reviewed development set passed. It runs locally and returns only a
bounded intent plus extracted fields; existing parameterized DBLP tools still
resolve entities, retrieve records, calculate results, and validate claims. It
does not write answers or SQL. Common deterministic routes run first, so the
model is used only for phrasing the current router does not recognize. The
generation mean was 3.50 seconds, p95 5.70 seconds, model load 5.93 seconds,
and peak working set 4.07 GiB. This small probe does not establish arbitrary
phrasing accuracy or multi-user capacity. The single model instance serializes
inference; conversation history and account-specific state are not implemented.

Milestone 4 has an initial deterministic implementation on the active database:
exact author/venue and title lookups, publication counts, year trends, venue
rankings, author/venue comparisons, shared-record coauthorship, and explicitly
labeled title-keyword classifications. SQL is fixed-form and parameterized,
read-only, limited to 9.5 seconds and 60 returned rows, configured for at most
4 GiB per connection, and capped at two concurrent assistant queries. Responses
include verified local entity links and calculation filters/database version.
Controlled templates still produce all user-facing answer wording.

Exact-title lookup and topic classification continue to use their existing
bounded DuckDB tools. Author and venue
rankings use distinct publication records; collaborator rankings use distinct
shared publication rows. One title-keyword
classification request took 6.41 seconds under the final 4 GiB query-memory cap; this is one
observation, not a latency percentile.

Milestone 5 has initial structured claim, number, source-reference, and local-link
validation for controlled answers. The earlier four-case answer-writing probe
failed 3/4 because the generated prose inferred gender. That model role remains
unused. The separate 20-case query-interpreter evaluation passed; because it
emits structured routing fields only, it cannot generate pronouns or factual
answer text. Claim validation still does not provide semantic entailment
checking for arbitrary language-model prose.

Milestone 6 now has a dedicated assistant dashboard page, versioned in-memory
answer caching (active-database file fingerprint plus a hash of normalized
question), and request/SQL timing diagnostics that omit question text. Existing
dashboard routes remain available. The new assistant UI displays loading, error,
answer/limitation states, claim references, DBLP records, and calculation filters/results.
These timings are instrumentation only; a representative ready-service latency
and cache-hit evaluation has not yet been run.

## Completed and checked

The repository has no Git metadata and no applicable AGENTS.md was found in the
repository/ancestor inspection. Baseline copies of edited backend files are under
`.work/trusted-rag-baseline`.

Read `trusted-data-contract.md` for the backend/frontend explanation, approved
fields/calculations, excluded evidence, and source inspection. Read
`title-repair-review.md` for the separate candidate and the author-name extraction
finding. `feasibility-review.md` contains measured local embedding/index results
and explicitly qualified projections.

At the earlier baseline, 61 distinct existing/boundary tests passed across `test_trusted_boundary`,
`test_api`, `test_final_intelligence`, and `test_strategic_intelligence`. Two additional
title-repair tests passed, including entity/nested-text recovery, unchanged source
hash and IDs, refusal to overwrite, mismatched-source rejection, and rejection of
unapproved XML resources. Resource warnings were treated as errors for the final
repair test run. The frontend TypeScript/Vite production build passed. Those were
63 distinct baseline tests, not a completed assistant release evaluation. The latest
backend and dashboard regression run passed all 76 tests in 53.5 seconds; the
frontend TypeScript/Vite production build also passed after adding the assistant page.

Read-only corpus audit: 8,738,331 publications, 8,730,137 eligible active titles,
8,194 active exclusions, zero publication-ID/key duplicates and orphan authorship
rows. It found 303 repeated authorship pairs (304 extra rows) and 29,414 repeated
paper-topic pairs. The new contract requires distinct publication counts.

The requested candidate repairs 205,674 titles and recovers all 8,194 empty titles.
Every publication ID and key stays unchanged. Independent comparisons passed with
zero unintended metadata, author, authorship, or venue changes. The active file's
SHA-256 remained unchanged. The candidate is not activated and its legacy
title-derived tables remain stale. It also retains author strings whose XML
entity decoding differs on 1,185,299 publication records.

The local embedding benchmark measured 378.05 titles/second and a 0.528 GiB process
peak over 20,012 titles; full embedding projects to 6.42 hours, excluding index work
and sustained-load effects. No full index or assistant latency target has been
verified. The keyword scaling check shows a recall/latency tradeoff that still
needs hybrid evaluation.

## Files changed or added

| Files | Purpose |
| --- | --- |
| `backend/app/routes/assistant.py` | Deterministic request routing, validated answers, hashed versioned answer cache, and timing-only diagnostics. |
| `backend/app/services/local_query_interpreter.py` | Lazy local Phi-3 intent/slot fallback, strict plan validation, and serialized inference. |
| `scripts/benchmark_local_query_interpreter.py`, `reports/assistant/local-query-interpreter-v1.json` | Fixed 20-case intent/slot evaluation and local runtime measurements. |
| `backend/app/services/assistant_tools.py` | Bounded read-only SQL forms for counts, author/venue rankings, trends, comparisons, exact lookup, collaborator rankings, pair coauthorship, and title classification. |
| `backend/app/services/assistant_claim_validation.py` | Structured claim/source/calculation and local dashboard-link validation for controlled responses. |
| `backend/app/schemas/models.py` | Bound question size, reject history/extra input, and define structured answer, source, calculation, and status fields. |
| `backend/app/services/evidence_contract.py` | Explicit approved fields/calculations, classification label, and default-deny exclusions. |
| `backend/tests/test_trusted_boundary.py` | Contract, generated-evidence exclusion, request limits, independent counts, source links, comparisons, coauthorship, claim validation, and cache privacy tests. |
| `dashboard/src/pages/Assistant.tsx`, `dashboard/src/assistant.css`, `dashboard/src/api.ts`, `dashboard/src/App.tsx` | Assistant question form, structured answer/source/provenance display, API typing, and a new navigation route. |
| `scripts/setup_local_explanation_model.py`, `scripts/benchmark_local_explanation_model.py`, `scripts/requirements-local-inference.txt` | One-time local candidate setup and isolated grounding/performance benchmark; candidate is not integrated. |
| `backend/tests/test_title_repair.py` | Candidate source/ID safety and XML recovery tests. |
| `backend/tests/test_api.py`, `test_final_intelligence.py`, `test_strategic_intelligence.py` | Replace obsolete assistant tests that expected fabricated responses; retain other dashboard tests. |
| `scripts/audit_trusted_data.py`, `audit_xml_title_fidelity.py` | Repeatable read-only provenance and extraction audits. |
| `scripts/prepare_title_repair_candidate.py`, `verify_title_repair_candidate.py` | Build and independently verify a separate title-only candidate; no activation command. |
| `backend/app/services/title_retrieval.py` | Version-checked local ONNX/Faiss/FTS retrieval; DuckDB revalidates every result ID. |
| `scripts/evaluate_assistant_title_retrieval.py`, `reports/assistant/connected-title-retrieval-v1.json` | Development recall, latency, memory, and assistant-route smoke measurements. |
| `scripts/setup_retrieval_benchmark.py`, `requirements-retrieval-benchmark.txt` | Isolated local retrieval dependencies and pinned model setup. |
| `scripts/benchmark_retrieval.py`, `benchmark_keyword_scale.py` | Offline embedding/vector/keyword feasibility and scale checks. |
| `docs/assistant/*.md`, `retrieval-probes-v1.json`, `evaluation-plan-v1.json` | Contract, review reports, development probes, and proposed release cases. |
| `reports/assistant/*.json` | Actual audit, validation, timing, and resource observations. |
| `database/active-source-v2.json` | Canonical database fingerprint and approved source record. |
| `.work/rag-benchmark/*` | Local model, dependencies, sample vectors, experimental indexes; not active retrieval. |

The active database, parser, shared search/embedding services, prior dashboard
routes, and visualization code have not changed. In particular, legacy dashboard
search still uses its previous synthetic signals and must not become assistant
evidence.

## Remaining gates and limitations

The canonical repaired database retains copied legacy
snapshots for citations, assigned institutions, forecasts, citation lineage, and
external metadata; those remain excluded from assistant evidence. Existing
dashboard pages may still display those legacy values. The assistant's title
index is connected and checks each returned ID against canonical DuckDB. No
records were merged, split, or removed during the repair.

Milestones 1-3 are complete for the canonical source and its verified sidecar.
Milestone 4 has bounded tools, deterministic routing, and a local model fallback
for phrasing inference. The fallback has passed only a 20-case development probe;
broader reviewed questions, concurrency/resource evaluation, ready-service
latency, cache/error rates, and regression verification remain open. Semantic
paper retrieval remains title-only, so it cannot establish paper methods/findings.
The endpoint answers only routed, bounded queries and returns structured
limitation states otherwise. Not every reviewed evaluation question is routed yet.

There is not yet a measured reviewed-set answer accuracy, claim-validation rate,
cache hit/error rate, or ready-service mean/p95 latency. Final temporary disk peak
was not captured. No 10-second or zero-future-error claim is made.
