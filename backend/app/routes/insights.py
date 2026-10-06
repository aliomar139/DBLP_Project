from fastapi import APIRouter
from ..schemas.models import Insights
from ..services.duckdb import query
from ..services.analytics import completed_year

router = APIRouter(tags=['Insights'])


@router.get('/api/insights', response_model=Insights)
def insights():
    end = completed_year()
    items = []
    years = query('SELECT year, publication_count AS count FROM publication_year_stats WHERE year IN (2000, ?) ORDER BY year', (end,))
    if len(years) == 2 and years[0]['count']:
        growth = 100 * (years[1]['count'] / years[0]['count'] - 1)
        items.append(dict(title='Research output since 2000',
            observation=f"Annual publications changed by {growth:+,.1f}%, from {years[0]['count']:,} in 2000 to {years[1]['count']:,} in {end}.",
            methodology='Annual indexed publication counts; latest completed calendar year. Coverage changes may affect comparison.', href='/trends'))
    team = query('''WITH papers AS (SELECT year, COUNT(*) AS n FROM publications WHERE year IN (2000, ?) GROUP BY year),
        authorships AS (SELECT p.year, COUNT(*) AS n FROM publications p JOIN publication_authors pa USING(publication_id)
        WHERE p.year IN (2000, ?) GROUP BY p.year)
        SELECT p.year, COALESCE(a.n, 0)::DOUBLE / p.n AS mean FROM papers p LEFT JOIN authorships a USING(year) ORDER BY year''', (end, end))
    if len(team) == 2:
        items.append(dict(title='The changing size of research teams',
            observation=f"Mean authors per paper changed from {team[0]['mean']:.2f} in 2000 to {team[1]['mean']:.2f} in {end}.",
            methodology='Authorship records divided by publications in each year, including papers without author records.', href='/trends'))
    venue = query('SELECT v.venue_id, v.name, s.publication_count AS n FROM venue_stats s JOIN venues v USING(name) ORDER BY n DESC, v.venue_id LIMIT 1')
    if venue:
        v = venue[0]
        items.append(dict(title='Largest publication venue', observation=f"{v['name']} contains {v['n']:,} indexed publications.",
            methodology='All-time indexed volume, including repositories and proceedings. Volume is not a measure of quality or influence.', href=f"/venues/{v['venue_id']}"))
    people = query('''WITH degrees AS (
        SELECT author1_id AS author_id, COUNT(*) AS n FROM author_collaboration GROUP BY author1_id
        UNION ALL SELECT author2_id AS author_id, COUNT(*) AS n FROM author_collaboration GROUP BY author2_id
    ), leaders AS (SELECT author_id, SUM(n) AS n FROM degrees GROUP BY author_id ORDER BY n DESC, author_id LIMIT 3)
    SELECT a.author_id, a.name, l.n FROM leaders l JOIN authors a USING(author_id) ORDER BY l.n DESC, a.author_id''')
    if people:
        items.append(dict(title='Researchers with the broadest collaboration reach',
            observation='; '.join(f"{a['name']} ({a['n']:,} collaborators)" for a in people) + '.',
            methodology='Distinct neighbors in the complete, all-time collaboration edge table. Coauthorship does not establish research impact.', href=f"/authors/{people[0]['author_id']}"))

    pair = query('''SELECT c.author1_id, a1.name as author1, c.author2_id, a2.name as author2, c.weight
        FROM author_collaboration_dashboard c
        JOIN authors a1 ON c.author1_id = a1.author_id
        JOIN authors a2 ON c.author2_id = a2.author_id
        ORDER BY c.weight DESC LIMIT 1''')
    if pair:
        p = pair[0]
        items.append(dict(
            title='Strongest scientific collaboration tie',
            observation=f"{p['author1']} and {p['author2']} have co-authored {p['weight']:,} papers together, representing the most prolific partnership in the repository.",
            methodology='All-time shared publication count from verified co-authorship records.',
            href=f"/network?author={p['author1_id']}"
        ))

    return dict(through_year=end, items=items)
