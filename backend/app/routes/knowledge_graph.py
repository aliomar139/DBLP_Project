"""Unified Scientific Knowledge Graph Router.

Builds a multi-entity graph universe linking:
- Researchers (indigo)
- Papers (teal)
- Topics (amber)
- Institutions (purple)
- Venues (emerald)

Provides graph expansion, cross-domain relationship discovery, and centrality analytics.
"""
from typing import Any
from fastapi import APIRouter, Query
from ..schemas.models import KnowledgeGraphResponse, KGNode, KGEdge, KGAnalytics
from ..services.duckdb import query
from ..services.analytics import search_term

router = APIRouter(prefix='/api/knowledge-graph', tags=['Knowledge Graph'])


@router.get('', response_model=KnowledgeGraphResponse)
def get_knowledge_graph(
    q: str | None = Query(None, max_length=120),
    center_type: str | None = Query(None, pattern='^(topic|researcher|institution|venue|paper)$'),
    center_id: str | None = Query(None, max_length=50),
    node_types: str = Query('researcher,topic,institution,venue,paper'),
    start_year: int | None = Query(None, ge=1950, le=2026),
    end_year: int | None = Query(None, ge=1950, le=2026),
    limit: int = Query(60, ge=10, le=150)
):
    """Retrieve multi-entity scientific knowledge subgraph centered on any entity or query."""
    allowed_types = {t.strip().lower() for t in node_types.split(',')}

    # 1. Determine focal entity
    focal_type = center_type
    focal_id = center_id
    focal_name = ""

    if not focal_id and q:
        # Search topics first
        topic_match = query("SELECT topic_id, topic_name FROM topics WHERE topic_name ILIKE ? ESCAPE '!' LIMIT 1", (search_term(q),))
        if topic_match:
            focal_type = 'topic'
            focal_id = str(topic_match[0]['topic_id'])
            focal_name = topic_match[0]['topic_name']
        else:
            inst_match = query("SELECT institution_id, name FROM institutions WHERE name ILIKE ? ESCAPE '!' OR short_name ILIKE ? ESCAPE '!' LIMIT 1", (search_term(q), search_term(q)))
            if inst_match:
                focal_type = 'institution'
                focal_id = str(inst_match[0]['institution_id'])
                focal_name = inst_match[0]['name']
            else:
                author_match = query("SELECT author_id, name FROM authors WHERE name ILIKE ? ESCAPE '!' LIMIT 1", (search_term(q),))
                if author_match:
                    focal_type = 'researcher'
                    focal_id = str(author_match[0]['author_id'])
                    focal_name = author_match[0]['name']

    # Default to Large Language Models (topic 1) if unspecified
    if not focal_type or not focal_id:
        focal_type = 'topic'
        focal_id = '1'
        focal_name = 'Large Language Models'

    nodes_map: dict[str, KGNode] = {}
    edges_list: list[KGEdge] = []

    def add_node(nid: str, name: str, etype: str, size: float, color: str, subtext: str = "", is_hub: bool = False, is_bridge: bool = False, cluster_id: int = 1):
        if etype in allowed_types and nid not in nodes_map:
            nodes_map[nid] = KGNode(
                id=nid,
                name=name,
                entity_type=etype,
                size=size,
                color=color,
                subtext=subtext,
                is_hub=is_hub,
                is_bridge=is_bridge,
                cluster_id=cluster_id
            )

    def add_edge(src: str, tgt: str, rel: str, weight: int = 1):
        if src in nodes_map and tgt in nodes_map:
            edges_list.append(KGEdge(source=src, target=tgt, relationship=rel, weight=weight))

    # =========================================================================
    # BUILD GRAPH AROUND FOCAL ENTITY
    # =========================================================================

    if focal_type == 'topic':
        tid = int(focal_id)
        t_info = query("SELECT topic_name, category, publication_count FROM topics WHERE topic_id = ?", (tid,))
        if t_info:
            focal_name = t_info[0]['topic_name']
            cat = t_info[0]['category']
            add_node(f"t_{tid}", focal_name, "topic", 28, "#d97706", f"{cat} · {t_info[0]['publication_count']:,} papers", is_hub=True, cluster_id=1)

            # Top researchers in topic
            top_scholars = query("""
            SELECT a.author_id, a.name, atp.publication_count as papers
            FROM author_topics atp
            JOIN authors a USING(author_id)
            WHERE atp.topic_id = ?
            ORDER BY atp.publication_count DESC
            LIMIT 12
            """, (tid,))
            for s in top_scholars:
                sid = f"r_{s['author_id']}"
                add_node(sid, s['name'], "researcher", 16, "#4f46e5", f"{s['papers']} topic papers", cluster_id=1)
                add_edge(sid, f"t_{tid}", "Researches", weight=s['papers'])

            # Top institutions in topic
            top_insts = query("""
            SELECT i.institution_id, i.name, i.short_name, it.publication_count as papers
            FROM institution_topics it
            JOIN institutions i USING(institution_id)
            WHERE it.topic_id = ?
            ORDER BY it.publication_count DESC
            LIMIT 8
            """, (tid,))
            for inst in top_insts:
                iid = f"i_{inst['institution_id']}"
                add_node(iid, inst['name'], "institution", 20, "#9333ea", f"{inst['short_name']} · {inst['papers']:,} papers", is_hub=True, cluster_id=2)
                add_edge(iid, f"t_{tid}", "Topic Hub", weight=inst['papers'])

            # Top venues in topic
            top_venues = query("""
            SELECT v.venue_id, v.name, vt.publication_count as papers
            FROM venue_topics vt
            JOIN venues v USING(venue_id)
            WHERE vt.topic_id = ?
            ORDER BY vt.publication_count DESC
            LIMIT 6
            """, (tid,))
            for v in top_venues:
                vid = f"v_{v['venue_id']}"
                add_node(vid, v['name'], "venue", 18, "#059669", f"{v['papers']} topic papers", cluster_id=3)
                add_edge(f"t_{tid}", vid, "Disseminated At", weight=v['papers'])

            # Related topics
            related_t = query("""
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
                LIMIT 5
            )
            SELECT t.topic_id, t.topic_name, t.category, c.shared_papers
            FROM co_occur c
            JOIN topics t USING(topic_id)
            """, (tid, tid))
            for rt in related_t:
                rtid = f"t_{rt['topic_id']}"
                add_node(rtid, rt['topic_name'], "topic", 20, "#b45309", f"{rt['category']}", is_bridge=True, cluster_id=4)
                add_edge(f"t_{tid}", rtid, "Related Topic", weight=rt['shared_papers'])

            # High citation papers in this topic
            top_papers = query("""
            SELECT p.publication_id, p.title, p.year, pc.citations
            FROM publication_topics pt
            JOIN publications p USING(publication_id)
            JOIN publication_citations pc USING(publication_id)
            WHERE pt.topic_id = ?
            ORDER BY pc.citations DESC
            LIMIT 8
            """, (tid,))
            for p in top_papers:
                pid = f"p_{p['publication_id']}"
                add_node(pid, p['title'][:40] + "…", "paper", 12, "#0891b2", f"{p['year']} · {p['citations']:,} cites", cluster_id=5)
                add_edge(pid, f"t_{tid}", "Addresses Topic", weight=p['citations'])

    elif focal_type == 'researcher':
        aid = int(focal_id)
        a_info = query("SELECT name, publication_count as papers FROM author_stats JOIN authors USING(author_id) WHERE author_id = ?", (aid,))
        if a_info:
            focal_name = a_info[0]['name']
            add_node(f"r_{aid}", focal_name, "researcher", 26, "#4f46e5", f"{a_info[0]['papers']} papers", is_hub=True, cluster_id=1)

            # Author topics
            a_topics = query("""
            SELECT t.topic_id, t.topic_name, atp.publication_count as papers
            FROM author_topics atp
            JOIN topics t USING(topic_id)
            WHERE atp.author_id = ?
            ORDER BY atp.publication_count DESC
            LIMIT 6
            """, (aid,))
            for t in a_topics:
                tid = f"t_{t['topic_id']}"
                add_node(tid, t['topic_name'], "topic", 20, "#d97706", f"{t['papers']} papers", is_bridge=True, cluster_id=2)
                add_edge(f"r_{aid}", tid, "Specializes In", weight=t['papers'])

            # Author institution
            inst = query("""
            SELECT i.institution_id, i.name, i.short_name, i.country
            FROM author_institutions ai
            JOIN institutions i USING(institution_id)
            WHERE ai.author_id = ?
            """, (aid,))
            if inst:
                iid = f"i_{inst[0]['institution_id']}"
                add_node(iid, inst[0]['name'], "institution", 22, "#9333ea", f"{inst[0]['country']}", is_hub=True, cluster_id=3)
                add_edge(f"r_{aid}", iid, "Affiliated With")

            # Collaborators
            collabs = query("""
            WITH ties AS (
                SELECT author2_id as peer_id, weight FROM author_collaboration WHERE author1_id = ?
                UNION ALL
                SELECT author1_id as peer_id, weight FROM author_collaboration WHERE author2_id = ?
            )
            SELECT a.author_id, a.name, t.weight as shared
            FROM ties t
            JOIN authors a ON a.author_id = t.peer_id
            ORDER BY shared DESC
            LIMIT 10
            """, (aid, aid))
            for c in collabs:
                cid = f"r_{c['author_id']}"
                add_node(cid, c['name'], "researcher", 15, "#6366f1", f"{c['shared']} shared papers", cluster_id=1)
                add_edge(f"r_{aid}", cid, "Collaborated With", weight=c['shared'])

            # Venues
            venues = query("""
            SELECT v.venue_id, v.name, COUNT(*) as papers
            FROM publication_authors pa
            JOIN publications p USING(publication_id)
            JOIN venues v USING(venue_id)
            WHERE pa.author_id = ?
            GROUP BY v.venue_id, v.name
            ORDER BY papers DESC
            LIMIT 5
            """, (aid,))
            for v in venues:
                vid = f"v_{v['venue_id']}"
                add_node(vid, v['name'], "venue", 17, "#059669", f"{v['papers']} papers", cluster_id=4)
                add_edge(f"r_{aid}", vid, "Published In", weight=v['papers'])

    elif focal_type == 'institution':
        iid = int(focal_id)
        inst_info = query("SELECT name, short_name, country, publication_count, citation_count FROM institutions WHERE institution_id = ?", (iid,))
        if inst_info:
            focal_name = inst_info[0]['name']
            add_node(f"i_{iid}", focal_name, "institution", 28, "#9333ea", f"{inst_info[0]['country']} · {inst_info[0]['publication_count']:,} papers", is_hub=True, cluster_id=1)

            # Top researchers at institution
            scholars = query("""
            SELECT a.author_id, a.name, a.publication_count as papers
            FROM author_institutions ai
            JOIN author_stats a USING(author_id)
            WHERE ai.institution_id = ?
            ORDER BY a.publication_count DESC
            LIMIT 12
            """, (iid,))
            for s in scholars:
                sid = f"r_{s['author_id']}"
                add_node(sid, s['name'], "researcher", 16, "#4f46e5", f"{s['papers']} papers", cluster_id=1)
                add_edge(f"i_{iid}", sid, "Employs")

            # Top topics
            inst_topics = query("""
            SELECT t.topic_id, t.topic_name, it.publication_count as papers
            FROM institution_topics it
            JOIN topics t USING(topic_id)
            WHERE it.institution_id = ?
            ORDER BY it.publication_count DESC
            LIMIT 8
            """, (iid,))
            for t in inst_topics:
                tid = f"t_{t['topic_id']}"
                add_node(tid, t['topic_name'], "topic", 20, "#d97706", f"{t['papers']} papers", is_bridge=True, cluster_id=2)
                add_edge(f"i_{iid}", tid, "Research Strength", weight=t['papers'])

            # Partner institutions
            partners = query("""
            WITH ties AS (
                SELECT institution2_id as pid, weight FROM institution_collaboration WHERE institution1_id = ?
                UNION ALL
                SELECT institution1_id as pid, weight FROM institution_collaboration WHERE institution2_id = ?
            )
            SELECT i.institution_id, i.name, i.short_name, SUM(t.weight) as shared
            FROM ties t
            JOIN institutions i ON i.institution_id = t.pid
            GROUP BY i.institution_id, i.name, i.short_name
            ORDER BY shared DESC
            LIMIT 6
            """, (iid, iid))
            for p in partners:
                pid = f"i_{p['institution_id']}"
                add_node(pid, p['name'], "institution", 20, "#a855f7", f"{p['shared']} joint papers", cluster_id=3)
                add_edge(f"i_{iid}", pid, "Partnership", weight=p['shared'])

    # Calculate degrees
    degree_counts: dict[str, int] = {}
    for edge in edges_list:
        degree_counts[edge.source] = degree_counts.get(edge.source, 0) + 1
        degree_counts[edge.target] = degree_counts.get(edge.target, 0) + 1

    for nid, node in nodes_map.items():
        node.degree = degree_counts.get(nid, 0)
        if node.degree >= 5:
            node.is_hub = True

    # Build analytics
    sorted_by_degree = sorted(nodes_map.values(), key=lambda n: n.degree, reverse=True)
    influential_hubs = [
        {"id": n.id, "name": n.name, "type": n.entity_type, "connections": n.degree}
        for n in sorted_by_degree[:5]
    ]

    bridge_entities = [
        {"id": n.id, "name": n.name, "type": n.entity_type, "subtext": n.subtext or ""}
        for n in nodes_map.values() if n.is_bridge
    ][:5]

    clusters: dict[int, int] = {}
    for n in nodes_map.values():
        clusters[n.cluster_id] = clusters.get(n.cluster_id, 0) + 1
    cluster_dist = [
        {"cluster_id": cid, "size": size, "label": f"Community {cid}"}
        for cid, size in clusters.items()
    ]

    analytics = KGAnalytics(
        total_nodes=len(nodes_map),
        total_edges=len(edges_list),
        influential_hubs=influential_hubs,
        bridge_entities=bridge_entities,
        cluster_distribution=cluster_dist
    )

    return KnowledgeGraphResponse(
        nodes=list(nodes_map.values()),
        edges=edges_list,
        analytics=analytics
    )
