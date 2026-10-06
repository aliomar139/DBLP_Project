"""Comparative Research Benchmarking Router.

Enables strategic head-to-head benchmarking across:
1. Institutions (e.g. MIT vs Stanford University)
2. Countries (e.g. United States vs China)
3. Topics (e.g. Large Language Models vs Computer Vision)

Compares:
- Research Output & Growth
- Scholarly Impact & Field-Adjusted Multipliers
- Talent Pool & Momentum
- Topic Specialization & Distribution
- Cross-Institutional Partnerships
"""
import math
from typing import Any
from fastapi import APIRouter, HTTPException, Query
from ..schemas.models import BenchmarkReport, BenchmarkMetric, BenchmarkSpecialization
from ..services.duckdb import query

router = APIRouter(prefix='/api/benchmark', tags=['Benchmarking Mode'])

PRESETS = [
    {
        "id": "mit-stanford",
        "type": "institution",
        "name": "MIT vs. Stanford University",
        "entity1_id": "1",
        "entity2_id": "2",
        "description": "Premier US research universities in computer science and artificial intelligence."
    },
    {
        "id": "cmu-berkeley",
        "type": "institution",
        "name": "Carnegie Mellon vs. UC Berkeley",
        "entity1_id": "4",
        "entity2_id": "3",
        "description": "Foundational computing institutions with massive systems and machine learning output."
    },
    {
        "id": "tsinghua-oxford",
        "type": "institution",
        "name": "Tsinghua vs. Oxford University",
        "entity1_id": "5",
        "entity2_id": "7",
        "description": "Top Asian engineering powerhouse vs. historic European academic center."
    },
    {
        "id": "us-china",
        "type": "country",
        "name": "United States vs. China",
        "entity1_id": "United States",
        "entity2_id": "China",
        "description": "Geopolitical AI and computing capacity benchmark."
    },
    {
        "id": "llm-cv",
        "type": "topic",
        "name": "Large Language Models vs. Computer Vision",
        "entity1_id": "1",
        "entity2_id": "2",
        "description": "Frontier AI domains: Foundation models vs visual perception."
    },
    {
        "id": "quantum-crypto",
        "type": "topic",
        "name": "Quantum Computing vs. Cryptography",
        "entity1_id": "31",
        "entity2_id": "16",
        "description": "Theoretical physics meets computational security."
    }
]


@router.get('/presets')
def list_presets():
    """Return curated strategic benchmark comparisons."""
    return PRESETS


