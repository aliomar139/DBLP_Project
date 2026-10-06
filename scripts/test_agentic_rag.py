"""Test script to verify the Agentic RAG service with Ollama and DuckDB.
"""
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.agentic_rag import is_ollama_ready, ask_agentic_rag, execute_safe_sql

def main():
    print("=" * 60)
    print("Testing DBLP Agentic RAG Pipeline")
    print("=" * 60)

    # 1. Test direct safe SQL execution on DuckDB
    print("\n1. Testing DuckDB connection & safe SQL...")
    rows, err = execute_safe_sql("SELECT COUNT(*) AS total_publications FROM publications;")
    if err:
        print(f"[ERROR] SQL Execution Error: {err}")
    else:
        print(f"[OK] DuckDB connection successful! Total publications in DB: {rows[0].get('total_publications', rows)}")

    # 2. Test Ollama availability
    print("\n2. Checking Ollama service & Qwen2.5-Coder-7b model...")
    ready = is_ollama_ready("qwen2.5-coder:7b")
    if not ready:
        print("[INFO] Ollama or 'qwen2.5-coder:7b' is not ready yet (likely still downloading).")
        print("       Once 'ollama pull qwen2.5-coder:7b' finishes, rerun this script to test end-to-end!")
        return

    print("[OK] Ollama is ready with qwen2.5-coder:7b!")

    # 3. Test end-to-end question
    test_queries = [
        "Which venues published the most papers in 2021?",
        "Find some recent papers about graph neural networks",
        "How many papers did Geoffrey Hinton publish?",
    ]

    for q in test_queries:
        print(f"\n--- Testing Query: '{q}' ---")
        t0 = time.time()
        res = ask_agentic_rag(q)
        elapsed = time.time() - t0
        print(f"Status: {res.status} (Elapsed: {elapsed:.2f}s)")
        print(f"Sources identified: {len(res.sources)}")
        print(f"Calculations attached: {len(res.calculations)}")
        print(f"Answer:\n{res.answer}\n")

if __name__ == "__main__":
    main()
