from fastapi import APIRouter, HTTPException, Query
from ..schemas.models import Graph, NetworkStats
from ..services.analytics import require_author
from ..services.duckdb import query
from ..services.graph_analytics import compute_network_intelligence

router = APIRouter(tags=['Collaboration'])


@router.get('/api/network/stats', response_model=NetworkStats)
def network_stats():
    totals = query('''SELECT 
        (SELECT total_authors FROM dashboard_summary) as total_researchers,
        (SELECT COUNT(*) FROM author_collaboration) as total_collaborations,
        ROUND((SELECT 2.0 * COUNT(*) FROM author_collaboration) / NULLIF((SELECT total_authors FROM dashboard_summary), 0), 2) as avg_collaborators_per_researcher''')[0]
    
    strongest = query('''SELECT author1, author2, weight
        FROM author_collaboration_dashboard_named
        ORDER BY weight DESC
        LIMIT 1''')
    strongest_pair = strongest[0] if strongest else None
    
    dist_rows = query('''SELECT 
        CASE 
            WHEN weight = 1 THEN '1 paper'
            WHEN weight = 2 THEN '2 papers'
            WHEN weight BETWEEN 3 AND 5 THEN '3-5 papers'
            WHEN weight BETWEEN 6 AND 10 THEN '6-10 papers'
            ELSE '11+ papers'
        END as bucket,
        COUNT(*) as count
    FROM author_collaboration
    GROUP BY 1
    ORDER BY MIN(weight)''')
    total_edges = totals['total_collaborations'] or 1
    weight_distribution = [
        dict(r, percentage=round(r['count'] * 100.0 / total_edges, 1))
        for r in dist_rows
    ]
    return dict(
        **totals,
        strongest_pair=strongest_pair,
        weight_distribution=weight_distribution
    )


@router.get('/api/collaboration', response_model=Graph)
def collaboration(author_id: int | None = Query(None, ge=1), limit: int = Query(50, ge=2, le=500),
                  min_weight: int = Query(1, ge=1, le=1000), start_year: int | None = Query(None, ge=1800, le=2100),
                  end_year: int | None = Query(None, ge=1800, le=2100)):
    if start_year and end_year and start_year > end_year:
        raise HTTPException(422, 'Start year must not exceed end year')
    if author_id is None:
        top = query('SELECT author_id FROM author_stats ORDER BY publication_count DESC, author_id LIMIT 1')
        if not top:
            raise HTTPException(404, 'No researchers available')
        author_id = top[0]['author_id']
    center = require_author(author_id)
    if start_year is not None or end_year is not None:
        edges = '''WITH selected_papers AS (
            SELECT p.publication_id FROM publication_authors pa JOIN publications p USING(publication_id)
            WHERE pa.author_id = ? AND p.year BETWEEN ? AND ?
        ), edges AS (
            SELECT pa.author_id, COUNT(*) AS weight FROM selected_papers p
            JOIN publication_authors pa USING(publication_id) WHERE pa.author_id <> ? GROUP BY pa.author_id
        )'''
        params = (author_id, start_year or 1800, end_year or 2100, author_id)
    else:
        edges = '''WITH edges AS (
            SELECT author2_id AS author_id, weight FROM author_collaboration WHERE author1_id = ?
            UNION ALL SELECT author1_id AS author_id, weight FROM author_collaboration WHERE author2_id = ?
        )'''
        params = (author_id, author_id)
    rows = query(edges + ''' SELECT author_id, weight, COUNT(*) OVER() AS matching FROM edges
        WHERE weight >= ? ORDER BY weight DESC, author_id LIMIT ?''', params + (min_weight, limit - 1))
    ids = (author_id,) + tuple(r['author_id'] for r in rows)
    marks = ','.join('?' for _ in ids)
    nodes = query(f'''WITH degrees AS (
        SELECT author1_id AS author_id, COUNT(*) AS n FROM author_collaboration WHERE author1_id IN ({marks}) GROUP BY author1_id
        UNION ALL SELECT author2_id AS author_id, COUNT(*) AS n FROM author_collaboration WHERE author2_id IN ({marks}) GROUP BY author2_id
    ), totals AS (SELECT author_id, SUM(n) AS collaborators FROM degrees GROUP BY author_id)
    SELECT CAST(a.author_id AS VARCHAR) AS id, a.name, a.publication_count AS publications,
        COALESCE(t.collaborators, 0) AS collaborators FROM author_stats a LEFT JOIN totals t USING(author_id)
        WHERE a.author_id IN ({marks}) ORDER BY a.author_id''', ids * 3)
    matching = rows[0]['matching'] if rows else 0
    return dict(center_id=str(center['author_id']), nodes=nodes,
                edges=[dict(source=str(author_id), target=str(r['author_id']), weight=r['weight']) for r in rows],
                matching_collaborators=matching, truncated=matching > len(rows), start_year=start_year, end_year=end_year)

    # Retrieve all ties between the selected nodes (induced subgraph)
    all_edges_sql = f'''
    SELECT CAST(author1_id AS VARCHAR) AS source, CAST(author2_id AS VARCHAR) AS target, weight
    FROM author_collaboration
    WHERE author1_id IN ({marks}) AND author2_id IN ({marks}) AND weight >= ?
    '''
    subgraph_edges = query(all_edges_sql, ids + ids + (min_weight,))
    edge_pairs = {(e['source'], e['target']) for e in subgraph_edges} | {(e['target'], e['source']) for e in subgraph_edges}
    for r in rows:
        s, t = str(author_id), str(r['author_id'])
        if (s, t) not in edge_pairs:
            subgraph_edges.append(dict(source=s, target=t, weight=r['weight']))
            edge_pairs.add((s, t))

    # Compute network intelligence: communities, centrality, PageRank, bridge detection
    enriched_nodes, communities, bridge_ids = compute_network_intelligence(nodes, subgraph_edges, str(author_id))

    return dict(
        center_id=str(center['author_id']),
        nodes=enriched_nodes,
        edges=subgraph_edges,
        matching_collaborators=matching,
        truncated=matching > len(rows),
        start_year=start_year,
        end_year=end_year,
        communities=communities,
        bridge_nodes=bridge_ids
    )
