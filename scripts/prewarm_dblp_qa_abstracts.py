"""Pre-warm script to fetch and cache abstracts for the 50 DBLP-QA benchmark papers."""
from __future__ import annotations

import csv
import json
from pathlib import Path
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import duckdb
from backend.app.services.abstract_service import (
    init_abstract_db,
    get_cached_abstract,
    save_cached_abstract,
    fetch_from_openalex,
    fetch_from_semantic_scholar,
    USER_AGENT
)

def fetch_s2_by_id(s2_id: str) -> str | None:
    """Directly fetch paper abstract from Semantic Scholar if ID is known."""
    if not s2_id:
        return None
    try:
        url = f"https://api.semanticscholar.org/graph/v1/paper/{s2_id}?fields=title,abstract"
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            abstract = data.get('abstract')
            if abstract and len(abstract.strip()) > 30:
                return abstract.strip()
    except Exception as exc:
        pass
    return None

def fetch_arxiv_by_dblp_key(db_key: str) -> str | None:
    """If db_key is an arXiv key like journals/corr/abs-2403-19918, fetch via arXiv / OpenAlex."""
    if 'journals/corr/abs-' in db_key:
        arxiv_id = db_key.split('abs-')[-1].replace('-', '.')
        try:
            url = f"https://api.openalex.org/works/https://doi.org/10.48550/arXiv.{arxiv_id}"
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                from backend.app.services.abstract_service import _reconstruct_openalex_abstract
                abstract = _reconstruct_openalex_abstract(data.get('abstract_inverted_index'))
                if abstract and len(abstract) > 30:
                    return abstract
        except Exception:
            pass
    return None

def main():
    print("=== Pre-warming Abstracts for DBLP-QA Benchmark ===")
    init_abstract_db()

    csv_path = ROOT / 'data' / 'benchmarks' / 'dblp_qa.csv'
    with open(csv_path, 'r', encoding='utf-8') as f:
        qa_pairs = list(csv.DictReader(f))

    print(f"Loaded {len(qa_pairs)} benchmark questions.")

    # Fetch title & pub_id from DuckDB
    db = duckdb.connect(str(ROOT / 'database' / 'dblp.duckdb'), read_only=True)
    all_keys = [item['dblp_key'] for item in qa_pairs]
    key_slots = ','.join(repr(k) for k in all_keys)
    rows = db.execute(f"SELECT publication_id, db_key, title FROM publications WHERE db_key IN ({key_slots})").fetchall()
    meta_map = {r[1]: {'publication_id': r[0], 'title': r[2]} for r in rows}
    db.close()

    success_count = 0
    total = len(qa_pairs)

    for i, item in enumerate(qa_pairs, 1):
        db_key = item['dblp_key']
        s2_id = item.get('semantic_scholar_id')
        meta = meta_map.get(db_key, {})
        title = meta.get('title', '')
        pub_id = meta.get('publication_id')

        cached = get_cached_abstract(db_key=db_key)
        if cached:
            print(f"[{i}/{total}] ALREADY CACHED: {db_key} ({len(cached)} chars)")
            success_count += 1
            continue

        abstract = None
        source = 'openalex'

        # 1. Try OpenAlex by title
        if title:
            abstract = fetch_from_openalex(title)

        # 2. Try arXiv lookup if applicable
        if not abstract:
            abstract = fetch_arxiv_by_dblp_key(db_key)

        # 3. Try Semantic Scholar by S2 ID
        if not abstract and s2_id:
            abstract = fetch_s2_by_id(s2_id)
            source = 'semanticscholar'

        # 4. Try Semantic Scholar by title search
        if not abstract and title:
            abstract = fetch_from_semantic_scholar(title)
            source = 'semanticscholar'

        if abstract:
            save_cached_abstract(
                db_key=db_key,
                title=title,
                abstract=abstract,
                publication_id=pub_id,
                source=source
            )
            print(f"[{i}/{total}] FETCHED ({source}): {db_key} - {title[:45]} ({len(abstract)} chars)")
            success_count += 1
        else:
            print(f"[{i}/{total}] MISSING: {db_key} - {title[:45]}")

        # Gentle rate limit pause
        time.sleep(0.3)

    print("\n" + "="*50)
    print(f"PRE-WARM COMPLETED: {success_count} / {total} benchmark abstracts cached.")
    print("="*50)

if __name__ == '__main__':
    main()

