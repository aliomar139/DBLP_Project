"""Agentic / Hybrid RAG service for DBLP using local Ollama (Qwen2.5-Coder-7b).

Translates natural language questions in any phrasing into:
1. Safe read-only DuckDB SQL queries (aggregates, rankings, trends, affiliations, citations).
2. Hybrid semantic + lexical paper title search (Faiss + SQLite FTS5) with exact title boosting.
3. On-demand scientific abstract retrieval (SQLite sidecar cache + OpenAlex / Semantic Scholar).
4. Top-3-CD grounded natural-language markdown answers with interactive source links and provenance.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Literal
from uuid import uuid4
from contextlib import closing
from threading import Timer

import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")

import httpx
from openai import OpenAI

from ..database import get_connection, DB_PATH
from ..schemas.models import (
    AssistantQueryResponse,
    AssistantSource,
    AssistantCalculation,
    AssistantClaim,
)
from .title_retrieval import search_titles, TitleIndexUnavailable
from .abstract_service import get_or_fetch_abstract, get_cached_abstract

logger = logging.getLogger(__name__)

# Primary Online Provider (Groq)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b").strip()

# Offline Local Fallback (Ollama)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1").strip()
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b").strip()
DEFAULT_MODEL = GROQ_MODEL if GROQ_API_KEY else OLLAMA_MODEL

QUERY_TIMEOUT_SECONDS = 12.0
MAX_SQL_ROWS = 40
OLLAMA_OPTIONS = {"num_thread": 8, "num_ctx": 2048, "num_predict": 450}


def _is_all_papers_request(query: str) -> bool:
    """Check if the user specifically requested 'all papers' on a topic/author/field."""
    q = query.strip().lower()
    patterns = [
        r"\b(?:all\s+(?:the\s+)?(?:papers|publications|articles))\b",
        r"\b(?:papers|publications|articles)\s*\((?:all|all\s+papers)\)",
        r"\ball\b.*?\b(?:papers|publications|articles)\b",
        r"\b(?:papers|publications|articles)\b.*?\ball\b",
    ]
    return any(re.search(p, q) for p in patterns)


def _extract_all_papers_topic(query: str) -> str:
    """Extract clean topic/search phrase from an all-papers request."""
    clean = query.strip()
    clean = re.sub(r"\(\s*all(?:\s+papers)?\s*\)", "", clean, flags=re.I)
    clean = re.sub(
        r"^(?:please\s+)?(?:show|list|give\s+me|find|get|display|retrieve|search\s+for)?\s*(?:all\s+(?:the\s+)?)?(?:papers|publications|articles)\s*(?:related\s+to|pertaining\s+to|addressing|discussing|dealing\s+with|on\s+the\s+topic\s+of|concerning|associated\s+with|about|on|for|regarding|in|by)?\s*",
        "",
        clean,
        flags=re.I
    )
    clean = re.sub(r"^(?:related\s+to|pertaining\s+to|addressing|discussing|about|on|for|in|by)\s+", "", clean, flags=re.I)
    return clean.strip("?\"' .")


LEAD_ACTION_WORDS = {
    'predict', 'predicting', 'prediction', 'predictions',
    'detect', 'detecting', 'detection',
    'classify', 'classifying', 'classification',
    'identify', 'identifying', 'identification',
    'evaluate', 'evaluating', 'evaluation',
    'measure', 'measuring', 'measurement',
    'model', 'modeling', 'modelling',
    'analyze', 'analyzing', 'analysis',
    'study', 'studying', 'studies',
    'investigate', 'investigating', 'investigation',
    'forecast', 'forecasting',
}

FTS_MAP_PATH = ROOT / "database" / "indexes" / "dblp-title-v2" / "keyword-map.sqlite"


def _fast_search_titles(query: str, limit: int = 8) -> list[dict[str, Any]]:
    """Ultra-fast lexical title search using SQLite FTS5 sidecar index (<10ms)."""
    if not FTS_MAP_PATH.exists():
        return []
    stop = {
        'what', 'is', 'how', 'does', 'why', 'explain', 'describe', 'a', 'an', 'the',
        'in', 'of', 'for', 'to', 'with', 'about', 'and', 'or', 'can', 'you', 'tell', 'me'
    }
    words = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', query) if len(w) >= 3 and w.lower() not in stop]
    if not words:
        return []

    candidate_pids: list[int] = []
    try:
        import sqlite3
        with sqlite3.connect(str(FTS_MAP_PATH)) as conn_fts:
            expr = " ".join(f"{w}*" for w in words)
            rows = conn_fts.execute(
                "SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT ?",
                (expr, limit)
            ).fetchall()
            candidate_pids = [r[0] for r in rows]

            # If fewer than limit results, expand by dropping lead action verbs or sub-combinations
            if len(candidate_pids) < limit and len(words) > 1:
                sub_words = [w for w in words if w not in LEAD_ACTION_WORDS]
                if sub_words and len(sub_words) < len(words):
                    sub_expr = " ".join(f"{w}*" for w in sub_words)
                    sub_rows = conn_fts.execute(
                        "SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT ?",
                        (sub_expr, limit - len(candidate_pids))
                    ).fetchall()
                    for sr in sub_rows:
                        if sr[0] not in candidate_pids:
                            candidate_pids.append(sr[0])

            if len(candidate_pids) < limit and len(words) > 1:
                for i in range(len(words)):
                    sub = [w for j, w in enumerate(words) if j != i]
                    sub_expr = " ".join(f"{w}*" for w in sub)
                    sub_rows = conn_fts.execute(
                        "SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT ?",
                        (sub_expr, limit - len(candidate_pids))
                    ).fetchall()
                    for sr in sub_rows:
                        if sr[0] not in candidate_pids:
                            candidate_pids.append(sr[0])
                    if len(candidate_pids) >= limit:
                        break
    except Exception as exc:
        logger.debug("Fast FTS5 search error: %s", exc)

    if not candidate_pids:
        return []

    try:
        with closing(get_connection()) as conn:
            placeholders = ",".join(str(p) for p in candidate_pids)
            rows = conn.execute(f"""
                SELECT publication_id, db_key, title, year, type
                FROM publications
                WHERE publication_id IN ({placeholders})
                ORDER BY year DESC NULLS LAST
            """).fetchall()
            return [
                {
                    "publication_id": r[0],
                    "db_key": r[1],
                    "title": r[2],
                    "year": r[3],
                    "type": r[4],
                    "score": 0.95,
                    "matched_by": "fts5_fast_title",
                }
                for r in rows
            ]
    except Exception as exc:
        logger.debug("DuckDB lookup error for FTS5 candidates: %s", exc)
        return []


def _fetch_all_topic_papers(term: str, limit: int = 150) -> list[dict[str, Any]]:
    """Fetch all matching papers for a given topic, author, or keywords from DuckDB + FTS5."""
    if not term or len(term.strip()) < 2:
        return []
    clean_term = term.strip()

    # 1. Match canonical topic in DuckDB
    try:
        with closing(get_connection()) as conn:
            topic_rows = conn.execute("""
                SELECT p.publication_id, p.db_key, p.title, p.year, p.type, COALESCE(v.name, '') as venue_name
                FROM publications p
                JOIN publication_topics pt ON p.publication_id = pt.publication_id
                JOIN topics t ON pt.topic_id = t.topic_id
                LEFT JOIN venues v ON p.venue_id = v.venue_id
                WHERE t.topic_name ILIKE ?
                ORDER BY p.year DESC NULLS LAST, p.publication_id DESC
                LIMIT ?
            """, (f"%{clean_term}%", limit)).fetchall()
            if topic_rows:
                return [
                    {
                        "publication_id": r[0],
                        "db_key": r[1],
                        "title": r[2],
                        "year": r[3],
                        "type": r[4],
                        "venue_name": r[5],
                        "matched_by": "topic"
                    }
                    for r in topic_rows
                ]

            # 2. Match author name (for 'all papers by X')
            author_pattern = f"%{clean_term.replace(' ', '%')}%"
            author_rows = conn.execute("""
                SELECT p.publication_id, p.db_key, p.title, p.year, p.type, COALESCE(v.name, '') as venue_name
                FROM publications p
                JOIN publication_authors pa ON p.publication_id = pa.publication_id
                JOIN authors a ON pa.author_id = a.author_id
                LEFT JOIN venues v ON p.venue_id = v.venue_id
                WHERE a.name ILIKE ?
                ORDER BY p.year DESC NULLS LAST, p.publication_id DESC
                LIMIT ?
            """, (author_pattern, limit)).fetchall()
            if author_rows:
                return [
                    {
                        "publication_id": r[0],
                        "db_key": r[1],
                        "title": r[2],
                        "year": r[3],
                        "type": r[4],
                        "venue_name": r[5],
                        "matched_by": "author"
                    }
                    for r in author_rows
                ]
    except Exception as exc:
        logger.debug("Topic/Author search error: %s", exc)

    # 3. High-precision SQLite FTS5 search (with typo tolerance, verb decomposition and sub-expression expansion)
    stop = {'related', 'to', 'about', 'on', 'for', 'regarding', 'in', 'of', 'the', 'a', 'an', 'with', 'papers', 'paper', 'articles', 'article', 'publications', 'all', 'list', 'show', 'find'}
    raw_tokens = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', clean_term) if len(w) >= 3 and w.lower() not in stop]
    candidate_pids: list[int] = []

    if raw_tokens and FTS_MAP_PATH.exists():
        try:
            import sqlite3
            with sqlite3.connect(str(FTS_MAP_PATH)) as conn_fts:
                fts_expr = " ".join(f"{t}*" for t in raw_tokens)
                rows = conn_fts.execute("SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT ?", (fts_expr, limit)).fetchall()
                candidate_pids = [r[0] for r in rows]

                # Decompose action/lead verbs (e.g. 'predicting student burnout' -> 'student* burnout*')
                if len(candidate_pids) < limit and len(raw_tokens) > 1:
                    sub_tokens = [w for w in raw_tokens if w not in LEAD_ACTION_WORDS]
                    if sub_tokens and len(sub_tokens) < len(raw_tokens):
                        sub_expr = " ".join(f"{t}*" for t in sub_tokens)
                        sub_rows = conn_fts.execute("SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT ?", (sub_expr, limit - len(candidate_pids))).fetchall()
                        for sr in sub_rows:
                            if sr[0] not in candidate_pids:
                                candidate_pids.append(sr[0])

                # Sub-expression fallback if still under limit
                if len(candidate_pids) < limit and len(raw_tokens) > 1:
                    for i in range(len(raw_tokens)):
                        sub_tokens = [t for j, t in enumerate(raw_tokens) if j != i]
                        if not sub_tokens:
                            continue
                        sub_expr = " ".join(f"{t}*" for t in sub_tokens)
                        sub_rows = conn_fts.execute("SELECT rowid FROM titles WHERE titles MATCH ? ORDER BY rank LIMIT ?", (sub_expr, limit - len(candidate_pids))).fetchall()
                        for sr in sub_rows:
                            if sr[0] not in candidate_pids:
                                candidate_pids.append(sr[0])
                        if len(candidate_pids) >= limit:
                            break
        except Exception as exc:
            logger.debug("FTS5 topic search error: %s", exc)

    if candidate_pids:
        try:
            with closing(get_connection()) as db:
                placeholders = ",".join(str(p) for p in candidate_pids)
                db_rows = db.execute(f"""
                    SELECT p.publication_id, p.db_key, p.title, p.year, p.type, COALESCE(v.name, '') as venue_name
                    FROM publications p
                    LEFT JOIN venues v ON p.venue_id = v.venue_id
                    WHERE p.publication_id IN ({placeholders})
                    ORDER BY p.year DESC NULLS LAST
                """).fetchall()
                return [
                    {
                        "publication_id": r[0],
                        "db_key": r[1],
                        "title": r[2],
                        "year": r[3],
                        "type": r[4],
                        "venue_name": r[5],
                        "matched_by": "fts5"
                    }
                    for r in db_rows
                ]
        except Exception as exc:
            logger.debug("DuckDB lookup error for FTS5 topic candidates: %s", exc)

    # 4. DuckDB title ILIKE fallback
    try:
        with closing(get_connection()) as db:
            title_rows = db.execute("""
                SELECT p.publication_id, p.db_key, p.title, p.year, p.type, COALESCE(v.name, '') as venue_name
                FROM publications p
                LEFT JOIN venues v ON p.venue_id = v.venue_id
                WHERE p.title ILIKE ?
                ORDER BY p.year DESC NULLS LAST, p.publication_id DESC
                LIMIT ?
            """, (f"%{clean_term}%", limit)).fetchall()
            return [
                {
                    "publication_id": r[0],
                    "db_key": r[1],
                    "title": r[2],
                    "year": r[3],
                    "type": r[4],
                    "venue_name": r[5],
                    "matched_by": "title"
                }
                for r in title_rows
            ]
    except Exception as exc:
        logger.error("DuckDB title search error for %r: %s", term, exc)
        return []


def _find_exact_title_candidates(query_text: str) -> list[dict[str, Any]]:
    """Boost exact or substring title matches from DuckDB for distinct technical terms."""
    technical_terms = re.findall(r"\b(?:[A-Za-z0-9]+-[A-Za-z0-9]+|[A-Za-z]*[A-Z][a-z]*[A-Z][A-Za-z]*|[A-Z]{2,})\b", query_text)
    term = None
    if technical_terms:
        term = technical_terms[0]
    else:
        clean = re.sub(r"^(?:what is|what are|how does|why is|explain|describe)\s+", "", query_text.strip(), flags=re.I)
        clean = clean.strip("?\"' .")
        # Only boost full phrase or distinct term, NEVER single common words
        if len(clean) >= 4 and len(clean.split()) <= 4:
            term = clean

    if not term:
        return []

    try:
        with closing(get_connection()) as conn:
            pattern = f"%{term}%"
            rows = conn.execute(
                "SELECT publication_id, db_key, title, year, type FROM publications "
                "WHERE title ILIKE ? "
                "ORDER BY (CASE WHEN title ILIKE ? THEN 1 WHEN title ILIKE ? THEN 2 ELSE 3 END), year DESC LIMIT 3",
                (pattern, f"{term}:%", f"% {term} %")
            ).fetchall()
            return [
                {
                    "publication_id": r[0],
                    "db_key": r[1],
                    "title": r[2],
                    "year": r[3],
                    "type": r[4],
                    "score": 1.0,
                    "matched_by": "exact_title_booster"
                }
                for r in rows
            ]
    except Exception as exc:
        logger.debug("Exact title booster error: %s", exc)
        return []


DB_SCHEMA_PROMPT = """
You have direct read-only access to a DuckDB database containing the canonical DBLP computer science bibliography dataset.

