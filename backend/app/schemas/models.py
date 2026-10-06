from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Author(BaseModel):
    author_id: int
    name: str
    papers: int
    venue_share: float | None = None


class Venue(BaseModel):
    venue_id: int
    name: str
    papers: int


class Activity(BaseModel):
    year: int
    count: int
    growth_rate: float | None = None
    growth_rate: int | float | None = None


class Collaborator(Author):
    shared_papers: int
    coauthorship_share: float | None = None


class AuthorProductivityPoint(BaseModel):
    year: int
    papers: int
    avg_coauthors: float
    solo_papers: int
    collaborative_papers: int


class AuthorProfile(BaseModel):
    id: int
    author_id: int
    name: str
    total_publications: int
    papers: int
    first_publication_year: int | None
    last_publication_year: int | None
    active_years: int
    career_duration: int
    collaborator_count: int
    collaboration_strength: int
    top_venues: list[Venue]
    yearly_activity: list[Activity]
    collaborators: list[Collaborator]
    total_solo_papers: int = 0
    total_collaborative_papers: int = 0
    collaboration_ratio: float = 0.0
    average_coauthors_per_paper: float = 0.0
    productivity_breakdown: list[AuthorProductivityPoint] = []
    # New Intelligence fields
    total_citations: int = 0
    avg_citations_per_paper: float = 0.0
    h_index: int = 0
    citation_velocity: float = 0.0
    highly_cited_papers_count: int = 0
    institution: str | None = None
    institution_id: int | None = None
    primary_topics: list[dict] = []
    # Extended Strategic Intelligence
    impact_profile: dict[str, Any] | None = None
    career_intelligence: dict[str, Any] | None = None
    external_records: list[dict[str, Any]] = []


class VenueProfile(BaseModel):
    id: int
    name: str
    total_publications: int
    first_publication_year: int | None
    last_publication_year: int | None
    active_years: int
    author_count: int
    yearly_growth: list[Activity]
    top_authors: list[Author]
    peak_year: int | None = None
    peak_publications: int | None = None
    top_topics: list[dict] = []


class GrowthRow(BaseModel):
    id: int
    name: str
    historical_publications: int
    recent_publications: int
    growth_rate: float | None
    growth_rate: int | float | None = None


class GrowthPage(BaseModel):
    items: list[GrowthRow]
    total: int
    limit: int
    offset: int
    recent_start: int
    recent_end: int
    historical_end: int
    minimum_recent: int
    methodology: str


class Decade(BaseModel):
    decade: int
    publications: int
    authors: int
    venues: int
    average_authors_per_paper: float
    observed_through: int | None


class CollaborationEvolutionPoint(BaseModel):
    year: int
    publications: int
    unique_authors: int
    total_authorships: int
    average_authors_per_paper: float


class TeamDistribution(BaseModel):
    category: str
    count: int
    percentage: float


class SearchResults(BaseModel):
    authors: list[Author]
    venues: list[Venue]
    papers_available: bool = False


class GraphNode(BaseModel):
    id: str
    name: str
    publications: int
    collaborators: int
    community_id: int = 1
    community_label: str = "Core Cluster"
    degree_centrality: float = 0.0
    betweenness_centrality: float = 0.0
    pagerank: float = 0.0
    is_bridge: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str
    weight: int


class Graph(BaseModel):
    center_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    matching_collaborators: int
    truncated: bool
    start_year: int | None
    end_year: int | None
    communities: list[dict] = []
    bridge_nodes: list[str] = []


class Insight(BaseModel):
    title: str
    observation: str
    methodology: str
    href: str


class Insights(BaseModel):
    through_year: int
    items: list[Insight]


class PublicationGrowthPoint(BaseModel):
    year: int
    publication_count: int
    growth_percentage: float | None = None


class PublicationTypeTimelinePoint(BaseModel):
    year: int
    type: str | None
    count: int


class AuthorRankingItem(BaseModel):
    author_id: int
    name: str
    papers: int
    collaborators: int | None = None
    career_span: int | None = None
    first_year: int | None = None
    last_year: int | None = None


class AuthorScatterPoint(BaseModel):
    author_id: int
    name: str
    papers: int
    collaborators: int


class CollabWeightBucket(BaseModel):
    bucket: str
    count: int
    percentage: float | None = None


class StrongestPair(BaseModel):
    author1: str
    author2: str
    weight: int


class NetworkStats(BaseModel):
    total_researchers: int
    total_collaborations: int
    avg_collaborators_per_researcher: float
    strongest_pair: StrongestPair | None = None
    weight_distribution: list[CollabWeightBucket] = []


class VenueHeatmapPoint(BaseModel):
    venue: str
    year: int
    count: int


# ====================================================================
# NEW RESEARCH INTELLIGENCE SCHEMAS
# ====================================================================

