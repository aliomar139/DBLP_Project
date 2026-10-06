from typing import Literal
from fastapi import APIRouter, HTTPException, Path, Query
from ..schemas.models import Venue, VenueProfile, GrowthPage, VenueHeatmapPoint
from ..services.duckdb import query
from ..services.analytics import activity, growth_page, search_term

router = APIRouter(prefix='/api/venues', tags=['Venues'])


@router.get('/top', response_model=list[Venue])
def top(limit: int = Query(20, ge=1, le=100), sort: Literal['papers', 'name'] = 'papers', order: Literal['asc', 'desc'] = 'desc'):
    direction = 'ASC' if order == 'asc' else 'DESC'
    column = 'papers' if sort == 'papers' else 'v.name'
    return query(f'SELECT v.venue_id, v.name, s.publication_count AS papers FROM venue_stats s JOIN venues v USING(name) ORDER BY {column} {direction}, v.venue_id LIMIT ?', (limit,))


@router.get('/search', response_model=list[Venue])
def search(q: str = Query(min_length=2, max_length=120), limit: int = Query(20, ge=1, le=50)):
    return query("SELECT v.venue_id, v.name, s.publication_count AS papers FROM venues v JOIN venue_stats s USING(name) WHERE v.name ILIKE ? ESCAPE '!' ORDER BY papers DESC, v.venue_id LIMIT ?", (search_term(q), limit))


@router.get('/growth', response_model=GrowthPage)
def growth(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0, le=10000000),
           sort: Literal['growth_rate', 'recent_publications', 'historical_publications', 'name'] = 'growth_rate',
           order: Literal['asc', 'desc'] = 'desc', minimum_recent: int = Query(10, ge=1, le=1000)):
    return growth_page('venues', limit, offset, sort, order, minimum_recent)


@router.get('/trends')
def trends(venues: str | None = Query(None, max_length=1500), limit: int = Query(6, ge=1, le=12)):
    selected = list(dict.fromkeys(s.strip() for s in (venues or '').split(',') if s.strip()))
    if len(selected) > 12:
        raise HTTPException(422, 'Select at most 12 venues')
    if not selected:
        selected = [r['name'] for r in top(limit)]
    if not selected:
        return []
    marks = ','.join('?' for _ in selected)
    return query(f'''SELECT p.year, v.name AS venue, COUNT(*) AS count FROM publications p
        JOIN venues v USING(venue_id) WHERE v.name IN ({marks}) AND p.year IS NOT NULL
        GROUP BY p.year, v.name ORDER BY p.year, v.name''', tuple(selected))


@router.get('/heatmap', response_model=list[VenueHeatmapPoint])
def heatmap(venues: str | None = Query(None, max_length=1500), limit: int = Query(12, ge=1, le=20),
            start_year: int = Query(2005, ge=1950, le=2026), end_year: int = Query(2025, ge=1950, le=2026)):
    if start_year > end_year:
        raise HTTPException(422, 'Start year must not exceed end year')
    selected = list(dict.fromkeys(s.strip() for s in (venues or '').split(',') if s.strip()))
    if len(selected) > 20:
        raise HTTPException(422, 'Select at most 20 venues')
    if not selected:
        selected = [r['name'] for r in top(limit)]
    if not selected:
        return []
    marks = ','.join('?' for _ in selected)
    return query(f'''SELECT v.name AS venue, p.year, COUNT(*) AS count FROM publications p
        JOIN venues v USING(venue_id) WHERE v.name IN ({marks}) AND p.year BETWEEN ? AND ?
        GROUP BY v.name, p.year ORDER BY v.name, p.year''', tuple(selected) + (start_year, end_year))


@router.get('/{venue_id}', response_model=VenueProfile)
def detail(venue_id: int = Path(ge=1)):
    venues = query('SELECT venue_id, name FROM venues WHERE venue_id = ?', (venue_id,))
    if not venues:
        raise HTTPException(404, 'Venue not found')
    summary = query('''SELECT COUNT(*) AS total_publications, MIN(year) AS first_publication_year,
        MAX(year) AS last_publication_year, COUNT(DISTINCT year) AS active_years
        FROM publications WHERE venue_id = ?''', (venue_id,))[0]
    years = activity(query('SELECT year, COUNT(*) AS count FROM publications WHERE venue_id = ? AND year IS NOT NULL GROUP BY year ORDER BY year', (venue_id,)))
    peak = max(years, key=lambda y: y['count']) if years else None
    total_pubs = summary['total_publications']
    authors = query('''WITH counts AS (SELECT pa.author_id, COUNT(*) AS papers FROM publications p
        JOIN publication_authors pa USING(publication_id) WHERE p.venue_id = ? GROUP BY pa.author_id)
        SELECT c.*, a.name, ROUND(c.papers * 100.0 / NULLIF(?, 0), 2) AS venue_share,
        COUNT(*) OVER() AS author_count FROM counts c JOIN authors a USING(author_id)
        ORDER BY papers DESC, author_id LIMIT 20''', (venue_id, total_pubs))
    return dict(id=venue_id, name=venues[0]['name'], **summary, yearly_growth=years,
                peak_year=peak['year'] if peak else None, peak_publications=peak['count'] if peak else None,
                author_count=authors[0]['author_count'] if authors else 0, top_authors=authors)
