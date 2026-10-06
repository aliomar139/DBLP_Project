"""Local-only partial-corpus feasibility experiment. Never activates a search index.

Dependencies live in .work/rag-benchmark/packages. Setup must finish first.
All test queries and vectors stay local; each sampled ID comes from active DuckDB.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".work/rag-benchmark/packages"))
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import duckdb
import faiss
import numpy as np
import onnxruntime as ort
import psutil
from tokenizers import Tokenizer


def stats(values):
    return {"mean": float(np.mean(values)), "p95": float(np.percentile(values, 95)),
            "max": float(np.max(values))}


def peak_rss():
    info = psutil.Process().memory_info()
    return getattr(info, "peak_wset", info.rss)


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


class Encoder:
    def __init__(self, model, threads):
        manifest = json.loads((model / "manifest.json").read_text(encoding="utf-8"))
        for name, expected in manifest["sha256"].items():
            if hashlib.sha256((model / name).read_bytes()).hexdigest() != expected:
                raise ValueError("Model file checksum mismatch")
        self.tokenizer = Tokenizer.from_file(str(model / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=256)
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]")
        options = ort.SessionOptions()
        options.intra_op_num_threads = threads
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(model / "onnx/model_quint8_avx2.onnx"),
            sess_options=options, providers=["CPUExecutionProvider"])
        self.input_names = {x.name for x in self.session.get_inputs()}
        self.truncated = 0

    def encode(self, titles):
        tokens = self.tokenizer.encode_batch(titles)
        self.truncated += sum(bool(t.overflowing) for t in tokens)
        data = {"input_ids": np.asarray([t.ids for t in tokens], dtype=np.int64),
                "attention_mask": np.asarray([t.attention_mask for t in tokens], dtype=np.int64),
                "token_type_ids": np.asarray([t.type_ids for t in tokens], dtype=np.int64)}
        outputs = self.session.run(None, {k: v for k, v in data.items() if k in self.input_names})
        # Official model uses attention-mask-weighted mean pooling, then L2 normalization.
        hidden = outputs[0]
        mask = data["attention_mask"][..., None].astype(np.float32)
        pooled = (hidden * mask).sum(axis=1) / mask.sum(axis=1).clip(min=1)
        pooled /= np.linalg.norm(pooled, axis=1, keepdims=True).clip(min=1e-9)
        return np.ascontiguousarray(pooled, dtype=np.float32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-size", type=int, default=20000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("DBLP_DB_PATH", ROOT / "database/dblp.duckdb")))
    parser.add_argument("--output", type=Path, default=ROOT / "reports/assistant/feasibility-v1.json")
    args = parser.parse_args()
    if not 1000 <= args.sample_size <= 100000 or not 1 <= args.batch_size <= 256 or not 1 <= args.threads <= 12:
        parser.error("bounded sample/batch/thread parameters required")
    start = perf_counter()
    model = ROOT / ".work/rag-benchmark/model"
    work = ROOT / ".work/rag-benchmark" / ("run-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    work.mkdir(parents=True)
    faiss.omp_set_num_threads(args.threads)
    probe_file = ROOT / "docs/assistant/retrieval-probes-v1.json"
    probes = json.loads(probe_file.read_text(encoding="utf-8"))["probes"]
    with closing(duckdb.connect(str(args.db), read_only=True, config={"memory_limit": "4GB", "threads": "4"})) as db:
        counts = db.execute("""SELECT count(*), count(*) FILTER(WHERE length(trim(title))>0),
            count(*) FILTER(WHERE title IS NULL OR length(trim(title))=0) FROM publications""").fetchone()
        sample_start = perf_counter()
        # Reservoir sampling runs after eligibility filtering, spans the entire table,
        # and uses one thread so the seed gives reproducible input ordering.
        db.execute("SET threads=1")
        rows = db.execute(f"""SELECT publication_id,title,year,type FROM
            (SELECT publication_id,title,year,type FROM publications WHERE length(trim(title))>0)
            USING SAMPLE reservoir({args.sample_size} ROWS) REPEATABLE(42)""").fetchall()
        probe_ids = [p['publication_id'] for p in probes]
        probe_rows = db.execute("SELECT publication_id,title,year,type FROM publications WHERE publication_id IN ("
            + ','.join('?' for _ in probe_ids) + ") AND length(trim(title))>0", probe_ids).fetchall()
        if len(probe_rows) != len(probe_ids):
            raise ValueError('Development probe IDs are not present in this database; review the probe set')
        sampled_ids = {r[0] for r in rows}
        supplement = [r for r in probe_rows if r[0] not in sampled_ids]
        rows.extend(supplement)
        rows.sort(key=lambda r: r[0])
        sample_seconds = perf_counter() - sample_start
        distributions = db.execute("""SELECT type,count(*) FROM publications
            WHERE length(trim(title))>0 GROUP BY type ORDER BY type""").fetchall()
    ids = np.asarray([r[0] for r in rows], dtype=np.int64)
    titles = [r[1] for r in rows]
    n = len(rows)
    report = {"benchmark_version": 1, "status": "partial_corpus_experiment_not_production",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_path": str(args.db.resolve()), "database_size_bytes": args.db.stat().st_size,
        "database_mtime_ns": args.db.stat().st_mtime_ns,
        "database_sha256": file_sha256(args.db),
        "model": json.loads((model / "manifest.json").read_text(encoding="utf-8")),
        "corpus_publications": counts[0], "eligible_titles": counts[1], "empty_title_exclusions": counts[2],
        "sample_size": n, "sample_seed": 42, "sample_strategy": "single-thread reservoir over all eligible titles, supplemented with development probe targets",
        "development_target_supplement_count": len(supplement),
        "sample_ids_sha256": hashlib.sha256(ids.tobytes()).hexdigest(),
        "sample_seconds": sample_seconds, "sample_type_counts": dict(Counter(r[3] for r in rows)),
        "corpus_type_counts": dict(distributions), "sample_year_range": [min(r[2] for r in rows if r[2]), max(r[2] for r in rows if r[2])],
        "title_characters": stats([len(t) for t in titles]),
        "machine": {"processor": os.environ.get("PROCESSOR_IDENTIFIER"), "logical_cpus": os.cpu_count(),
                    "ram_bytes": psutil.virtual_memory().total, "threads": args.threads},
        "batch_size": args.batch_size, "work_directory": str(work), "lexical": {}, "vector": {}}
    (work / "sample.json").write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
    print(f"Sample ready: {n} / {counts[1]} eligible titles", flush=True)
    t = perf_counter()
    encoder = Encoder(model, args.threads)
    report["model_load_seconds"] = perf_counter() - t
    encoder.encode(titles[:args.batch_size])
    encoder.truncated = 0
    vectors = np.lib.format.open_memmap(work / "vectors.npy", mode="w+", dtype=np.float32, shape=(n,384))
    durations = []
    for offset in range(0,n,args.batch_size):
        t = perf_counter()
        vectors[offset:offset+args.batch_size] = encoder.encode(titles[offset:offset+args.batch_size])
        durations.append(perf_counter()-t)
        if offset % (args.batch_size*20) == 0:
            print(f"Embedded {min(offset+args.batch_size,n)}/{n}; {peak_rss()/2**30:.3f} GiB process peak", flush=True)
    vectors.flush()
    seconds = sum(durations)
    report["embedding"] = {"seconds": seconds, "titles_per_second": n/seconds,
        "batch_seconds": stats(durations), "truncated_titles": encoder.truncated,
        "projected_full_embedding_hours": counts[1]*seconds/n/3600,
        "projection_warning": "Linear sample projection excludes thermal slowdown, full-index construction, retries and validation.",
        "peak_process_rss_bytes": peak_rss()}
    # Exact-title probes test identity retrieval, not semantic understanding.
    positions = np.linspace(0,n-1,100,dtype=int)
    queries = [titles[i] for i in positions]
    qv = np.concatenate([encoder.encode(queries[i:i+args.batch_size]) for i in range(0,len(queries),args.batch_size)])
    id_positions = {int(pid): i for i,pid in enumerate(ids)}
    if any(p["publication_id"] not in id_positions for p in probes):
        raise ValueError("Development probe IDs absent from sample; regenerate and review probes for this database/sample")
    paraphrase_vectors = encoder.encode([p["query"] for p in probes])
    report["development_probes"] = {"file":str(probe_file),"sha256":hashlib.sha256(probe_file.read_bytes()).hexdigest(),
        "count":len(probes),"qualification":"Title-only development set; not held-out evaluation or full-corpus recall"}
    exact = faiss.IndexFlatIP(384)
    exact.add(vectors)
    _, ground_truth = exact.search(qv,10)
    _, paraphrase_truth = exact.search(paraphrase_vectors,10)
    report["development_probes"]["exact_vector_target_hit_at_10"] = float(np.mean([
        id_positions[p["publication_id"]] in paraphrase_truth[i] for i,p in enumerate(probes)]))
    for name in ("hnsw32_float32", "hnsw32_scalar8"):
        if name.endswith("float32"):
            index = faiss.IndexHNSWFlat(384,32,faiss.METRIC_INNER_PRODUCT)
        else:
            index = faiss.IndexHNSWSQ(384,faiss.ScalarQuantizer.QT_8bit,32,faiss.METRIC_INNER_PRODUCT)
        index.hnsw.efConstruction = 120
        t = perf_counter()
        if not index.is_trained:
            index.train(vectors)
        training = perf_counter()-t
        t = perf_counter()
        for offset in range(0,n,1000):
            index.add(vectors[offset:offset+1000])
        build = perf_counter()-t
        faiss.write_index(index,str(work/(name+".faiss")))
        size = (work/(name+".faiss")).stat().st_size
        settings = []
        for ef in (32,64,128):
            index.hnsw.efSearch = ef
            latencies, recall, self_hits = [], [], []
            for qi, query in enumerate(qv):
                t = perf_counter()
                _, found = index.search(query[None,:],10)
                latencies.append((perf_counter()-t)*1000)
                recall.append(len(set(found[0]) & set(ground_truth[qi]))/10)
                self_hits.append(int(positions[qi] in found[0]))
            settings.append({"ef_search": ef, "ann_recall_at_10": float(np.mean(recall)),
                "exact_title_id_hit_at_10": float(np.mean(self_hits)), "search_ms": stats(latencies)})
            t = perf_counter()
            _, found = index.search(paraphrase_vectors,10)
            settings[-1]["development_paraphrase_ann_recall_at_10"] = float(np.mean([
                len(set(found[i]) & set(paraphrase_truth[i]))/10 for i in range(len(probes))]))
            settings[-1]["development_paraphrase_target_hit_at_10"] = float(np.mean([
                id_positions[p["publication_id"]] in found[i] for i,p in enumerate(probes)]))
        report["vector"][name] = {"training_seconds":training,"add_seconds":build,"bytes":size,
            "linear_projected_full_bytes":int(size/n*counts[1]),
            "linear_projected_full_add_hours_lower_bound":build/n*counts[1]/3600,
            "projection_warning":"Graph construction/search costs change with corpus size; sample timing is not full-scale proof.",
            "settings":settings,"peak_process_rss_bytes":peak_rss()}
        del index
        print(f"Benchmarked {name}",flush=True)
    for name,tokenizer in (("unicode","unicode61"),("porter","porter unicode61")):
        path = work/(name+".sqlite")
        with closing(sqlite3.connect(path)) as lex:
            lex.execute("PRAGMA cache_size=-65536")
            lex.execute(f"CREATE VIRTUAL TABLE titles USING fts5(title,tokenize='{tokenizer}')")
            t = perf_counter()
            lex.executemany("INSERT INTO titles(rowid,title) VALUES(?,?)",[(r[0],r[1]) for r in rows])
            lex.commit()
            lex.execute("INSERT INTO titles(titles) VALUES('optimize')")
            lex.commit()
            build = perf_counter()-t
            latency,hits = [],[]
            for pos,q in zip(positions,queries):
                tokens = re.findall(r"\w+",q)[:32]
                expression = " OR ".join('"'+s+'"' for s in tokens)
                t = perf_counter()
                found = lex.execute("SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT 10",(expression,)).fetchall() if expression else []
                latency.append((perf_counter()-t)*1000)
                hits.append(int(int(ids[pos]) in {x[0] for x in found}))
            report["lexical"][name] = {"build_seconds":build,"bytes":path.stat().st_size,
                "linear_projected_full_bytes":int(path.stat().st_size/n*counts[1]),
                "linear_projected_full_build_minutes":build/n*counts[1]/60,
                "exact_title_id_hit_at_10":float(np.mean(hits)),"search_ms":stats(latency),
                "queries":"Bounded first 32 title tokens joined by OR; exact-title discovery proxy only"}
            probe_results = []
            for probe in probes:
                expression = " OR ".join('"'+s+'"' for s in re.findall(r"\w+",probe['query'])[:32])
                found = lex.execute("SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT 10",(expression,)).fetchall()
                probe_results.append({"id":probe['id'],"target_hit_at_10":probe['publication_id'] in {r[0] for r in found}})
            report['lexical'][name]['development_paraphrase_results'] = probe_results
            report['lexical'][name]['development_paraphrase_target_hit_at_10'] = float(np.mean([r['target_hit_at_10'] for r in probe_results]))
    report["peak_process_rss_bytes"] = peak_rss()
    report["experiment_disk_bytes"] = sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
    report["duration_seconds"] = perf_counter()-start
    report["limitations"] = ["No full-corpus build or 10-second end-to-end latency measurement.",
        "ANN recall against exact neighbors measures index fidelity, not relevance.",
        "Paraphrases form a 12-item title-only development set, not user-reviewed or held-out evaluation.",
        "Process peak includes retained vectors, exact baseline, and sequential candidate builds.",
        "Full build must handle or explicitly report long-title token truncation.",
        "Results bind to the recorded database fingerprint; candidate and active corpora must not be confused."]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"report":str(args.output),"embedding":report['embedding'],"seconds":report['duration_seconds']}),flush=True)


if __name__ == "__main__":
    main()
