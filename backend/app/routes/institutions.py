from typing import Literal
from fastapi import APIRouter, HTTPException, Path, Query
from ..schemas.models import (
    Institution, InstitutionProfile, Author, Venue, Activity
)
from ..services.duckdb import query
from ..services.analytics import activity, search_term

router = APIRouter(prefix='/api/institutions', tags=['Institution Intelligence'])


@router.get('', response_model=list[Institution])
def list_institutions(
    sort: Literal['publication_count', 'citation_count', 'h_index', 'name'] = 'publication_count',
    order: Literal['asc', 'desc'] = 'desc',
    country: str | None = Query(None, max_length=100),
    type: str | None = Query(None, max_length=50),
    q: str | None = Query(None, max_length=120),
    limit: int = Query(50, ge=1, le=100)
):
    clauses = []
    params = []

    if country:
        clauses.append("country = ?")
        params.append(country)
    if type:
        clauses.append("type = ?")
        params.append(type)
    if q:
        clauses.append("(name ILIKE ? ESCAPE '!' OR short_name ILIKE ? ESCAPE '!')")
        term = search_term(q)
        params.extend([term, term])

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    direction = "ASC" if order == 'asc' else "DESC"

    sql = f"""
    SELECT 
        institution_id,
        name,
        short_name,
        country,
        type,
        publication_count,
        citation_count,
        h_index
    FROM institutions
    {where}
    ORDER BY {sort} {direction} NULLS LAST, institution_id
    LIMIT ?
    """
    params.append(limit)
    return query(sql, tuple(params))


@router.get('/{institution_id}', response_model=InstitutionProfile)
def institution_detail(institution_id: int = Path(ge=1)):
    rows = query("""
    SELECT 
        institution_id,
        name,
        short_name,
        country,
        type,
        publication_count,
        citation_count,
        h_index
    FROM institutions
    WHERE institution_id = ?
    """, (institution_id,))

    if not rows:
        raise HTTPException(404, 'Institution not found')

    inst = rows[0]

    # Top researchers affiliated with this institution
    top_researchers = query("""
    SELECT 
        a.author_id,
        a.name,
        a.publication_count as papers
    FROM author_institutions ai
    JOIN author_stats a USING(author_id)
    WHERE ai.institution_id = ?
    ORDER BY a.publication_count DESC, a.author_id
    LIMIT 20
    """, (institution_id,))

    # Top research topics
    top_topics = query("""
    SELECT 
        t.topic_id,
        t.topic_name,
        t.category,
        it.publication_count as papers
    FROM institution_topics it
    JOIN topics t USING(topic_id)
    WHERE it.institution_id = ?
    ORDER BY it.publication_count DESC, t.topic_id
    LIMIT 10
    """, (institution_id,))

    # Top venues
    top_venues = query("""
    WITH inst_authors AS (
        SELECT author_id FROM author_institutions WHERE institution_id = ?
    ),
    inst_pubs AS (
        SELECT DISTINCT pa.publication_id
        FROM inst_authors ia
        JOIN publication_authors pa USING(author_id)
    )
    SELECT 
        v.venue_id,
        v.name,
        COUNT(*) as papers
    FROM inst_pubs ip
    JOIN publications p USING(publication_id)
    JOIN venues v USING(venue_id)
    GROUP BY v.venue_id, v.name
    ORDER BY papers DESC, v.venue_id
    LIMIT 10
    """, (institution_id,))

    # Yearly publication activity
    raw_activity = query("""
    SELECT year, publication_count as count
    FROM institution_year_stats
    WHERE institution_id = ?
    ORDER BY year
    """, (institution_id,))
    yearly_activity = activity(raw_activity)

    # Top collaborating institutions
    collaborators = query("""
    WITH ties AS (
        SELECT institution2_id as partner_id, weight FROM institution_collaboration WHERE institution1_id = ?
        UNION ALL
        SELECT institution1_id as partner_id, weight FROM institution_collaboration WHERE institution2_id = ?
    )
    SELECT 
        i.institution_id,
        i.name,
        i.short_name,
        i.country,
        SUM(t.weight) as shared_papers
    FROM ties t
    JOIN institutions i ON i.institution_id = t.partner_id
    GROUP BY i.institution_id, i.name, i.short_name, i.country
    ORDER BY shared_papers DESC, i.institution_id
    LIMIT 10
    """, (institution_id, institution_id))

    return InstitutionProfile(
        institution_id=inst['institution_id'],
        name=inst['name'],
        short_name=inst['short_name'],
        country=inst['country'],
        type=inst['type'],
        publication_count=inst['publication_count'],
        citation_count=inst['citation_count'],
        h_index=inst['h_index'],
        top_researchers=top_researchers,
        top_topics=top_topics,
        top_venues=top_venues,
        yearly_activity=yearly_activity,
        collaborating_institutions=collaborators
    )

