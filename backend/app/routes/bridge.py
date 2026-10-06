from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.analytics import require_author
from ..services.duckdb import query

router = APIRouter(prefix='/api', tags=['Bridge Finder'])


class BridgeNode(BaseModel):
    author_id: int
    name: str
    papers: int


class BridgeLink(BaseModel):
    source: int
    target: int
    shared_papers: int
    explanation: str


class BridgeResponse(BaseModel):
    found: bool
    hops: int
    nodes: list[BridgeNode]
    links: list[BridgeLink]
    message: str


@router.get('/bridge', response_model=BridgeResponse)
def find_bridge(
    source: int = Query(ge=1),
    target: int = Query(ge=1),
    max_hops: int = Query(5, ge=1, le=8),
):
    require_author(source)
    require_author(target)

    if source == target:
        author = query('SELECT author_id, name, publication_count AS papers FROM author_stats WHERE author_id = ?', (source,))[0]
        return dict(found=True, hops=0, nodes=[author], links=[], message='Choose two different researchers to find a bridge.')

    frontier = {source}
    parent: dict[int, int | None] = {source: None}
    edge_weights: dict[tuple[int, int], int] = {}

    for _ in range(max_hops):
        if not frontier:
            break
        frontier_ids = tuple(frontier)
        marks = ','.join('?' for _ in frontier_ids)
        edge_rows = query(f'''SELECT author1_id AS source, author2_id AS target, weight
            FROM author_collaboration
            WHERE author1_id IN ({marks}) OR author2_id IN ({marks})
            ORDER BY weight DESC
            LIMIT 10000''', frontier_ids + frontier_ids)
        next_frontier: set[int] = set()
        for edge in edge_rows:
            left, right = edge['source'], edge['target']
            for current, neighbor in ((left, right), (right, left)):
                if current in frontier and neighbor not in parent:
                    parent[neighbor] = current
                    edge_weights[(current, neighbor)] = edge['weight']
                    next_frontier.add(neighbor)
        if target in parent:
            break
        frontier = next_frontier

    if target not in parent:
        return dict(found=False, hops=0, nodes=[], links=[], message=f'No co-authorship path found within {max_hops} steps.')

    ids = []
    current = target
    while current is not None:
        ids.append(current)
        current = parent[current]
    ids.reverse()
    marks = ','.join('?' for _ in ids)
    nodes = query(f'''SELECT author_id, name, publication_count AS papers
        FROM author_stats WHERE author_id IN ({marks})''', tuple(ids))
    node_map = {row['author_id']: row for row in nodes}
    link_rows = query(f'''SELECT author1_id AS source, author2_id AS target, weight AS shared_papers
        FROM author_collaboration
        WHERE author1_id IN ({marks}) AND author2_id IN ({marks})''', tuple(ids) + tuple(ids))

    link_map = {(row['source'], row['target']): row for row in link_rows}
    link_map.update({(row['target'], row['source']): row for row in link_rows})
    links = []
    for left, right in zip(ids, ids[1:]):
        edge = link_map.get((left, right), {'shared_papers': edge_weights.get((left, right), 0)})
        links.append(dict(source=left, target=right, shared_papers=edge['shared_papers'], explanation=f"{edge['shared_papers']} shared publication{'s' if edge['shared_papers'] != 1 else ''}"))

    return dict(
        found=True,
        hops=len(ids) - 1,
        nodes=[node_map[author_id] for author_id in ids],
        links=links,
        message=f"A {len(ids) - 1}-step co-authorship path connects these researchers."
    )