# 1. Topics
class TopicKeyword(BaseModel):
    keyword: str
    weight: float


class Topic(BaseModel):
    topic_id: int
    topic_name: str
    category: str
    description: str
    first_seen_year: int | None = None
    latest_activity_year: int | None = None
    publication_count: int = 0
    growth_rate: float | None = None
    growth_rate: int | float | None = None


class TopicProfile(BaseModel):
    topic_id: int
    topic_name: str
    category: str
    description: str
    publication_count: int
    growth_rate: float | None
    growth_rate: int | float | None = None
    first_seen_year: int | None
    latest_activity_year: int | None
    top_researchers: list[Author]
    top_institutions: list[dict]
    top_venues: list[Venue]
    yearly_growth: list[Activity]
    related_topics: list[dict]


class TopicTimelineSeries(BaseModel):
    topic_id: int
    topic_name: str
    category: str
    yearly_data: list[dict]


# 2. Author Momentum & Impact
class AuthorMomentumItem(BaseModel):
    author_id: int
    name: str
    momentum_rank: int
    momentum_score: float
    damped_growth_rate: float
    raw_growth_rate: float | None = None
    momentum_score: int | float
    damped_growth_rate: int | float
    raw_growth_rate: int | float | None = None
    recent_publications: int
    historical_publications: int
    recent_collaborators: int
    career_stage: str
    career_span: int
    primary_topic: str | None = None
    explanation: str


class AuthorMomentumPage(BaseModel):
    items: list[AuthorMomentumItem]
    total: int
    limit: int
    offset: int


class AuthorImpactItem(BaseModel):
    author_id: int
    name: str
    papers: int
    total_citations: int
    avg_citations_per_paper: float
    h_index: int
    citation_velocity: float
    citation_velocity: int | float
    highly_cited_papers_count: int


class ResearcherCatalogItem(BaseModel):
    author_id: int
    name: str
    papers: int
    total_citations: int
    avg_citations_per_paper: float
    h_index: int
    citation_velocity: float
    highly_cited_papers_count: int
    career_stage: str | None = None
    career_span: int | None = None
    primary_topic: str | None = None
    institution: str | None = None


class ResearcherCatalogPage(BaseModel):
    items: list[ResearcherCatalogItem]
    total: int
    limit: int
    offset: int


# 3. Institutions
class Institution(BaseModel):
    institution_id: int
    name: str
    short_name: str
    country: str
    type: str
    publication_count: int
    citation_count: int
    h_index: int


class InstitutionProfile(BaseModel):
    institution_id: int
    name: str
    short_name: str
    country: str
    type: str
    publication_count: int
    citation_count: int
    h_index: int
    top_researchers: list[Author]
    top_topics: list[dict]
    top_venues: list[Venue]
    yearly_activity: list[Activity]
    collaborating_institutions: list[dict]


# 4. Publications & Search
class PublicationAuthor(BaseModel):
    author_id: int
    name: str


class PublicationItem(BaseModel):
    publication_id: int
    title: str
    year: int | None = None
    type: str | None = None
    venue_id: int | None = None
    venue_name: str | None = None
    authors: list[PublicationAuthor] = []
    citations: int = 0
    topics: list[dict] = []
    dblp_url: str | None = None


class PublicationDetail(BaseModel):
    publication_id: int
    title: str
    year: int | None = None
    type: str | None = None
    venue_id: int | None = None
    venue_name: str | None = None
    authors: list[PublicationAuthor] = []
    citations: int = 0
    influential_citations: int = 0
    citation_velocity: float = 0.0
    citation_velocity: int | float = 0
    topics: list[dict] = []
    dblp_url: str | None = None
    related_papers: list[PublicationItem] = []
    external_records: list[dict[str, Any]] = []
    lineage_summary: str | None = None


class PublicationSearchResponse(BaseModel):
    items: list[PublicationItem]
    total: int
    limit: int
    offset: int


class SearchResults(BaseModel):
    authors: list[Author]
    venues: list[Venue]
    papers_available: bool = True
    papers: list[PublicationItem] = []


