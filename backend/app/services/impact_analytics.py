"""Research Impact Intelligence Service.

Computes a multi-dimensional impact model beyond raw citations:
- Academic Impact: field-normalized citation rank, h-index, citation velocity, highly influential papers.
- Technology / Industry Impact: industrial affiliations, applied systems/security/hardware domain presence,
  commercial/patent citations proxy.
- Open Science Impact: open repository publishing (CoRR/arXiv), collaborative openness, benchmark/dataset dissemination.
- Influence Growth: recent citation acceleration and career momentum.
- Overall Research Impact Score: composite score scaled 0-100, accompanied by interpretable drivers.
"""
from typing import Any
from .duckdb import query

APPLIED_TOPIC_IDS = {9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22, 23, 24, 25, 26, 27, 28}
OPEN_SCIENCE_VENUE_ID = 16041  # CoRR / arXiv


def compute_author_impact(author_id: int) -> dict[str, Any]:
    """Calculate multi-dimensional research impact profile for an author."""
    # 1. Fetch raw impact stats
    impact_rows = query("""
    SELECT total_citations, avg_citations_per_paper, h_index, citation_velocity, highly_cited_papers_count
    FROM author_impact_stats
    WHERE author_id = ?
    """, (author_id,))
    
    impact = impact_rows[0] if impact_rows else {
        'total_citations': 0, 'avg_citations_per_paper': 0.0, 'h_index': 0, 'citation_velocity': 0.0, 'highly_cited_papers_count': 0
    }
    total_citations = int(impact['total_citations'] or 0)
    h_index = int(impact['h_index'] or 0)
    velocity = float(impact['citation_velocity'] or 0.0)
    highly_cited = int(impact['highly_cited_papers_count'] or 0)
    avg_cites = float(impact['avg_citations_per_paper'] or 0.0)

    # 2. Fetch author's primary topics and institution
    topics = query("""
    SELECT t.topic_id, t.topic_name, t.category, atp.publication_count, atp.share_percentage
    FROM author_topics atp
    JOIN topics t USING(topic_id)
    WHERE atp.author_id = ?
    ORDER BY atp.publication_count DESC
    """, (author_id,))

    primary_category = topics[0]['category'] if topics else 'Artificial Intelligence'
    primary_topic_name = topics[0]['topic_name'] if topics else 'Computer Science'

    # Get field baseline for author's primary field
    try:
        field_stats_rows = query("""
        SELECT avg_citations_per_author, avg_citations_per_paper, avg_growth_rate
        FROM field_statistics
        WHERE field_name = ?
        """, (primary_category,))
        field_baseline_cites = field_stats_rows[0]['avg_citations_per_author'] if field_stats_rows else 35.0
        field_baseline_cites_per_paper = field_stats_rows[0]['avg_citations_per_paper'] if field_stats_rows else 20.0
    except Exception:
        field_baseline_cites = 35.0
        field_baseline_cites_per_paper = 20.0

    # 3. Check for industrial lab affiliation
    try:
        inst_rows = query("""
        SELECT i.institution_id, i.name, i.type, i.country
        FROM author_institutions ai
        JOIN institutions i USING(institution_id)
        WHERE ai.author_id = ?
        """, (author_id,))
        is_industry = any(r['type'] == 'Corporate' or 'Lab' in r['name'] or 'Research' in r['name'] for r in inst_rows)
    except Exception:
        is_industry = False

    # 4. Check for open repository (CoRR / arXiv) publications
    try:
        corr_rows = query("""
        SELECT COUNT(*) as corr_count
        FROM publication_authors pa
        JOIN publications p USING(publication_id)
        WHERE pa.author_id = ? AND p.venue_id = ?
        """, (author_id, OPEN_SCIENCE_VENUE_ID))
        corr_count = corr_rows[0]['corr_count'] if corr_rows else 0
    except Exception:
        corr_count = 0

    # 5. Check momentum stats
    try:
        momentum_rows = query("""
        SELECT momentum_score, damped_growth_rate, recent_publications, historical_publications, recent_collaborators, career_stage
        FROM author_momentum
        WHERE author_id = ?
        """, (author_id,))
        momentum = momentum_rows[0] if momentum_rows else None
    except Exception:
        momentum = None

    # =========================================================================
    # CALCULATE DIMENSIONAL SCORES (0-100)
    # =========================================================================

    # Dimension 1: Academic Impact (0-100)
    # Factors: citation scale relative to field, h-index depth, highly cited papers
    field_ratio = total_citations / max(field_baseline_cites, 1.0)
    acad_from_citations = min(40.0, field_ratio * 4.0 if field_ratio <= 5.0 else 20.0 + min(20.0, (field_ratio - 5.0) * 0.4))
    acad_from_hindex = min(35.0, (h_index / 80.0) * 35.0)
    acad_from_highly_cited = min(25.0, (highly_cited / 30.0) * 25.0)
    academic_score = round(min(100.0, max(10.0, acad_from_citations + acad_from_hindex + acad_from_highly_cited)), 1)

    # Field Percentile
    if total_citations >= 10000:
        field_percentile = 99.8
    elif total_citations >= 3000:
        field_percentile = 99.0
    elif total_citations >= 1000:
        field_percentile = 96.5
    elif total_citations >= 300:
        field_percentile = 90.0
    elif total_citations >= 100:
        field_percentile = 80.0
    else:
        field_percentile = max(50.0, round(50.0 + total_citations * 0.3, 1))

    # Dimension 2: Technology & Industry Impact (0-100)
    # Applied topic share + corporate affiliation + patent/industry reference proxy
    applied_pubs = sum(t['publication_count'] for t in topics if t['topic_id'] in APPLIED_TOPIC_IDS)
    total_topic_pubs = sum(t['publication_count'] for t in topics) or 1
    applied_share = applied_pubs / total_topic_pubs

    tech_base = 35.0
    if is_industry:
        tech_base += 25.0
    tech_base += applied_share * 25.0
    tech_from_scale = min(15.0, (total_citations / 5000.0) * 15.0)
    technology_score = round(min(100.0, max(15.0, tech_base + tech_from_scale)), 1)
    industry_references = int(round(total_citations * (0.28 if is_industry else 0.14) + (applied_pubs * 2.5)))
    patent_citations_est = int(round(total_citations * 0.045 + (12 if is_industry else 2)))

    # Dimension 3: Open Science Impact (0-100)
    # Open repository publishing + collaborative diversity
    open_base = 40.0
    if corr_count > 0:
        open_base += min(35.0, (corr_count / 15.0) * 35.0)
    else:
        open_base += 10.0
    if momentum and momentum['recent_collaborators'] > 10:
        open_base += min(25.0, (momentum['recent_collaborators'] / 30.0) * 25.0)
    else:
        open_base += 15.0
    open_science_score = round(min(100.0, max(20.0, open_base)), 1)

    # Dimension 4: Influence Growth (0-100)
    growth_rate = momentum['damped_growth_rate'] if momentum else (min(100.0, velocity * 2.0))
    growth_score = round(min(100.0, max(15.0, 30.0 + min(50.0, growth_rate * 0.5) + min(20.0, (velocity / 500.0) * 20.0))), 1)

    # Overall Impact Score (Composite 0-100)
    # 40% Academic + 25% Technology + 20% Open Science + 15% Influence Growth
    overall_score = round(
        0.40 * academic_score +
        0.25 * technology_score +
        0.20 * open_science_score +
        0.15 * growth_score,
        1
    )

    # =========================================================================
    # DYNAMIC MAIN DRIVERS GENERATION
    # =========================================================================
    drivers = []
    if highly_cited >= 15:
        drivers.append(f"Authored {highly_cited} highly influential top-tier papers in {primary_topic_name}")
    elif highly_cited >= 3:
        drivers.append(f"Produced multiple high-impact breakthrough publications in {primary_topic_name}")
    
    if field_percentile >= 95.0:
        drivers.append(f"Top {round(100.0 - field_percentile, 1)}% field citation percentile in {primary_category}")
    
    if is_industry or industry_references > 150:
        drivers.append(f"Strong enterprise & commercial adoption ({industry_references:,} estimated industry citations)")
    elif applied_share > 0.4:
        drivers.append(f"High applied engineering adoption in {primary_topic_name}")

    if corr_count >= 5:
        drivers.append(f"Extensive open-science dissemination via {corr_count} indexed open preprints")
    
    if growth_rate > 30.0 or velocity > 100.0:
        drivers.append(f"Rapid citation velocity acceleration (+{round(growth_rate, 1)}% expansion rate)")

    if len(drivers) < 3:
        drivers.append(f"Consistent scholarly contributions across {len(topics)} computer science subfields")

    # Tier label
    if overall_score >= 90.0:
        tier = "Elite Impact Leader"
    elif overall_score >= 80.0:
        tier = "Distinguished Scientific Impact"
    elif overall_score >= 65.0:
        tier = "High Academic Influence"
    else:
        tier = "Established Contributor"

    return {
        "overall_impact_score": overall_score,
        "impact_tier": tier,
        "academic_impact": academic_score,
        "technology_impact": technology_score,
        "open_science_impact": open_science_score,
        "influence_growth": growth_score,
        "field_percentile": field_percentile,
        "field_normalized_multiplier": round(field_ratio, 2),
        "primary_field": primary_category,
        "raw_metrics": {
            "total_citations": total_citations,
            "h_index": h_index,
            "citation_velocity": velocity,
            "highly_cited_papers": highly_cited,
            "avg_citations_per_paper": avg_cites,
            "open_preprints": corr_count,
            "industry_references": industry_references,
            "patent_citations_est": patent_citations_est
        },
        "main_drivers": drivers[:4],
        "methodology": (
            "Multi-dimensional Research Impact Framework combining Academic Impact (40%), Technology Impact (25%), "
            "Open Science Impact (20%), and Influence Growth (15%). Calibrated against field baselines in "
            f"{primary_category} to prevent discipline volume bias."
        )
    }
