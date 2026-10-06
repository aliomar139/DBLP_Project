"""Abstract Caching & Retrieval Service for Scientific Literature.

Maintains an immutable SQLite sidecar cache (`database/abstracts_cache.sqlite`)
and fetches missing abstracts on demand from OpenAlex (primary) and Semantic Scholar (fallback).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CACHE_DB_PATH = ROOT / 'database' / 'abstracts_cache.sqlite'

_log = logging.getLogger(__name__)

USER_AGENT = 'DBLP-Research-Intelligence/1.0 (mailto:research@dblp-intelligence.local)'


def get_db_connection() -> sqlite3.Connection:
    CACHE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(CACHE_DB_PATH), timeout=10.0)
    conn.execute('PRAGMA journal_mode=WAL;')
    return conn


def init_abstract_db() -> None:
    """Initialize the schema for the SQLite abstract sidecar cache."""
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS paper_abstracts (
                publication_id INTEGER,
                db_key TEXT UNIQUE,
                title TEXT,
                doi TEXT,
                abstract TEXT,
                source TEXT,
                fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_abstracts_db_key ON paper_abstracts(db_key);')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_abstracts_pub_id ON paper_abstracts(publication_id);')


def get_cached_abstract(db_key: str | None = None, publication_id: int | None = None) -> str | None:
    """Retrieve an abstract from local SQLite cache if available."""
    init_abstract_db()
    with get_db_connection() as conn:
        if db_key:
            row = conn.execute('SELECT abstract FROM paper_abstracts WHERE db_key = ?', (db_key,)).fetchone()
            if row and row[0]:
                return row[0]
        if publication_id is not None:
            row = conn.execute('SELECT abstract FROM paper_abstracts WHERE publication_id = ?', (publication_id,)).fetchone()
            if row and row[0]:
                return row[0]
    return None


def save_cached_abstract(
    db_key: str,
    title: str,
    abstract: str,
    publication_id: int | None = None,
    doi: str | None = None,
    source: str = 'openalex'
) -> None:
    """Persist an abstract into the SQLite sidecar cache."""
    if not abstract or not abstract.strip():
        return
    init_abstract_db()
    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO paper_abstracts (publication_id, db_key, title, doi, abstract, source, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(db_key) DO UPDATE SET
                abstract = excluded.abstract,
                title = COALESCE(excluded.title, paper_abstracts.title),
                doi = COALESCE(excluded.doi, paper_abstracts.doi),
                source = excluded.source,
                fetched_at = CURRENT_TIMESTAMP
        ''', (publication_id, db_key, title, doi, abstract.strip(), source))


def _reconstruct_openalex_abstract(inverted_index: dict[str, list[int]] | None) -> str | None:
    """Rebuild plain-text abstract from OpenAlex's inverted word-position map."""
    if not inverted_index:
        return None
    words_with_pos: list[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        for pos in positions:
            words_with_pos.append((pos, word))
    if not words_with_pos:
        return None
    words_with_pos.sort(key=lambda x: x[0])
    return ' '.join(word for _, word in words_with_pos).strip()


def _clean_title_for_search(title: str) -> str:
    cleaned = re.sub(r'[\.\:\;\,\?\!\'\"]', ' ', title)
    return ' '.join(cleaned.split())


def fetch_from_openalex(title: str, doi: str | None = None) -> str | None:
    """Fetch publication abstract from OpenAlex API."""
    try:
        # Case 1: Fetch via DOI if provided
        if doi:
            clean_doi = doi.strip()
            if clean_doi.startswith('http'):
                url = f"https://api.openalex.org/works/{clean_doi}"
            else:
                url = f"https://api.openalex.org/works/https://doi.org/{clean_doi}"
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            with urllib.request.urlopen(req, timeout=6.0) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                abstract = _reconstruct_openalex_abstract(data.get('abstract_inverted_index'))
                if abstract and len(abstract) > 30:
                    return abstract

        # Case 2: Fetch via title search
        clean_title = _clean_title_for_search(title)
        encoded_title = urllib.parse.quote(clean_title)
        url = f"https://api.openalex.org/works?search={encoded_title}&per_page=3"
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            results = data.get('results', [])
            for work in results:
                abstract = _reconstruct_openalex_abstract(work.get('abstract_inverted_index'))
                if abstract and len(abstract) > 30:
                    return abstract
    except Exception as exc:
        _log.debug('OpenAlex fetch failed for %r: %s', title[:40], exc)
    return None


def fetch_from_semantic_scholar(title: str) -> str | None:
    """Fallback: Fetch publication abstract from Semantic Scholar Graph API."""
    try:
        clean_title = _clean_title_for_search(title)
        encoded_query = urllib.parse.quote(clean_title)
        url = f"https://api.semanticscholar.org/graph/v1/paper/search?query={encoded_query}&limit=2&fields=title,abstract"
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            papers = data.get('data', [])
            for paper in papers:
                abstract = paper.get('abstract')
                if abstract and len(abstract.strip()) > 30:
                    return abstract.strip()
    except Exception as exc:
        _log.debug('Semantic Scholar fetch failed for %r: %s', title[:40], exc)
    return None


def get_or_fetch_abstract(
    db_key: str,
    title: str,
    publication_id: int | None = None,
    doi: str | None = None
) -> str | None:
    """Retrieve an abstract from cache, or fetch it online and cache it immediately."""
    cached = get_cached_abstract(db_key=db_key, publication_id=publication_id)
    if cached:
        return cached

    # Try OpenAlex first
    abstract = fetch_from_openalex(title, doi)
    source = 'openalex'

    # Fallback to Semantic Scholar
    if not abstract:
        abstract = fetch_from_semantic_scholar(title)
        source = 'semanticscholar'

    if abstract:
        save_cached_abstract(
            db_key=db_key,
            title=title,
            abstract=abstract,
            publication_id=publication_id,
            doi=doi,
            source=source
        )
        return abstract

    return None


def get_or_fetch_abstracts_batch(papers: list[dict[str, Any]], max_workers: int = 5) -> dict[str, str]:
    """Retrieve or fetch abstracts for a batch of candidate papers.
    
    Each item in `papers` is expected to have 'db_key', 'title', and optionally 'publication_id', 'doi'.
    Returns a dict mapping db_key -> abstract string.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, str] = {}
    missing: list[dict[str, Any]] = []

    for p in papers:
        db_key = p.get('db_key')
        pub_id = p.get('publication_id')
        if not db_key:
            continue
        cached = get_cached_abstract(db_key=db_key, publication_id=pub_id)
        if cached:
            results[db_key] = cached
        else:
            missing.append(p)

    if missing:
        def _fetch_one(item: dict[str, Any]) -> tuple[str, str | None]:
            k = item['db_key']
            abs_text = get_or_fetch_abstract(
                db_key=k,
                title=item.get('title', ''),
                publication_id=item.get('publication_id'),
                doi=item.get('doi')
            )
            return k, abs_text

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_key = {executor.submit(_fetch_one, item): item['db_key'] for item in missing}
            for fut in as_completed(future_to_key):
                try:
                    k, abs_text = fut.result()
                    if abs_text:
                        results[k] = abs_text
                except Exception as exc:
                    _log.debug('Batch fetch error for paper: %s', exc)

    return results

