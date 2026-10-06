from fastapi import APIRouter, HTTPException
from ..schemas.models import (
    Activity, Decade, CollaborationEvolutionPoint, TeamDistribution,
    PublicationGrowthPoint, PublicationTypeTimelinePoint
)
from ..services.duckdb import query
from ..services.analytics import activity

router = APIRouter(prefix='/api', tags=['Trends'])


@router.get('/overview')
def overview():
    rows = query('SELECT * FROM dashboard_summary LIMIT 1')
    if not rows:
        raise HTTPException(503, 'Dataset summary is unavailable')
    metrics = query('''SELECT COUNT(*)::DOUBLE / NULLIF((SELECT COUNT(*) FROM publications), 0) AS average_authors_per_paper,
        (SELECT AVG(publication_count) FROM publication_year_stats) AS average_publications_per_year FROM publication_authors''')[0]
    result = dict(rows[0], **metrics)
    result['active_years'] = (result['last_year'] - result['first_year'] + 1) if result['first_year'] is not None else 0
    return result


@router.get('/publications/timeline', response_model=list[Activity])
def timeline():
    return activity(query('SELECT year, publication_count AS count FROM publication_year_stats WHERE year IS NOT NULL ORDER BY year'))


@router.get('/publications/growth', response_model=list[PublicationGrowthPoint])
def growth():
    return query('''WITH stats AS (
        SELECT year, publication_count 
        FROM publication_year_stats 
        WHERE year IS NOT NULL 
        ORDER BY year
    )
    SELECT 
        year, 
        publication_count,
        ROUND(100.0 * (publication_count - LAG(publication_count) OVER (ORDER BY year)) / NULLIF(LAG(publication_count) OVER (ORDER BY year), 0), 2) AS growth_percentage
    FROM stats
    ORDER BY year''')


@router.get('/publications/types')
def types():
    return query('SELECT type, COUNT(*) AS count FROM publications GROUP BY type ORDER BY count DESC')


@router.get('/publications/types/timeline', response_model=list[PublicationTypeTimelinePoint])
def types_timeline():
    return query('''SELECT year, type, COUNT(*) as count
        FROM publications
        WHERE year IS NOT NULL AND year BETWEEN 1970 AND 2025
        GROUP BY year, type
        ORDER BY year, type''')


@router.get('/trends/decades', response_model=list[Decade])
def decades():
    rows = query('''WITH papers AS (
        SELECT (year // 10) * 10 AS decade, COUNT(*) AS publications,
            COUNT(DISTINCT venue_id) AS venues, MAX(year) AS observed_through
        FROM publications WHERE year BETWEEN 1950 AND 2029 GROUP BY decade
    ), people AS (
        SELECT (p.year // 10) * 10 AS decade, COUNT(DISTINCT pa.author_id) AS authors, COUNT(*) AS authorships
        FROM publications p JOIN publication_authors pa USING(publication_id)
        WHERE p.year BETWEEN 1950 AND 2029 GROUP BY decade
    ) SELECT p.*, COALESCE(a.authors, 0) AS authors,
        COALESCE(a.authorships, 0)::DOUBLE / NULLIF(p.publications, 0) AS average_authors_per_paper
        FROM papers p LEFT JOIN people a USING(decade) ORDER BY decade''')
    by_decade = {r['decade']: r for r in rows}
    return [by_decade.get(d, dict(decade=d, publications=0, venues=0, authors=0, average_authors_per_paper=0, observed_through=None)) for d in range(1950, 2030, 10)]


@router.get('/trends/collaboration-evolution', response_model=list[CollaborationEvolutionPoint])
def collaboration_evolution():
    return query('''WITH authorships AS (
        SELECT p.year,
               COUNT(*) as total_authorships,
               COUNT(DISTINCT pa.author_id) as unique_authors
        FROM publications p
        JOIN publication_authors pa USING (publication_id)
        WHERE p.year BETWEEN 1970 AND 2025
        GROUP BY p.year
    )
    SELECT a.year,
           COALESCE(y.publication_count, 0) as publications,
           a.unique_authors,
           a.total_authorships,
           ROUND(a.total_authorships::DOUBLE / NULLIF(y.publication_count, 0), 2) as average_authors_per_paper
    FROM authorships a
    LEFT JOIN publication_year_stats y USING (year)
    ORDER BY a.year''')


@router.get('/trends/team-distribution', response_model=list[TeamDistribution])
def team_distribution():
    rows = query('''WITH paper_authors AS (
        SELECT publication_id, COUNT(author_id) as author_count
        FROM publication_authors
        GROUP BY publication_id
    )
    SELECT 
        CASE 
            WHEN author_count = 1 THEN 'Solo (1 author)'
            WHEN author_count = 2 THEN 'Duo (2 authors)'
            WHEN author_count BETWEEN 3 AND 5 THEN 'Small Team (3-5)'
            ELSE 'Large Team (6+)'
        END as category,
        COUNT(*) as count
    FROM paper_authors
    GROUP BY 1
    ORDER BY count DESC''')
    total = sum(r['count'] for r in rows) or 1
    return [dict(r, percentage=round(r['count'] * 100.0 / total, 1)) for r in rows]
