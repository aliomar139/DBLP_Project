import time
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.services.agentic_rag import stream_agentic_rag, ask_agentic_rag

queries = [
    "list all papers related to prediciting student burnout",
    "What is CtRL-Sim?"
]

print("=== STARTING BENCHMARK ===", flush=True)

for q in queries:
    print("\n" + "=" * 60, flush=True)
    print(f"QUERY: {q}", flush=True)
    
    # Test Streaming
    t0 = time.time()
    first_token_time = None
    first_content_time = None
    sources_count = 0
    token_count = 0
    full_text = []

    for chunk in stream_agentic_rag(q):
        now = time.time()
        if chunk.startswith("data: "):
            payload = json.loads(chunk[6:].strip())
            ptype = payload.get("type")
            if ptype == "init":
                sources = payload.get("sources", [])
                sources_count = len(sources)
                print(f"  [STREAM INIT] Status: {payload.get('status')}, Sources: {sources_count}, is_all: {payload.get('is_all_papers')}", flush=True)
            elif ptype == "token":
                if first_content_time is None:
                    first_content_time = now - t0
                token_count += 1
                full_text.append(payload.get("token", ""))
            elif ptype == "done":
                pass

    total_time = time.time() - t0
    print(f"  STREAM Total Time: {total_time:.2f}s", flush=True)
    print(f"  STREAM Time to First Token: {first_content_time:.3f}s" if first_content_time else "  No tokens", flush=True)
    print(f"  STREAM Sources Returned: {sources_count}", flush=True)
    print(f"  STREAM Token Count: {token_count}", flush=True)
    print(f"  STREAM Response Preview: {''.join(full_text)[:200]}...", flush=True)

    # Test Synchronous ask_agentic_rag
    t_sync = time.time()
    resp = ask_agentic_rag(q)
    sync_duration = time.time() - t_sync
    print(f"  SYNC Total Time: {sync_duration:.2f}s", flush=True)
    print(f"  SYNC Status: {resp.status}, Sources: {len(resp.sources)}", flush=True)
    print(f"  SYNC Answer Preview: {resp.answer[:200]}...", flush=True)

print("\n=== BENCHMARK COMPLETED ===", flush=True)