@router.get('/compare', response_model=BenchmarkReport)
def compare_entities(
    type: str = Query('institution', pattern='^(institution|country|topic)$'),
    entity1: str = Query('1', description='ID or identifier for Entity 1'),
    entity2: str = Query('2', description='ID or identifier for Entity 2'),
    topic_id: int | None = Query(None, description='Optional topic filter')
):
    """Generate head-to-head strategic benchmark report between two scientific entities."""
    metrics: list[BenchmarkMetric] = []
    specializations: list[BenchmarkSpecialization] = []
    scholars1: list[dict[str, Any]] = []
    scholars2: list[dict[str, Any]] = []

    if type == 'institution':
        i1_rows = query("SELECT institution_id, name, short_name, country, publication_count, citation_count, h_index FROM institutions WHERE institution_id = ?", (int(entity1),))
        i2_rows = query("SELECT institution_id, name, short_name, country, publication_count, citation_count, h_index FROM institutions WHERE institution_id = ?", (int(entity2),))

        if not i1_rows or not i2_rows:
            raise HTTPException(404, "One or both institutions not found")
        e1, e2 = i1_rows[0], i2_rows[0]
        e1_name, e2_name = e1['name'], e2['name']
        e1_short, e2_short = e1['short_name'], e2['short_name']

        # Researchers count
        r1_count = query("SELECT COUNT(DISTINCT author_id) as n FROM author_institutions WHERE institution_id = ?", (e1['institution_id'],))[0]['n']
        r2_count = query("SELECT COUNT(DISTINCT author_id) as n FROM author_institutions WHERE institution_id = ?", (e2['institution_id'],))[0]['n']

        # Citations per paper
        cpp1 = round(e1['citation_count'] / max(e1['publication_count'], 1), 1)
        cpp2 = round(e2['citation_count'] / max(e2['publication_count'], 1), 1)

        # Field adjusted impact multiplier (baseline approx 22.0)
        f_mult1 = round(cpp1 / 22.0, 2)
        f_mult2 = round(cpp2 / 22.0, 2)

        def add_metric(name: str, label: str, v1: float, v2: float, d1: str, d2: str):
            diff = abs(v1 - v2)
            max_v = max(v1, v2)
            pct = round((diff / max(min(v1, v2), 1)) * 100.0, 1) if min(v1, v2) > 0 else 0.0
            pct = math.floor((diff / max(min(v1, v2), 1)) * 100.0) if min(v1, v2) > 0 else 0
            adv = "entity1" if v1 > v2 else ("entity2" if v2 > v1 else "tied")
            metrics.append(BenchmarkMetric(
                metric_name=name, label=label,
                entity1_value=v1, entity2_value=v2,
                entity1_display=d1, entity2_display=d2,
                advantage=adv, advantage_pct=pct
            ))

        add_metric("publications", "Total Publications", float(e1['publication_count']), float(e2['publication_count']), f"{e1['publication_count']:,}", f"{e2['publication_count']:,}")
        add_metric("citations", "Total Calibrated Citations", float(e1['citation_count']), float(e2['citation_count']), f"{e1['citation_count']:,}", f"{e2['citation_count']:,}")
        add_metric("cpp", "Citations per Paper", cpp1, cpp2, f"{cpp1}", f"{cpp2}")
        add_metric("h_index", "Institutional h-index", float(e1['h_index']), float(e2['h_index']), f"h={e1['h_index']}", f"h={e2['h_index']}")
        add_metric("field_multiplier", "Field-Adjusted Impact", f_mult1, f_mult2, f"{f_mult1}x field avg", f"{f_mult2}x field avg")
        add_metric("talent", "Affiliated Researchers", float(r1_count), float(r2_count), f"{r1_count:,}", f"{r2_count:,}")
        add_metric("talent", "Key Core Researchers", float(r1_count), float(r2_count), f"{r1_count:,} scholars", f"{r2_count:,} scholars")
        add_metric("field_multiplier", "Discipline Citation Multiplier", f_mult1, f_mult2, f"{f_mult1}x field base", f"{f_mult2}x field base")

        # Top Scholars
        scholars1 = query("""
        SELECT a.author_id, a.name, a.publication_count as papers, COALESCE(i.total_citations, 0) as citations
        FROM author_institutions ai
        JOIN author_stats a USING(author_id)
        LEFT JOIN author_impact_stats i USING(author_id)
        WHERE ai.institution_id = ?
        ORDER BY a.publication_count DESC
        LIMIT 5
        """, (e1['institution_id'],))
        # Top scholars
        scholars1 = query("SELECT a.author_id, a.name, a.publication_count as papers, i.total_citations as citations FROM author_institutions ai JOIN author_stats a USING(author_id) LEFT JOIN author_impact_stats i USING(author_id) WHERE ai.institution_id = ? ORDER BY a.publication_count DESC LIMIT 5", (e1['institution_id'],))
        scholars2 = query("SELECT a.author_id, a.name, a.publication_count as papers, i.total_citations as citations FROM author_institutions ai JOIN author_stats a USING(author_id) LEFT JOIN author_impact_stats i USING(author_id) WHERE ai.institution_id = ? ORDER BY a.publication_count DESC LIMIT 5", (e2['institution_id'],))

        scholars2 = query("""
        SELECT a.author_id, a.name, a.publication_count as papers, COALESCE(i.total_citations, 0) as citations
        FROM author_institutions ai
        JOIN author_stats a USING(author_id)
        LEFT JOIN author_impact_stats i USING(author_id)
        WHERE ai.institution_id = ?
        ORDER BY a.publication_count DESC
        LIMIT 5
        """, (e2['institution_id'],))

        # Specializations
        specs = query("""
        WITH t1 AS (
            SELECT topic_id, publication_count FROM institution_topics WHERE institution_id = ?
        ),
        t2 AS (
            SELECT topic_id, publication_count FROM institution_topics WHERE institution_id = ?
        )
        SELECT 
            t.topic_name,
            t.category,
            COALESCE(t1.publication_count, 0) as count1,
            COALESCE(t2.publication_count, 0) as count2
        FROM topics t
        LEFT JOIN t1 USING(topic_id)
        LEFT JOIN t2 USING(topic_id)
        WHERE COALESCE(t1.publication_count, 0) > 0 OR COALESCE(t2.publication_count, 0) > 0
        ORDER BY (COALESCE(t1.publication_count, 0) + COALESCE(t2.publication_count, 0)) DESC
        LIMIT 8
        """, (e1['institution_id'], e2['institution_id']))

        tot1 = sum(s['count1'] for s in specs) or 1
        tot2 = sum(s['count2'] for s in specs) or 1
        for s in specs:
            specializations.append(BenchmarkSpecialization(
                topic_name=s['topic_name'],
                category=s['category'],
                entity1_share=math.floor((s['count1'] / tot1) * 100.0),
                entity2_share=math.floor((s['count2'] / tot2) * 100.0)
            ))

        # Executive summary
        adv_p = e1_short if e1['publication_count'] > e2['publication_count'] else e2_short
        adv_c = e1_short if cpp1 > cpp2 else e2_short
        summary = (
            f"**{e1_short}** vs. **{e2_short}** Research Benchmark: **{adv_p}** maintains publication volume leadership "
            f"({max(e1['publication_count'], e2['publication_count']):,} indexed papers), while **{adv_c}** demonstrates "
            f"superior citation density ({max(cpp1, cpp2)} cites/paper, {max(f_mult1, f_mult2)}x field baseline). "
            f"Both institutions demonstrate elite academic output with global influence."
        )

    elif type == 'country':
        c1, c2 = entity1, entity2
        e1_name, e2_name = c1, c2

        c1_stats = query("SELECT SUM(publication_count) as pubs, SUM(citation_count) as cites, AVG(h_index) as avg_h, COUNT(*) as inst_count FROM institutions WHERE country = ?", (c1,))[0]
        c2_stats = query("SELECT SUM(publication_count) as pubs, SUM(citation_count) as cites, AVG(h_index) as avg_h, COUNT(*) as inst_count FROM institutions WHERE country = ?", (c2,))[0]

        p1 = c1_stats['pubs'] or 1
        p2 = c2_stats['pubs'] or 1
        cites1 = c1_stats['cites'] or 1
        cites2 = c2_stats['cites'] or 1
        cpp1 = round(cites1 / p1, 1)
        cpp2 = round(cites2 / p2, 1)

        def add_metric(name: str, label: str, v1: float, v2: float, d1: str, d2: str):
            diff = abs(v1 - v2)
            pct = round((diff / max(min(v1, v2), 1)) * 100.0, 1) if min(v1, v2) > 0 else 0.0
            pct = math.floor((diff / max(min(v1, v2), 1)) * 100.0) if min(v1, v2) > 0 else 0
            adv = "entity1" if v1 > v2 else ("entity2" if v2 > v1 else "tied")
            metrics.append(BenchmarkMetric(
                metric_name=name, label=label,
                entity1_value=v1, entity2_value=v2,
                entity1_display=d1, entity2_display=d2,
                advantage=adv, advantage_pct=pct
            ))

        add_metric("publications", "Indexed Publications", float(p1), float(p2), f"{p1:,}", f"{p2:,}")
        add_metric("citations", "Total Citations", float(cites1), float(cites2), f"{cites1:,}", f"{cites2:,}")
        add_metric("cpp", "Mean Citations/Paper", cpp1, cpp2, f"{cpp1}", f"{cpp2}")
        add_metric("institutions", "Top Tier Research Hubs", float(c1_stats['inst_count']), float(c2_stats['inst_count']), f"{c1_stats['inst_count']}", f"{c2_stats['inst_count']}")

        scholars1 = query("SELECT a.author_id, a.name, a.publication_count as papers FROM author_institutions ai JOIN institutions i USING(institution_id) JOIN author_stats a USING(author_id) WHERE i.country = ? ORDER BY a.publication_count DESC LIMIT 5", (c1,))
        scholars2 = query("SELECT a.author_id, a.name, a.publication_count as papers FROM author_institutions ai JOIN institutions i USING(institution_id) JOIN author_stats a USING(author_id) WHERE i.country = ? ORDER BY a.publication_count DESC LIMIT 5", (c2,))

        summary = f"National research ecosystem comparison: **{c1}** vs. **{c2}** across computer science publication volume and citations."

    else:
        # Topic vs Topic
        t1 = query("SELECT topic_id, topic_name, category, publication_count, growth_rate FROM topics WHERE topic_id = ?", (int(entity1),))[0]
        t2 = query("SELECT topic_id, topic_name, category, publication_count, growth_rate FROM topics WHERE topic_id = ?", (int(entity2),))[0]
        t1 = query("SELECT topic_id, topic_name, category, publication_count, CAST(FLOOR(growth_rate) AS BIGINT) as growth_rate FROM topics WHERE topic_id = ?", (int(entity1),))[0]
        t2 = query("SELECT topic_id, topic_name, category, publication_count, CAST(FLOOR(growth_rate) AS BIGINT) as growth_rate FROM topics WHERE topic_id = ?", (int(entity2),))[0]
        e1_name, e2_name = t1['topic_name'], t2['topic_name']

        def add_metric(name: str, label: str, v1: float, v2: float, d1: str, d2: str):
            diff = abs(v1 - v2)
            pct = round((diff / max(min(v1, v2), 1)) * 100.0, 1) if min(v1, v2) > 0 else 0.0
            pct = math.floor((diff / max(min(v1, v2), 1)) * 100.0) if min(v1, v2) > 0 else 0
            adv = "entity1" if v1 > v2 else ("entity2" if v2 > v1 else "tied")
            metrics.append(BenchmarkMetric(
                metric_name=name, label=label,
                entity1_value=v1, entity2_value=v2,
                entity1_display=d1, entity2_display=d2,
                advantage=adv, advantage_pct=pct
            ))

        add_metric("publications", "Indexed Publications", float(t1['publication_count']), float(t2['publication_count']), f"{t1['publication_count']:,}", f"{t2['publication_count']:,}")
        add_metric("growth_rate", "10-Year Growth Rate", float(t1['growth_rate'] or 0.0), float(t2['growth_rate'] or 0.0), f"+{t1['growth_rate']}%", f"+{t2['growth_rate']}%")
        add_metric("growth_rate", "10-Year Growth Rate", float(t1['growth_rate'] or 0.0), float(t2['growth_rate'] or 0.0), f"+{math.floor(t1['growth_rate'] or 0)}%", f"+{math.floor(t2['growth_rate'] or 0)}%")

        scholars1 = query("SELECT a.author_id, a.name, atp.publication_count as papers FROM author_topics atp JOIN author_stats a USING(author_id) WHERE atp.topic_id = ? ORDER BY atp.publication_count DESC LIMIT 5", (t1['topic_id'],))
        scholars2 = query("SELECT a.author_id, a.name, atp.publication_count as papers FROM author_topics atp JOIN author_stats a USING(author_id) WHERE atp.topic_id = ? ORDER BY atp.publication_count DESC LIMIT 5", (t2['topic_id'],))

        summary = f"Domain benchmark: **{t1['topic_name']}** vs. **{t2['topic_name']}**."

    return BenchmarkReport(
        comparison_type=type,
        entity1_id=str(entity1),
        entity1_name=e1_name,
        entity2_id=str(entity2),
        entity2_name=e2_name,
        period="1970–2026 (Calibrated Historical)",
        executive_summary=summary,
        metrics=metrics,
        specializations=specializations,
        top_scholars_entity1=scholars1,
        top_scholars_entity2=scholars2
    )
