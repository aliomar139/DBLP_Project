"""Build author_momentum table in DuckDB."""
import time
from pathlib import Path
import duckdb

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "dblp.duckdb"

def build_momentum():
    t0 = time.time()
    print("Connecting to DuckDB...")
    con = duckdb.connect(str(DB_PATH))
    con.execute("DROP TABLE IF EXISTS author_momentum")
    print("Computing Research Momentum Scores...")
    con.execute("""
    CREATE TABLE author_momentum AS
    WITH period_counts AS (
        SELECT 
            pa.author_id,
            COUNT(*) FILTER (WHERE p.year < 2016) as hist_pubs,
            COUNT(*) FILTER (WHERE p.year BETWEEN 2016 AND 2025) as rec_pubs,
            MIN(p.year) as first_year,
            MAX(p.year) as last_year
        FROM publication_authors pa
        JOIN publications p USING(publication_id)
        WHERE p.year IS NOT NULL
        GROUP BY pa.author_id
        HAVING COUNT(*) FILTER (WHERE p.year BETWEEN 2016 AND 2025) >= 8
    ),
    recent_collabs AS (
        SELECT 
            pa.author_id,
            COUNT(DISTINCT pa2.author_id) as recent_collaborators
        FROM publication_authors pa
        JOIN publications p USING(publication_id)
        JOIN publication_authors pa2 USING(publication_id)
        WHERE p.year BETWEEN 2016 AND 2025 AND pa.author_id <> pa2.author_id
        GROUP BY pa.author_id
    ),
    author_top_topic AS (
        SELECT 
            atp.author_id,
            t.topic_name,
            ROW_NUMBER() OVER (PARTITION BY atp.author_id ORDER BY atp.publication_count DESC) as rn
        FROM author_topics atp
        JOIN topics t USING(topic_id)
    ),
    scored AS (
        SELECT 
            c.author_id,
            a.name,
            c.hist_pubs,
            c.rec_pubs,
            ROUND(100.0 * (c.rec_pubs - c.hist_pubs) / NULLIF(c.hist_pubs, 0), 1) as raw_growth_rate,
            ROUND(100.0 * (c.rec_pubs - c.hist_pubs) / (c.hist_pubs + 8.0), 1) as damped_growth_rate,
            COALESCE(rc.recent_collaborators, 0) as recent_collaborators,
            (c.last_year - c.first_year + 1) as career_span,
            CASE 
                WHEN (c.last_year - c.first_year + 1) <= 7 THEN 'Early-Career'
                WHEN (c.last_year - c.first_year + 1) <= 15 THEN 'Mid-Career'
                ELSE 'Senior'
            END as career_stage,
            COALESCE(att.topic_name, 'Computer Science') as primary_topic,
            ROUND(
                GREATEST(0.0, (100.0 * (c.rec_pubs - c.hist_pubs) / (c.hist_pubs + 8.0)))
                * ln(c.rec_pubs + 1.0)
                * (CASE 
                    WHEN (c.last_year - c.first_year + 1) <= 7 THEN 1.35
                    WHEN (c.last_year - c.first_year + 1) <= 15 THEN 1.15
                    ELSE 1.0
                   END)
                * (1.0 + LEAST(0.4, 0.02 * COALESCE(rc.recent_collaborators, 0))),
                1
            ) as momentum_score
        FROM period_counts c
        JOIN authors a USING(author_id)
        LEFT JOIN recent_collabs rc USING(author_id)
        LEFT JOIN author_top_topic att ON att.author_id = c.author_id AND att.rn = 1
    ),
    ranked AS (
        SELECT 
            *,
            ROW_NUMBER() OVER (ORDER BY momentum_score DESC, rec_pubs DESC) as momentum_rank
        FROM scored
        WHERE damped_growth_rate > 0
    )
    SELECT 
        author_id,
        name,
        momentum_rank,
        momentum_score,
        damped_growth_rate,
        raw_growth_rate,
        rec_pubs as recent_publications,
        hist_pubs as historical_publications,
        recent_collaborators,
        career_stage,
        career_span,
        primary_topic,
        'Ranked #' || momentum_rank || ' with Momentum Score ' || momentum_score || ': +' || 
        CAST(damped_growth_rate AS VARCHAR) || '% acceleration, ' || 
        rec_pubs || ' papers published (2016–2025), ' || 
        recent_collaborators || ' active co-authors, ' || 
        career_stage || ' researcher active in ' || primary_topic || '.' as explanation
    FROM ranked
    """)

    count = con.execute("SELECT COUNT(*) FROM author_momentum").fetchone()[0]
    sample = con.execute("SELECT author_id, name, momentum_rank, momentum_score, primary_topic, explanation FROM author_momentum LIMIT 3").fetchall()
    print(f"Indexed {count:,} researchers in author_momentum ({time.time()-t0:.1f}s)")
    for s in sample:
        print(" ", s)
    con.close()

if __name__ == "__main__":
    build_momentum()

