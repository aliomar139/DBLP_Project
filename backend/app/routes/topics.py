from typing import Literal
from fastapi import APIRouter, HTTPException, Path, Query
from ..schemas.models import Topic, TopicProfile, Activity, Author, Venue
from ..services.duckdb import query
from ..services.analytics import activity, search_term

router = APIRouter(prefix='/api/topics', tags=['Topic Intelligence'])


@router.get('', response_model=list[Topic])
def list_topics(
    sort: Literal['growth_rate', 'publication_count', 'topic_name'] = 'growth_rate',
    order: Literal['asc', 'desc'] = 'desc',
    category: str | None = Query(None, max_length=100),
    q: str | None = Query(None, max_length=120),
    limit: int = Query(50, ge=1, le=100)
):
    clauses = []
    params = []
    if category:
        clauses.append("category = ?")
        params.append(category)
    if q:
        clauses.append("topic_name ILIKE ? ESCAPE '!'")
        params.append(search_term(q))

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    direction = "ASC" if order == 'asc' else "DESC"
    sort_col = sort

    sql = f"""
    SELECT 
        topic_id,
        topic_name,
        category,
        description,
        first_seen_year,
        latest_activity_year,
        publication_count,
        CAST(FLOOR(growth_rate) AS BIGINT) as growth_rate
    FROM topics
    {where}
    ORDER BY {sort_col} {direction} NULLS LAST, topic_id
    LIMIT ?
    """
    params.append(limit)
    return query(sql, tuple(params))


@router.get('/timeline')
def topic_timeline(
    topics: str | None = Query(None, max_length=500),
    start_year: int = Query(1980, ge=1950, le=2026),
    end_year: int = Query(2025, ge=1950, le=2026)
):
    if start_year > end_year:
        raise HTTPException(422, 'Start year must not exceed end year')

    topic_ids = []
    if topics:
        for s in topics.split(','):
            s = s.strip()
            if s.isdigit():
                topic_ids.append(int(s))

    if not topic_ids:
        # Default to top 5 growing topics
        top_rows = query("SELECT topic_id FROM topics ORDER BY growth_rate DESC NULLS LAST LIMIT 5")
        topic_ids = [r['topic_id'] for r in top_rows]

    if not topic_ids:
        return []

    marks = ','.join('?' for _ in topic_ids)
    sql = f"""
    SELECT 
        t.topic_id,
        t.topic_name,
        t.category,
        s.year,
        s.publication_count as count
    FROM topic_year_stats s
    JOIN topics t USING(topic_id)
    WHERE s.topic_id IN ({marks}) AND s.year BETWEEN ? AND ?
    ORDER BY s.year, t.topic_name
    """
    params = tuple(topic_ids) + (start_year, end_year)
    return query(sql, params)


@router.get('/{topic_id}', response_model=TopicProfile)
def topic_detail(topic_id: int = Path(ge=1)):
    topic_rows = query("""
    SELECT 
        topic_id,
        topic_name,
        category,
        description,
        publication_count,
        CAST(FLOOR(growth_rate) AS BIGINT) as growth_rate,
        first_seen_year,
        latest_activity_year
    FROM topics
    WHERE topic_id = ?
    """, (topic_id,))

    if not topic_rows:
        raise HTTPException(404, 'Research topic not found')

    topic = topic_rows[0]

    # Yearly activity
    raw_years = query("""
    SELECT year, publication_count as count
    FROM topic_year_stats
    WHERE topic_id = ?
    ORDER BY year
    """, (topic_id,))
    years = activity(raw_years)

    # Top researchers in this topic
    top_researchers = query("""
    SELECT 
        a.author_id,
        a.name,
        atp.publication_count as papers
    FROM author_topics atp
    JOIN author_stats a USING(author_id)
    WHERE atp.topic_id = ?
    ORDER BY atp.publication_count DESC, a.author_id
    LIMIT 20
    """, (topic_id,))

    # Top institutions in this topic
    top_institutions = query("""
    SELECT 
        i.institution_id,
        i.name,
        i.short_name,
        i.country,
        it.publication_count as papers
    FROM institution_topics it
    JOIN institutions i USING(institution_id)
    WHERE it.topic_id = ?
    ORDER BY it.publication_count DESC, i.institution_id
    LIMIT 10
    """, (topic_id,))

    # Top venues in this topic
    top_venues = query("""
    SELECT 
        v.venue_id,
        v.name,
        vt.publication_count as papers
    FROM venue_topics vt
    JOIN venues v USING(venue_id)
    WHERE vt.topic_id = ?
    ORDER BY vt.publication_count DESC, v.venue_id
    LIMIT 10
    """, (topic_id,))

    # Related topics (frequently co-occurring on same publications)
    related = query("""
    WITH pub_matches AS (
        SELECT publication_id FROM publication_topics WHERE topic_id = ?
    ),
    co_occur AS (
        SELECT pt.topic_id, COUNT(*) as shared_papers
        FROM pub_matches pm
        JOIN publication_topics pt USING(publication_id)
        WHERE pt.topic_id <> ?
        GROUP BY pt.topic_id
        ORDER BY shared_papers DESC
        LIMIT 6
    )
    SELECT 
        t.topic_id,
        t.topic_name,
        t.category,
        c.shared_papers
    FROM co_occur c
    JOIN topics t USING(topic_id)
    ORDER BY c.shared_papers DESC
    """, (topic_id, topic_id))

    return dict(
        **topic,
        top_researchers=top_researchers,
        top_institutions=top_institutions,
        top_venues=top_venues,
        yearly_growth=years,
        related_topics=related
    )