### Tables & Columns:
1. `publications` (publication_id BIGINT, db_key VARCHAR, type VARCHAR, title VARCHAR, year INT, venue_id BIGINT)
2. `authors` (author_id BIGINT, name VARCHAR)
3. `publication_authors` (publication_id BIGINT, author_id BIGINT)
4. `venues` (venue_id BIGINT, name VARCHAR)
5. `institutions` (institution_id BIGINT, name VARCHAR, short_name VARCHAR, country VARCHAR, publication_count BIGINT)
6. `author_institutions` (author_id BIGINT, institution_id BIGINT)
7. `publication_citations` (publication_id BIGINT, citations INT, influential_citations INT, citation_velocity DOUBLE)
8. `topics` (topic_id BIGINT, topic_name VARCHAR, category VARCHAR)
9. `publication_topics` (publication_id BIGINT, topic_id BIGINT)

### Relationships:
- authors.author_id <-> publication_authors.author_id
- publications.publication_id <-> publication_authors.publication_id
- publications.venue_id <-> venues.venue_id
- authors.author_id <-> author_institutions.author_id <-> institutions.institution_id
- publications.publication_id <-> publication_citations.publication_id
- publications.publication_id <-> publication_topics.publication_id <-> topics.topic_id

### Query Guidelines:
- Only generate standard DuckDB SELECT queries (never DROP, UPDATE, INSERT, ALTER).
- For matching author or venue names, prefer flexible matching like `a.name ILIKE '%First%Last%'` (or exact name with disambiguation suffixes like `0002`: `a1.name ILIKE '%Hussein Hazimeh 0002%'`).
- When counting publications across author or venue joins, ALWAYS use `COUNT(DISTINCT p.publication_id)` to avoid inflated duplicate counts.
- For coauthors or collaborators of author X, ALWAYS use this exact fast query template:
  SELECT a2.author_id, a2.name, COUNT(DISTINCT pa1.publication_id) AS shared_publications
  FROM authors a1
  JOIN publication_authors pa1 ON a1.author_id = pa1.author_id
  JOIN publication_authors pa2 ON pa1.publication_id = pa2.publication_id
  JOIN authors a2 ON pa2.author_id = a2.author_id
  WHERE a1.name ILIKE '%X%' AND a2.author_id != a1.author_id
  GROUP BY a2.author_id, a2.name
  ORDER BY shared_publications DESC LIMIT 10;
