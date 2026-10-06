"""Fixed-form SQL tools for trusted assistant answers.

No caller or model supplies SQL. Parameters are bound, evidence is projected
from approved core tables, and each request is read-only and time-bounded.
"""
from __future__ import annotations

from contextlib import closing
from contextvars import ContextVar
from dataclasses import dataclass
import logging
import json
import os
from pathlib import Path
from threading import BoundedSemaphore, Timer
import time
from typing import Any, Literal

from ..database import DB_PATH, get_connection
from .evidence_contract import (AUTHOR_IDENTITY_NOTE, TITLE_CLASSIFICATION_LABEL,
                                require_fields, require_repaired_summary_fields)
from .title_retrieval import TitleIndexUnavailable, search_titles
from .assistant_query_planner import compile_plan

EntityKind = Literal['author', 'venue']
MAX_RESULT_ROWS = 60
QUERY_TIMEOUT_SECONDS = 9.5
_QUERY_SLOTS = BoundedSemaphore(2)
_REPAIRED_CANDIDATE_BYTES = 3_395_301_376
_REQUEST_ID: ContextVar[str] = ContextVar('assistant_request_id', default='unknown')
_logger = logging.getLogger(__name__)


class ToolFailure(RuntimeError):
    pass


@dataclass(frozen=True)
class Evidence:
    kind: str
    row: dict[str, Any]
    calculation: str | None = None
    filters: dict[str, Any] | None = None


def database_version() -> str:
    """Return a dynamic local-file version token without hashing gigabytes per request."""
    path = Path(os.environ.get('DBLP_DB_PATH', str(DB_PATH)))
    try:
        stat = path.stat()
    except OSError:
        return 'active-database-unavailable'
    return f'dblp.duckdb:size={stat.st_size}:mtime_ns={stat.st_mtime_ns}'


def retrieval_version() -> str:
    """Version answer-cache entries against the sidecar manifest as well as DB."""
    from .title_retrieval import SIDECAR_PATH
    manifest = SIDECAR_PATH / 'manifest.json'
    try:
        stat = manifest.stat()
        data = json.loads(manifest.read_text(encoding='utf-8'))
        return f"{data.get('corpus_id', 'unknown')}:size={stat.st_size}:mtime_ns={stat.st_mtime_ns}"
    except (OSError, ValueError):
        return 'title-index-unavailable'


def _uses_verified_repaired_candidate() -> bool:
    configured = Path(os.environ.get('DBLP_DB_PATH', str(DB_PATH)))
    try:
        return (configured.resolve() == Path(DB_PATH).resolve() and
                configured.stat().st_size == _REPAIRED_CANDIDATE_BYTES)
    except OSError:
        return False


