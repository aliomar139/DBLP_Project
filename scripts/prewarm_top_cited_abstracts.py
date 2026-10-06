"""Bulk Pre-population of Scientific Abstracts for Top-Cited DBLP Papers.

Queries the canonical DuckDB database for top-cited publications across premier venues
and fetches/caches their abstracts using OpenAlex & Semantic Scholar into the SQLite sidecar.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import logging
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.app.database import get_connection
from backend.app.services.abstract_service import (
    init_abstract_db,
    get_cached_abstract,
    get_or_fetch_abstract,
    get_db_connection,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("bulk_prewarm")


def prewarm_top_cited(limit: int = 50, batch_pause: float = 0.25) -> None:
    init_abstract_db()

    logger.info("Connecting to canonical DuckDB to query top %d cited papers...", limit)
    with closing(get_connection()) as conn:
        rows = conn.execute(f"""
            SELECT p.publication_id, p.db_key, p.title, p.year, COALESCE(c.citations, 0) as citations
            FROM publications p
            JOIN publication_citations c ON p.publication_id = c.publication_id
            WHERE p.title IS NOT NULL AND length(p.title) > 10
            ORDER BY c.citations DESC
            LIMIT {limit}
        """).fetchall()

    logger.info("Retrieved %d candidates from DuckDB.", len(rows))

    already_cached = 0
    fetched_now = 0
    failed = 0

    started = time.perf_counter()

    for i, (pub_id, db_key, title, year, citations) in enumerate(rows, 1):
        cached = get_cached_abstract(db_key=db_key, publication_id=pub_id, title=title)
        if cached:
            already_cached += 1
            logger.info("[%d/%d] CACHED: %s (%d chars)", i, len(rows), db_key, len(cached))
            continue

        abstract = get_or_fetch_abstract(db_key=db_key, title=title, publication_id=pub_id)
        if abstract:
            fetched_now += 1
            logger.info("[%d/%d] FETCHED (%d cites): %s -> %s (%d chars)", i, len(rows), citations, db_key, title[:40], len(abstract))
        else:
            failed += 1
            logger.warning("[%d/%d] MISSED: %s -> %s", i, len(rows), db_key, title[:40])

        time.sleep(batch_pause)

    elapsed = time.perf_counter() - started

    # Get total cache size in SQLite
    with get_db_connection() as s_conn:
        total_in_cache = s_conn.execute("SELECT count(*) FROM paper_abstracts").fetchone()[0]

    logger.info("=" * 60)
    logger.info("BULK PRE-WARM COMPLETED in %.1fs", elapsed)
    logger.info("Processed: %d | Already Cached: %d | Newly Fetched: %d | Missed: %d", len(rows), already_cached, fetched_now, failed)
    logger.info("Total abstracts now in local cache: %d", total_in_cache)
    logger.info("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk pre-warm abstracts for top-cited papers")
    parser.add_argument("--limit", type=int, default=50, help="Number of top papers to process (default: 50)")
    parser.add_argument("--pause", type=float, default=0.2, help="Pause between API calls (default: 0.2s)")
    args = parser.parse_args()

    prewarm_top_cited(limit=args.limit, batch_pause=args.pause)

