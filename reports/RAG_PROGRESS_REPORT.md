# RAG Progress Report: DBLP Research Intelligence vs. Scientific Abstract RAG

**Status:** Active  
**Author:** DBLP Research Intelligence Team  
**Last Updated:** October 2026  
**Reference Benchmark:** DBLP-QA (Neekhra, Nilles, & Schenkel, SCOLIA '26)

---

## 1. Executive Summary & Purpose

This progress report tracks the development, benchmarking, and architectural evolution of the **Retrieval-Augmented Generation (RAG)** systems within the `DBLP_Project` repository. It provides:
1. Formal definitions and operational mechanics of each RAG approach studied and deployed.
2. An empirical head-to-head comparison against the state-of-the-art academic benchmark **DBLP-QA / RAGScholar**.
3. A breakdown of domain trade-offs (Bibliographic Relational Intelligence vs. Scientific Abstract Reading).
4. Concrete technical progress milestones and future integration roadmap.

---

## 2. Definitions & Approach Overviews

### A. RAGScholar (Abstract-Reading Scientific RAG)
* **Definition:** A traditional document-grounded RAG architecture specifically built to answer scientific definition and research outcome questions by reading publication abstracts.
* **Architecture:**
  * **Knowledge Base:** 4.6 million computer science abstracts obtained by enriching dblp metadata with the Semantic Scholar API.
  * **Retriever:** Apache Lucene BM25 ($k_1=1.2, b=2.0$) indexing paper titles, abstracts, authors, and venues.
  * **Context Formulation:** Top-$k$ Concatenated Documents (`Top-k-CD`, with $k \in \{3, 5\}$). Raw abstract texts are merged into the LLM prompt.
  * **Generator:** Instruction-tuned LLMs (Mistral-7B, Phi-4, TinyLlama-1.1B, FLAN-T5).
* **Primary Objective:** Answer questions formulated around the internal content of research papers (e.g., *"What is CtRL-Sim?"*, *"Why is differential diagnosis difficult for physicians?"*).

### B. DBLP Research Intelligence (Our System — Agentic Relational RAG)
* **Definition:** A schema-aware, hybrid agentic system combining Text-to-SQL on relational data warehouses with semantic vector search for end-to-end bibliographic discovery and analytics.
* **Architecture:**
  * **Knowledge Base:** Canonical DuckDB database (`database/dblp.duckdb`, 3.4 GB) with 8.7M publications, authors, affiliations, venues, citation lineage, and topic tables.
  * **Title Retriever:** Hybrid sidecar (`database/indexes/dblp-title-v2`) combining Faiss HNSW embeddings (MiniLM-L6-v2, 384-dim) and SQLite FTS5 lexical matching across 8,738,331 titles.
  * **Planner & Self-Correction:** Local Ollama (`qwen2.5-coder:7b`) with schema-aware SQL formulation, single-statement execution guards, memory limits, 8s timeouts, and automatic retry on DuckDB errors.
  * **Generator:** `qwen2.5-coder:7b` conditioned on returned SQL rows or retrieved publication cards, returning structured `AssistantSource` and calculation provenance.
* **Primary Objective:** Answer complex analytical, institutional, bibliometric, and discovery questions across the computing literature landscape.

### C. Legacy Bounded Interpreter (Offline Fallback)
* **Definition:** A deterministic classifier and bounded tool executor designed as a resilient fail-safe when local LLM inference engines are offline.
* **Architecture:**
  * Fixed regex patterns and local Phi-3 Mini intent classifier mapping queries to 17 predefined parameter slots.
  * Deterministic query execution across static helper functions (`backend/app/services/assistant_tools.py`).

---

## 3. Key Differences Between Approaches

| Dimension | RAGScholar (Paper) | DBLP Research Intelligence (Our Project) |
| :--- | :--- | :--- |
| **Data Scope** | 4.6M paper abstracts (merged via Semantic Scholar) | 8.7M bibliographic records, citations, authors, affiliations, venues, topics |
| **Abstract Availability** | **Yes** (core source of evidence) | **No** (DBLP XML dump is strictly bibliographic metadata) |
| **Retrieval Mechanism** | Lexical BM25 over abstract text | Hybrid Semantic Vector (Faiss HNSW) + SQLite FTS5 on titles |
| **Query Flexibility** | Unstructured text retrieval only | Hybrid: Structured DuckDB SQL + Unstructured Title Discovery |
| **Execution Paradigm** | Single-turn static prompt context (`Top-k-CD`) | Multi-step Agentic planning, Text-to-SQL, and self-correction |
| **Hardware Footprint** | Cloud/Server-grade LLM inference | 100% Local CPU inference (Intel i5, 40GB RAM, Ollama) |
| **Response Contract** | Text answer + cited document IDs | Markdown synthesis + Clickable entity cards + Calculation provenance |

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
      RAGScholar is Superior                                                DBLP System is Superior
   (Grounds answers in abstract texts)                                  (Executes multi-table relational SQL)
```

### Where RAGScholar Wins
1. **Methodological Question Answering:** Questions addressing how algorithms work, experimental findings, and paper definitions.
2. **Dense Keyword Matching in Bodies:** Queries with terms only discussed inside the abstract body (e.g., matching *"Time Warp speedup"* to a paper titled *"Corolla partitioning for VLSI"*).
3. **Multi-Abstract Synthesis:** Comparing findings directly across 3 to 5 paper abstracts.

### Where DBLP Research Intelligence Wins
1. **Complex Relational Analytics:** Queries requiring aggregations over millions of rows (e.g., *"Which university published the most papers at NeurIPS between 2020 and 2024?"*).
2. **Citation Lineage & Impact:** Tracing paper citation trees, author h-indices, and co-authorship graphs.
3. **Cross-Entity Benchmarking:** Head-to-head comparisons between institutions, topics, or countries.
4. **Data Breadth:** Full coverage of all 8.7M dblp entries, including pre-abstract and book/proceedings metadata.
5. **Explainable Provenance:** Every claim is tied to real DuckDB rows and verifiable database SQL queries.

---

## 5. Empirical Benchmark Comparison (DBLP-QA Test)

We executed the official **50-query DBLP-QA benchmark** against our active system and recorded direct metric comparisons with RAGScholar.

### A. Retrieval Evaluation (RQ1)

| Metric | RAGScholar (Lucene BM25) | DBLP Hybrid Title Index | Gap Explanation |
| :--- | :--- | :--- | :--- |
| **Indexed Content** | Titles + Abstracts | Titles Only | DBLP XML dump lacks abstracts |
| **Recall@1** | **0.8800** (44 / 50) | **0.1800** (9 / 50) | Abstract-specific terms not present in titles |
| **Recall@3** | **1.0000** (50 / 50) | **0.2000** (10 / 50) | Benchmark questions derived from abstract body |
| **Recall@5** | *Not Reported* | **0.2200** (11 / 50) | 11 out of 50 found in top 5 |
| **MRR@3** | **0.9300** | **0.1867** | High precision when title matches; 0 otherwise |
| **Latency** | Server-grade | **~850 ms** | Fast local CPU search across 8.73M records |

#### Diagnostic Analysis of Retrieval Gap
* **Title Matches (100% Rank 1 Success):** When a question mentions terms present in the title (e.g., *"Zero-Maintenance Address Allocation"*, *"Enclosure Sphere Based Cell Visibility"*, *"SLO Auditing"*, *"TRaX"*), our hybrid retriever placed the target paper at **Rank 1 in <900ms**.
* **Abstract-Exclusive Concepts:** For questions like *"What are the two main overhead factors that influence the speedup of Time Warp simulation systems?"* (Paper title: *"Corolla partitioning for distributed logic simulation of VLSI circuits"*), a title-only index cannot retrieve the document because the relevant keywords exist **exclusively in the abstract**.

### B. Generation Quality (RQ2 & RQ4)

| Model & Setting | Context Strategy | ROUGE-L F1 | Latency / Call | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Mistral-7B (Paper)** | Top-5 Concatenated Abstracts (`Top-5-CD`) | **0.3400** | GPU | Best overall paper score |
| **Mistral-7B (Paper)** | No-Context Baseline | **0.2100** | GPU | Parametric memory hallucination |
| **Phi-4 (Paper)** | Top-3 Concatenated Abstracts (`Top-3-CD`) | **0.3700** | GPU | High precision on abstract reading |
| **Phi-4 (Paper)** | No-Context Baseline | **0.1000** | GPU | Strict refusals without context |
| **Qwen-2.5-Coder:7B (Ours)** | Title + Domain Concept Context | **0.3556** | **~25.5s** | Runs locally on CPU; strong technical alignment |

---

## 6. Implementation Progress Tracker

### Completed Milestones
- [x] **Milestone 1 — Relational Core:** DuckDB schema loaded with 8.7M publications, authors, citations, venues, and institutions.
- [x] **Milestone 2 — Title Indexing:** Full 8.73M title hybrid index built and verified using Faiss HNSW embeddings + SQLite FTS5.
- [x] **Milestone 3 — Agentic Text-to-SQL Engine:** Schema-aware query planner (`agentic_rag.py`) with self-correction retry loops, safety filters, and structured responses.
- [x] **Milestone 4 — DBLP-QA Benchmark Harness:** Ingested the official 50-pair DBLP-QA dataset, mapped all 50 keys to active DuckDB records, and implemented automated evaluation scripts (`scripts/evaluate_dblp_qa.py`).
- [x] **Milestone 5 — Empirical Baseline Established:** Generated full retrieval and generation metrics comparing our system against RAGScholar.

### Completed Milestones (Continued)
- [x] **Milestone 6 — Abstract Enrichment Layer:** Built SQLite sidecar cache (`database/abstracts_cache.sqlite` with WAL mode) with OpenAlex API (inverted index reconstruction) and Semantic Scholar fallback. Pre-warmed benchmark & top-cited abstracts.
- [x] **Milestone 7 — Hybrid Unified Router & Top-3-CD Context:** Equipped `agentic_rag.py` with exact title term boosting and `Top-3-CD` concatenated abstract document grounding, boosting scientific ROUGE-L to **0.4648** (surpassing RAGScholar's 0.34–0.37).
- [x] **Milestone 8 — Streaming Truncation Resolution:** Resolved token cutoff by raising synthesis budget to 1,200 tokens with 4,096 context window, accompanied by client-side SSE buffer stream flushing.
- [x] **Milestone 9 — All-Papers Topic Discovery & Excel Abstract Export:** Added intelligent `(all papers)` intent detection, dynamically querying DuckDB without standard candidate caps (up to 150 papers). Integrated styled Excel (`.xlsx`) generation via `openpyxl` with on-demand scientific abstract fetching for all matching records.

---

## 7. Verified Empirical Benchmark Summary

| System / Setting | Architecture | Context Strategy | Scientific ROUGE-L | Grounding Source |
| :--- | :--- | :--- | :--- | :--- |
| **RAGScholar (SCOLIA '26)** | Mistral-7B / BM25 | `Top-5-CD` Concatenated Abstracts | 0.3400 | Lucene abstracts index |
| **RAGScholar (SCOLIA '26)** | Phi-4 / BM25 | `Top-3-CD` Concatenated Abstracts | 0.3700 | Lucene abstracts index |
| **DBLP Intelligence (Ours - Title Only)** | Qwen2.5-Coder:7B | Hybrid Title Match | 0.3556 | Title Index |
| **DBLP Super-System (Ours - Grounded)** | Qwen2.5-Coder:7B | `Top-3-CD` Abstracts + Title Boost | **0.4648** | OpenAlex/Semantic Scholar SQLite Sidecar Cache |

---

## 8. Strategic Roadmap & Live Features

1. **Relational Core Moat:** DuckDB Text-to-SQL handles all complex bibliometric, coauthorship, trajectory, and citation network queries.
2. **On-Demand Abstract Fetching:** SQLite sidecar cache eliminates the need for 30+ GB local abstract storage while delivering sub-second cached abstract hits and concurrent OpenAlex background fetching.
3. **Super-System All-Papers Discovery:** Users can ask for all papers on any topic (`"papers on large language models (all papers)"`), inspect the complete catalog in the UI, and download a styled Excel spreadsheet containing titles, authors, venues, years, DBLP links, and full scientific abstracts.
