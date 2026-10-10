"""DBLP-QA Benchmark Evaluation: Comparing Title-Level Hybrid Retrieval against RAGScholar BM25."""
from __future__ import annotations

import csv
import argparse
import json
from pathlib import Path
import re
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.work' / 'rag-benchmark' / 'packages'))

import duckdb
from backend.app.services.title_retrieval import get_full_title_index

def lcs_length(x: list[str], y: list[str]) -> int:
    m, n = len(x), len(y)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(m):
        for j in range(n):
            if x[i] == y[j]:
                dp[i + 1][j + 1] = dp[i][j] + 1
            else:
                dp[i + 1][j + 1] = max(dp[i + 1][j], dp[i][j + 1])
    return dp[m][n]

def rouge_l(reference: str, hypothesis: str) -> float:
    ref_tokens = re.findall(r'\w+', reference.lower())
    hyp_tokens = re.findall(r'\w+', hypothesis.lower())
    if not ref_tokens or not hyp_tokens:
        return 0.0
    lcs = lcs_length(ref_tokens, hyp_tokens)
    prec = lcs / len(hyp_tokens)
    rec = lcs / len(ref_tokens)
    return (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'reports' / 'dblp_qa_retrieval_results.json')
    parser.add_argument('--expected-engine', choices=('tantivy', 'sqlite_fts5'), default='tantivy')
    args = parser.parse_args()

    print("=== Loading DBLP-QA Dataset ===")
    csv_path = ROOT / 'data' / 'benchmarks' / 'dblp_qa.csv'
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        qa_pairs = list(reader)

    print(f"Loaded {len(qa_pairs)} benchmark QA pairs.")

    print("=== Mapping DBLP keys to publication metadata in DuckDB ===")
    db = duckdb.connect(str(ROOT / 'database' / 'dblp.duckdb'), read_only=True)
    all_keys = [item['dblp_key'] for item in qa_pairs]
    key_slots = ','.join(repr(k) for k in all_keys)
    rows = db.execute(f"SELECT publication_id, db_key, title, year FROM publications WHERE db_key IN ({key_slots})").fetchall()
    key_to_pub = {row[1]: {'publication_id': row[0], 'title': row[2], 'year': row[3]} for row in rows}
    db.close()
    print(f"Matched {len(key_to_pub)} / {len(qa_pairs)} keys in DuckDB.")

    print("=== Initializing Local Hybrid Title Index ===")
    start_init = time.perf_counter()
    index = get_full_title_index()
    if index._keyword_engine != args.expected_engine:
        raise RuntimeError(
            f"Expected keyword engine {args.expected_engine}, got {index._keyword_engine}; refusing to run the wrong benchmark."
        )
    print(f"Keyword engine: {index._keyword_engine}")
    print(f"Index ready in {time.perf_counter() - start_init:.2f}s")

    print("\n=== Evaluating Retrieval Performance (RQ1) ===")
    results = []
    ranks = []
    latencies = []
    
    for i, item in enumerate(qa_pairs, 1):
        q_id = item['id']
        question = item['question']
        target_key = item['dblp_key']
        target_meta = key_to_pub.get(target_key)
        target_pid = target_meta['publication_id'] if target_meta else None

        # Perform retrieval
        start_q = time.perf_counter()
        matches = index.search(question, limit=5)
        latency = (time.perf_counter() - start_q) * 1000
        latencies.append(latency)

        retrieved_keys = [m.db_key for m in matches]
        retrieved_titles = [m.title for m in matches]

        rank = None
        if target_key in retrieved_keys:
            rank = retrieved_keys.index(target_key) + 1
        ranks.append(rank)

        results.append({
            'id': q_id,
            'question': question,
            'ground_truth_answer': item['answer'],
            'target_key': target_key,
            'target_title': target_meta['title'] if target_meta else '',
            'rank': rank,
            'latency_ms': latency,
            'top1_retrieved_title': retrieved_titles[0] if retrieved_titles else '',
            'top1_retrieved_key': retrieved_keys[0] if retrieved_keys else '',
        })

    total = len(qa_pairs)
    r_at_1 = sum(1 for r in ranks if r == 1) / total
    r_at_2 = sum(1 for r in ranks if r is not None and r <= 2) / total
    r_at_3 = sum(1 for r in ranks if r is not None and r <= 3) / total
    r_at_5 = sum(1 for r in ranks if r is not None and r <= 5) / total

    rr_at_3 = sum(1.0 / r for r in ranks if r is not None and r <= 3) / total
    rr_at_5 = sum(1.0 / r for r in ranks if r is not None and r <= 5) / total

    print("\n" + "="*50)
    print("RETRIEVAL EVALUATION RESULTS (50 DBLP-QA queries)")
    print("="*50)
    print(f"Total Queries: {total}")
    print(f"Recall@1: {r_at_1:.4f}  ({sum(1 for r in ranks if r == 1)}/{total})  [RAGScholar Paper BM25: 0.8800]")
    print(f"Recall@3: {r_at_3:.4f}  ({sum(1 for r in ranks if r is not None and r <= 3)}/{total})  [RAGScholar Paper BM25: 1.0000]")
    print(f"Recall@5: {r_at_5:.4f}  ({sum(1 for r in ranks if r is not None and r <= 5)}/{total})  [RAGScholar Paper: N/A]")
    print(f"MRR@3:    {rr_at_3:.4f}  [RAGScholar Paper BM25: 0.9300]")
    print(f"MRR@5:    {rr_at_5:.4f}")
    print("="*50)

    # Save retrieval results
    output_path = args.output if args.output.is_absolute() else ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'keyword_engine': index._keyword_engine,
            'index_id': index.manifest['corpus_id'],
            'index_title_count': index.manifest['expected_eligible_titles'],
            'total': total,
            'mean_latency_ms': statistics.fmean(latencies) if latencies else 0,
            'p95_latency_ms': sorted(latencies)[min(len(latencies) - 1, round((len(latencies) - 1) * .95))] if latencies else 0,
            'recall_at_1': r_at_1,
            'recall_at_3': r_at_3,
            'recall_at_5': r_at_5,
            'mrr_at_3': rr_at_3,
            'mrr_at_5': rr_at_5,
            'paper_baseline': {
                'recall_at_1': 0.88,
                'recall_at_3': 1.00,
                'mrr_at_3': 0.93,
            },
            'details': results
        }, f, indent=2)
    print(f"Detailed retrieval results saved to {output_path}")

if __name__ == '__main__':
    main()
