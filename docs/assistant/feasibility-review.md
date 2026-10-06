# Retrieval feasibility: full index built; quality and activation remain under review

The full-corpus index uses repaired candidate v2, not the active database. Its SHA-256
is `3b1b26662df6e8759ff0e5247fc073403c15b21815cc697d9dd66d279482e250`.
The candidate contains 8,738,331 eligible titles and zero empty-title exclusions.
It remains review-only and is not loaded by the assistant. The unchanged active database
still has 8,730,137 eligible titles and 8,194 exclusions.

## Experiment

The benchmark sampled 20,000 eligible candidate records with single-threaded
reservoir sampling and seed 42, then added 12 development targets absent from the
sample. All 20,012 IDs are unique and match the candidate titles. The sample spans
the corpus instead of selecting highly cited or recent papers. The JSON report
includes type distributions, year range, title lengths, settings, and file hashes.

The encoder is the official quantized AVX2 ONNX export of
[`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2),
pinned to revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. It runs locally with
ONNX Runtime on CPU. Its model card specifies masked mean pooling and normalized
384-dimensional vectors. The implementation follows that procedure. Only titles
enter the encoder; no outside metadata or abstracts enter retrieval evidence.
Downloads were setup operations, not external inference calls.

The process used six compute threads on a machine reporting 12 logical CPUs and
42,641,252,352 bytes of physical memory. The benchmark compares SQLite FTS5
`unicode61`/Porter tokenization and Faiss HNSW32 float32/scalar-8 storage. These are
experiments in isolated sidecar files; the application does not load them.
See the primary [SQLite FTS5 documentation](https://www.sqlite.org/fts5.html) and
[Faiss index documentation](https://github.com/facebookresearch/faiss/wiki/Faiss-indexes)
for the implementation choices.

## Measured results

| Measurement | Result |
| --- | ---: |
| Embedded titles | 20,012 |
| Batched embedding time, after warmup | 52.93 seconds |
| Embedding throughput | 378.05 titles/second |
| Encoder construction in the benchmark process | 0.240 seconds |
| Embedding batch p95, 64 titles per batch | 0.243 seconds |
| Process lifetime peak working set | 566,763,520 bytes / 0.528 GiB |
| Total initial experiment duration | 82.13 seconds |
| Initial experiment artifact disk | 91,166,696 bytes |
| Truncated sample titles at 256 tokens | 0 |
| Invalid IDs or mismatched titles | 0 |
| Non-finite vectors | 0 |

Encoder construction is not a cold-machine startup measurement: model files may
already be in the OS file cache. The memory number includes the process's sample
vectors, exact search baseline, and sequential candidate builds. It is not a
full-build or total-system memory measurement.

| Vector candidate, efSearch 64 | Sample index bytes | ANN recall@10, 100 exact-title probes | ANN recall@10, 12 paraphrases | Query p95 |
| --- | ---: | ---: | ---: | ---: |
| HNSW32 float32 | 36,184,178 | 99.7% | 100% | 0.725 ms |
| HNSW32 scalar-8 | 13,133,462 | 99.3% | 99.17% | 0.592 ms |

ANN recall compares approximate neighbors to exact vector neighbors. It does not
measure whether an answer is true or all relevant papers were found. Both candidates
found the target IDs for all 100 exact-title probes and all 12 development
paraphrases within their top 10 in this small corpus. The development set is easy,
small, and not held out or user reviewed. It must not be reported as full-corpus
retrieval accuracy. No generated citation count was used for sampling or ranking.

Both initial keyword tokenizers found all development targets. Unicode keyword
query p95 was 25.75 ms for the 100 exact-title probes; Porter was 27.06 ms. These
queries use a bounded OR over title tokens, so common words can match many rows.

## Keyword scaling exposed a tradeoff

A separate experiment sampled 100,000 and 1,000,000 candidate titles and included
the same development targets. The one-million sample contained 1,000,010 records.

| Policy on one million titles | Mean | p95 | Development target hit@10 |
| --- | ---: | ---: | ---: |
| All query terms joined by OR | 434.54 ms | 737.86 ms | 10/12 |
| Four rarest indexed terms joined by OR | 13.10 ms | 20.81 ms | 8/12 |

The one-million-title keyword index took 20.29 seconds to build and occupies
163,811,328 bytes. Rare-term timing includes vocabulary lookups. Its speed gain
comes with missed development targets. Do not silently select this policy on
latency alone. Full hybrid evaluation must determine whether semantic candidates
recover the missing targets. Exact-title lookup should have its own bounded path.

## Projections and resource decision

At the measured rate, candidate-wide embedding projects to **6.42 hours**. This
linear estimate excludes thermal slowdown, restart/retry costs, validation, and
index construction. The sample graph-add rates project to lower bounds of roughly
30 minutes for float32 and 16 minutes for scalar-8; graph construction costs change
with scale, so these are not delivery promises. The million-title lexical build
rate projects to roughly three minutes, but full-scale behavior remains unmeasured.

Sample index size projects to about **14.72 GiB** for float32 HNSW and **5.34 GiB**
for scalar-8 HNSW. The measured lexical samples project to roughly 1.4–2.0 GB.
Keeping all 384-dimensional float32 embeddings would add about **12.50 GiB** on
disk. Holding that entire array together with the float32 graph would leave too
little memory headroom for DuckDB, model inference, and build overhead.

The next design to test is scalar-8 HNSW with bounded batches and disk-backed or
sharded construction, plus SQLite keyword retrieval. Shards would reduce build
memory but require globally merged results and a full-corpus recall check. This
has not been implemented or activated. Float32 remains a comparison option if
larger-scale scalar-8 recall proves inadequate. Reranking is not proposed.

Projected storage fits within the 40–60 GB build allowance if temporary artifacts
are bounded and obsolete builds are deliberately managed. **Full-build peak RAM,
temporary disk peak, sustained throughput, full-corpus recall, and end-to-end p95
are not measured.** The sample therefore cannot certify the 25–28 GB memory cap or
10-second ready-service response target. There is no measured contradiction of the
few-day schedule yet; the projected embedding pass alone uses a substantial part
of a day, and source repair plus later milestones still need work.

## Reproduce and review

Dependencies live in `.work/rag-benchmark/packages`; application dependencies are
unchanged. The setup script downloads only model files and pins their commit and
SHA-256 values. All benchmark inference runs offline.

```powershell
venv/Scripts/python.exe -m pip install --index-url https://pypi.org/simple --target .work/rag-benchmark/packages -r scripts/requirements-retrieval-benchmark.txt
venv/Scripts/python.exe scripts/setup_retrieval_benchmark.py
venv/Scripts/python.exe scripts/benchmark_retrieval.py --db database/dblp.duckdb
venv/Scripts/python.exe scripts/benchmark_keyword_scale.py
```

The keyword scaling script refuses to overwrite earlier experiment files. Preserve
or move them before another run. On this Windows sandbox, pip-installed directories
required an unsandboxed process for runtime imports. No system-wide installation
or security-policy change was made.

Machine-readable reports: `reports/assistant/feasibility-v1.json`,
`keyword-scale-v1.json`, and `benchmark-validation-v1.json` in the same directory.
The separate `docs/assistant/evaluation-plan-v1.json` proposes 24 release cases and
records expected states, evidence paths, failure conditions, and unmeasured latency.
It has not been run as a release evaluation. A local explanation model has not
been selected; this benchmark measures an embedding model only.

## Full-corpus index build results

Milestone 3 completed on 2026-09-28. The v2 sidecar covers every one of its
8,738,331 nonempty titles, with zero exclusions. An independent verifier compared
all IDs in exact source order and all stored title strings; it passed. Faiss, ID
mapping, and FTS5 each contain 8,738,331 entries. The independent scan took 29.8
seconds. Builder-reported peak working set was 9.93 GiB, below the 25?28 GiB target.
The current sidecar directory occupies 18,121,397,414 bytes, including retained
checkpoint files; the ready Faiss and SQLite artifacts themselves total about
7.26 GB. Temporary disk peak was not measured. The final resumed pass took 1,699
seconds while replaying 8.53 million saved IDs and adding 204,800 vectors. Because
the build was paused and resumed for tuning, the total uninterrupted full-build
wall time is not available as one reliable measurement.

The 12-probe development evaluation achieved target hit@10 of 1.00 for exact-title
semantic and keyword retrieval, 1.00 for paraphrase semantic retrieval, 0.833 for
paraphrase keyword retrieval, and 0.917 for paraphrase hybrid retrieval. All returned
IDs were valid. This development set is not held out or user-reviewed. Semantic
query mean/p95 was 4.4/10.8 ms; keyword query mean/p95 was 4.21/6.61 seconds. The
keyword latency is too high for the desired end-to-end response time. No local
assistant route loads this candidate sidecar until its source database is approved
or a matching index is built for the selected database.

The remaining paragraphs in this section preserve historical checkpoint and tuning
observations from before the final build completed.

The first full review-only v2 build used an ID-ordered DuckDB scan,
checkpoint-prefix verification, 64-title embedding batches, SQLite FTS5, and
Faiss HNSW scalar-8. At its first 50,000-title progress report, the measured
end-to-end build rate at 51,200 titles was 145.25 titles/second (352.5 seconds elapsed), projecting
about 16.7 hours for 8,738,331 titles if that early rate holds. The process peak
working set at that point was 1.812 GiB. This is an early projection, not a final
build measurement; indexing costs may change as the graph grows. The measured rate
is slower than the 378.05 titles/second embedding-only sample, which confirms that
the sample alone did not predict full-build throughput. This was an early projection; the build was later tuned and completed. See
`reports/assistant/full-index-build-v2.json` for the final build status and
`reports/assistant/full-index-verification-v2.json` for the independent verifier.

At 102,400 titles (647.3 seconds elapsed), throughput improved to 158.2
titles/second, projecting 15.35 hours if that rate holds. Peak working set was
1.864 GiB. The C: drive had 732,607,004,672 bytes free at the time of measurement;
this is system-wide free space, not space consumed by the build.

At 153,600 titles (945.3 seconds elapsed), the rate was 162.49 titles/second,
projecting 14.93 hours; peak working set was 1.916 GiB. This is still an early
linear projection. See the machine-readable build report for the latest point.

The previous full-corpus run reached 819,200 titles (9.37% coverage), with a
durable checkpoint at 501,760 vectors. It was paused there for speed tuning. Its
measured rate was 189.36 titles/second with a 2,685,689,856-byte peak working set.

## Build-speed tuning

A 12,000-title local embedding benchmark compared batch sizes 64, 128, 256, and
512 at 6, 8, 10, and 12 CPU threads. The best measured setting was **64 titles at
6 threads: 508 titles/second**. Larger batches and higher thread counts were slower;
the 256-title batch reached 254/second at six threads. More embedding batch memory
would not improve this workload.

A separate Faiss insertion benchmark cloned the real 501,760-vector checkpoint and
added 8,192 locally generated vectors. Four threads with 256-vector adds reached
2,446 titles/second, compared with 640/second for the existing six-thread,
64-vector adds. The builder now keeps the measured 64-title embedding batch and
buffers four batches for each 256-vector Faiss insertion. This decouples the two
settings and uses only a small vector buffer. Based on the previous full-build
stage timings, this projects roughly 9.5 hours for the corpus, down from 12.8 hours;
this is an estimate from a partial graph, not a measured new end-to-end rate.

The resumed tuned build has now added 102,400 vectors beyond its 501,760-vector
checkpoint in 253.1 seconds: 404.64 titles/second including the FTS prefix replay.
Embedding measured 546.46 titles/second and Faiss insertion measured 2,086.15
titles/second. Peak working set so far is 2.22 GiB. At this measured resume rate,
the remaining work projects to about 5.6 hours. The index is still partial, so
later graph growth may change that rate. A progress-log calculation that briefly
counted the already-saved checkpoint as new work was corrected in the builder and
is explicitly qualified in the JSON report.

The next checkpoint report shows 655,360 total vectors, with 153,600 added after
resume in 392.8 seconds. That is 391.1 titles/second including the prefix replay;
embedding ran at 517 titles/second and Faiss insertion at 1,969 titles/second.
Peak working set is 2.26 GiB, and the remaining-work projection is now 5.7 hours.

Machine-readable benchmark results are in `embedding-batch-tuning-v2.json` and
`faiss-insertion-tuning-v2.json`. These are historical partial-build measurements; the final full-corpus result is recorded above.
