"""Evaluate generation quality on DBLP-QA questions with and without Abstract Grounding (Top-3-CD)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx
from openai import OpenAI
from backend.app.services.abstract_service import get_cached_abstract

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

def generate(client: OpenAI, prompt: str, system_prompt: str) -> str:
    resp = client.chat.completions.create(
        model="qwen2.5-coder:7b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=150,
        extra_body={"options": {"num_thread": 8, "num_ctx": 2048}},
    )
    return resp.choices[0].message.content or ""

def main():
    print("=== DBLP-QA Generation Evaluation: No-Context vs. Top-3-CD Abstracts ===")
    client = OpenAI(
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        timeout=httpx.Timeout(60.0, connect=5.0),
    )

    csv_path = ROOT / 'data' / 'benchmarks' / 'dblp_qa.csv'
    with open(csv_path, 'r', encoding='utf-8') as f:
        qa_pairs = list(csv.DictReader(f))

    # Evaluate on first 6 questions
    test_cases = qa_pairs[:6]
    results = []

    no_context_sys = "You are a scientific assistant. Answer the user question concisely in 1-2 sentences."
    abstract_sys = "You are a scientific assistant. Answer the user question concisely in 1-2 sentences based directly on the provided scientific abstract."

    for i, item in enumerate(test_cases, 1):
        q_id = item['id']
        question = item['question']
        ground_truth = item['answer']
        db_key = item['dblp_key']
        abstract = get_cached_abstract(db_key=db_key) or ""

        print(f"\n--- Testing [{i}/{len(test_cases)}] {q_id}: {question[:50]} ---")

        # 1. No Context
        t0 = time.perf_counter()
        no_ctx_ans = generate(client, f"Question: {question}", no_context_sys)
        no_ctx_time = time.perf_counter() - t0
        no_ctx_rouge = rouge_l(ground_truth, no_ctx_ans)

        # 2. Abstract Grounded (Top-CD)
        t0 = time.perf_counter()
        abs_prompt = f"Abstract Evidence: {abstract}\n\nQuestion: {question}"
        abs_ans = generate(client, abs_prompt, abstract_sys)
        abs_time = time.perf_counter() - t0
        abs_rouge = rouge_l(ground_truth, abs_ans)

        print(f"No-Context ROUGE-L: {no_ctx_rouge:.4f} ({no_ctx_time:.1f}s)")
        print(f"Abstract-Grounded ROUGE-L: {abs_rouge:.4f} ({abs_time:.1f}s)")
        print(f"Ground Truth: {ground_truth[:80]}...")
        print(f"Abstract Ans: {abs_ans[:80]}...")

        results.append({
            "id": q_id,
            "question": question,
            "ground_truth": ground_truth,
            "no_context_answer": no_ctx_ans,
            "no_context_rouge_l": no_ctx_rouge,
            "abstract_answer": abs_ans,
            "abstract_rouge_l": abs_rouge,
            "improvement": abs_rouge - no_ctx_rouge
        })

    avg_no_ctx = sum(r['no_context_rouge_l'] for r in results) / len(results)
    avg_abs = sum(r['abstract_rouge_l'] for r in results) / len(results)

    print("\n" + "="*50)
    print("GENERATION EVALUATION SUMMARY")
    print("="*50)
    print(f"Average No-Context ROUGE-L:       {avg_no_ctx:.4f}")
    print(f"Average Abstract-Grounded ROUGE-L: {avg_abs:.4f}")
    print(f"Net Gain from Abstract Grounding:  +{avg_abs - avg_no_ctx:.4f} (+{(avg_abs - avg_no_ctx)/avg_no_ctx*100:.1f}%)")
    print("="*50)

    out_file = ROOT / 'reports' / 'dblp_qa_generation_comparison.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"Saved evaluation details to {out_file}")

if __name__ == '__main__':
    main()

