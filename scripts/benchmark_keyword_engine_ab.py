"""Compare the live Tantivy and FTS5 paths on identical full-retrieval probes."""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys_path_root = str(ROOT)
import sys
if sys_path_root not in sys.path:
    sys.path.insert(0, sys_path_root)

from backend.app.services.title_retrieval import get_full_title_index


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def run_query(index, engine: str, query: str, target: int) -> dict:
    index._keyword_engine = engine
    index._tantivy_searcher = index._active_tantivy_searcher if engine == 'tantivy' else None
    started = perf_counter()
    matches = index.search(query, limit=8)
    elapsed_ms = (perf_counter() - started) * 1000
    ids = [match.publication_id for match in matches]
    return {
        'target_rank_at_8': ids.index(target) + 1 if target in ids else None,
        'records_validated': all(match.db_key and match.title for match in matches),
        'elapsed_ms': elapsed_ms,
        'stages': dict(index.last_timings),
    }


def main() -> None:
    probes = json.loads((ROOT / 'docs/assistant/retrieval-probes-v1.json').read_text(encoding='utf-8'))['probes']
    index = get_full_title_index()
    index._active_tantivy_searcher = index._tantivy_searcher
    if index._active_tantivy_searcher is None:
        raise RuntimeError('The versioned Tantivy index is not active; refusing to compare.')
    # Warm both paths before timed runs; alternate order by probe to reduce cache bias.
    first = probes[0]
    for engine in ('fts5', 'tantivy'):
        run_query(index, engine, first['query'], int(first['publication_id']))
    cases = []
    timings = {'fts5': [], 'tantivy': []}
    hits = {'fts5': 0, 'tantivy': 0}
    for i, probe in enumerate(probes):
        target = int(probe['publication_id'])
        order = ('fts5', 'tantivy') if i % 2 == 0 else ('tantivy', 'fts5')
        results = {}
        for engine in order:
            results[engine] = run_query(index, engine, probe['query'], target)
            timings[engine].append(results[engine]['elapsed_ms'])
            if results[engine]['target_rank_at_8'] is not None:
                hits[engine] += 1
        cases.append({'case_id': probe['id'], **results})
    def summarize(engine: str) -> dict:
        values = timings[engine]
        return {
            'target_hit_at_8': hits[engine] / len(probes),
            'mean_ms': statistics.fmean(values),
            'p50_ms': statistics.median(values),
            'p95_ms': percentile(values, .95),
            'max_ms': max(values),
            'mean_keyword_stage_ms': statistics.fmean(
                case[engine]['stages']['keyword_ms'] for case in cases),
        }
    report = {
        'status': 'paired_full_retriever_keyword_engine_comparison',
        'observed_at_utc': datetime.now(timezone.utc).isoformat(),
        'corpus_sha256': index.manifest['corpus_sha256'],
        'index_title_count': index.manifest['expected_eligible_titles'],
        'probe_count': len(probes),
        'warmup_runs_per_engine': 1,
        'engine_results': {engine: summarize(engine) for engine in ('fts5', 'tantivy')},
        'qualification': '12 title-only development probes; paired full retrieval includes Faiss, keyword search, RRF, and active DuckDB validation. Not held-out or user-reviewed.',
        'cases': cases,
    }
    output = ROOT / 'reports/assistant/keyword-engine-ab-v1.json'
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
