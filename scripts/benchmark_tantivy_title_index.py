"""Build an isolated Tantivy title index and compare it with SQLite FTS5."""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path
from statistics import mean
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
STOP_WORDS = {'a', 'an', 'and', 'are', 'for', 'from', 'in', 'of', 'on', 'or',
              'papers', 'paper', 'research', 'the', 'to', 'with', 'about'}


def lexical_terms(query: str) -> list[str]:
    return [token for token in dict.fromkeys(re.findall(r'[a-z0-9]+', query.casefold()))
            if len(token) > 1 and token not in STOP_WORDS][:24]


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, round((len(ordered) - 1) * pct))]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--sidecar', type=Path, default=ROOT / 'database/indexes/dblp-title-v2')
    ap.add_argument('--index', type=Path, default=ROOT / '.work/tantivy-title-v1')
    ap.add_argument('--package-dir', type=Path, default=ROOT / '.work/rag-benchmark/packages')
    ap.add_argument('--output', type=Path, default=ROOT / 'reports/assistant/tantivy-title-benchmark-v1.json')
    ap.add_argument('--threads', type=int, default=4)
    ap.add_argument('--rebuild', action='store_true')
    args = ap.parse_args()

    sys.path.insert(0, str(args.package_dir))
    import tantivy

    sqlite_path = args.sidecar / 'keyword-map.sqlite'
    manifest = json.loads((args.sidecar / 'manifest.json').read_text(encoding='utf-8'))
    probes = json.loads((ROOT / 'docs/assistant/retrieval-probes-v1.json').read_text(encoding='utf-8'))['probes']
    args.index.mkdir(parents=True, exist_ok=True)
    schema_builder = tantivy.SchemaBuilder()
    schema_builder.add_text_field('title', stored=False)
    schema_builder.add_integer_field('publication_id', stored=True, indexed=False)
    schema = schema_builder.build()
    if args.rebuild and any(args.index.iterdir()):
        import shutil
        shutil.rmtree(args.index)
        args.index.mkdir(parents=True)
    start_all = perf_counter()
    build_seconds = 0.0
    if not any(args.index.iterdir()):
        index = tantivy.Index(schema, path=str(args.index))
        writer = index.writer(heap_size=256_000_000, num_threads=args.threads)
        db = sqlite3.connect(f'file:{sqlite_path.resolve().as_posix()}?mode=ro&immutable=1', uri=True)
        cur = db.execute('SELECT rowid,title FROM titles ORDER BY rowid')
        build_started = perf_counter()
        count = 0
        try:
            while rows := cur.fetchmany(5000):
                for publication_id, title in rows:
                    writer.add_document(tantivy.Document(
                        title=[title], publication_id=int(publication_id)))
                count += len(rows)
                if count % 500_000 == 0:
                    print(f'indexed {count:,} titles', flush=True)
            writer.commit()
            writer.wait_merging_threads()
        finally:
            db.close()
        build_seconds = perf_counter() - build_started
        index.reload()
        print(f'index complete: {count:,} titles in {build_seconds:.1f}s', flush=True)
    else:
        index = tantivy.Index.open(str(args.index))
    searcher = index.searcher()

    def tantivy_search(query: str) -> tuple[list[int], float]:
        terms = lexical_terms(query)
        expr = ' OR '.join('"' + t.replace('"', '') + '"' for t in terms)
        if not expr:
            return [], 0.0
        t0 = perf_counter()
        parsed = index.parse_query(expr, ['title'])
        found = searcher.search(parsed, 50)
        ids = [int(searcher.doc(address)['publication_id'][0]) for _, address in found.hits]
        return ids, (perf_counter() - t0) * 1000

    fts_times: list[float] = []
    tantivy_times: list[float] = []
    cases = []
    db = sqlite3.connect(f'file:{sqlite_path.resolve().as_posix()}?mode=ro&immutable=1', uri=True)
    try:
        for probe in probes:
            query = probe['query']
            terms = lexical_terms(query)
            expr = ' OR '.join('"' + t.replace('"', '') + '"' for t in terms)
            t0 = perf_counter()
            fts_rows = db.execute(
                'SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT 50', (expr,)
            ).fetchall() if expr else []
            fts_ms = (perf_counter() - t0) * 1000
            fts_ids = [int(row[0]) for row in fts_rows]
            tantivy_ids, tantivy_ms = tantivy_search(query)
            target = int(probe['publication_id'])
            cases.append({
                'case_id': probe['id'], 'target_id': target,
                'fts5_rank': fts_ids.index(target) + 1 if target in fts_ids else None,
                'tantivy_rank': tantivy_ids.index(target) + 1 if target in tantivy_ids else None,
                'fts5_ms': fts_ms, 'tantivy_ms': tantivy_ms,
                'top10_overlap': len(set(fts_ids[:10]) & set(tantivy_ids[:10])),
            })
            fts_times.append(fts_ms)
            tantivy_times.append(tantivy_ms)
    finally:
        db.close()
    def hit(field: str) -> float:
        return sum(c[field] is not None and c[field] <= 10 for c in cases) / len(cases)
    index_bytes = sum(f.stat().st_size for f in args.index.rglob('*') if f.is_file())
    result = {
        'status': 'isolated_full_title_keyword_engine_comparison',
        'tantivy_version': getattr(tantivy, '__version__', 'unknown'),
        'index_document_count': manifest['expected_eligible_titles'],
        'source_manifest_sha256': __import__('hashlib').sha256((args.sidecar / 'manifest.json').read_bytes()).hexdigest(),
        'probe_count': len(cases),
        'build_seconds': build_seconds,
        'tantivy_index_bytes': index_bytes,
        'retrieval': {
            'fts5_target_hit_at_10': hit('fts5_rank'),
            'tantivy_target_hit_at_10': hit('tantivy_rank'),
            'mean_top10_overlap': mean(c['top10_overlap'] for c in cases),
        },
        'latency_ms': {
            'fts5_mean': mean(fts_times), 'fts5_p95': percentile(fts_times, .95),
            'tantivy_mean': mean(tantivy_times), 'tantivy_p95': percentile(tantivy_times, .95),
        },
        'qualification': '12 title-only development probes, not held-out or user-reviewed; candidate ranking measured without DuckDB validation.',
        'cases': cases,
        'elapsed_seconds': perf_counter() - start_all,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    main()
