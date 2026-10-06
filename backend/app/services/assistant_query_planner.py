"""Schema-aware natural-language query plans for trusted DBLP records.

The model emits a small declarative plan, never SQL. The compiler below owns
all identifiers, joins, operators, and parameter binding.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .local_query_interpreter import generate_local_text

PLANNER_VERSION = 'dblp-query-plan-v1'

FIELDS = {
    'publications.publication_id': ('p', 'publication_id'),
    'publications.db_key': ('p', 'db_key'),
    'publications.type': ('p', 'type'),
    'publications.title': ('p', 'title'),
    'publications.year': ('p', 'year'),
    'publications.venue_id': ('p', 'venue_id'),
    'authors.author_id': ('a', 'author_id'),
    'authors.name': ('a', 'name'),
    'venues.venue_id': ('v', 'venue_id'),
    'venues.name': ('v', 'name'),
    'publication_authors.publication_id': ('pa', 'publication_id'),
    'publication_authors.author_id': ('pa', 'author_id'),
}
TABLES = {
    'publications': 'p', 'authors': 'a', 'venues': 'v',
    'publication_authors': 'pa',
}
OPERATORS = {'eq', 'contains', 'starts_with', 'gt', 'gte', 'lt', 'lte'}
AGGREGATES = {'count_distinct', 'min', 'max', 'avg'}
INTEGER_FIELDS = {
    'publications.publication_id', 'publications.year', 'publications.venue_id',
    'authors.author_id', 'venues.venue_id', 'publication_authors.publication_id',
    'publication_authors.author_id',
}

SYSTEM = '''You translate a question about the DBLP database into one JSON query plan. Return JSON only, with exactly these keys:
{"mode":"query|title_search","search_query":null,"fields":[],"metrics":[],"filters":[],"group_by":[],"order_by":[],"limit":20}

Available fields (use these exact names):
publications.publication_id, publications.db_key, publications.type, publications.title, publications.year, publications.venue_id
authors.author_id, authors.name
venues.venue_id, venues.name
publication_authors.publication_id, publication_authors.author_id

Each metric is {"fn":"count_distinct|min|max|avg","field":"an available field"}.
Each filter is {"field":"an available field","op":"eq|contains|starts_with|gt|gte|lt|lte","value":value}.
Each order_by entry is {"field":"an available field or metric name","direction":"asc|desc"}.
Only use stored facts. Authors link to publications through publication_authors; publications link to venues through venue_id. Count distinct publication IDs when counting papers, including across joins. Group non-aggregated fields when using metrics. Include author_id or venue_id when grouping by a name so same-name records remain distinct. Use a limit no greater than 50.
For broad paper discovery by a research topic, choose mode title_search and put only the topic in search_query. This uses semantic and keyword title retrieval. The title does not reveal methods, findings, citations, affiliations, or paper content. For exact filters, aggregates, rankings, comparisons, and records, choose mode query and use the query fields. Do not invent fields or facts. If a request cannot be answered from the listed fields, return mode query with empty fields and metrics.

Examples:
Question: Which venues had the most papers in 2020?
Plan: {"mode":"query","search_query":null,"fields":["venues.name","venues.venue_id"],"metrics":[{"fn":"count_distinct","field":"publications.publication_id"}],"filters":[{"field":"publications.year","op":"eq","value":2020}],"group_by":["venues.name","venues.venue_id"],"order_by":[{"field":"count_distinct_publications_publication_id","direction":"desc"}],"limit":10}
Question: Find papers about graph neural networks after 2021
Plan: {"mode":"title_search","search_query":"graph neural networks","fields":[],"metrics":[],"filters":[],"group_by":[],"order_by":[],"limit":10}
Question: How many papers did Geoffrey Hinton publish?
Plan: {"mode":"query","search_query":null,"fields":["authors.name","authors.author_id"],"metrics":[{"fn":"count_distinct","field":"publications.publication_id"}],"filters":[{"field":"authors.name","op":"eq","value":"Geoffrey Hinton"}],"group_by":["authors.name","authors.author_id"],"order_by":[],"limit":10}
'''


def _extract_object(text: str) -> dict[str, Any] | None:
    text = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', text, flags=re.I)
    start, end = text.find('{'), text.rfind('}')
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except (TypeError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def interpret_database_question(question: str) -> dict[str, Any] | None:
    raw = generate_local_text(SYSTEM, json.dumps({'question': question}, ensure_ascii=False), max_new_tokens=300)
    if raw is None:
        return None
    return validate_plan(_extract_object(raw))


def validate_plan(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if not value or set(value) != {'mode', 'search_query', 'fields', 'metrics', 'filters', 'group_by', 'order_by', 'limit'}:
        return None
    mode, search_query = value['mode'], value['search_query']
    fields, metrics = value['fields'], value['metrics']
    filters, groups, ordering, limit = value['filters'], value['group_by'], value['order_by'], value['limit']
    if not all(isinstance(x, list) for x in (fields, metrics, filters, groups, ordering)):
        return None
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        return None
    if mode == 'title_search':
        if (not isinstance(search_query, str) or not 2 <= len(search_query.strip()) <= 500
                or any((fields, metrics, filters, groups, ordering))):
            return None
        return {'mode': 'title_search', 'search_query': search_query.strip(),
                'fields': [], 'metrics': [], 'filters': [], 'group_by': [], 'order_by': [], 'limit': min(limit, 8)}
    if mode != 'query' or search_query is not None:
        return None
    if (len(fields) > 8 or len(metrics) > 4 or len(filters) > 8 or len(groups) > 8
            or len(ordering) > 8):
        return None
    if not fields and not metrics:
        return None
    if any(not isinstance(field, str) for field in fields + groups):
        return None
    if any(field not in FIELDS for field in fields + groups):
        return None
    if len(set(fields)) != len(fields) or len(set(groups)) != len(groups):
        return None
    clean_metrics = []
    metric_names = set()
    for metric in metrics:
        if not isinstance(metric, dict) or set(metric) not in ({'fn', 'field'}, {'fn', 'field', 'name'}):
            return None
        fn, field = metric['fn'], metric['field']
        if not isinstance(fn, str) or not isinstance(field, str) or fn not in AGGREGATES or field not in FIELDS:
            return None
        name = f'{fn}_{field.replace(".", "_")}'
        if metric.get('name', name) != name:
            return None
        if name in metric_names:
            return None
        metric_names.add(name)
        clean_metrics.append({'fn': fn, 'field': field, 'name': name})
    clean_filters = []
    for item in filters:
        if not isinstance(item, dict) or set(item) != {'field', 'op', 'value'}:
            return None
        field, op, val = item['field'], item['op'], item['value']
        if (not isinstance(field, str) or not isinstance(op, str) or field not in FIELDS
                or op not in OPERATORS or isinstance(val, (dict, list, bool)) or val is None):
            return None
        if field in INTEGER_FIELDS:
            if not isinstance(val, int):
                return None
        elif not isinstance(val, str) or op in {'gt', 'gte', 'lt', 'lte'}:
            return None
        if isinstance(val, str):
            val = val.strip()
            if not val or len(val) > 300:
                return None
        elif not isinstance(val, (int, float)):
            return None
        if field.endswith('.year') and (not isinstance(val, int) or not 1800 <= val <= 2200):
            return None
        clean_filters.append({'field': field, 'op': op, 'value': val})
    if metrics and any(field not in groups for field in fields):
        # Names are grouped alongside their IDs, preserving separate name records.
        return None
    if metrics and any(field not in fields for field in groups):
        return None
    if not metrics and groups:
        return None
    if metrics:
        for name_field, id_field in (
            ('authors.name', 'authors.author_id'),
            ('venues.name', 'venues.venue_id'),
        ):
            if name_field in fields and id_field not in fields:
                return None
            if name_field in fields and id_field not in groups:
                return None
    clean_ordering = []
    allowed_order = set(fields) | metric_names
    for item in ordering:
        if not isinstance(item, dict) or set(item) != {'field', 'direction'}:
            return None
        if (not isinstance(item['field'], str) or not isinstance(item['direction'], str)
                or item['field'] not in allowed_order or item['direction'] not in {'asc', 'desc'}):
            return None
        clean_ordering.append(dict(item))
    used_tables = {item.split('.', 1)[0] for item in fields + groups}
    used_tables.update(item['field'].split('.', 1)[0] for item in clean_metrics + clean_filters)
    if len(used_tables) > 4:
        return None
    return {
        'mode': 'query', 'search_query': None,
        'fields': list(fields), 'metrics': clean_metrics, 'filters': clean_filters,
        'group_by': list(groups), 'order_by': clean_ordering, 'limit': limit,
    }


def _join_tables(required: set[str]) -> tuple[str, list[str]] | None:
    """Build only the known DBLP relationship joins, with stable aliases."""
    if not required or not required <= set(TABLES):
        return None
    needed = set(required)
    if 'publication_authors' in needed:
        needed.update({'publications', 'authors'})
    if 'authors' in needed and 'publications' in needed:
        needed.add('publication_authors')
    if 'venues' in needed and 'authors' in needed:
        needed.update({'publications', 'publication_authors', 'authors'})
    if len(needed) > 4:
        return None

    if 'publications' in needed:
        from_sql = 'publications AS p'
        joined = {'publications'}
    elif 'authors' in needed:
        from_sql = 'authors AS a'
        joined = {'authors'}
    else:
        from_sql = 'venues AS v'
        joined = {'venues'}
    joins = []
    while joined != needed:
        if 'publications' in joined and 'publication_authors' in needed and 'publication_authors' not in joined:
            joins.append('JOIN publication_authors AS pa ON pa.publication_id = p.publication_id')
            joined.add('publication_authors')
        elif 'publication_authors' in joined and 'authors' in needed and 'authors' not in joined:
            joins.append('JOIN authors AS a ON a.author_id = pa.author_id')
            joined.add('authors')
        elif 'publications' in joined and 'venues' in needed and 'venues' not in joined:
            joins.append('JOIN venues AS v ON v.venue_id = p.venue_id')
            joined.add('venues')
        elif 'venues' in joined and 'publications' in needed and 'publications' not in joined:
            joins.append('JOIN publications AS p ON p.venue_id = v.venue_id')
            joined.add('publications')
        elif 'authors' in joined and 'publication_authors' in needed and 'publication_authors' not in joined:
            joins.append('JOIN publication_authors AS pa ON pa.author_id = a.author_id')
            joined.add('publication_authors')
        elif 'publication_authors' in joined and 'publications' in needed and 'publications' not in joined:
            joins.append('JOIN publications AS p ON p.publication_id = pa.publication_id')
            joined.add('publications')
        else:
            return None
    return from_sql, joins


def compile_plan(plan: dict[str, Any]) -> tuple[str, tuple[Any, ...], dict[str, Any]] | None:
    """Compile a validated declarative plan to one bounded parameterized SELECT."""
    checked = validate_plan(plan)
    if checked is None or checked['mode'] != 'query':
        return None
    references = checked['fields'] + checked['group_by']
    references += [item['field'] for item in checked['metrics'] + checked['filters']]
    required = {field.split('.', 1)[0] for field in references}
    join_data = _join_tables(required)
    if join_data is None:
        return None
    from_sql, joins = join_data
    select_sql = []
    for field in checked['fields']:
        alias, column = FIELDS[field]
        output_name = field.replace('.', '_')
        select_sql.append(f'"{alias}"."{column}" AS "{output_name}"')
    for metric in checked['metrics']:
        alias, column = FIELDS[metric['field']]
        if metric['fn'] == 'count_distinct':
            expression = f'COUNT(DISTINCT "{alias}"."{column}")'
        else:
            expression = f'{metric["fn"].upper()}("{alias}"."{column}")'
        select_sql.append(f'{expression} AS "{metric["name"]}"')
    params: list[Any] = []
    predicates = []
    for item in checked['filters']:
        alias, column = FIELDS[item['field']]
        ref = f'"{alias}"."{column}"'
        op, val = item['op'], item['value']
        if op == 'eq' and isinstance(val, str):
            predicates.append(f'LOWER(TRIM(CAST({ref} AS VARCHAR))) = LOWER(TRIM(?))')
            params.append(val)
        elif op in {'contains', 'starts_with'}:
            escaped = str(val).replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            pattern = f'%{escaped}%' if op == 'contains' else f'{escaped}%'
            predicates.append(f'CAST({ref} AS VARCHAR) ILIKE ? ESCAPE \'\\\'')
            params.append(pattern)
        else:
            sql_op = {'eq': '=', 'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<='}[op]
            predicates.append(f'{ref} {sql_op} ?')
            params.append(val)
    sql = ('SELECT ' if checked['metrics'] else 'SELECT DISTINCT ') + ', '.join(select_sql) + ' FROM ' + from_sql
    if joins:
        sql += ' ' + ' '.join(joins)
    if predicates:
        sql += ' WHERE ' + ' AND '.join(predicates)
    if checked['metrics'] and checked['group_by']:
        group_sql = [f'"{FIELDS[field][0]}"."{FIELDS[field][1]}"' for field in checked['group_by']]
        sql += ' GROUP BY ' + ', '.join(group_sql)
    ordering = []
    aliases = {field: field.replace('.', '_') for field in checked['fields']}
    aliases.update({metric['name']: metric['name'] for metric in checked['metrics']})
    for item in checked['order_by']:
        ordering.append(f'"{aliases[item["field"]]}" {item["direction"].upper()}')
    if ordering:
        sql += ' ORDER BY ' + ', '.join(ordering)
    sql += ' LIMIT ?'
    params.append(checked['limit'])
    return sql, tuple(params), checked


def generate_grounded_answer(question: str, result: dict[str, Any]) -> str | None:
    system = '''Answer the DBLP question using only the supplied query result. Give a direct answer and explain what the rows or metric show. Do not add facts, assumptions, citations, methods, findings, identities, or metrics absent from the result. If the result is empty, say no matching rows were returned. Output plain text only, at most 180 words.'''
    evidence = dict(result)
    result_rows = result.get('rows', result.get('matches', []))
    if isinstance(result_rows, list) and len(result_rows) > 12:
        evidence['rows'] = result_rows[:12]
        evidence['rows_shown'] = 12
        evidence['rows_truncated_for_answer'] = True
    raw = generate_local_text(system, json.dumps({'question': question, 'evidence': evidence}, ensure_ascii=False), max_new_tokens=220)
    if not raw:
        return None
    answer = re.sub(r'^\s*```(?:text)?\s*|\s*```\s*$', '', raw, flags=re.I).strip()
    return answer[:3000] if answer else None