- For rankings and top lists, always include `ORDER BY ... DESC LIMIT 10` (or requested limit, max 30).
- For publication titles or years, always select publication_id, title, and year where possible so the user interface can generate clickable links.
"""

ROUTER_SYSTEM_PROMPT = f"""You are the query planner for a DBLP research assistant.
Analyze the user's question and choose the best retrieval action.

{DB_SCHEMA_PROMPT}

You must respond in ONLY valid JSON with this exact format:
{{
  "action": "sql" | "title_search" | "direct",
  "sql": "SELECT ... LIMIT 20;" (required if action is 'sql', otherwise null),
  "search_query": "concise topic or method" (required if action is 'title_search', otherwise null),
  "thought": "brief 1-sentence rationale"
}}

Rules:
- Choose "sql" for questions about publication counts, author/venue rankings, collaborations, co-authorship, years, trends, institutions, affiliations, citations, or looking up a specific author/venue.
- Choose "title_search" for questions asking about methods, concepts, algorithms, definitions (e.g. "What is CtRL-Sim?", "How does TRaX work?"), or broad paper discovery (e.g., "Find papers about graph neural networks"). For concept/definition queries, extract the concise subject/method name into "search_query".
- Choose "direct" only for simple greetings or general capabilities questions that require no database lookup.
- Output pure JSON only without markdown formatting.
"""

SYNTHESIS_SYSTEM_PROMPT = """You are the DBLP Research Intelligence Assistant.
Your task is to answer the user's question directly, accurately, and concisely based ONLY on the provided evidence.

