"""Hybrid Scientific Search Engine.

Combines:
1. Keyword Relevance (Lexical matching via ILIKE / BM25)
2. Semantic Similarity (Cosine similarity in dense 64-dim embedding space)
3. Citation Relevance (Calibrated citation impact log-scaling)

Returns categorized results:
- Relevant Papers
- Leading Researchers
- Dominant Institutions
- Aligned CS Topics
"""
import math
import numpy as np
from typing import Any
from .duckdb import query
from .analytics import search_term
from .semantic_embeddings import generate_embedding, cosine_similarity


def execute_hybrid_search(raw_query: str, limit: int = 10) -> dict[str, Any]:
    q_clean = raw_query.strip()
    if len(q_clean) < 2:
        return {
            "query": raw_query,
            "total_results": 0,
            "papers": [],
            "researchers": [],
            "institutions": [],
            "topics": [],
            "top_matches": []
        }

    q_vec = generate_embedding(q_clean)

    # =========================================================================
    # 1. SEMANTIC & KEYWORD MATCHING ON PAPERS
    # =========================================================================
    # Fetch candidate papers via lexical search and precomputed embedding pool
    candidate_papers = []
    seen_paper_ids = set()

    # (A) Lexical candidates
    try:
        lex_rows = query("""
        SELECT 
            p.publication_id,
            p.title,
            p.year,
            COALESCE(v.name, '') as venue,
            COALESCE(c.citations, 0) as citations,
            1.0 as lexical_score
        FROM publications p
        LEFT JOIN venues v USING(venue_id)
        LEFT JOIN publication_citations c USING(publication_id)
        WHERE p.title ILIKE ? ESCAPE '!'
        ORDER BY c.citations DESC, p.year DESC
        LIMIT 30
        """, (search_term(q_clean),))
        for r in lex_rows:
            candidate_papers.append(r)
            seen_paper_ids.add(r['publication_id'])
    except Exception:
        pass

    # (B) Semantic embedding pool candidates
    try:
        embed_rows = query("""
        SELECT pe.entity_id as publication_id, pe.embedding_vector,
               p.title, p.year, COALESCE(v.name, '') as venue, COALESCE(c.citations, 0) as citations
        FROM paper_embeddings pe
        JOIN publications p ON pe.entity_id = p.publication_id
        LEFT JOIN venues v USING(venue_id)
        LEFT JOIN publication_citations c ON p.publication_id = c.publication_id
        LIMIT 600
        """)
        for r in embed_rows:
            sim = cosine_similarity(q_vec, r['embedding_vector'])
            if sim > 0.38 or r['publication_id'] in seen_paper_ids:
                if r['publication_id'] not in seen_paper_ids:
                    r['lexical_score'] = 0.0
                    candidate_papers.append(r)
                    seen_paper_ids.add(r['publication_id'])
                else:
                    # Update similarity for existing lexical candidate
                    for existing in candidate_papers:
                        if existing['publication_id'] == r['publication_id']:
                            existing['embedding_vector'] = r['embedding_vector']
    except Exception:
        pass

    # Rank and score papers using Hybrid formula
    scored_papers = []
    for p in candidate_papers:
        p_vec = p.get('embedding_vector') or generate_embedding(f"{p['title']} {p.get('venue', '')}")
        sem_sim = float(max(0.0, cosine_similarity(q_vec, p_vec)))
        lex_score = float(p.get('lexical_score', 0.0) or 0.0)
        cits = int(p.get('citations', 0) or 0)
        cit_score = float(min(1.0, math.log1p(cits) / math.log1p(3000)))

        # Hybrid weighting: 35% lexical + 45% semantic + 20% citation
        hybrid_score = round(0.35 * lex_score + 0.45 * sem_sim + 0.20 * cit_score, 3)
        match_type = "exact" if lex_score > 0.8 and sem_sim > 0.6 else ("hybrid" if lex_score > 0 else "semantic")

        scored_papers.append({
            "entity_type": "paper",
            "entity_id": p['publication_id'],
            "title": p['title'],
            "subtitle": f"{p.get('venue') or 'Computer Science'} · {p.get('year', '')}",
            "year": p.get('year'),
            "venue": p.get('venue'),
            "citations": cits,
            "relevance_score": hybrid_score,
            "match_type": match_type,
            "href": f"/papers/{p['publication_id']}"
        })

    scored_papers.sort(key=lambda x: x['relevance_score'], reverse=True)
    top_papers = scored_papers[:limit]

    # =========================================================================
    # 2. TOPIC MATCHING
    # =========================================================================
    scored_topics = []
    try:
        topic_rows = query("""
        SELECT t.topic_id, t.topic_name, t.category, t.publication_count, t.growth_rate,
               te.embedding_vector
        FROM topics t
        LEFT JOIN topic_embeddings te ON t.topic_id = te.entity_id
        """)
        for t in topic_rows:
            t_vec = t.get('embedding_vector') or generate_embedding(f"{t['topic_name']} {t['category']}")
            sem_sim = max(0.0, cosine_similarity(q_vec, t_vec))
            lex_match = 1.0 if q_clean.lower() in t['topic_name'].lower() or t['topic_name'].lower() in q_clean.lower() else 0.0
            score = round(0.40 * lex_match + 0.60 * sem_sim, 3)

            if score > 0.35 or lex_match > 0:
                scored_topics.append({
                    "entity_type": "topic",
                    "entity_id": t['topic_id'],
                    "title": t['topic_name'],
                    "subtitle": f"{t['category']} · {t['publication_count']:,} papers (+{t['growth_rate']}% growth)",
                    "year": None,
                    "venue": None,
                    "citations": None,
                    "relevance_score": score,
                    "match_type": "exact" if lex_match > 0 else "semantic",
                    "href": f"/topics/{t['topic_id']}"
                })
        scored_topics.sort(key=lambda x: x['relevance_score'], reverse=True)
    except Exception:
        pass

    # =========================================================================
    # 3. RESEARCHER MATCHING
    # =========================================================================
    scored_authors = []
    try:
        # Lexical authors
        auth_rows = query("""
        SELECT a.author_id, a.name, ast.publication_count as papers,
               COALESCE(imp.total_citations, 0) as citations,
               COALESCE(m.momentum_score, 0.0) as momentum
        FROM authors a
        JOIN author_stats ast USING(author_id)
        LEFT JOIN author_impact_stats imp USING(author_id)
        LEFT JOIN author_momentum m USING(author_id)
        WHERE a.name ILIKE ? ESCAPE '!'
        ORDER BY ast.publication_count DESC
        LIMIT 10
        """, (search_term(q_clean),))
        for a in auth_rows:
            scored_authors.append({
                "entity_type": "author",
                "entity_id": a['author_id'],
                "title": a['name'],
                "subtitle": f"{a['papers']} papers · {a['citations']:,} citations",
                "year": None,
                "venue": None,
                "citations": a['citations'],
                "relevance_score": 0.95,
                "match_type": "exact",
                "href": f"/authors/{a['author_id']}"
            })

        # If lexical didn't fill limit, match authors by the top semantic topic
        if len(scored_authors) < 5 and scored_topics:
            top_t_id = scored_topics[0]['entity_id']
            semantic_authors = query("""
            SELECT a.author_id, a.name, atp.publication_count as papers,
                   COALESCE(imp.total_citations, 0) as citations
            FROM author_topics atp
            JOIN authors a USING(author_id)
            LEFT JOIN author_impact_stats imp USING(author_id)
            WHERE atp.topic_id = ?
            ORDER BY atp.publication_count DESC
            LIMIT 5
            """, (top_t_id,))
            for sa in semantic_authors:
                if not any(x['entity_id'] == sa['author_id'] for x in scored_authors):
                    scored_authors.append({
                        "entity_type": "author",
                        "entity_id": sa['author_id'],
                        "title": sa['name'],
                        "subtitle": f"{scored_topics[0]['title']} leader · {sa['papers']} papers",
                        "year": None,
                        "venue": None,
                        "citations": sa['citations'],
                        "relevance_score": round(scored_topics[0]['relevance_score'] * 0.9, 3),
                        "match_type": "semantic",
                        "href": f"/authors/{sa['author_id']}"
                    })
    except Exception:
        pass

    # =========================================================================
    # 4. INSTITUTION MATCHING
    # =========================================================================
    scored_insts = []
    try:
        inst_rows = query("""
        SELECT institution_id, name, short_name, country, publication_count
        FROM institutions
        WHERE name ILIKE ? ESCAPE '!' OR short_name ILIKE ? ESCAPE '!'
        ORDER BY publication_count DESC
        LIMIT 5
        """, (search_term(q_clean), search_term(q_clean)))
        for inst in inst_rows:
            scored_insts.append({
                "entity_type": "institution",
                "entity_id": inst['institution_id'],
                "title": inst['name'],
                "subtitle": f"{inst['country']} · {inst['publication_count']:,} papers",
                "year": None,
                "venue": None,
                "citations": None,
                "relevance_score": 0.96,
                "match_type": "exact",
                "href": f"/institutions/{inst['institution_id']}"
            })

        if not scored_insts and scored_topics:
            top_t_id = scored_topics[0]['entity_id']
            domain_insts = query("""
            SELECT i.institution_id, i.name, i.country, it.publication_count as papers
            FROM institution_topics it
            JOIN institutions i USING(institution_id)
            WHERE it.topic_id = ?
            ORDER BY it.publication_count DESC
            LIMIT 4
            """, (top_t_id,))
            for di in domain_insts:
                scored_insts.append({
                    "entity_type": "institution",
                    "entity_id": di['institution_id'],
                    "title": di['name'],
                    "subtitle": f"Top hub in {scored_topics[0]['title']} · {di['papers']:,} papers",
                    "year": None,
                    "venue": None,
                    "citations": None,
                    "relevance_score": round(scored_topics[0]['relevance_score'] * 0.88, 3),
                    "match_type": "semantic",
                    "href": f"/institutions/{di['institution_id']}"
                })
    except Exception:
        pass

    # Combine top matches
    top_matches = []
    if top_papers:
        top_matches.append(top_papers[0])
    if scored_topics:
        top_matches.append(scored_topics[0])
    if scored_authors:
        top_matches.append(scored_authors[0])
    if scored_insts:
        top_matches.append(scored_insts[0])
    if len(top_papers) > 1:
        top_matches.extend(top_papers[1:3])

    return {
        "query": raw_query,
        "total_results": len(top_papers) + len(scored_topics) + len(scored_authors) + len(scored_insts),
        "papers": top_papers,
        "researchers": scored_authors[:6],
        "institutions": scored_insts[:4],
        "topics": scored_topics[:5],
        "top_matches": top_matches
    }