# 5. AI Research Assistant
class AssistantQueryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    query: str = Field(min_length=3, max_length=1000)

    @field_validator('query')
    @classmethod
    def trim_question(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError('Query must contain at least 3 non-padding characters')
        return value


class AssistantMetric(BaseModel):
    label: str
    value: str
    detail: str | None = None


class AssistantDataPoint(BaseModel):
    name: str
    value: float
    secondary: float | None = None
    category: str | None = None


class AssistantChart(BaseModel):
    type: str
    title: str
    x_label: str | None = None
    y_label: str | None = None
    data: list[AssistantDataPoint] = []


class AssistantEntityLink(BaseModel):
    kind: str
    id: str
    title: str
    subtitle: str | None = None
    href: str


class AssistantSource(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['author', 'venue', 'paper', 'topic']
    id: int
    title: str
    href: str
    detail: str | None = None
    abstract: str | None = None


class AssistantCalculation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    description: str
    filters: dict[str, Any] = Field(default_factory=dict)
    database_version: str
    result: dict[str, Any] = Field(default_factory=dict)


class AssistantClaim(BaseModel):
    model_config = ConfigDict(extra='forbid')
    claim_id: str
    text: str
    source_refs: list[str] = Field(default_factory=list)
    calculation_refs: list[int] = Field(default_factory=list)


class AssistantQueryResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['answered', 'ambiguous', 'not_found', 'insufficient_evidence', 'outside_scope', 'unavailable']
    answer: str
    request_id: str
    limitation_code: str | None = None
    sources: list[AssistantSource] = Field(default_factory=list)
    calculations: list[AssistantCalculation] = Field(default_factory=list)
    claims: list[AssistantClaim] = Field(default_factory=list)
    is_all_papers: bool = False
    export_query: str | None = None


class AssistantExportRequest(BaseModel):
    query: str | None = None
    publication_ids: list[int] | None = None
    limit: int = 150
    format: Literal['xlsx', 'csv'] = 'xlsx'


# ====================================================================
# STRATEGIC SCIENTIFIC INTELLIGENCE SCHEMAS
# ====================================================================

# 1. Research Impact Intelligence
class ImpactProfile(BaseModel):
    overall_impact_score: float
    impact_tier: str
    academic_impact: float
    technology_impact: float
    open_science_impact: float
    influence_growth: float
    field_percentile: float
    field_normalized_multiplier: float
    primary_field: str
    raw_metrics: dict[str, Any]
    main_drivers: list[str]
    methodology: str


# 2. Field Normalization
class ResearchField(BaseModel):
    field_id: int
    name: str
    slug: str
    description: str
    icon: str


class FieldStatistics(BaseModel):
    field_id: int
    field_name: str
    publication_count: int
    author_count: int
    total_citations: int
    avg_citations_per_paper: float
    avg_citations_per_author: float
    avg_publications_per_author: float
    avg_growth_rate: float
    avg_authors_per_paper: float


class FieldNormalizedAuthor(BaseModel):
    author_id: int
    name: str
    papers: int
    total_citations: int
    h_index: int
    citation_velocity: float
    citation_velocity: int | float
    primary_field: str
    field_adjusted_impact: float
    field_adjusted_productivity: float
    field_percentile: float
    raw_rank: int | None = None
    normalized_rank: int | None = None


# 3. Career Intelligence
class BreakthroughMoment(BaseModel):
    year: int
    growth_pct: float
    papers_in_year: int
    new_coauthors: int
    focus_topic: str
    signals: list[str]
    description: str


class TopicTransitionEra(BaseModel):
    era_name: str
    start_year: int
    end_year: int
    primary_focus: str
    description: str


class CareerIntelligence(BaseModel):
    career_stage: str
    career_stage_description: str
    career_span_years: int
    first_year: int
    latest_year: int
    peak_year: int
    peak_papers: int
    breakthrough_moments: list[BreakthroughMoment] = []
    topic_transitions: list[TopicTransitionEra] = []
    narrative: str


# 4. Researcher Similarity
class SimilarResearcher(BaseModel):
    author_id: int
    name: str
    similarity_score: int
    papers: int
    h_index: int
    total_citations: int
    institution: str
    primary_topic: str
    topic_overlap_pct: float
    venue_overlap_pct: float
    reasons: list[str] = []
    shared_topics: list[str] = []
    shared_venues: list[str] = []


# 5. Scientific Knowledge Graph
class KGNode(BaseModel):
    id: str
    name: str
    entity_type: str
    size: float
    color: str
    subtext: str | None = None
    degree: int = 0
    cluster_id: int = 1
    is_hub: bool = False
    is_bridge: bool = False


class KGEdge(BaseModel):
    source: str
    target: str
    relationship: str
    weight: int = 1


class KGAnalytics(BaseModel):
    total_nodes: int
    total_edges: int
    influential_hubs: list[dict[str, Any]] = []
    bridge_entities: list[dict[str, Any]] = []
    cluster_distribution: list[dict[str, Any]] = []


class KnowledgeGraphResponse(BaseModel):
    nodes: list[KGNode]
    edges: list[KGEdge]
    analytics: KGAnalytics


# 6. Benchmarking Mode
class BenchmarkMetric(BaseModel):
    metric_name: str
    label: str
    entity1_value: float
    entity2_value: float
    entity1_display: str
    entity2_display: str
    advantage: str
    advantage_pct: float | None = None


class BenchmarkSpecialization(BaseModel):
    topic_name: str
    category: str
    entity1_share: float
    entity2_share: float


class BenchmarkReport(BaseModel):
    comparison_type: str
    entity1_id: str
    entity1_name: str
    entity2_id: str
    entity2_name: str
    period: str
    executive_summary: str
    metrics: list[BenchmarkMetric]
    specializations: list[BenchmarkSpecialization]
    top_scholars_entity1: list[dict[str, Any]] = []
    top_scholars_entity2: list[dict[str, Any]] = []


# 7. Data Quality & Trust
class DatabaseHealth(BaseModel):
    total_publications: int
    total_authors: int
    total_venues: int
    total_collaborations: int
    active_years_span: str
    last_updated: str
    storage_engine: str
    dataset_source: str


class MetadataCompletenessAudit(BaseModel):
    dimension: str
    metric: str
    completeness_percentage: float
    status: str


class MetricFormulaDoc(BaseModel):
    metric_id: str
    name: str
    formula: str
    inputs: list[str]
    interpretation: str
    baseline: str
    limitations: str
    confidence_level: str


class ExternalSourceCoverage(BaseModel):
    source_name: str
    category: str
    coverage_pct: float
    records_count: str
    sync_status: str
    last_synced: str


class ConflictResolutionItem(BaseModel):
    metric: str
    sources_compared: list[str]
    discrepancy_rate: str
    resolution_strategy: str


class DataQualityResponse(BaseModel):
    health: DatabaseHealth
    audits: list[MetadataCompletenessAudit]
    formulas: list[MetricFormulaDoc]
    external_sources: list[ExternalSourceCoverage] = []
    source_conflicts: list[ConflictResolutionItem] = []


# ====================================================================
# FINAL STRATEGIC SCIENTIFIC INTELLIGENCE SCHEMAS
# ====================================================================

# 1. Semantic Research Intelligence Layer
class SemanticSearchItem(BaseModel):
    entity_type: str
    entity_id: int
    title: str
    subtitle: str | None = None
    year: int | None = None
    venue: str | None = None
    citations: int | None = None
    relevance_score: float
    match_type: str
    href: str


class SemanticSearchResponse(BaseModel):
    query: str
    total_results: int
    papers: list[SemanticSearchItem] = []
    researchers: list[SemanticSearchItem] = []
    institutions: list[SemanticSearchItem] = []
    topics: list[SemanticSearchItem] = []
    top_matches: list[SemanticSearchItem] = []


# 2. Predictive Research Forecasting Engine
class TopicForecast(BaseModel):
    topic_id: int
    topic_name: str
    category: str
    publication_growth: float
    growth_acceleration: float
    researcher_inflow: float
    new_researchers_count: int
    citation_momentum: float
    venue_adoption_level: str
    collaboration_expansion: float
    opportunity_score: float
    trend_status: str
    forecast_summary: str
    strategic_recommendation: str


class BreakoutResearcher(BaseModel):
    author_id: int
    name: str
    momentum_score: float
    velocity_multiplier: float
    primary_topic: str
    papers: int
    citations: int
    career_stage: str
    acceleration_reason: str


class ForecastOverviewResponse(BaseModel):
    forecast_horizon: str
    total_topics_monitored: int
    macro_outlook: str
    emerging_fields: list[TopicForecast]
    declining_fields: list[TopicForecast]
    accelerating_fields: list[TopicForecast]
    breakout_researchers: list[BreakoutResearcher]


# 3. External Research Ecosystem
class ExternalEcosystemRecord(BaseModel):
    entity_type: str
    entity_id: int
    source: str
    external_id: str
    external_url: str
    metric_key: str
    metric_value: str
    confidence: str
    last_updated: str


# 4. Paper Citation Lineage & Idea Evolution Graph
class LineageNode(BaseModel):
    id: str
    publication_id: int
    title: str
    year: int
    authors: list[str] = []
    venue: str | None = None
    citations: int = 0
    influential_citations: int = 0
    topic: str | None = None
    impact_score: float = 0.0
    era: str
    role: str


class LineageEdge(BaseModel):
    source: str
    target: str
    citation_year: int
    citation_strength: float
    influence_type: str


class LineageFoundationalRoot(BaseModel):
    publication_id: int
    title: str
    year: int
    lead_author: str
    citations: int
    centrality_score: float
    why_foundational: str


class PaperLineageResponse(BaseModel):
    target_publication_id: int
    target_title: str
    target_year: int
    total_ancestors: int
    total_descendants: int
    foundational_roots: list[LineageFoundationalRoot]
    lineage_summary: str
    nodes: list[LineageNode]
    edges: list[LineageEdge]
    eras: list[dict[str, Any]]