def _select(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    # This guard is defense in depth; all SQL below is a literal tool-owned form.
    if not sql.startswith(('SELECT ', 'WITH ')):
        raise ValueError('Assistant SQL must be a fixed SELECT or CTE statement')
    if not _QUERY_SLOTS.acquire(timeout=0.05):
        raise ToolFailure('The local DBLP query service is busy')
    started = time.perf_counter()
    try:
        try:
            connection = get_connection()
        except Exception as exc:
            raise ToolFailure('The DBLP database is unavailable') from exc
        with closing(connection) as db:
            try:
                db.execute("SET memory_limit='4GB'")
                db.execute('SET threads=4')
            except Exception as exc:
                raise ToolFailure('The DBLP query session could not be configured') from exc
            timer = Timer(QUERY_TIMEOUT_SECONDS, db.interrupt)
            timer.daemon = True
            timer.start()
            try:
                cur = db.execute(sql, params)
                columns = [field[0] for field in cur.description]
                rows = cur.fetchmany(MAX_RESULT_ROWS + 1)
                if len(rows) > MAX_RESULT_ROWS:
                    raise ToolFailure('The result exceeded the assistant row limit')
                _logger.info('Assistant stage request_id=%s stage=sql elapsed_ms=%.1f outcome=ok',
                             _REQUEST_ID.get(), (time.perf_counter() - started) * 1000)
                return [dict(zip(columns, row)) for row in rows]
            except ToolFailure:
                raise
            except Exception as exc:
                _logger.warning('Assistant stage request_id=%s stage=sql elapsed_ms=%.1f outcome=%s',
                                _REQUEST_ID.get(), (time.perf_counter() - started) * 1000,
                                type(exc).__name__)
                message = str(exc).lower()
                if 'interrupt' in message or 'cancel' in message or 'timeout' in message:
                    raise ToolFailure('The DBLP query exceeded its time limit') from exc
                raise ToolFailure('The DBLP evidence query failed') from exc
            finally:
                timer.cancel()
                timer.join()
    finally:
        _QUERY_SLOTS.release()


def resolve_entity(kind: EntityKind, exact_name: str) -> list[Evidence]:
    """Case-insensitive exact match only; similar names are never substituted."""
    if not exact_name.strip() or len(exact_name) > 300:
        return []
    if kind == 'author':
        require_fields('authors', {'author_id', 'name'})
        rows = _select(
            'SELECT author_id, name FROM authors WHERE lower(trim(name)) = lower(trim(?)) '
            'ORDER BY author_id LIMIT 21', (exact_name,))
    elif kind == 'venue':
        require_fields('venues', {'venue_id', 'name'})
        rows = _select(
            'SELECT venue_id, name FROM venues WHERE lower(trim(name)) = lower(trim(?)) '
            'ORDER BY venue_id LIMIT 21', (exact_name,))
    else:
        raise ValueError('Unsupported entity kind')
    if len(rows) > MAX_RESULT_ROWS:
        raise ToolFailure('Too many exact-name records to resolve safely')
    return [Evidence(kind, row) for row in rows]


def publication_count(kind: EntityKind, entity_id: int,
                      year_from: int | None = None,
                      year_to: int | None = None) -> Evidence:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError('The starting year must not exceed the ending year')
    require_fields('publications', {'publication_id', 'year', 'venue_id'})
    where_parts: list[str]
    params: list[Any]
    if kind == 'author':
        require_fields('publication_authors', {'publication_id', 'author_id'})
        from_sql = 'publication_authors pa JOIN publications p ON p.publication_id=pa.publication_id'
        where_parts = ['pa.author_id=?']
        params = [entity_id]
        description = 'COUNT(DISTINCT publication_id) for the exact matched author ID'
    elif kind == 'venue':
        from_sql = 'publications p'
        where_parts = ['p.venue_id=?']
        params = [entity_id]
        description = 'COUNT(DISTINCT publication_id) for the exact matched venue ID'
    else:
        raise ValueError('Unsupported entity kind')
    filters: dict[str, Any] = {'entity_id': entity_id}
    if year_from is not None:
        where_parts.append('p.year >= ?'); params.append(year_from)
        filters['year_from_inclusive'] = year_from
    if year_to is not None:
        where_parts.append('p.year <= ?'); params.append(year_to)
        filters['year_to_inclusive'] = year_to
    row = _select(
        'SELECT count(DISTINCT p.publication_id) AS publication_count, '
        'min(p.year) AS first_year, max(p.year) AS last_year FROM ' + from_sql +
        ' WHERE ' + ' AND '.join(where_parts), tuple(params))[0]
    return Evidence('calculation', row, description, filters)


def corpus_count() -> Evidence:
    require_fields('publications', {'publication_id'})
    row = _select('SELECT count(*) AS publication_count FROM publications')[0]
    return Evidence('calculation', row,
                    'COUNT(*) over every stored publication row, including empty-title rows', {})


def venue_ranking(limit: int = 10, year_from: int | None = None,
                  year_to: int | None = None) -> Evidence:
    limit = min(max(int(limit), 1), 10)
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError('The starting year must not exceed the ending year')
    require_fields('venues', {'venue_id', 'name'})
    require_fields('publications', {'publication_id', 'venue_id', 'year'})
    conditions = ['p.venue_id IS NOT NULL']
    params: list[Any] = []
    filters: dict[str, Any] = {'limit': limit}
    if year_from is not None:
        conditions.append('p.year >= ?'); params.append(year_from)
        filters['year_from_inclusive'] = year_from
    if year_to is not None:
        conditions.append('p.year <= ?'); params.append(year_to)
        filters['year_to_inclusive'] = year_to
    rows = _select(
        'SELECT v.venue_id, v.name, count(DISTINCT p.publication_id) AS publication_count '
        'FROM publications p JOIN venues v ON v.venue_id=p.venue_id WHERE ' +
        ' AND '.join(conditions) +
        ' GROUP BY v.venue_id, v.name ORDER BY publication_count DESC, v.venue_id LIMIT ?',
        tuple(params + [limit]))
    return Evidence('ranking', {'venues': rows},
                    'Distinct DBLP publication count, descending; venue ID breaks ties', filters)


def author_ranking(limit: int = 10, year_from: int | None = None,
                   year_to: int | None = None) -> Evidence:
    limit = min(max(int(limit), 1), 10)
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError('The starting year must not exceed the ending year')
    require_fields('authors', {'author_id', 'name'})
    require_fields('publication_authors', {'publication_id', 'author_id'})
    require_fields('publications', {'publication_id', 'year'})
    conditions = ['a.name IS NOT NULL']
    params: list[Any] = []
    filters: dict[str, Any] = {'limit': limit}
    if year_from is not None:
        conditions.append('p.year >= ?'); params.append(year_from)
        filters['year_from_inclusive'] = year_from
    if year_to is not None:
        conditions.append('p.year <= ?'); params.append(year_to)
        filters['year_to_inclusive'] = year_to
    if year_from is None and year_to is None:
        if _uses_verified_repaired_candidate():
            require_repaired_summary_fields('author_stats', {'author_id', 'name', 'publication_count'})
            ranking_sql = (
                'SELECT a.author_id, a.name, s.publication_count FROM author_stats s '
                'JOIN authors a ON a.author_id=s.author_id WHERE a.name IS NOT NULL '
                'ORDER BY s.publication_count DESC, a.author_id LIMIT ?')
            query_params: tuple[Any, ...] = (limit,)
            filters['calculation_source'] = 'verified repaired-candidate author_stats; distinct publication IDs'
        else:
            # Avoid joining all 8.7M publication rows when no year filter is asked.
            ranking_sql = (
                'SELECT a.author_id, a.name, count(DISTINCT pa.publication_id) AS publication_count '
                'FROM authors a JOIN publication_authors pa ON pa.author_id=a.author_id '
                'WHERE a.name IS NOT NULL GROUP BY a.author_id, a.name '
                'ORDER BY publication_count DESC, a.author_id LIMIT ?')
            query_params = (limit,)
    else:
        ranking_sql = (
            'SELECT a.author_id, a.name, count(DISTINCT p.publication_id) AS publication_count '
            'FROM authors a JOIN publication_authors pa ON pa.author_id=a.author_id '
            'JOIN publications p ON p.publication_id=pa.publication_id WHERE ' +
            ' AND '.join(conditions) +
            ' GROUP BY a.author_id, a.name ORDER BY publication_count DESC, a.author_id LIMIT ?')
        query_params = tuple(params + [limit])
    rows = _select(ranking_sql, query_params)
    description = 'Distinct DBLP publication count, descending; author ID breaks ties'
    if filters.get('calculation_source'):
        description += '; count read from the independently verified repaired-candidate distinct-count summary'
    return Evidence('ranking', {'authors': rows}, description, filters)


def publication_trend(year_from: int | None = None,
                      year_to: int | None = None) -> Evidence:
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError('The starting year must not exceed the ending year')
    require_fields('publications', {'publication_id', 'year'})
    conditions = ['year IS NOT NULL']
    params: list[Any] = []
    filters: dict[str, Any] = {'null_years': 'excluded'}
    if year_from is not None:
        conditions.append('year >= ?'); params.append(year_from)
        filters['year_from_inclusive'] = year_from
    if year_to is not None:
        conditions.append('year <= ?'); params.append(year_to)
        filters['year_to_inclusive'] = year_to
    rows = _select(
        'SELECT year, count(DISTINCT publication_id) AS publication_count FROM publications '
        'WHERE ' + ' AND '.join(conditions) +
        ' GROUP BY year ORDER BY year LIMIT 60', tuple(params))
    null_count = _select('SELECT count(*) AS missing_year_count FROM publications WHERE year IS NULL')[0]
    filters['missing_year_count'] = null_count['missing_year_count']
    return Evidence('trend', {'years': rows},
                    'COUNT(DISTINCT publication_id) grouped by stored year; null years excluded', filters)


def shared_publications(author_a: int, author_b: int, limit: int = 10) -> Evidence:
    if author_a == author_b:
        raise ValueError('A coauthor comparison needs two different author records')
    limit = min(max(int(limit), 1), 10)
    require_fields('publication_authors', {'publication_id', 'author_id'})
    require_fields('publications', {'publication_id', 'db_key', 'title', 'year'})
    count_row = _select(
        'SELECT count(DISTINCT p.publication_id) AS shared_count FROM publications p '
        'JOIN publication_authors a ON a.publication_id=p.publication_id '
        'JOIN publication_authors b ON b.publication_id=p.publication_id '
        'WHERE a.author_id=? AND b.author_id=?', (author_a, author_b))[0]
    rows = _select(
        'SELECT p.publication_id, p.db_key, p.title, p.year FROM publications p '
        'JOIN publication_authors a ON a.publication_id=p.publication_id '
        'JOIN publication_authors b ON b.publication_id=p.publication_id '
        'WHERE a.author_id=? AND b.author_id=? '
        'GROUP BY p.publication_id, p.db_key, p.title, p.year '
        'ORDER BY p.year DESC NULLS LAST, p.publication_id LIMIT ?',
        (author_a, author_b, limit))
    return Evidence('shared_publications', {'publications': rows,
                                             'shared_count': int(count_row['shared_count'])},
                    'Distinct publication records shared by the two matched author IDs',
                    {'author_ids': [author_a, author_b], 'limit': limit,
                     'qualification': AUTHOR_IDENTITY_NOTE})


def author_collaborators(author_id: int, limit: int = 10) -> Evidence:
    """Rank collaborators by distinct shared DBLP publication records."""
    limit = min(max(int(limit), 1), 10)
    require_fields('publication_authors', {'publication_id', 'author_id'})
    require_fields('publications', {'publication_id'})
    require_fields('authors', {'author_id', 'name'})
    rows = _select(
        'SELECT co.author_id, co.name, count(DISTINCT p.publication_id) AS shared_publications '
        'FROM publication_authors pa '
        'JOIN publication_authors pb ON pb.publication_id=pa.publication_id AND pb.author_id<>pa.author_id '
        'JOIN publications p ON p.publication_id=pa.publication_id '
        'JOIN authors co ON co.author_id=pb.author_id '
        'WHERE pa.author_id=? AND co.name IS NOT NULL '
        'GROUP BY co.author_id, co.name ORDER BY shared_publications DESC, co.author_id LIMIT ?',
        (author_id, limit))
    return Evidence('collaborators', {'collaborators': rows},
                    'Distinct DBLP publication records shared by each collaborator and the resolved author ID',
                    {'author_ids': [author_id], 'limit': limit,
                     'qualification': AUTHOR_IDENTITY_NOTE})


def exact_title(title: str) -> list[Evidence]:
    """Look up an exact stored title without silently promoting fuzzy matches."""
    if not title.strip() or len(title) > 500:
        return []
    require_fields('publications', {'publication_id', 'db_key', 'title', 'year', 'type', 'venue_id'})
    rows = _select(
        'SELECT publication_id, db_key, title, year, type, venue_id FROM publications '
        'WHERE lower(trim(title))=lower(trim(?)) ORDER BY publication_id LIMIT 21', (title,))
    if len(rows) > MAX_RESULT_ROWS:
        raise ToolFailure('Too many records share that exact title')
    return [Evidence('paper', row) for row in rows]


def title_search(query_text: str, limit: int = 8) -> Evidence:
    """Retrieve title-only candidates; the service validates IDs against DuckDB."""
    require_fields('publications', {'publication_id', 'db_key', 'title', 'year', 'type', 'venue_id'})
    try:
        results = search_titles(query_text, limit)
    except TitleIndexUnavailable as exc:
        raise ToolFailure('The local full-title retrieval service is unavailable') from exc
    except Exception as exc:
        raise ToolFailure('The local full-title retrieval service failed') from exc
    rows = [{
        'publication_id': item.publication_id,
        'db_key': item.db_key,
        'title': item.title,
        'year': item.year,
        'type': item.publication_type,
        'venue_id': item.venue_id,
        'matched_by': list(item.matched_by),
    } for item in results]
    return Evidence(
        'title_search', {'matches': rows},
        'Bounded reciprocal-rank fusion of local semantic and SQLite FTS title candidates; every result was reloaded by publication ID from canonical DuckDB',
        {'query_mode': 'title-only semantic and keyword retrieval',
         'candidate_limit_per_retriever': 50, 'returned_limit': min(max(int(limit), 1), 8),
         'title_only': True, 'empty_title_exclusions': 0},
    )


def planned_database_query(plan: dict[str, Any]) -> Evidence:
    """Execute a validated generic plan compiled from approved DBLP fields."""
    compiled = compile_plan(plan)
    if compiled is None:
        raise ValueError('The assistant query plan is outside the approved DBLP query contract')
    sql, params, checked_plan = compiled
    field_refs = checked_plan['fields'] + checked_plan['group_by']
    field_refs += [item['field'] for item in checked_plan['metrics'] + checked_plan['filters']]
    used = {ref.split('.', 1)[0] for ref in field_refs}
    if 'venues' in used and 'authors' in used:
        used.update({'publications', 'publication_authors'})
    if 'authors' in used and 'publications' in used:
        used.add('publication_authors')
    if 'publication_authors' in used:
        used.update({'authors', 'publications'})
    columns: dict[str, set[str]] = {table: set() for table in used}
    for ref in field_refs:
        table, column = ref.split('.', 1)
        columns[table].add(column)
    if 'publications' in used:
        columns['publications'].add('publication_id')
        if 'venues' in used:
            columns['publications'].add('venue_id')
    if 'authors' in used:
        columns['authors'].add('author_id')
    if 'venues' in used:
        columns['venues'].add('venue_id')
    if 'publication_authors' in used:
        columns['publication_authors'].update({'publication_id', 'author_id'})
    for table, fields in columns.items():
        require_fields(table, fields)
    rows = _select(sql, params)
    result = {
        'columns': [field.replace('.', '_') for field in checked_plan['fields']]
                  + [metric['name'] for metric in checked_plan['metrics']],
        'rows': rows,
        'row_count': len(rows),
    }
    return Evidence(
        'query_result', result,
        'Read-only query over approved DBLP publication, author, venue, and authorship fields',
        {'plan': checked_plan, 'limit': checked_plan['limit'],
         'database_contract': 'dblp-evidence-v1'},
    )


def latest_author_publications(author_id: int, limit: int = 10) -> Evidence:
    """Return all top-year papers for an exact author ID (year is not a date)."""
    limit = min(max(int(limit), 1), 10)
    require_fields('publication_authors', {'publication_id', 'author_id'})
    require_fields('publications', {'publication_id', 'db_key', 'title', 'year', 'type', 'venue_id'})
    rows = _select(
        'WITH latest AS MATERIALIZED ('
        ' SELECT max(p.year) AS publication_year FROM publications p '
        ' JOIN publication_authors pa ON pa.publication_id=p.publication_id '
        ' WHERE pa.author_id=? AND p.year IS NOT NULL) '
        'SELECT DISTINCT p.publication_id,p.db_key,p.title,p.year,p.type,p.venue_id '
        'FROM publication_authors pa JOIN publications p ON p.publication_id=pa.publication_id '
        'CROSS JOIN latest l WHERE pa.author_id=? AND p.year=l.publication_year '
        'ORDER BY p.publication_id LIMIT ?', (author_id, author_id, limit + 1))
    if len(rows) > limit:
        raise ToolFailure('Too many publications tie at the latest stored year')
    latest_year = int(rows[0]['year']) if rows else None
    return Evidence(
        'latest_author_publications', {'publication_year': latest_year, 'publications': rows},
        'Maximum non-null stored publication year among records linked to the exact author ID; year does not establish when the work was performed',
        {'author_id': author_id, 'year_nulls': 'excluded', 'tie_limit': limit})


def title_classification(topic_name: str, year_from: int | None = None,
                         year_to: int | None = None, sample_limit: int = 5) -> list[Evidence]:
    """Recompute a project topic count from literal title-keyword matches."""
    if year_from is not None and year_to is not None and year_from > year_to:
        raise ValueError('The starting year must not exceed the ending year')
    require_fields('topics', {'topic_id', 'topic_name'}, label=TITLE_CLASSIFICATION_LABEL)
    topics = _select(
        'SELECT topic_id, topic_name FROM topics WHERE lower(trim(topic_name))=lower(trim(?)) '
        'ORDER BY topic_id LIMIT 21', (topic_name,))
    if not topics:
        return []
    if len(topics) > MAX_RESULT_ROWS:
        raise ToolFailure('Too many exact topic classification records')
    require_fields('topic_keywords', {'topic_id', 'keyword'}, label=TITLE_CLASSIFICATION_LABEL)
    results = []
    for topic in topics:
        keywords = _select(
            'SELECT DISTINCT keyword FROM topic_keywords WHERE topic_id=? '
            'AND keyword IS NOT NULL AND length(trim(keyword))>0 ORDER BY keyword',
            (int(topic['topic_id']),))
        terms = [str(row['keyword']) for row in keywords]
        if not terms:
            results.append(Evidence('classification', {
                'topic_id': int(topic['topic_id']), 'topic_name': topic['topic_name'],
                'keywords': [], 'publication_count': 0, 'sample_publications': []},
                f"{TITLE_CLASSIFICATION_LABEL}: zero configured title keywords", {
                    'classification_label': TITLE_CLASSIFICATION_LABEL,
                    'topic_id': int(topic['topic_id']), 'year_from_inclusive': year_from,
                    'year_to_inclusive': year_to}))
            continue
        require_fields('publications', {'publication_id', 'title', 'year', 'db_key', 'type', 'venue_id'})
        title_predicate = ' OR '.join('position(lower(?) in lower(p.title)) > 0' for _ in terms)
        conditions = ['p.title IS NOT NULL', 'length(trim(p.title))>0', f'({title_predicate})']
        params: list[Any] = list(terms)
        filters: dict[str, Any] = {
            'classification_label': TITLE_CLASSIFICATION_LABEL,
            'topic_id': int(topic['topic_id']), 'matched_keywords': terms,
        }
        if year_from is not None:
            conditions.append('p.year >= ?'); params.append(year_from)
            filters['year_from_inclusive'] = year_from
        if year_to is not None:
            conditions.append('p.year <= ?'); params.append(year_to)
            filters['year_to_inclusive'] = year_to
        rows = _select(
            'WITH matched AS MATERIALIZED (SELECT p.publication_id, p.db_key, p.title, '
            'p.year, p.type, p.venue_id FROM publications p WHERE ' + ' AND '.join(conditions) + '), '
            'totals AS (SELECT count(*) AS publication_count FROM matched), '
            'samples AS (SELECT * FROM matched ORDER BY year DESC NULLS LAST, publication_id LIMIT ?) '
            'SELECT totals.publication_count, samples.publication_id, samples.db_key, samples.title, '
            'samples.year, samples.type, samples.venue_id FROM totals LEFT JOIN samples ON TRUE '
            'ORDER BY samples.year DESC NULLS LAST, samples.publication_id',
            tuple(params + [max(1, min(int(sample_limit), 5))]))
        count = int(rows[0]['publication_count']) if rows else 0
        sample_rows = [
            {'publication_id': row['publication_id'], 'db_key': row['db_key'],
             'title': row['title'], 'year': row['year'], 'type': row['type'],
             'venue_id': row['venue_id']}
            for row in rows if row['publication_id'] is not None
        ]
        row = {'topic_id': int(topic['topic_id']), 'topic_name': topic['topic_name'],
               'keywords': terms, 'publication_count': count,
               'sample_publications': sample_rows}
        results.append(Evidence('classification', row,
                                f"COUNT(DISTINCT publication_id) matching project keywords in stored titles; label: {TITLE_CLASSIFICATION_LABEL}",
                                filters))
    return results
