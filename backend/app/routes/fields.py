from fastapi import APIRouter, HTTPException, Path
from ..schemas.models import ResearchField, FieldStatistics, FieldNormalizedAuthor
from ..services.duckdb import query

router = APIRouter(prefix='/api/fields', tags=['Field Intelligence'])


@router.get('', response_model=list[FieldStatistics])
def list_fields():
    """List all Computer Science fields with comprehensive baseline statistics."""
    return query("""
    SELECT 
        field_id,
        field_name,
        publication_count,
        author_count,
        total_citations,
        avg_citations_per_paper,
        avg_citations_per_author,
        avg_publications_per_author,
        avg_growth_rate,
        avg_authors_per_paper
    FROM field_statistics
    ORDER BY field_id
    """)


@router.get('/definitions', response_model=list[ResearchField])
def field_definitions():
    """List field taxonomy definitions, descriptions, and icon identifiers."""
    return query("""
    SELECT field_id, name, slug, description, icon
    FROM research_fields
    ORDER BY field_id
    """)


@router.get('/{field_id}')
def field_detail(field_id: int = Path(ge=1, le=8)):
    """Retrieve detailed baseline statistics, constituent topics, and leading venues for a field."""
    field_rows = query("SELECT * FROM field_statistics WHERE field_id = ?", (field_id,))
    if not field_rows:
        raise HTTPException(404, "Research field not found")
    field = field_rows[0]
    field_name = field['field_name']

    # Sub-topics belonging to this field
    topics = query("""
    SELECT topic_id, topic_name, publication_count, growth_rate, description
    FROM topics
    WHERE category = ?
    ORDER BY publication_count DESC
    """, (field_name,))

    # Top venues in this field
    venues = query("""
    WITH field_pubs AS (
        SELECT DISTINCT pt.publication_id
        FROM publication_topics pt
        JOIN topics t USING(topic_id)
        WHERE t.category = ?
    )
    SELECT v.venue_id, v.name, COUNT(*) as papers
    FROM field_pubs fp
    JOIN publications p USING(publication_id)
    JOIN venues v USING(venue_id)
    GROUP BY v.venue_id, v.name
    ORDER BY papers DESC, v.venue_id
    LIMIT 10
    """, (field_name,))

    # Top institutions in this field
    institutions = query("""
    SELECT i.institution_id, i.name, i.short_name, i.country, SUM(it.publication_count) as papers
    FROM institution_topics it
    JOIN topics t USING(topic_id)
    JOIN institutions i USING(institution_id)
    WHERE t.category = ?
    GROUP BY i.institution_id, i.name, i.short_name, i.country
    ORDER BY papers DESC
    LIMIT 10
    """, (field_name,))

    return {
        "field": field,
        "topics": topics,
        "top_venues": venues,
        "top_institutions": institutions
    }

