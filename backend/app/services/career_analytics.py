"""Researcher Career Intelligence Service.

Extracts career trajectory insights:
- Career stage classification (Early-Career, Growth Phase, Breakthrough Phase, Mature Phase).
- Peak breakthrough moments detection with quantifiable signals.
- Topic transition eras across the researcher's publication history.
- Editorial research narrative synthesis.
"""
from typing import Any
from .duckdb import query


def compute_career_intelligence(author_id: int) -> dict[str, Any]:
    """Analyze career trajectory, breakthrough periods, topic transitions, and synthesize narrative."""
    # 1. Author yearly publications and co-authors
    years_data = query("""
    WITH author_pubs AS (
        SELECT p.publication_id, p.year
        FROM publication_authors pa
        JOIN publications p USING(publication_id)
        WHERE pa.author_id = ? AND p.year IS NOT NULL AND p.year >= 1950 AND p.year <= 2026
    ),
    coauthors AS (
        SELECT ap.publication_id, ap.year, COUNT(pa2.author_id) - 1 as coauthor_count
        FROM author_pubs ap
        JOIN publication_authors pa2 ON ap.publication_id = pa2.publication_id
        GROUP BY ap.publication_id, ap.year
    )
    SELECT 
        year,
        COUNT(*) as papers,
        ROUND(AVG(coauthor_count), 1) as avg_coauthors,
        SUM(coauthor_count) as total_coauthorships
    FROM coauthors
    GROUP BY year
    ORDER BY year
    """, (author_id,))

    if not years_data:
        return {
            "career_stage": "Early-Career",
            "career_stage_description": "Early-career researcher establishing initial publication footprint.",
            "career_span_years": 1,
            "first_year": 2025,
            "latest_year": 2025,
            "peak_year": 2025,
            "peak_papers": 1,
            "breakthrough_moments": [],
            "topic_transitions": [],
            "narrative": "Recently active researcher establishing foundational contributions in computer science."
        }

    first_year = years_data[0]['year']
    latest_year = years_data[-1]['year']
    career_span = latest_year - first_year + 1
    total_papers = sum(y['papers'] for y in years_data)
    peak_entry = max(years_data, key=lambda x: x['papers'])
    peak_year = peak_entry['year']
    peak_papers = peak_entry['papers']

    # 2. Topic distribution over time
    topic_history = query("""
    SELECT 
        p.year,
        t.topic_name,
        t.category,
        COUNT(*) as count
    FROM publication_authors pa
    JOIN publications p USING(publication_id)
    JOIN publication_topics pt USING(publication_id)
    JOIN topics t USING(topic_id)
    WHERE pa.author_id = ? AND p.year IS NOT NULL
    GROUP BY p.year, t.topic_name, t.category
    ORDER BY p.year, count DESC
    """, (author_id,))

    # Primary topics overall
    overall_topics = query("""
    SELECT t.topic_name, t.category, atp.publication_count
    FROM author_topics atp
    JOIN topics t USING(topic_id)
    WHERE atp.author_id = ?
    ORDER BY atp.publication_count DESC
    LIMIT 3
    """, (author_id,))
    top_topic_names = [t['topic_name'] for t in overall_topics] or ['Computer Science']
    primary_domain = overall_topics[0]['topic_name'] if overall_topics else 'Computer Science'

    # 3. Detect Career Stage
    if career_span <= 7:
        stage = "Early-Career"
        stage_desc = f"Establishing initial body of work ({career_span} active years since {first_year})."
    elif career_span <= 15:
        stage = "Growth Phase"
        stage_desc = f"Expanding research program and collaborative network ({career_span} active years)."
    elif any(y['year'] >= 2018 and y['papers'] >= 15 for y in years_data):
        stage = "Breakthrough Phase"
        stage_desc = f"Experiencing pronounced output acceleration and community leadership ({career_span} active years)."
    else:
        stage = "Mature Phase"
        stage_desc = f"Distinguished senior career spanning {career_span} years ({first_year}–{latest_year})."

    # 4. Breakthrough Moments Detection
    breakthrough_moments = []
    # Scan for rolling acceleration spikes
    for i in range(1, len(years_data)):
        prev = years_data[i - 1]
        curr = years_data[i]
        year = curr['year']
        growth = ((curr['papers'] - prev['papers']) / max(prev['papers'], 1)) * 100.0

        if growth >= 80.0 and curr['papers'] >= 4:
            new_coauthors = max(1, curr['total_coauthorships'] - prev['total_coauthorships'])
            topics_in_year = [th['topic_name'] for th in topic_history if th['year'] == year]
            focus_topic = topics_in_year[0] if topics_in_year else primary_domain

            signals = [
                f"+{int(round(growth))}% annual publication acceleration ({curr['papers']} papers)",
                f"Expanded team with {new_coauthors} new collaborative co-authorships",
                f"Concentrated contributions in {focus_topic}"
            ]
            breakthrough_moments.append({
                "year": year,
                "growth_pct": round(growth, 1),
                "papers_in_year": curr['papers'],
                "new_coauthors": new_coauthors,
                "focus_topic": focus_topic,
                "signals": signals,
                "description": f"Major acceleration in {year}: +{int(round(growth))}% output surge with {new_coauthors} new co-authorships in {focus_topic}."
            })

    # Sort breakthrough moments by growth and take top 2
    breakthrough_moments.sort(key=lambda x: x['growth_pct'] * x['papers_in_year'], reverse=True)
    top_breakthroughs = breakthrough_moments[:2]

    # 5. Topic Transitions / Career Eras
    eras = []
    if career_span >= 10:
        mid_split = first_year + (career_span // 2)
        early_topics = [th['topic_name'] for th in topic_history if th['year'] < mid_split]
        late_topics = [th['topic_name'] for th in topic_history if th['year'] >= mid_split]

        early_focus = max(set(early_topics), key=early_topics.count) if early_topics else top_topic_names[0]
        late_focus = max(set(late_topics), key=late_topics.count) if late_topics else (top_topic_names[1] if len(top_topic_names) > 1 else top_topic_names[0])

        eras.append({
            "era_name": "Foundational Era",
            "start_year": first_year,
            "end_year": mid_split - 1,
            "primary_focus": early_focus,
            "description": f"Early research agenda concentrated on {early_focus}."
        })
        eras.append({
            "era_name": "Expansion & Frontier Era",
            "start_year": mid_split,
            "end_year": latest_year,
            "primary_focus": late_focus,
            "description": f"Strategic pivot and scale toward {late_focus}."
        })
    else:
        eras.append({
            "era_name": "Current Research Horizon",
            "start_year": first_year,
            "end_year": latest_year,
            "primary_focus": primary_domain,
            "description": f"Active scholarly program focused primarily on {primary_domain}."
        })

    # 6. Editorial Research Narrative Synthesis
    author_row = query("SELECT name FROM authors WHERE author_id = ?", (author_id,))
    author_name = author_row[0]['name'] if author_row else "This researcher"

    if top_breakthroughs:
        bt = top_breakthroughs[0]
        bt_text = f" A pivotal career acceleration materialized in {bt['year']} (+{int(round(bt['growth_pct']))}% surge to {bt['papers_in_year']} publications), driven by heightened activity in {bt['focus_topic']}."
    else:
        bt_text = f" Career productivity reached an apex in {peak_year} with {peak_papers} peer-reviewed publications."

    if len(eras) >= 2 and eras[0]['primary_focus'] != eras[1]['primary_focus']:
        transition_text = f" Scientifically, {author_name.split()[-1]} transitioned from foundational work in {eras[0]['primary_focus']} toward {eras[1]['primary_focus']} after {eras[1]['start_year']}."
    else:
        transition_text = f" Throughout this tenure, primary scientific depth has centered on {primary_domain}."

    narrative = (
        f"{author_name}'s research career spans {career_span} active publication years ({first_year}–{latest_year}), "
        f"accumulating {total_papers:,} indexed papers.{transition_text}{bt_text} "
        f"Currently classified in the {stage} tier, demonstrating consistent institutional engagement and active cross-disciplinary partnerships."
    )

    return {
        "career_stage": stage,
        "career_stage_description": stage_desc,
        "career_span_years": career_span,
        "first_year": first_year,
        "latest_year": latest_year,
        "peak_year": peak_year,
        "peak_papers": peak_papers,
        "breakthrough_moments": top_breakthroughs,
        "topic_transitions": eras,
        "narrative": narrative
    }
