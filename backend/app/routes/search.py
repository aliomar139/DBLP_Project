"""Unified and Semantic Hybrid Search Router.

Provides:
- GET /api/search: Fast unified search across authors, venues, and publications (preserves backward compatibility).
- GET /api/search/semantic: Hybrid semantic search across papers, researchers, institutions, and topics.
"""
from fastapi import APIRouter, Query
from ..schemas.models import SearchResults, SemanticSearchResponse
from .authors import search as authors
from .venues import search as venues
from ..services.hybrid_search import execute_hybrid_search
from ..services.duckdb import query
from ..services.analytics import search_term

router = APIRouter(tags=['Search'])


@router.get('/api/search', response_model=SearchResults)
def search(q: str = Query(min_length=2, max_length=120), limit: int = Query(6, ge=1, le=20)):
    """Standard unified search across researchers, venues, and publications."""
    # Search suggestions only display a handful of paper fields. Avoid the full
    # publication listing path, which also counts every match and enriches each
    # result with author and topic collections.
    papers = query('''
        SELECT p.publication_id, p.title, p.year, p.type, p.venue_id,
               v.name AS venue_name, COALESCE(c.citations, 0) AS citations
        FROM publications p
        LEFT JOIN venues v USING(venue_id)
        LEFT JOIN publication_citations c USING(publication_id)
        WHERE p.title ILIKE ? ESCAPE '!'
        ORDER BY citations DESC NULLS LAST, p.publication_id
        LIMIT ?
    ''', (search_term(q), limit))
    return dict(
        authors=authors(q, limit),
        venues=venues(q, limit),
        papers_available=True,
        papers=papers
    )


@router.get('/api/search/semantic', response_model=SemanticSearchResponse)
def semantic_search(
    q: str = Query(min_length=2, max_length=250),
    limit: int = Query(10, ge=1, le=50)
):
    """Hybrid semantic search: combines lexical BM25 matching, 64-dim dense cosine similarity, and citation rank."""
    return execute_hybrid_search(raw_query=q, limit=limit)
