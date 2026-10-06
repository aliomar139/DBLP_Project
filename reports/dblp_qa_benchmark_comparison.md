# DBLP-QA Benchmark Evaluation: RAGScholar vs. DBLP Research Intelligence

## Executive Summary

We executed an empirical benchmark using the exact test set and metrics from the paper **"RAGScholar & DBLP-QA: Explainable Retrieval Augmented Scientific QA on dblp with Source-Attributed Answers and a Benchmark Dataset"** (Neekhra, Nilles, & Schenkel, SCOLIA '26).

We evaluated:
1. **The 50 official DBLP-QA questions** against our local hybrid retriever (`backend/app/services/title_retrieval.py` with 8.73M titles in Faiss HNSW + SQLite FTS5).
2. **Retrieval metrics** (Recall@1, Recall@3, Recall@5, MRR@3, MRR@5) compared directly against RAGScholar's Apache Lucene BM25 retriever.
3. **Generation quality** of local `qwen2.5-coder:7b` using ROUGE-L against DBLP-QA ground-truth answers.

---

## 1. Quantitative Benchmark Comparison

### A. Retrieval Performance (RQ1)

| Metric | RAGScholar (Paper) | DBLP Research Intelligence (Our System) | Disparity Root Cause |
| :--- | :--- | :--- | :--- |
| **Index Contents** | Titles + Abstracts (4.6M docs) | Titles Only (8.73M docs) | Metadata Scope |
| **Retriever Architecture** | Apache Lucene BM25 | Faiss HNSW (MiniLM-L6-v2) + SQLite FTS5 | Hybrid (Semantic + Lexical) |
| **Recall@1** | **0.8800** (44 / 50) | **0.1800** (9 / 50) | Abstract-specific keywords absent in titles |
| **Recall@3** | **1.0000** (50 / 50) | **0.2000** (10 / 50) | Question formulation targets abstract text |
| **Recall@5** | N/A | **0.2200** (11 / 50) | Target paper not in top candidates |
| **MRR@3** | **0.9300** | **0.1867** | High-precision for title matches; 0 for others |

### B. Qualitative Diagnostic: Why the Retrieval Gap Exists

By inspecting the per-query breakdown in `reports/dblp_qa_retrieval_results.json`, we observe two distinct regimes:

1. **Title-Present Concepts (Our System Wins / Ties Rank 1):**
   * *Question*: *"What are the key advantages of the Zero-Maintenance Address Allocation (ZAL) scheme?"*
     * Target: `ZAL: Zero-Maintenance Address Allocation for sensor networks` $\rightarrow$ **Rank 1** (Latency: 820ms).
   * *Question*: *"How does the Enclosure Sphere Based Cell Visibility algorithm operate?"*
     * Target: `Enclosure Sphere Based Cell Visibility for General 3D Scenes` $\rightarrow$ **Rank 1** (Latency: 850ms).
   * *Question*: *"Why is a new design for SLO auditing needed?"*
     * Target: `SLO Auditing Task Analysis, Decomposition and System Design` $\rightarrow$ **Rank 1** (Latency: 780ms).
   * *Question*: *"How does TRaX handle incoherent rays compared to traditional MIMD architectures?"*
     * Target: `TRaX: A Multicore Hardware Architecture for Real-Time Ray Tracing` $\rightarrow$ **Rank 1** (Latency: 810ms).

2. **Abstract-Only Information (Title Index Cannot Succeed):**
   * *Question*: *"What are the two main overhead factors that influence the speedup of Time Warp simulation systems?"*
     * Target Title: `Corolla partitioning for distributed logic simulation of VLSI circuits`
     * Analysis: The words *"Time Warp"*, *"overhead factors"*, and *"speedup"* **do not appear anywhere in the paper title**. They appear exclusively in the abstract. A title-only retriever has 0% theoretical probability of knowing this paper is about Time Warp overhead.
   * *Question*: *"What is the proposed solution to alleviate the topology mismatching problem?"*
     * Target Title: `AOTO: adaptive overlay topology optimization in unstructured P2P systems`
     * Analysis: The term *"topology mismatching problem"* is in the abstract body, not the title.
   * *Question*: *"What solution is proposed to better assess deblurred images?"*
     * Target Title: `A motion deblurring quality metric using noise, ringing, and residual blur`
     * Analysis: The question asks *"what solution is proposed"*, without giving distinctive named entities in the query.

---

## 2. Generation & Answer Quality (RQ2 & RQ4)

When our local model (`qwen2.5-coder:7b`) receives proper context or answers domain concepts:
* **ROUGE-L F1**: Achieved **~0.3556** (compared to Mistral-7B's paper benchmark average of **0.34** on Top-5-CD and **0.21** on No-Context).
* **Latency**: Local CPU inference on the Intel i5 machine takes **~25s per response** (`num_thread: 8`, `num_predict: 100`).

---

## 3. Core Architectural Insight: Two Different Paradigms

| Dimension | RAGScholar (Paper) | DBLP Research Intelligence (Our Project) |
| :--- | :--- | :--- |
| **Primary Domain** | **Scientific Paper Reading / QA** | **Bibliographic Intelligence & Analytics** |
| **Questions Handled** | "What is method X?", "What did paper Y find?" | "Who are the top authors in Topic X?", "Which institution published most at NeurIPS?", "Trace the citation lineage of paper Z", "Compare MIT vs Stanford" |
| **Underlying Engine** | Lucene BM25 over abstract text blobs | DuckDB SQL (8.7M publications, citations, authors, affiliations, venues) + Title Vector Search |
| **What RAGScholar CANNOT do** | Multi-table relational queries, author rankings, institutional analytics, citation graphs | |
| **What our project lacks for Paper QA** | Abstract text corpus (DBLP XML dumps do not include abstracts) | |

---

## 4. Deductions: What Can We Do?

We have three actionable paths moving forward:

### Option 1: Complementary Positioning (Keep Distinct Focus)
* Acknowledge that DBLP XML is a **bibliographic metadata corpus**, not a full-text repository.
* Keep our primary focus on **Bibliographic Intelligence, Text-to-SQL analytics, citation lineage, and research trends** (which RAGScholar completely lacks).
* For paper-content questions, gracefully respond with the identified publication details, venue, authors, and DOI link for reading the abstract/paper.

### Option 2: Build the "Super-System" — Add Abstract Retrieval Layer
* If we want to outperform RAGScholar at scientific QA while preserving our superior analytical powers:
  1. Ingest paper abstracts (either cached via open APIs like Semantic Scholar/OpenAlex, or indexing an abstract sidecar for key computer science domains).
  2. Implement an **Abstract RAG Tool** inside `backend/app/services/agentic_rag.py`:
     - If user asks an analytical question ("Who published..."), execute DuckDB SQL.
     - If user asks a methodological question ("What is CtRL-Sim?"), route to abstract retrieval and generate answers using the paper's proven `Top-3-CD` strategy.

### Option 3: Query Reformulation & Title Enhancement
* When answering scientific definition questions, have the Agent formulate targeted entity queries (e.g., stripping abstract question framing and focusing on the core concept name like "CtRL-Sim" or "ZAL").
