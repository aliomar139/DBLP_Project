# RAG Progress Report: DBLP Research Intelligence vs. Scientific Abstract RAG

**Status:** Active  
**Author:** DBLP Research Intelligence Team  
**Last Updated:** October 6, 2026  
**Reference Benchmark:** DBLP-QA (Neekhra, Nilles, & Schenkel, SCOLIA '26)

---

## 1. Executive Summary & Purpose

This report compares the project’s metadata-centered assistant with RAGScholar, a paper-content system that retrieves abstracts. The systems answer different kinds of questions: our system is built for DBLP record discovery and relational analysis, while RAGScholar’s abstract corpus can support questions about paper content.

The project now uses Groq Cloud with `qwen/qwen3.8-27b` as the primary model for agentic planning and answer synthesis when credentials are configured. Failed cloud calls fall back to Ollama’s local `qwen2.5-coder:7b`. A two-prompt smoke benchmark completed through both streaming and synchronous paths on October 6. It records latency and successful responses, not answer quality or ROUGE-L.

This update keeps the original RAGScholar comparison, corrects older claims that no longer match the implementation, and separates retrieval measurements from generation measurements.

---

## 2. Definitions & Approach Overviews

### A. RAGScholar (Abstract-Reading Scientific RAG)
* **Definition:** A document-grounded RAG system designed to answer scientific questions using publication abstracts.
* **Architecture reported by the paper:**
  * **Knowledge Base:** About 4.6 million computer science abstracts enriched from DBLP records using Semantic Scholar.
  * **Retriever:** Apache Lucene BM25 over titles, abstracts, authors, and venues, with the paper reporting `k1=1.2` and `b=2.0`.
  * **Context Formulation:** Top-k concatenated documents (`Top-k-CD`), with k values including 3 and 5.
  * **Generator:** The paper evaluates instruction-tuned models including Mistral-7B, Phi-4, TinyLlama-1.1B, and FLAN-T5.
* **Primary Objective:** Answer questions about paper definitions, methods, and findings, such as “What is CtRL-Sim?” or “Why is differential diagnosis difficult for physicians?”

### B. DBLP Research Intelligence (Our System — Agentic Relational RAG)
* **Definition:** A schema-aware assistant that combines relational queries with title-level hybrid retrieval over DBLP bibliographic records.
* **Architecture:**
  * **Knowledge Base:** Canonical DuckDB database (`database/dblp.duckdb`) containing approximately 8.7 million publication records, with author, venue, topic, and other project-derived analytical tables.
  * **Title Retriever:** Local sidecar (`database/indexes/dblp-title-v2`) combining 384-dimensional MiniLM embeddings in Faiss HNSW with SQLite FTS5 over 8,738,331 titles. Retrieved IDs are validated against DuckDB.
  * **Planner and Generator:** Groq Cloud using configured model `qwen/qwen3.8-27b` is primary when credentials are present. On call failure, the dispatcher falls back to Ollama `qwen2.5-coder:7b`. Structured questions execute through validated query plans; discovery questions use title retrieval.
  * **Abstract Enrichment:** A separate SQLite cache can store abstracts retrieved from OpenAlex and Semantic Scholar. Chat searches check for cached abstracts; catalog export fetches missing abstracts. The project does not have an indexed abstract corpus.
* **Primary Objective:** Support bibliographic discovery, author and venue questions, counts, rankings, and other relational analysis. Abstract-dependent responses rely on abstracts available in the cache.

### C. Legacy Bounded Interpreter (Offline Fallback)
* **Definition:** A local intent classifier and bounded executor for supported queries when the agentic route cannot complete.
* **Architecture:** Fixed intent patterns and a local Phi-3 Mini model map questions to predefined slots, then deterministic database tools execute the supported operation. This path covers fewer questions than the main agentic route.

### D. Why These Models and Retrieval Components

**Primary model: Groq `qwen/qwen3.8-27b`.** The project uses a hosted 27B model for planning and synthesis so those generation steps do not depend on laptop CPU inference. The October 6 smoke run confirms the configured model completes the current assistant path in 3.15-9.58 seconds across two prompts and two request modes. That is an operational check, not evidence that this model is more accurate than Mistral, Phi, or other hosted models. The repository has no same-prompt, same-evidence quality comparison that would justify calling it the best model.

**Fallback model: Ollama `qwen2.5-coder:7b`.** This is the configured local alternative when a Groq request fails, preserving an offline route without requiring another hosted provider. Its trade-off is local hardware dependence and likely slower generation. The fallback was not available in the October 6 restricted-network run, so this report does not claim a successful live fallback benchmark. The legacy Phi-3 Mini interpreter remains a smaller, intent-limited option; it does not replace the general answer generator.

**Semantic retrieval: MiniLM embeddings with Faiss HNSW.** Titles are embedded locally into 384-dimensional vectors. HNSW searches an approximate-neighbor graph instead of calculating similarity against every one of 8.7 million titles for each query; the index uses 8-bit scalar quantization to reduce vector storage. This makes broad topical and paraphrase discovery practical on a local sidecar, with an explicit recall-versus-resource trade-off. It retrieves by title meaning, not by methods or findings absent from the title.

**Lexical retrieval: SQLite FTS5.** A full-text inverted index can match literal terms, acronyms, names, and technical phrases that an embedding model may rank poorly. It runs locally beside the vector index and does not require a separate search service. The assistant combines the semantic and lexical ranked lists with reciprocal-rank fusion (RRF), which rewards items appearing in both lists without requiring their raw scores to share a scale. Candidate lists are bounded before canonical DuckDB validation.

The two retrievers were selected to cover different query shapes over a title-only corpus: semantic similarity for wording variation and lexical matching for exact vocabulary. The 12 development probes show 100% paraphrase target hit@10 for semantic search, 83.3% for keyword search, and 91.7% for the fused hybrid. On this small set, hybrid did not beat semantic search alone, so the probe results support feasibility but do not establish a measured quality gain from fusion. The lexical timing in that probe harness also averaged about 4.21 seconds (p95 6.61 seconds); this is a warning to profile and optimize the lexical path, not proof of production latency.

---

## 3. Key Differences Between Approaches

| Dimension | RAGScholar (Paper) | DBLP Research Intelligence (Our Project) |
| :--- | :--- | :--- |
| **Data Scope** | Paper metadata enriched with an indexed abstract corpus | Approximately 8.7M bibliographic records and project-derived relational data |
| **Abstract Availability** | Abstracts are a core retrieval source | DBLP records contain metadata; optional abstracts live in a separate cache |
| **Retrieval Mechanism** | Lucene BM25 over titles and abstracts | DuckDB query plans for structured questions; Faiss HNSW + SQLite FTS5 over titles for discovery |
| **Query Flexibility** | Document retrieval and synthesis | Relational analytics plus bounded title discovery |
| **Generation Path** | Models and settings reported by the paper | Groq `qwen/qwen3.8-27b` primary; local Ollama `qwen2.5-coder:7b` fallback |
| **Response Contract** | Text answer with source-attributed paper IDs | Answer, DBLP source records, and calculation provenance |

---

## 4. Where Each Approach Is Better

```
                        ┌────────────────────────────────────────────────────────┐
                        │              Scholarly Information Space                │
                        └───────────────────────────┬────────────────────────────┘
                                                    │
                 ┌──────────────────────────────────┴──────────────────────────────────┐
                 ▼                                                                     ▼
   [ Scientific Content & Findings ]                                   [ Bibliometrics & Ecosystem Analytics ]
   - "What is CtRL-Sim?"                                               - "Who are the top authors in GNNs?"
   - "How does algorithm X improve speed?"                             - "Compare CMU vs Berkeley AI citations"
   - "Explain why differential diagnosis is hard"                      - "What was Hinton's publication output in 2021?"
                 │                                                                     │
                 ▼                                                                     ▼
  RAGScholar has the abstract evidence                                  DBLP system queries relational records
```

### Where RAGScholar Has an Advantage
1. **Paper-content questions:** Abstract retrieval can support questions about methods, definitions, and reported findings when those details do not appear in a title.
2. **Abstract-level matching:** Queries may match terms that occur in abstract text but not in the paper title.
3. **Cross-paper content synthesis:** Retrieved abstracts provide direct source material for comparing papers.

### Where DBLP Research Intelligence Has an Advantage
1. **Relational analytics:** DBLP tables support counts, rankings, and filters across millions of records.
2. **Entity relationships:** The project can answer supported questions involving authors, venues, topics, and citation or collaboration data.
3. **Metadata breadth:** DBLP coverage includes records that may not have abstracts, including books and proceedings.
4. **Database provenance:** Structured responses can include the matched records and calculation details.

These strengths are complementary. Our title index cannot match RAGScholar’s abstract search for abstract-only concepts, and the available benchmark figures do not compare the same corpus or generation path.

---

## 5. Empirical Benchmark Comparison (DBLP-QA Test)

The repository contains a 50-question DBLP-QA retrieval result and paper-reported RAGScholar figures. The figures below compare retrieval outcomes on the benchmark, but they should not be read as a controlled comparison of identical indexes: RAGScholar searches titles and abstracts, while this project’s DBLP index searches titles.

### A. Retrieval Evaluation (RQ1)

| Metric | RAGScholar (Lucene BM25, paper-reported) | DBLP Hybrid Title Index (repository result) | Interpretation |
| :--- | :--- | :--- | :--- |
| **Indexed Content** | Titles and abstracts | Titles only | Abstract-only query terms are unavailable to our index |
| **Recall@1** | **0.8800** (44 / 50) | **0.1800** (9 / 50) | The benchmark includes many content questions |
| **Recall@3** | **1.0000** (50 / 50) | **0.2000** (10 / 50) | Different evidence coverage limits direct comparison |
| **Recall@5** | Not reported | **0.2200** (11 / 50) | Repository artifact reports title-index result |
| **MRR@3** | **0.9300** | **0.1867** | Paper-reported and repository-reported values |
| **Latency** | Server-grade, paper setup | Varies by query and run | Do not compare the prior approximate latency note as a controlled measurement |

The repository’s detailed result is [`reports/dblp_qa_retrieval_results.json`](dblp_qa_retrieval_results.json). For example, a Time Warp question targets “Corolla partitioning for distributed logic simulation of VLSI circuits”; the terms asked about do not appear in that title. An abstract index can retrieve evidence that a title-only index cannot see.

The current full-corpus title-index evaluation is a separate 12-probe development set in [`reports/assistant/full-retrieval-evaluation-v2.json`](assistant/full-retrieval-evaluation-v2.json). Its hybrid paraphrase target hit rate is 91.7% at rank 10. The probes are not held out or user-reviewed and do not replace the DBLP-QA evaluation. In the evaluation script, Faiss lookup averaged 4.4 ms (search stage only; encoding and ID mapping excluded), while the SQLite FTS5 query averaged 4.21 seconds with a 6.61-second p95. The FTS5 timing is a material bottleneck in that probe run and should be optimized before making a latency claim for hybrid retrieval.

### B. Generation Quality (RQ2 & RQ4)

| Model & Setting | Context Strategy | ROUGE-L F1 | Latency / Call | Evidence status |
| :--- | :--- | :--- | :--- | :--- |
| **Mistral-7B (RAGScholar paper)** | Top-5 concatenated abstracts | **0.3400** | GPU in paper setup | Paper-reported |
| **Mistral-7B (RAGScholar paper)** | No-context baseline | **0.2100** | GPU in paper setup | Paper-reported |
| **Phi-4 (RAGScholar paper)** | Top-3 concatenated abstracts | **0.3700** | GPU in paper setup | Paper-reported |
| **Phi-4 (RAGScholar paper)** | No-context baseline | **0.1000** | GPU in paper setup | Paper-reported |
| **Qwen `qwen/qwen3.8-27b` (ours)** | Live assistant retrieval and synthesis | Not measured | 3.15–9.58 s in smoke run | Two prompts; no correctness score or repeated trials |
| **Qwen2.5-Coder:7B (local fallback)** | Same RAG dispatcher after online failure | Not measured in successful run | Not measured | Ollama was unavailable during the restricted-network run |

On October 6, 2026, `scripts/run_benchmark.py` completed two prompts using the configured Groq model. Each prompt ran once through streaming and once synchronously. The successful run had no fallback warning.

| Prompt | Streaming total | Time to first content | Synchronous total | Sources |
| :--- | ---: | ---: | ---: | ---: |
| “list all papers related to prediciting student burnout” | 9.58 s | 4.96 s | 3.15 s | 26 |
| “What is CtRL-Sim?” | 5.44 s | 5.22 s | 4.26 s | 8 |

This is a smoke benchmark, not a quality comparison. It has two prompts, no repeated trials, and no ROUGE-L or correctness scoring. The CtRL-Sim answer may have used cached abstract evidence; the harness did not record which sources carried abstracts. An earlier restricted-network run could not reach Groq or Ollama and ended with synthesis errors, so the fallback requires Ollama to be running locally with the configured model.

Earlier copies of this report claimed a local ROUGE-L score of 0.4648 and projected a cloud score from it. The checked-in artifacts do not establish those as results for the current route or configured Groq model, so they are not included as verified results here.

---

## 6. Implementation Progress Tracker

### Completed Milestones
- [x] **Milestone 1 — Relational Core:** Canonical DuckDB database holds approximately 8.7M publication records and associated author, venue, and analytical data.
- [x] **Milestone 2 — Title Indexing:** Built a full 8.73M-title sidecar with Faiss HNSW embeddings and SQLite FTS5; the runtime validates the index against the canonical database fingerprint.
- [x] **Milestone 3 — Agentic Query and Retrieval:** Added structured query planning, guarded database execution, hybrid title retrieval, and source/provenance responses.
- [x] **Milestone 4 — DBLP-QA Retrieval Evaluation:** Added the 50-question retrieval harness and saved per-question results.
- [x] **Milestone 5 — Retrieval Baseline:** Recorded title retrieval metrics alongside paper-reported RAGScholar results, with the data-scope difference documented above.

### Completed Milestones (Continued)
- [x] **Milestone 6 — Abstract Enrichment Cache:** Added a SQLite cache populated on demand from OpenAlex, with Semantic Scholar as a fallback. Successful results are reused for later requests and exports.
- [x] **Milestone 7 — Cached Abstract Grounding:** Topic discovery can attach cached abstracts for up to the first three candidates to answer synthesis. Chat search does not fetch missing abstracts; catalog export performs the on-demand fetch.
- [x] **Milestone 8 — Streaming Assistant:** Added server-sent event streaming for status, sources, and answer content. The current benchmark records first-content and total response times for two prompts.
- [x] **Milestone 9 — All-Papers Discovery and Catalog Export:** Added all-papers intent handling and Excel/CSV export with authors, venues, years, DBLP links, and abstract lookup. Current chat and export paths are capped at 150 records by default.
- [x] **Milestone 10 — Primary Cloud Model with Local Fallback (2026-10-06):** Configured Groq Cloud with `qwen/qwen3.8-27b` as the primary model and Ollama `qwen2.5-coder:7b` as fallback. The dispatcher catches online-call failures and tries the local model. Readiness checks allow the main route to run when Groq credentials exist, even if Ollama is not active. A two-prompt smoke benchmark completed through Groq; no ROUGE-L claim is made for this run.

---

## 7. Verified Empirical Benchmark Summary

| System / Setting | Architecture | Context Strategy | Retrieval / Generation Result | Grounding Source | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **RAGScholar (SCOLIA '26 paper)** | Lucene BM25 + paper models | Top-k abstracts | Recall@1 0.88; Recall@3 1.00; paper-reported ROUGE-L 0.34–0.37 for listed settings | Indexed abstract corpus | Published comparison values; not rerun here |
| **DBLP title retrieval, DBLP-QA set** | Faiss HNSW + SQLite FTS5 | Title candidates | Recall@1 0.18; Recall@3 0.20; Recall@5 0.22; MRR@3 0.1867 | DBLP titles | Saved 50-question repository result |
| **DBLP title retrieval, development probes** | Full-corpus MiniLM/Faiss + SQLite FTS5 | Hybrid title retrieval | 91.7% paraphrase target hit@10 | DBLP titles | 12 development probes, not held out |
| **DBLP assistant, configured Groq model** | Agentic planner + retrieval + `qwen/qwen3.8-27b` | Live retrieved records; cached abstracts when available | 3.15–9.58 s total across two prompts and two modes; no ROUGE-L | DBLP metadata and optional cached abstracts | October 6 smoke benchmark |
| **DBLP assistant, local Ollama fallback** | `qwen2.5-coder:7b` | Same dispatcher after online error | No successful fallback measurement in this pass | Depends on retrieved DBLP evidence | Local service was unavailable during restricted-network run |

---

## 8. Strategic Roadmap & Live Features

1. **Relational analytics:** Continue using DuckDB for supported bibliographic queries, counts, rankings, and entity relationships.
2. **Abstract enrichment:** Keep fetching abstracts on catalog export and reusing cached abstracts during later topic searches. Track which returned records have abstract evidence.
3. **All-papers discovery:** The current 150-record cap applies to both chat results and exports. To support larger catalogs, remove the cap in a controlled export path, add batching, and report partial abstract-fetch failures; avoid sending an unbounded publication list inside the chat response.
4. **Inference evaluation:** Run a larger reviewed prompt set against the same retrieved evidence on Groq and local Ollama. Record model ID, provider path, source IDs, cache coverage, answer correctness, first-content latency, total latency, and errors before making quality or speed comparisons.
