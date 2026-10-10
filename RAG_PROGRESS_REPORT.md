# RAG Progress Report: DBLP Research Intelligence and RAGScholar

**Status:** Active  
**Updated:** October 10, 2026  
**Reference benchmark:** DBLP-QA (Neekhra, Nilles, & Schenkel, SCOLIA '26)

## Current status

- **Keyword search changed:** SQLite FTS5 was the previous engine. Tantivy now handles keyword search; FTS5 remains as a fallback.
- **What improved:** On 12 paired development queries, both engines found the target in the top eight 11 times. Tantivy cut average full retrieval time from 1,273 ms to 753 ms, about 41% faster.
- **50-question check:** Tantivy produced the same target rank as the saved FTS5 run on all 50 DBLP-QA questions. Recall@1, @3, @5 and MRR@3 are unchanged.
- **Remaining limit:** These results measure retrieval for one benchmark set. They do not establish answer quality or performance on other query sets.

**Next evaluation:** Review a larger, user-checked set that includes title-only and abstract-dependent questions.

## 1. What the systems answer

**DBLP Research Intelligence** searches publication records. It supports bibliographic discovery and questions about authors, venues, topics, counts, rankings, and supported relationships.

**RAGScholar** searches paper abstracts. That evidence helps answer questions about a paper's methods, definitions, or findings, including details missing from the title.

These systems use different evidence, so the results below are not a controlled comparison of identical indexes or answer models.

## 2. How DBLP title search works

1. **Semantic search:** MiniLM turns each title into a 384-number vector. Faiss HNSW finds nearby vectors without comparing every query to all 8.7 million titles. The vectors use 8-bit scalar quantization to save storage.
2. **Keyword search:** Tantivy searches an inverted index of all 8,738,331 titles and ranks matches with BM25. It runs locally. The earlier SQLite FTS5 index remains available as a fallback.
3. **Combine and check:** Reciprocal-rank fusion (RRF) combines the semantic and keyword ranks. A title can rank well from either search; a title found by both can receive a boost. The system limits candidates, then validates every returned record against canonical DuckDB.

The title index can find similar wording and exact terms. It cannot retrieve methods or findings that a title never mentions.

## 3. Keyword engine change and measured result

### What changed

| Before | Now |
| :--- | :--- |
| SQLite FTS5 handled keyword title search. | Tantivy handles keyword title search. |
| FTS5 returned ranked title matches but could take hundreds of milliseconds per query. | Tantivy uses a local BM25 inverted index. FTS5 stays available as a fallback. |

### What Tantivy added

The paired comparison ran both engines over the same 12 queries and the same full retrieval path: Faiss, keyword search, rank fusion, and DuckDB validation.

| Measure | SQLite FTS5 | Tantivy | Change |
| :--- | ---: | ---: | :--- |
| Target hit@8 | 11/12 (91.7%) | 11/12 (91.7%) | Same result on this probe set |
| Mean keyword stage | 577 ms | 7 ms | About 79x faster |
| Mean full retrieval | 1,273 ms | 753 ms | About 41% faster |
| P95 full retrieval | 1,750 ms | 875 ms | About 50% faster |

The Tantivy index covers all 8,738,331 titles, uses about 309 MB, and took about 27 seconds to build in the benchmark. Since FTS5 remains available, Tantivy adds storage instead of removing the old SQLite index.

**Limit:** These 12 probes show a speed improvement, not a general quality gain. The queries are not held out or user-reviewed. Per-query results are in [`reports/assistant/keyword-engine-ab-v1.json`](reports/assistant/keyword-engine-ab-v1.json); the Tantivy-only run is in [`reports/assistant/tantivy-connected-retrieval-v1.json`](reports/assistant/tantivy-connected-retrieval-v1.json).

## 4. Models and fallback paths

### Model guide: what each one does

| Model | How it works | Purpose in this project |
| :--- | :--- | :--- |
| **MiniLM** | A small transformer turns a title into a 384-number vector. Titles with related wording tend to have nearby vectors. | Finds papers by topic or paraphrase in the DBLP title index. It does not write answers. |
| **Qwen `qwen/qwen3.8-27b`** | A large language model reads the question and the supplied search results, then generates a response. It runs through Groq Cloud. | Main answer writer for the DBLP assistant, when cloud credentials are available. |
| **Qwen2.5-Coder:7B** | A smaller Qwen language model that generates text from the question and supplied context. It runs locally through Ollama. | Local fallback answer writer when a Groq request fails. It has not yet had a successful benchmark run in this project. |
| **Phi-3 Mini** | A compact language model classifies a request into a limited set of known intents. | Legacy offline route: helps select a predefined query type; deterministic database code runs the query. It is not the general answer writer. |
| **Mistral-7B** | A 7-billion-parameter language model that generates an answer from its input text. | One of the answer models evaluated in the RAGScholar paper. |
| **Phi-4** | A language model that generates an answer from its input text. | Evaluated by the RAGScholar paper with retrieved abstracts and without retrieval context. |
| **TinyLlama-1.1B** | A compact language model with about 1.1 billion parameters. | One of the answer models evaluated in the RAGScholar paper. |
| **FLAN-T5** | A text-to-text model tuned to follow instructions; it produces output text from input text. | One of the answer models evaluated in the RAGScholar paper. |

Faiss, Tantivy, SQLite FTS5, DuckDB, and BM25 are search or database tools, not language models. They find, rank, or validate records; they do not generate answers.

### Answer generation

- **Primary:** Groq Cloud with `qwen/qwen3.8-27b`, when credentials are configured. The October 6 smoke run completed in 3.15-9.58 seconds across two prompts and two request modes. This checks that the route operates; it does not measure answer accuracy.
- **Fallback:** Ollama `qwen2.5-coder:7b` after a Groq call fails. It depends on local hardware and may run more slowly. Ollama was unavailable during the October 6 restricted-network run, so there is no successful live fallback measurement.
- **Legacy offline route:** Phi-3 Mini maps a limited set of intents to predefined query slots. Deterministic database tools execute those requests. It is not a general answer generator.

The repository has no same-prompt, same-evidence quality comparison between Groq and other models. Earlier report versions claimed a local ROUGE-L score of 0.4648 and projected a cloud score; checked-in artifacts do not verify either number for the current route.

### RAGScholar models

The paper evaluates Mistral-7B, Phi-4, TinyLlama-1.1B, and FLAN-T5. Its generator receives the top-ranked abstracts, with context settings including 3 or 5 documents.

## 5. System comparison

| Area | RAGScholar | DBLP Research Intelligence |
| :--- | :--- | :--- |
| **Collection** | About 4.6 million computer science abstracts enriched from DBLP using Semantic Scholar | About 8.7 million bibliographic records and project-derived tables |
| **Search** | Lucene BM25 over titles, abstracts, authors, and venues; paper reports `k1=1.2`, `b=2.0` | DuckDB plans for structured questions; Faiss HNSW and Tantivy over titles for discovery |
| **Abstracts** | Indexed and central to retrieval | Optional abstracts in a separate SQLite cache; no indexed abstract collection |
| **Best for** | Paper methods, definitions, findings, and cross-paper content comparison | Relational analysis, author and venue questions, counts, rankings, and title discovery |
| **Answer models** | Models and settings reported by the paper | Groq `qwen/qwen3.8-27b`; local Ollama `qwen2.5-coder:7b` fallback |
| **Response evidence** | Answer with source-attributed paper IDs | Answer, DBLP source records, and calculation provenance |

DBLP's broader metadata includes books and proceedings that may lack abstracts. Its title index cannot find a concept that appears only in an abstract.

## 6. Retrieval benchmark results

### DBLP-QA: saved 50-question baseline

The table compares RAGScholar paper figures with the saved DBLP FTS5 baseline and the new Tantivy run. RAGScholar searches titles and abstracts; DBLP searches titles only.

| Metric | RAGScholar, paper | DBLP FTS5 baseline | DBLP Tantivy run |
| :--- | ---: | ---: | ---: |
| Indexed content | Titles and abstracts | Titles only | Titles only |
| Recall@1 | 0.8800 (44/50) | 0.1800 (9/50) | 0.1800 (9/50) |
| Recall@3 | 1.0000 (50/50) | 0.2000 (10/50) | 0.2000 (10/50) |
| Recall@5 | Not reported | 0.2200 (11/50) | 0.2200 (11/50) |
| MRR@3 | 0.9300 | 0.1867 | 0.1867 |
| MRR@5 | Not reported | 0.1917 | 0.1917 |

The saved FTS5 results are in [`reports/dblp_qa_retrieval_results.json`](reports/dblp_qa_retrieval_results.json); Tantivy results are in [`reports/assistant/dblp-qa-tantivy-v1.json`](reports/assistant/dblp-qa-tantivy-v1.json). Tantivy returned the same target rank as FTS5 for all 50 questions. One Time Warp question targets "Corolla partitioning for distributed logic simulation of VLSI circuits." The question's terms do not appear in the title, so an abstract search can find evidence the DBLP title index cannot.

The saved FTS5 run averaged 1,733 ms per query, with a 3,046 ms p95. The Tantivy run averaged 802 ms, with a 1,016 ms p95. These timings come from separate runs, so treat them as directional rather than as a controlled latency comparison. The target ranks, however, match exactly across all 50 questions.

### Earlier retrieval probes

A separate full-corpus evaluation used 12 development probes. It reported 4.4 ms average for the Faiss search stage only and 4.21 seconds average for SQLite FTS5, with a 6.61-second p95. That harness differs from the paired A/B run, so its FTS5 timing is not directly comparable. The earlier evaluation is in [`reports/assistant/full-retrieval-evaluation-v2.json`](reports/assistant/full-retrieval-evaluation-v2.json).

## 7. Answer-generation benchmark results

| Model and setting | Context | ROUGE-L F1 | Latency | Evidence status |
| :--- | :--- | ---: | :--- | :--- |
| Mistral-7B, RAGScholar | Top 5 joined abstracts | 0.3400 | GPU in paper setup | Paper-reported |
| Mistral-7B, RAGScholar | No context | 0.2100 | GPU in paper setup | Paper-reported |
| Phi-4, RAGScholar | Top 3 joined abstracts | 0.3700 | GPU in paper setup | Paper-reported |
| Phi-4, RAGScholar | No context | 0.1000 | GPU in paper setup | Paper-reported |
| Qwen `qwen/qwen3.8-27b`, DBLP | Live retrieval and synthesis | Not measured | 3.15-9.58 seconds in smoke run | Two prompts; no correctness score or repeated trials |
| Qwen2.5-Coder:7B fallback | Same dispatcher after online error | Not measured | Not measured | Ollama unavailable during the restricted-network run |

On October 6, `scripts/run_benchmark.py` completed two prompts through Groq. Each prompt ran once in streaming mode and once synchronously; neither triggered a fallback.

| Prompt | Streaming total | First content | Synchronous total | Sources |
| :--- | ---: | ---: | ---: | ---: |
| "list all papers related to prediciting student burnout" | 9.58 s | 4.96 s | 3.15 s | 26 |
| "What is CtRL-Sim?" | 5.44 s | 5.22 s | 4.26 s | 8 |

The run had two prompts and no repeated trials or answer-quality scoring. The CtRL-Sim response may have used cached abstract evidence; the benchmark did not record which sources had abstracts. An earlier restricted-network run could not reach Groq or Ollama and ended with synthesis errors. A live fallback measurement requires Ollama to run locally with the configured model.

## 8. Implementation progress

### Completed milestones 1-5

1. **Relational core:** DuckDB contains about 8.7 million publications and related author, venue, and analytical data.
2. **Title index:** Built Faiss HNSW and SQLite FTS5 indexes for 8.73 million titles. The runtime checks the index against the canonical database fingerprint.
3. **Agentic queries:** Added structured query planning, guarded database execution, hybrid title search, and source/provenance responses.
4. **DBLP-QA evaluation:** Added a 50-question retrieval harness and saved per-question results.
5. **Retrieval baseline:** Recorded title-search metrics beside RAGScholar paper figures and documented the difference in data scope.

### Completed milestones 6-11

6. **Abstract cache:** Added a SQLite cache populated on demand from OpenAlex, with Semantic Scholar as a fallback. Successful results are reused in later requests and exports.
7. **Cached abstract grounding:** Topic discovery can attach cached abstracts for up to the first three candidates during synthesis. Chat search does not fetch missing abstracts; catalog export can fetch them on demand.
8. **Streaming assistant:** Added server-sent events for status, sources, and answer content. The smoke benchmark records first-content and total times for two prompts.
9. **All-papers discovery and export:** Added all-papers intent handling and Excel/CSV export with authors, venues, years, DBLP links, and abstract lookup. Chat and export paths default to a 150-record cap.
10. **Cloud model and local fallback (October 6):** Set Groq `qwen/qwen3.8-27b` as primary and Ollama `qwen2.5-coder:7b` as fallback. The two-prompt smoke run completed through Groq; no ROUGE-L claim is made.
11. **Tantivy keyword replacement (October 10):** Replaced FTS5 as the active keyword engine with Tantivy; FTS5 remains the fallback. On 12 development probes, both had 91.7% hit@8 and Tantivy cut average full retrieval time by about 41%. On DBLP-QA, both engines produced the same target ranks for all 50 questions and the same recall/MRR scores.

## 9. Verified results at a glance

| System and setting | Method | Result | Status |
| :--- | :--- | :--- | :--- |
| RAGScholar, SCOLIA '26 paper | Lucene BM25 and paper-evaluated models | Recall@1 0.88; Recall@3 1.00; reported ROUGE-L 0.34-0.37 | Published figures; not rerun here |
| DBLP title retrieval, DBLP-QA | Faiss HNSW with FTS5 and Tantivy | Both engines: Recall@1 0.18; Recall@3 0.20; Recall@5 0.22; MRR@3 0.1867; identical rank on all 50 questions | Saved FTS5 baseline and new Tantivy run |
| DBLP keyword engine A/B | Faiss with FTS5 or Tantivy plus DuckDB validation | Both hit 11/12 targets at rank 8; Tantivy mean 753 ms vs. FTS5 1,273 ms | 12 development probes; not held out or user-reviewed |
| DBLP assistant, Groq | Agentic planner, retrieval, and `qwen/qwen3.8-27b` | 3.15-9.58 seconds across two prompts and two modes; no ROUGE-L | October 6 smoke run |
| DBLP assistant, Ollama fallback | `qwen2.5-coder:7b` through the same dispatcher | No successful measurement in this pass | Local service unavailable during restricted-network run |

## 10. Roadmap

1. **Review retrieval on more queries.** Add user-checked examples, including questions that require abstract content.
2. **Track abstract coverage.** Record which returned papers have cached abstract evidence.
3. **Support larger exports.** Add batching, report partial abstract-fetch failures, and avoid unbounded publication lists in chat.
4. **Evaluate answer quality.** Test Groq and local Ollama on a larger reviewed prompt set using the same retrieved evidence. Record model ID, provider path, source IDs, abstract-cache coverage, correctness, first-content time, total time, and errors.
