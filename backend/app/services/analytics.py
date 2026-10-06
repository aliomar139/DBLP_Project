from datetime import date
from fastapi import HTTPException
from .duckdb import query


def activity(rows: list[dict]) -> list[dict]:
    """Fill missing calendar years so growth always means year over year."""
    if not rows:
        return []
    counts = {r['year']: r['count'] for r in rows if r['year'] is not None}
    if not counts:
        return []
    result, previous = [], None
    for year in range(min(counts), max(counts) + 1):
        count = counts.get(year, 0)
        growth = round((count - previous) * 100 / previous, 2) if previous else None
        result.append(dict(year=year, count=count, growth_rate=growth))
        previous = count
    return result


def completed_year() -> int:
    row = query('SELECT MAX(year) AS year FROM publication_year_stats WHERE year < ?', (date.today().year,))[0]
    return row['year'] if row['year'] is not None else date.today().year - 1


def require_author(author_id: int) -> dict:
    rows = query('SELECT author_id, name, publication_count AS papers FROM author_stats WHERE author_id = ?', (author_id,))
    if not rows:
        raise HTTPException(404, 'Researcher not found')
    return rows[0]


def search_term(q: str) -> str:
    term = q.strip()
    if len(term) < 2:
        raise HTTPException(422, 'Enter at least two non-space characters')
    return '%' + term.replace('!', '!!').replace('%', '!%').replace('_', '!_') + '%'


def growth_page(kind: str, limit: int, offset: int, sort: str, order: str, minimum_recent: int) -> dict:
    end = completed_year()
    start = end - 9
    # Identifiers and sort expressions come exclusively from these allowlists.
    source = {'authors': ('pa.author_id', 'JOIN publication_authors pa USING (publication_id)', 'authors', 'author_id'),
              'venues': ('p.venue_id', '', 'venues', 'venue_id')}[kind]
    ident, join, table, column = source
    sort_column = {'growth_rate': 'growth_rate', 'recent_publications': 'recent_publications',
                   'historical_publications': 'historical_publications', 'name': 'name'}[sort]
    direction = {'asc': 'ASC', 'desc': 'DESC'}[order]
    cte = f'''WITH counts AS (
        SELECT {ident} AS id,
            COUNT(*) FILTER (WHERE p.year < ?) AS historical_publications,
            COUNT(*) FILTER (WHERE p.year BETWEEN ? AND ?) AS recent_publications
        FROM publications p {join} WHERE p.year <= ? AND p.year IS NOT NULL
        GROUP BY {ident}
    ), ranked AS (
        SELECT c.*, n.name,
            ROUND(100.0 * (recent_publications - historical_publications) / NULLIF(historical_publications, 0), 2) AS growth_rate
        FROM counts c JOIN {table} n ON n.{column} = c.id WHERE recent_publications >= ?
    )'''
    params = (start, start, end, end, minimum_recent)
    rows = query(cte + f' SELECT *, COUNT(*) OVER () AS total FROM ranked ORDER BY {sort_column} {direction} NULLS LAST, id LIMIT ? OFFSET ?', params + (limit, offset))
    total = rows[0]['total'] if rows else query(cte + ' SELECT COUNT(*) AS total FROM ranked', params)[0]['total']
    return dict(items=rows, total=total, limit=limit, offset=offset, recent_start=start, recent_end=end,
                historical_end=start - 1, minimum_recent=minimum_recent,
                methodology='Growth = (recent papers - all earlier dated papers) / all earlier dated papers × 100. Unequal period lengths; activity, not impact. Zero history has no percentage. Current and future calendar years are excluded.')
