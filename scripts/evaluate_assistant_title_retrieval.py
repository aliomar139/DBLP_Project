"""Measure the connected local title-retrieval service on the reviewed dev probes."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import statistics
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / '.work' / 'rag-benchmark' / 'packages'))

from backend.app.services.title_retrieval import get_full_title_index
from fastapi.testclient import TestClient
from backend.app.main import app


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    at = (len(ordered) - 1) * percent
    low, high = int(at), min(int(at) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (at - low)


def main() -> None:
    import psutil

    probe_path = ROOT / 'docs' / 'assistant' / 'retrieval-probes-v1.json'
    probes = json.loads(probe_path.read_text(encoding='utf-8'))['probes']
    service_started = perf_counter()
    index = get_full_title_index()
    initialization_seconds = perf_counter() - service_started
    cases = []
    query_seconds = []
    for probe in probes:
        started = perf_counter()
        matches = index.search(probe['query'], limit=8)
        elapsed = perf_counter() - started
        query_seconds.append(elapsed)
        ids = [item.publication_id for item in matches]
        target = int(probe['publication_id'])
        cases.append({
            'case_id': probe['id'],
            'expected_publication_id': target,
            'target_rank_at_8': ids.index(target) + 1 if target in ids else None,
            'returned_ids_validated_against_active_duckdb': all(
                item.publication_id > 0 and item.db_key and item.title for item in matches),
            'stage_latency_ms': dict(index.last_timings),
        })
    first = probes[0]
    assistant_started = perf_counter()
    with TestClient(app) as client:
        response = client.post('/api/assistant/query', json={
            'query': f"Find papers about {first['query']}"})
    assistant_elapsed_ms = (perf_counter() - assistant_started) * 1000
    assistant_result = response.json()
    assistant_route = {
        'http_status': response.status_code,
        'elapsed_ms_single_sample': assistant_elapsed_ms,
        'status': assistant_result.get('status'),
        'expected_target_id': int(first['publication_id']),
        'expected_target_cited': any(
            source.get('id') == int(first['publication_id']) and
            source.get('href') == f"/papers/{int(first['publication_id'])}"
            for source in assistant_result.get('sources', [])),
        'title_only_qualification_present': 'title matches do not establish paper contents'
            in assistant_result.get('answer', ''),
        'claims_validated': bool(assistant_result.get('claims')),
    }
    hits = [case['target_rank_at_8'] is not None for case in cases]
    latency_ms = [seconds * 1000 for seconds in query_seconds]
    process = psutil.Process()
    report = {
        'version': 1,
        'status': 'connected_full_title_retrieval_development_evaluation',
        'observed_at_utc': datetime.now(timezone.utc).isoformat(),
        'database_sha256': index.manifest['corpus_sha256'],
        'index_id': index.manifest['corpus_id'],
        'eligible_titles': index.manifest['expected_eligible_titles'],
        'empty_title_exclusions': index.manifest['empty_title_exclusions'],
        'index_initialization_seconds_including_database_fingerprint_check': initialization_seconds,
        'probe_count': len(cases),
        'assistant_route_smoke': assistant_route,
        'target_recall_at_8': sum(hits) / len(hits) if hits else 0.0,
        'latency_ms': {
            'mean': statistics.fmean(latency_ms) if latency_ms else 0.0,
            'p95': percentile(latency_ms, .95),
            'max': max(latency_ms, default=0.0),
        },
        'process_working_set_bytes': process.memory_info().rss,
        'process_peak_working_set_bytes': getattr(process.memory_info(), 'peak_wset', process.memory_info().rss),
        'cases': cases,
        'qualification': '12 title-only development probes, not held-out relevance or answer accuracy. Latency excludes index initialization and measures warmed retrieval plus active-DuckDB validation.',
    }
    output = ROOT / 'reports' / 'assistant' / 'connected-title-retrieval-v1.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
