"""Versioned DBLP evidence boundary. Unknown tables/fields are denied by default.

This is a contract, not a SQL sandbox. Assistant tools must own their query forms;
neither callers nor a language model may supply SQL or arbitrary evidence rows.
"""
from types import MappingProxyType

CONTRACT_VERSION = "dblp-evidence-v1"
TITLE_CLASSIFICATION_LABEL = "title-based project classification"
AUTHOR_IDENTITY_NOTE = (
    "Author records group stored names and may merge different people with the same name."
)
STORED_TITLE_NOTE = (
    "Titles reflect the current database import; XML entity and nested-text extraction "
    "can leave them incomplete. Titles do not establish paper methods or findings."
)

# IDs identify this database version, not stable identities across parser rebuilds.
CORE_FIELDS = MappingProxyType({
    "publications": frozenset({"publication_id", "db_key", "type", "title", "year", "venue_id"}),
    "authors": frozenset({"author_id", "name"}),
    "venues": frozenset({"venue_id", "name"}),
    "publication_authors": frozenset({"publication_id", "author_id"}),
})
VERIFIED_REPAIRED_SUMMARY_FIELDS = MappingProxyType({
    "author_stats": frozenset({"author_id", "name", "publication_count"}),
})
CLASSIFICATION_FIELDS = MappingProxyType({
    "topics": frozenset({"topic_id", "topic_name", "category"}),
    "topic_keywords": frozenset({"topic_id", "keyword"}),
})
# Recompute classifications with literal, case-insensitive title substring matching.
# Legacy publication_topics can contain repeated pairs and nondeterministic ties.
EXCLUDED_TABLES = frozenset({
    "publication_citations", "author_impact_stats", "institutions", "author_institutions",
    "institution_topics", "institution_year_stats", "institution_collaboration",
    "paper_citation_lineage", "topic_forecast_signals", "external_ecosystem_metadata",
    "paper_embeddings", "author_embeddings", "topic_embeddings", "author_momentum",
    "field_statistics", "research_fields", "publication_topics", "topic_year_stats",
    "author_topics", "venue_topics", "author_collaboration", "author_collaboration_dashboard",
    "author_collaboration_dashboard_named", "author_stats", "venue_stats",
    "publication_year_stats", "dashboard_summary", "top_authors", "raw_publications",
})


def require_fields(table: str, fields: set[str] | frozenset[str], *, label: str | None = None) -> None:
    """Reject unreviewed evidence projections, including mixed-trust tables."""
    allowed = CORE_FIELDS.get(table)
    if table in CLASSIFICATION_FIELDS:
        if label != TITLE_CLASSIFICATION_LABEL:
            raise ValueError("Project classification requires its explicit label")
        allowed = CLASSIFICATION_FIELDS[table]
    if not fields or allowed is None or not fields <= allowed:
        raise ValueError("Fields are outside the approved DBLP evidence contract")


def require_repaired_summary_fields(table: str, fields: set[str] | frozenset[str]) -> None:
    """Allow summaries only through a separately verified repaired-corpus path."""
    allowed = VERIFIED_REPAIRED_SUMMARY_FIELDS.get(table)
    if not fields or allowed is None or not fields <= allowed:
        raise ValueError("Fields are outside the verified repaired summary contract")


CALCULATIONS = MappingProxyType({
    "corpus_count": "COUNT(*) over publications; all stored publication types, including empty titles",
    "eligible_titles": "title IS NOT NULL AND length(trim(title)) > 0",
    "author_publications": "COUNT(DISTINCT publication_id) for a verified author_id joined to publications",
    "venue_publications": "COUNT(DISTINCT publication_id) for a verified venue_id",
    "year_trend": "COUNT(DISTINCT publication_id) grouped by stored year; disclose null-year exclusions",
    "coauthorship": "Distinct publications shared by two verified author IDs; exclude self-pairs",
    "classification_count": "Distinct publication IDs whose titles contain a declared project keyword",
    "comparison": "Same publication-count calculation and inclusive year filters for each entity",
    "ranking": "Publication counts descending, entity ID ascending to resolve count ties",
})
