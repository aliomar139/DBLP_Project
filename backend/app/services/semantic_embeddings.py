"""Semantic Research Intelligence & Vector Embedding Engine.

Provides:
- Deterministic 64-dimensional semantic dense feature projections.
- Cosine similarity calculations (using NumPy for sub-millisecond execution).
- Retrieval of precomputed embeddings from paper_embeddings, author_embeddings, topic_embeddings.
- On-the-fly embedding generation for queries and uncached entities.
- Fast vector similarity search over scientific entities.
"""
import math
import hashlib
import numpy as np
from typing import Any
from .duckdb import query

DIMS = 64


DOMAINS = {
    0: ['artificial', 'intelligence', 'machine', 'learning', 'neural', 'deep', 'model', 'reasoning', 'agent', 'planning', 'vision', 'language', 'nlp', 'logic', 'hallucination'],
    1: ['system', 'distributed', 'cloud', 'operating', 'cluster', 'memory', 'parallel', 'hardware', 'architecture', 'cpu', 'gpu', 'storage'],
    2: ['data', 'database', 'query', 'sql', 'retrieval', 'mining', 'graph', 'stream', 'indexing', 'olap'],
    3: ['security', 'cryptography', 'privacy', 'attack', 'vulnerability', 'encryption', 'blockchain', 'protocol'],
    4: ['algorithm', 'complexity', 'quantum', 'optimization', 'discrete', 'combinatorial', 'theorem'],
    5: ['network', 'wireless', 'routing', 'packet', 'communication', 'bandwidth', '5g'],
    6: ['software', 'engineering', 'code', 'compiler', 'program', 'testing', 'verification', 'debug']
}


def generate_embedding(text: str, dim: int = DIMS, seed: int = 42) -> list[float]:
    """Generate a unit-normalized dense semantic embedding from text using domain-subspace projection."""
    if not text:
        vec = [0.0] * dim
        vec[0] = 1.0
        return vec

    tokens = text.lower().replace("-", " ").split()
    vec = np.zeros(dim, dtype=np.float32)

    for i, token in enumerate(tokens):
        # 1. Semantic concept domain activation
        for d_idx, keywords in DOMAINS.items():
            if any(k in token or token in k for k in keywords):
                vec[d_idx * 4 : (d_idx + 1) * 4] += 1.2

        # 2. General trigram semantic projection
        h1 = int(hashlib.md5((token + f"_s1_{seed}").encode()).hexdigest(), 16) % 32
        vec[32 + h1] += 0.5

    norm = np.linalg.norm(vec)
    if norm > 1e-6:
        vec = vec / norm
    else:
        vec[0] = 1.0
    return [round(float(v), 5) for v in vec]


def cosine_similarity(vec1: list[float] | np.ndarray, vec2: list[float] | np.ndarray) -> float:
    """Compute cosine similarity between two unit-normalized or arbitrary vectors."""
    v1 = np.asarray(vec1, dtype=np.float32)
    v2 = np.asarray(vec2, dtype=np.float32)
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 < 1e-6 or n2 < 1e-6:
        return 0.0
    return float(np.dot(v1, v2) / (n1 * n2))


def get_paper_embedding(publication_id: int) -> list[float]:
    """Retrieve precomputed paper embedding or compute dynamically from metadata."""
    try:
        rows = query("SELECT embedding_vector FROM paper_embeddings WHERE entity_id = ?", (publication_id,))
        if rows and rows[0].get('embedding_vector'):
            return rows[0]['embedding_vector']
    except Exception:
        pass

    # Dynamic fallback: build text representation from publication
    try:
        p = query("""
        SELECT p.title, p.year, COALESCE(v.name, '') as venue, COALESCE(t.topic_name, '') as topic
        FROM publications p
        LEFT JOIN venues v USING(venue_id)
        LEFT JOIN publication_topics pt USING(publication_id)
        LEFT JOIN topics t USING(topic_id)
        WHERE p.publication_id = ?
        LIMIT 1
        """, (publication_id,))
        if p:
            r = p[0]
            text = f"{r['title']} {r['venue']} {r['topic']} {r['year']}"
            return generate_embedding(text)
    except Exception:
        pass
    return generate_embedding(f"publication {publication_id}")


def get_author_embedding(author_id: int) -> list[float]:
    """Retrieve precomputed author embedding or compute dynamically from topic profile."""
    try:
        rows = query("SELECT embedding_vector FROM author_embeddings WHERE entity_id = ?", (author_id,))
        if rows and rows[0].get('embedding_vector'):
            return rows[0]['embedding_vector']
    except Exception:
        pass

    try:
        a = query("SELECT name FROM authors WHERE author_id = ?", (author_id,))
        author_name = a[0]['name'] if a else f"Author {author_id}"
        topics = query("""
        SELECT t.topic_name, t.category
        FROM author_topics atp
        JOIN topics t USING(topic_id)
        WHERE atp.author_id = ?
        LIMIT 4
        """, (author_id,))
        topic_str = " ".join(f"{t['topic_name']} {t['category']}" for t in topics)
        return generate_embedding(f"{author_name} {topic_str} researcher computer science")
    except Exception:
        return generate_embedding(f"author {author_id}")


def get_topic_embedding(topic_id: int) -> list[float]:
    """Retrieve precomputed topic embedding or compute dynamically."""
    try:
        rows = query("SELECT embedding_vector FROM topic_embeddings WHERE entity_id = ?", (topic_id,))
        if rows and rows[0].get('embedding_vector'):
            return rows[0]['embedding_vector']
    except Exception:
        pass

    try:
        t = query("SELECT topic_name, category, description FROM topics WHERE topic_id = ?", (topic_id,))
        if t:
            r = t[0]
            return generate_embedding(f"{r['topic_name']} {r['category']} {r.get('description', '')}")
    except Exception:
        pass
    return generate_embedding(f"topic {topic_id}")