Guidelines:
- Provide a direct, focused answer in 1-2 clear paragraphs (under 150 words).
- When paper abstracts are provided, explain the requested concepts, methods, or definitions concisely.
- For lists or comparisons, present at most the top 5 key highlights in bullet points.
- Do not invent facts, methods, or findings not present in the evidence.
- Avoid repetitive filler, preamble, or boilerplate.
"""


def _get_groq_client() -> OpenAI | None:
    if not GROQ_API_KEY:
        return None
    return OpenAI(
        base_url=GROQ_BASE_URL,
        api_key=GROQ_API_KEY,
        timeout=httpx.Timeout(8.0, connect=3.5),
    )


def _get_ollama_client() -> OpenAI:
    return OpenAI(
        base_url=OLLAMA_BASE_URL,
        api_key="ollama",
        timeout=httpx.Timeout(60.0, connect=5.0),
    )


def is_local_ollama_ready(model: str = OLLAMA_MODEL) -> bool:
    """Check if the local Ollama instance is running and has the model available."""
    try:
        resp = httpx.get(f"http://localhost:11434/api/tags", timeout=1.0)
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            return any(model in name for name in model_names)
    except Exception:
        pass
    return False


def is_online_llm_ready() -> bool:
    """Check if online Groq credentials are configured."""
    return bool(GROQ_API_KEY)


def is_agentic_rag_ready() -> bool:
    """Ready if either online Groq is configured OR local Ollama is active."""
    return is_online_llm_ready() or is_local_ollama_ready()


def is_ollama_ready(model: str = DEFAULT_MODEL) -> bool:
    """Backward compatibility alias for existing routes and tests."""
    return is_agentic_rag_ready()


def call_rag_llm(
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float = 0.0,
    stream: bool = False,
):
    """
    Unified LLM dispatcher for RAG:
    1. Primary (Online): Groq Cloud (fast inference ~400 t/s).
    2. Fallback (Offline): Local Ollama on CPU if network fails or offline.
    """
    groq_client = _get_groq_client()
    if groq_client:
        try:
            return groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
            )
        except Exception as exc:
            logger.warning(
                "Online LLM provider (%s) unavailable or network failed (%s). Falling back to local Ollama (%s)...",
                GROQ_MODEL, exc, OLLAMA_MODEL,
            )

    ollama_client = _get_ollama_client()
    return ollama_client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
        extra_body={"options": OLLAMA_OPTIONS},
    )


def execute_safe_sql(sql: str) -> tuple[list[dict[str, Any]], str | None]:
    """Execute a read-only DuckDB SQL query safely with timeouts and limits."""
    cleaned = sql.strip().strip(";").strip()
    if (not re.match(r"^(SELECT|WITH)\b", cleaned, re.IGNORECASE)
            or ";" in cleaned
            or re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|COPY|ATTACH|DETACH|CALL|EXPORT|IMPORT|INSTALL|LOAD|PRAGMA|SET|RESET|READ_CSV|READ_CSV_AUTO|READ_JSON|READ_PARQUET|PARQUET_SCAN|GLOB|READ_BLOB|SQLITE_SCAN|POSTGRES_SCAN|HTTPFS)\b", cleaned, re.IGNORECASE)):
        return [], "Only read-only SELECT and WITH statements are permitted."

    cleaned = f"SELECT * FROM ({cleaned}) AS agentic_result LIMIT {MAX_SQL_ROWS}"

    try:
        conn = get_connection()
    except Exception as exc:
        return [], f"Database connection failed: {exc}"

    with closing(conn) as db:
        try:
            db.execute("SET memory_limit='4GB'")
            db.execute("SET threads=4")
        except Exception:
            pass

        timer = Timer(QUERY_TIMEOUT_SECONDS, db.interrupt)
        timer.daemon = True
        timer.start()
        try:
            cur = db.execute(cleaned)
            cols = [desc[0] for desc in cur.description]
            raw_rows = cur.fetchall()
            rows = [dict(zip(cols, row)) for row in raw_rows[:MAX_SQL_ROWS]]
            return rows, None
        except Exception as exc:
            return [], f"Query execution failed: {exc}"
        finally:
            timer.cancel()


def _extract_json(text: str) -> dict[str, Any] | None:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", text.strip(), flags=re.I)
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except Exception:
            pass
    return None


def _extract_sources(rows: list[dict[str, Any]]) -> list[AssistantSource]:
    """Extract recognized entity sources from query rows for dashboard links."""
    sources: list[AssistantSource] = []
    seen = set()

    for row in rows:
        author_id = row.get("author_id") or row.get("authors_author_id")
        author_name = row.get("name") or row.get("author_name") or row.get("authors_name")
        if author_id is not None and author_name and ("author", int(author_id)) not in seen:
            seen.add(("author", int(author_id)))
            sources.append(
                AssistantSource(
                    kind="author",
                    id=int(author_id),
                    title=str(author_name),
                    href=f"/authors/{author_id}",
                    detail="DBLP author profile",
                )
            )

        venue_id = row.get("venue_id") or row.get("venues_venue_id")
        venue_name = row.get("venue_name") or row.get("venues_name") or (row.get("name") if "venue" in str(row) else None)
        if venue_id is not None and venue_name and ("venue", int(venue_id)) not in seen:
            seen.add(("venue", int(venue_id)))
            sources.append(
                AssistantSource(
                    kind="venue",
                    id=int(venue_id),
                    title=str(venue_name),
                    href=f"/venues/{venue_id}",
                    detail="DBLP venue record",
                )
            )

        pub_id = row.get("publication_id") or row.get("publications_publication_id")
        pub_title = row.get("title") or row.get("publication_title")
        if pub_id is not None and pub_title and ("paper", int(pub_id)) not in seen:
            seen.add(("paper", int(pub_id)))
            year = row.get("year")
            detail = f"Published: {year}" if year else "DBLP record"
            sources.append(
                AssistantSource(
                    kind="paper",
                    id=int(pub_id),
                    title=str(pub_title),
                    href=f"/papers/{pub_id}",
                    detail=detail,
                )
            )

        topic_id = row.get("topic_id")
        topic_name = row.get("topic_name")
        if topic_id is not None and topic_name and ("topic", int(topic_id)) not in seen:
            seen.add(("topic", int(topic_id)))
            sources.append(
                AssistantSource(
                    kind="topic",
                    id=int(topic_id),
                    title=str(topic_name),
                    href=f"/topics/{topic_id}",
                    detail="DBLP research topic",
                )
            )

        if len(sources) >= 15:
            break

    return sources


def ask_agentic_rag(query: str, request_id: str | None = None) -> AssistantQueryResponse:
    """Main Agentic RAG workflow: Plan -> Execute (SQL/Vector + Exact Booster) -> Synthesize Answer."""
    req_id = request_id or str(uuid4())

    if not is_agentic_rag_ready():
        return AssistantQueryResponse(
            status="unavailable",
            answer=(
                "Neither online AI service (Groq) nor local AI model (Ollama) is available. "
                "Please connect to the internet or start local Ollama ('ollama run qwen2.5-coder:7b')."
            ),
            request_id=req_id,
            limitation_code="model_unavailable",
        )

    is_all = _is_all_papers_request(query)
    clean_topic = _extract_all_papers_topic(query) if is_all else None

    # Step 1: Query Planning & Candidate Retrieval
    if is_all and clean_topic:
        all_papers = _fetch_all_topic_papers(clean_topic, limit=150)
        # Instant cache lookup (no blocking network calls during chat)
        for item in all_papers:
            cached = get_cached_abstract(db_key=item.get("db_key"), publication_id=item.get("publication_id"))
            if cached:
                item["abstract"] = cached[:900] + "..." if len(cached) > 900 else cached

        evidence_rows = all_papers
        sources = [
            AssistantSource(
                kind="paper",
                id=item["publication_id"],
                title=item["title"],
                href=f"/papers/{item['publication_id']}",
                detail=(
                    f"Year: {item.get('year') or 'N/A'}; Venue: {item.get('venue_name') or 'N/A'}"
                    + ("; Abstract grounded" if "abstract" in item else "")
                ),
                abstract=item.get("abstract"),
            )
            for item in all_papers
        ]
        calculations = [
            AssistantCalculation(
                description=f"All Papers Search for '{clean_topic}'",
                filters={"topic_or_term": clean_topic, "mode": "all_papers"},
                database_version="dblp.duckdb:v2",
                result={"total_matched": len(all_papers), "display_limit": 150},
            )
        ]
        action = "all_papers"
    else:
        concept_match = re.match(r"^(?:what is|what are|explain|describe|how does)\s+(.+?)(?:\s+work|\s+function|\?)?$", query.strip(), re.I)
        if concept_match:
            plan = {"action": "title_search", "search_query": concept_match.group(1).strip("?\"' .")}
        else:
            try:
                plan_resp = call_rag_llm(
                    messages=[
                        {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                        {"role": "user", "content": query},
                    ],
                    temperature=0.0,
                    max_tokens=160,
                )
                plan_text = plan_resp.choices[0].message.content or ""
                plan = _extract_json(plan_text)
                if not plan:
                    sql_match = re.search(r"(?:SELECT|WITH)\s+.+?;?", plan_text, re.IGNORECASE | re.DOTALL)
                    if sql_match:
                        plan = {"action": "sql", "sql": sql_match.group(0).strip()}
                    else:
                        plan = {"action": "title_search", "search_query": query}
            except Exception as exc:
                logger.error("Planning failed: %s", exc)
                plan = {"action": "title_search", "search_query": query}

        action = plan.get("action", "title_search")
        evidence_rows: list[dict[str, Any]] = []
        calculations: list[AssistantCalculation] = []
        sources: list[AssistantSource] = []

        # Step 2: Execution
        if action == "sql" and plan.get("sql"):
            sql_query = plan["sql"].strip()
            rows, err = execute_safe_sql(sql_query)

            # Self-correction attempt if SQL failed
            if err:
                logger.warning("Initial SQL failed (%s), attempting self-correction...", err)
                try:
                    fix_resp = call_rag_llm(
                        messages=[
                            {"role": "system", "content": f"{DB_SCHEMA_PROMPT}\nYou fix failed DuckDB SQL. Return pure SQL only."},
                            {"role": "user", "content": f"The query '{sql_query}' produced error: {err}. Please fix it for question: '{query}'."},
                        ],
                        temperature=0.0,
                        max_tokens=260,
                    )
                    fixed_sql = re.sub(r"```(?:sql)?|```", "", fix_resp.choices[0].message.content or "").strip()
                    rows, err = execute_safe_sql(fixed_sql)
                    if not err:
                        sql_query = fixed_sql
                except Exception:
                    pass

            calculations.append(
                AssistantCalculation(
                    description="DuckDB SQL Execution",
                    filters={"sql": sql_query},
                    database_version="dblp.duckdb:v2",
                    result={"row_count": len(rows), "error": err, "sample": rows[:5] if rows else []},
                )
            )
            if not err and rows:
                evidence_rows = rows
                sources = _extract_sources(rows)
            elif err:
                evidence_rows = [{"error": err}]

        elif action == "title_search":
            search_query = plan.get("search_query") or query
            try:
                exact_boosts = _find_exact_title_candidates(search_query)
                fast_matches = _fast_search_titles(search_query, limit=8)

                seen_ids = set()
                candidate_list: list[dict[str, Any]] = []

                for b in exact_boosts:
                    if b["publication_id"] not in seen_ids:
                        seen_ids.add(b["publication_id"])
                        candidate_list.append(b)

                for m in fast_matches:
                    if m["publication_id"] not in seen_ids:
                        seen_ids.add(m["publication_id"])
                        candidate_list.append(m)

                if len(candidate_list) < 3:
                    raw_matches = search_titles(search_query, limit=8)
                    for m in raw_matches:
                        if m.publication_id not in seen_ids:
                            seen_ids.add(m.publication_id)
                            candidate_list.append({
                                "publication_id": m.publication_id,
                                "db_key": m.db_key,
                                "title": m.title,
                                "year": m.year,
                                "type": m.publication_type,
                                "score": round(m.retrieval_score, 4),
                                "matched_by": "hybrid_search",
                            })

                evidence_rows = candidate_list[:10]

                # Instant cache lookup only (no blocking HTTP requests during chat)
                abstracts_grounded = 0
                for item in evidence_rows[:3]:
                    abs_text = get_cached_abstract(
                        db_key=item.get("db_key", ""),
                        publication_id=item.get("publication_id")
                    )
                    if abs_text:
                        item["abstract"] = abs_text[:900] + "..." if len(abs_text) > 900 else abs_text
                        abstracts_grounded += 1

                calculations.append(
                    AssistantCalculation(
                        description="Hybrid Vector (MiniLM) + Lexical (SQLite FTS5) Title Search with Abstract Grounding",
                        filters={"search_query": search_query},
                        database_version="dblp-title-v2",
                        result={"candidates_matched": len(evidence_rows), "abstracts_grounded": abstracts_grounded},
                    )
                )
                sources = [
                    AssistantSource(
                        kind="paper",
                        id=item["publication_id"],
                        title=item["title"],
                        href=f"/papers/{item['publication_id']}",
                        detail=(
                            f"Year: {item.get('year') or 'N/A'}; Abstract grounded"
                            if "abstract" in item
                            else f"Year: {item.get('year') or 'N/A'}"
                        ),
                        abstract=item.get("abstract"),
                    )
                    for item in evidence_rows
                ]
            except TitleIndexUnavailable as exc:
                evidence_rows = [{"error": f"Title search index temporarily unavailable: {exc}"}]

    # Step 3: Synthesis (Format Top-3-CD concatenated documents if abstracts present)
    if is_all:
        intro_text = (
            f"Retrieved **{len(evidence_rows)}** publications matching **{clean_topic}** from DBLP.\n\n"
            "All matching papers are displayed below with publication years, venues, and bibliographic links. "
            "You can also download the complete catalog with scientific abstracts as an Excel (.xlsx) file.\n\n"
            "**Research Overview:**\n"
        )
        synthesis_payload = {
            "topic": clean_topic,
            "sample_titles": [r.get("title") for r in evidence_rows[:5]],
            "instruction": "Write a concise 2-sentence summary of the research focus based on these titles. Do not list papers individually."
        }
        ask_tokens = 45
    else:
        intro_text = ""
        has_abstracts = any("abstract" in r for r in evidence_rows[:3])
        if has_abstracts:
            context_docs = []
            for i, r in enumerate(evidence_rows[:3], 1):
                if "abstract" in r:
                    context_docs.append(f"Document {i} ({r.get('title', 'Paper')}): {r['abstract']}")
                else:
                    context_docs.append(f"Document {i}: {r.get('title', '')} ({r.get('year', '')})")
            synthesis_payload = {
                "user_question": query,
                "retrieved_abstract_documents": context_docs,
                "bibliographic_metadata": evidence_rows[:6],
            }
        else:
            synthesis_payload = {
                "user_question": query,
                "retrieved_evidence": evidence_rows[:8],
            }
        ask_tokens = 250 if GROQ_API_KEY else 110

    try:
        synth_resp = call_rag_llm(
            messages=[
                {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(synthesis_payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=ask_tokens,
        )
        answer_text = intro_text + (synth_resp.choices[0].message.content or "No response could be generated.")
    except Exception as exc:
        logger.error("Synthesis failed: %s", exc)
        answer_text = f"Retrieved {len(evidence_rows)} records from DBLP database, but answer synthesis encountered an error: {exc}"

    status: Literal["answered", "not_found", "insufficient_evidence"] = (
        "answered" if action == "direct" or (evidence_rows and not ("error" in evidence_rows[0])) else "not_found"
    )

    return AssistantQueryResponse(
        status=status,
        answer=answer_text,
        request_id=req_id,
        sources=sources,
        calculations=calculations,
        is_all_papers=is_all,
        export_query=clean_topic if is_all else None,
    )


def stream_agentic_rag(query: str, request_id: str | None = None):
    """Yield SSE formatted events as the model synthesizes the response in real-time."""
    req_id = request_id or str(uuid4())

    if not is_agentic_rag_ready():
        yield f"data: {json.dumps({'type': 'error', 'message': 'Neither online LLM nor local Ollama is available.'})}\n\n"
        return

    is_all = _is_all_papers_request(query)
    clean_topic = _extract_all_papers_topic(query) if is_all else None

    if is_all and clean_topic:
        yield f"data: {json.dumps({'type': 'status', 'message': f'Retrieving all matching papers for "{clean_topic}" from DBLP database...'})}\n\n"
        all_papers = _fetch_all_topic_papers(clean_topic, limit=150)
        # Instant cache lookup (no blocking network calls during chat)
        for item in all_papers:
            cached = get_cached_abstract(db_key=item.get("db_key"), publication_id=item.get("publication_id"))
            if cached:
                item["abstract"] = cached[:900] + "..." if len(cached) > 900 else cached

        evidence_rows = all_papers
        sources = [
            AssistantSource(
                kind="paper",
                id=item["publication_id"],
                title=item["title"],
                href=f"/papers/{item['publication_id']}",
                detail=(
                    f"Year: {item.get('year') or 'N/A'}; Venue: {item.get('venue_name') or 'N/A'}"
                    + ("; Abstract grounded" if "abstract" in item else "")
                ),
                abstract=item.get("abstract"),
            )
            for item in all_papers
        ]
        calculations = [
            AssistantCalculation(
                description=f"All Papers Search for '{clean_topic}'",
                filters={"topic_or_term": clean_topic, "mode": "all_papers"},
                database_version="dblp.duckdb:v2",
                result={"total_matched": len(all_papers), "display_limit": 150},
            )
        ]
        action = "all_papers"
    else:
        concept_match = re.match(r"^(?:what is|what are|explain|describe|how does)\s+(.+?)(?:\s+work|\s+function|\?)?$", query.strip(), re.I)
        if concept_match:
            plan = {"action": "title_search", "search_query": concept_match.group(1).strip("?\"' .")}
        else:
            yield f"data: {json.dumps({'type': 'status', 'message': 'Analyzing question...'})}\n\n"
            try:
                plan_resp = call_rag_llm(
                    messages=[
                        {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
                        {"role": "user", "content": query},
                    ],
                    temperature=0.0,
                    max_tokens=160,
                )
                plan_text = plan_resp.choices[0].message.content or ""
                plan = _extract_json(plan_text)
                if not plan:
                    sql_match = re.search(r"(?:SELECT|WITH)\s+.+?;?", plan_text, re.IGNORECASE | re.DOTALL)
                    if sql_match:
                        plan = {"action": "sql", "sql": sql_match.group(0).strip()}
                    else:
                        plan = {"action": "title_search", "search_query": query}
            except Exception as exc:
                logger.error("Planning failed: %s", exc)
                plan = {"action": "title_search", "search_query": query}

        action = plan.get("action", "title_search")
        evidence_rows = []
        calculations = []
        sources = []

        yield f"data: {json.dumps({'type': 'status', 'message': 'Running database search...'})}\n\n"

        # Step 2: Execution
        if action == "sql" and plan.get("sql"):
            sql_query = plan["sql"].strip()
            rows, err = execute_safe_sql(sql_query)

            # Self-correction attempt if SQL failed
            if err:
                logger.warning("Initial SQL failed (%s), attempting self-correction...", err)
                try:
                    fix_resp = call_rag_llm(
                        messages=[
                            {"role": "system", "content": f"{DB_SCHEMA_PROMPT}\nYou fix failed DuckDB SQL. Return pure SQL only."},
                            {"role": "user", "content": f"The query '{sql_query}' produced error: {err}. Please fix it for question: '{query}'."},
                        ],
                        temperature=0.0,
                        max_tokens=260,
                    )
                    fixed_sql = re.sub(r"```(?:sql)?|```", "", fix_resp.choices[0].message.content or "").strip()
                    rows, err = execute_safe_sql(fixed_sql)
                    if not err:
                        sql_query = fixed_sql
                except Exception:
                    pass

            calculations.append(
                AssistantCalculation(
                    description="DuckDB SQL Execution",
                    filters={"sql": sql_query},
                    database_version="dblp.duckdb:v2",
                    result={"row_count": len(rows), "error": err, "sample": rows[:5] if rows else []},
                )
            )
            if not err and rows:
                evidence_rows = rows
                sources = _extract_sources(rows)
            elif err:
                evidence_rows = [{"error": err}]

        elif action == "title_search":
            search_query = plan.get("search_query") or query
            try:
                exact_boosts = _find_exact_title_candidates(search_query)
                fast_matches = _fast_search_titles(search_query, limit=8)

                seen_ids = set()
                candidate_list: list[dict[str, Any]] = []

                for b in exact_boosts:
                    if b["publication_id"] not in seen_ids:
                        seen_ids.add(b["publication_id"])
                        candidate_list.append(b)

                for m in fast_matches:
                    if m["publication_id"] not in seen_ids:
                        seen_ids.add(m["publication_id"])
                        candidate_list.append(m)

                if len(candidate_list) < 3:
                    raw_matches = search_titles(search_query, limit=8)
                    for m in raw_matches:
                        if m.publication_id not in seen_ids:
                            seen_ids.add(m.publication_id)
                            candidate_list.append({
                                "publication_id": m.publication_id,
                                "db_key": m.db_key,
                                "title": m.title,
                                "year": m.year,
                                "type": m.publication_type,
                                "score": round(m.retrieval_score, 4),
                                "matched_by": "hybrid_search",
                            })

                evidence_rows = candidate_list[:10]

                # Instant cache lookup only (no blocking HTTP requests during chat)
                abstracts_grounded = 0
                for item in evidence_rows[:3]:
                    abs_text = get_cached_abstract(
                        db_key=item.get("db_key", ""),
                        publication_id=item.get("publication_id")
                    )
                    if abs_text:
                        item["abstract"] = abs_text[:900] + "..." if len(abs_text) > 900 else abs_text
                        abstracts_grounded += 1

                calculations.append(
                    AssistantCalculation(
                        description="Hybrid Vector (MiniLM) + Lexical (SQLite FTS5) Title Search with Abstract Grounding",
                        filters={"search_query": search_query},
                        database_version="dblp-title-v2",
                        result={"candidates_matched": len(evidence_rows), "abstracts_grounded": abstracts_grounded},
                    )
                )
                sources = [
                    AssistantSource(
                        kind="paper",
                        id=item["publication_id"],
                        title=item["title"],
                        href=f"/papers/{item['publication_id']}",
                        detail=(
                            f"Year: {item.get('year') or 'N/A'}; Abstract grounded"
                            if "abstract" in item
                            else f"Year: {item.get('year') or 'N/A'}"
                        ),
                        abstract=item.get("abstract"),
                    )
                    for item in evidence_rows
                ]
            except TitleIndexUnavailable as exc:
                evidence_rows = [{"error": f"Title search index temporarily unavailable: {exc}"}]

    status: Literal["answered", "not_found", "insufficient_evidence"] = (
        "answered" if action == "direct" or (evidence_rows and not ("error" in evidence_rows[0])) else "not_found"
    )

    # Yield initial metadata event (so UI immediately displays sources & query badges)
    init_data = {
        "type": "init",
        "request_id": req_id,
        "status": status,
        "sources": [s.model_dump() for s in sources],
        "calculations": [c.model_dump() for c in calculations],
        "is_all_papers": is_all,
        "export_query": clean_topic if is_all else None,
    }
    yield f"data: {json.dumps(init_data)}\n\n"

    # Step 3: Stream synthesis tokens
    if is_all:
        intro_text = (
            f"Retrieved **{len(evidence_rows)}** publications matching **{clean_topic}** from DBLP.\n\n"
            "All matching papers are displayed below with publication years, venues, and bibliographic links. "
            "You can also download the complete catalog with scientific abstracts as an Excel (.xlsx) file.\n\n"
            "**Research Overview:**\n"
        )
        yield f"data: {json.dumps({'type': 'token', 'token': intro_text})}\n\n"

        synthesis_payload = {
            "topic": clean_topic,
            "sample_titles": [r.get("title") for r in evidence_rows[:5]],
            "instruction": "Write a concise 2-sentence summary of the research focus based on these titles. Do not list papers individually."
        }
        stream_tokens = 45
    else:
        has_abstracts = any("abstract" in r for r in evidence_rows[:3])
        if has_abstracts:
            context_docs = []
            for i, r in enumerate(evidence_rows[:3], 1):
                if "abstract" in r:
                    context_docs.append(f"Document {i} ({r.get('title', 'Paper')}): {r['abstract']}")
                else:
                    context_docs.append(f"Document {i}: {r.get('title', '')} ({r.get('year', '')})")
            synthesis_payload = {
                "user_question": query,
                "retrieved_abstract_documents": context_docs,
                "bibliographic_metadata": evidence_rows[:6],
            }
        else:
            synthesis_payload = {
                "user_question": query,
                "retrieved_evidence": evidence_rows[:8],
            }
        stream_tokens = 300 if GROQ_API_KEY else 110

    try:
        stream = call_rag_llm(
            messages=[
                {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(synthesis_payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=stream_tokens,
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            if content:
                yield f"data: {json.dumps({'type': 'token', 'token': content})}\n\n"
    except Exception as exc:
        logger.error("Streaming synthesis error: %s", exc)
        yield f"data: {json.dumps({'type': 'token', 'token': f' [Error generating complete answer: {exc}]'})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
