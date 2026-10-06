const API = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export type Overview = {
  total_publications: number
  total_authors: number
  total_venues: number
  first_year: number | null
  last_year: number | null
  active_years: number
  average_authors_per_paper: number | null
  average_publications_per_year: number | null
}

export type TimelinePoint = {
  year: number
  count: number
  growth_rate: number | null
}

export type PublicationType = {
  type: string | null
  count: number
}

export type Author = {
  author_id: number
  name: string
  papers: number
  venue_share?: number | null
}

export type ResearcherCatalogItem = {
  author_id: number
  name: string
  papers: number
  total_citations: number
  avg_citations_per_paper: number
  h_index: number
  citation_velocity: number
  highly_cited_papers_count: number
  career_stage: string | null
  career_span: number | null
  primary_topic: string | null
  institution: string | null
}

export type ResearcherCatalogPage = {
  items: ResearcherCatalogItem[]
  total: number
  limit: number
  offset: number
}

export type ResearcherSort = 'name' | 'papers' | 'total_citations' | 'h_index' | 'avg_citations_per_paper' | 'citation_velocity'

export type Venue = {
  venue_id: number
  name: string
  papers: number
}

export type Collaborator = Author & {
  shared_papers: number
  coauthorship_share?: number | null
}

export type AuthorProductivityPoint = {
  year: number
  papers: number
  avg_coauthors: number
  solo_papers: number
  collaborative_papers: number
}

export type AuthorProfile = {
  id: number
  author_id?: number
  name: string
  total_publications: number
  first_publication_year: number | null
  last_publication_year: number | null
  active_years: number
  career_duration: number
  collaborator_count: number
  collaboration_strength: number
  top_venues: Venue[]
  yearly_activity: TimelinePoint[]
  collaborators: Collaborator[]
  total_solo_papers: number
  total_collaborative_papers: number
  collaboration_ratio: number
  average_coauthors_per_paper: number
  productivity_breakdown: AuthorProductivityPoint[]
  total_citations?: number
  avg_citations_per_paper?: number
  h_index?: number
  citation_velocity?: number
  institution?: string | null
  institution_id?: number | null
  primary_topics?: { topic_id: number; topic_name: string; publication_count: number; share_percentage: number }[]
  impact_profile?: ImpactProfile
  career_intelligence?: CareerIntelligence
}

export type VenueProfile = {
  id: number
  name: string
  total_publications: number
  first_publication_year: number | null
  last_publication_year: number | null
  active_years: number
  author_count: number
  yearly_growth: TimelinePoint[]
  top_authors: Author[]
  peak_year?: number | null
  peak_publications?: number | null
  top_topics?: { topic_id: number; topic_name: string; publication_count: number }[]
}

export type GraphCommunity = {
  community_id: number
  label: string
  size: number
  member_ids: string[]
}

export type GraphNode = {
  id: string
  name: string
  publications: number
  collaborators: number
  community_id?: number
  community_label?: string
  degree_centrality?: number
  betweenness_centrality?: number
  pagerank?: number
  is_bridge?: boolean
}

export type Graph = {
  center_id: string
  nodes: GraphNode[]
  edges: { source: string; target: string; weight: number }[]
  matching_collaborators: number
  truncated: boolean
  start_year: number | null
  end_year: number | null
  communities?: GraphCommunity[]
  bridge_nodes?: string[]
}

export type BridgeResponse = {
  found: boolean
  hops: number
  nodes: { author_id: number; name: string; papers: number }[]
  links: { source: number; target: number; shared_papers: number; explanation: string }[]
  message: string
}

export type Decade = {
  decade: number
  publications: number
  authors: number
  venues: number
  average_authors_per_paper: number
  observed_through: number | null
}

export type CollaborationEvolutionPoint = {
  year: number
  publications: number
  unique_authors: number
  total_authorships: number
  average_authors_per_paper: number
}

export type TeamDistribution = {
  category: string
  count: number
  percentage: number
}

export type GrowthRow = {
  id: number
  name: string
  historical_publications: number
  recent_publications: number
  growth_rate: number | null
}

export type GrowthPage = {
  items: GrowthRow[]
  total: number
  limit: number
  offset: number
  recent_start: number
  recent_end: number
  historical_end: number
  minimum_recent: number
  methodology: string
}

export type PublicationAuthor = {
  author_id: number
  name: string
}

export type PublicationItem = {
  publication_id: number
  title: string
  year: number | null
  type: string | null
  venue_id: number | null
  venue_name: string | null
  authors: PublicationAuthor[]
  citations: number
  topics: { topic_id: number; topic_name: string; category: string }[]
  dblp_url?: string | null
}

export type ExternalEcosystemRecord = {
  entity_type: string
  entity_id: number
  source: string
  external_id: string
  external_url: string
  metric_key: string
  metric_value: string
  confidence: string
  last_updated: string
}

export type PublicationDetail = PublicationItem & {
  influential_citations: number
  citation_velocity: number
  related_papers: PublicationItem[]
  external_records?: ExternalEcosystemRecord[]
  lineage_summary?: string | null
}

export type PublicationSearchResponse = {
  items: PublicationItem[]
  total: number
  limit: number
  offset: number
}

export type SearchResults = {
  authors: Author[]
  venues: Venue[]
  papers_available: boolean
  papers?: PublicationItem[]
}

export type InsightItem = { title: string; observation: string; methodology: string; href: string }
export type Insights = { through_year: number; items: InsightItem[] }

export type SortKey = 'name' | 'growth_rate' | 'recent_publications' | 'historical_publications'
export type Order = 'asc' | 'desc'
export type PublicationGrowthPoint = { year: number; publication_count: number; growth_percentage: number | null }
export type PublicationTypeTimelinePoint = { year: number; type: string | null; count: number }

export type AuthorRankingItem = {
  author_id: number
  name: string
  papers: number
  collaborators?: number | null
  collaborator_count?: number | null
  collaboration_strength?: number | null
  career_span?: number | null
  first_year?: number | null
  last_year?: number | null
}

export type AuthorScatterPoint = { author_id: number; name: string; papers: number; collaborators: number }
export type CollabWeightBucket = { bucket: string; count: number; percentage?: number | null }
export type StrongestPair = { author1: string; author2: string; weight: number }
export type NetworkStats = { total_researchers: number; total_collaborations: number; avg_collaborators_per_researcher: number; strongest_pair: StrongestPair | null; weight_distribution: CollabWeightBucket[] }
export type VenueHeatmapPoint = { venue: string; year: number; count: number }

// Topic Intelligence
export type Topic = {
  topic_id: number
  topic_name: string
  category: string
  description: string
  first_seen_year: number | null
  latest_activity_year: number | null
  publication_count: number
  growth_rate: number | null
}

export type TopicProfile = Topic & {
  top_researchers: Author[]
  top_institutions: { institution_id: number; name: string; short_name: string; country: string; papers: number }[]
  top_venues: Venue[]
  yearly_growth: TimelinePoint[]
  related_topics: { topic_id: number; topic_name: string; category: string; shared_papers: number }[]
}

export type TopicTimelinePoint = {
  topic_id: number
  topic_name: string
  category: string
  year: number
  count: number
}

// Institutions
export type Institution = {
  institution_id: number
  name: string
  short_name: string
  country: string
  type: string
  publication_count: number
  citation_count: number
  h_index: number
}

export type InstitutionProfile = Institution & {
  top_researchers: Author[]
  top_topics: { topic_id: number; topic_name: string; category: string; papers: number }[]
  top_venues: Venue[]
  yearly_activity: TimelinePoint[]
  collaborating_institutions: { institution_id: number; name: string; short_name: string; country: string; shared_papers: number }[]
}

// Author Momentum & Impact
export type AuthorMomentumItem = {
  author_id: number
  name: string
  momentum_rank: number
  momentum_score: number
  damped_growth_rate: number
  raw_growth_rate: number | null
  recent_publications: number
  historical_publications: number
  total_publications?: number
  recent_collaborators: number
  career_stage: string
  career_span: number
  primary_topic: string | null
  explanation: string
}

export type AuthorMomentumPage = {
  items: AuthorMomentumItem[]
  total: number
  limit: number
  offset: number
}

export type AuthorImpactItem = {
  author_id: number
  name: string
  papers: number
  total_publications?: number
  total_citations: number
  avg_citations_per_paper: number
  h_index: number
  citation_velocity: number
  highly_cited_papers_count: number
}

// 1. Research Impact Intelligence
export type RawImpactMetrics = {
  total_citations: number
  h_index: number
  citation_velocity: number
  highly_cited_papers: number
  avg_citations_per_paper: number
  open_preprints: number
  industry_references: number
  patent_citations_est: number
}

export type ImpactProfile = {
  overall_impact_score: number
  impact_tier: string
  academic_impact: number
  technology_impact: number
  open_science_impact: number
  influence_growth: number
  field_percentile: number
  field_normalized_multiplier: number
  primary_field: string
  raw_metrics: RawImpactMetrics
  main_drivers: string[]
  methodology: string
}

// 2. Career Intelligence
export type BreakthroughMoment = {
  year: number
  growth_pct: number
  papers_in_year: number
  new_coauthors: number
  focus_topic: string
  signals: string[]
  description: string
}

export type TopicTransitionEra = {
  era_name: string
  start_year: number
  end_year: number
  primary_focus: string
  description: string
}

export type CareerIntelligence = {
  career_stage: string
  career_stage_description: string
  career_span_years: number
  first_year: number
  latest_year: number
  peak_year: number
  peak_papers: number
  breakthrough_moments: BreakthroughMoment[]
  topic_transitions: TopicTransitionEra[]
  narrative: string
}

// 3. Researcher Similarity
export type SimilarResearcher = {
  author_id: number
  name: string
  similarity_score: number
  papers: number
  h_index: number
  total_citations: number
  institution: string
  primary_topic: string
  topic_overlap_pct: number
  venue_overlap_pct: number
  reasons: string[]
  shared_topics: string[]
  shared_venues: string[]
}

// 4. Field Normalization
export type ResearchField = {
  field_id: number
  name: string
  slug: string
  description: string
  icon: string
}

export type FieldStatistics = {
  field_id: number
  field_name: string
  publication_count: number
  author_count: number
  total_citations: number
  avg_citations_per_paper: number
  avg_citations_per_author: number
  avg_publications_per_author: number
  avg_growth_rate: number
  avg_authors_per_paper: number
}

export type FieldNormalizedAuthor = {
  author_id: number
  name: string
  papers: number
  total_citations: number
  h_index: number
  citation_velocity: number
  primary_field: string
  field_adjusted_impact: number
  field_adjusted_productivity: number
  field_percentile: number
  raw_rank?: number | null
  normalized_rank?: number | null
}

// 6. Benchmarking
export type BenchmarkMetric = {
  metric_name: string
  label: string
  entity1_value: number
  entity2_value: number
  entity1_display: string
  entity2_display: string
  advantage: string
  advantage_pct?: number | null
}

export type BenchmarkSpecialization = {
  topic_name: string
  category: string
  entity1_share: number
  entity2_share: number
}

export type BenchmarkPreset = {
  id: string
  type: string
  name: string
  entity1_id: string
  entity2_id: string
  description: string
}

export type BenchmarkReport = {
  comparison_type: string
  entity1_id: string
  entity1_name: string
  entity2_id: string
  entity2_name: string
  period: string
  executive_summary: string
  metrics: BenchmarkMetric[]
  specializations: BenchmarkSpecialization[]
  top_scholars_entity1: { author_id: number; name: string; papers: number; citations?: number }[]
  top_scholars_entity2: { author_id: number; name: string; papers: number; citations?: number }[]
}

// 7. Data Quality & Trust
export type DatabaseHealth = {
  total_publications: number
  total_authors: number
  total_venues: number
  total_collaborations: number
  active_years_span: string
  last_updated: string
  storage_engine: string
  dataset_source: string
}

export type MetadataCompletenessAudit = {
  dimension: string
  metric: string
  completeness_percentage: number
  status: string
}

export type MetricFormulaDoc = {
  metric_id: string
  name: string
  formula: string
  inputs: string[]
  interpretation: string
  baseline: string
  limitations: string
  confidence_level: string
}

export type ExternalSourceCoverage = {
  source_name: string
  category: string
  coverage_pct: number
  records_count: string
  sync_status: string
  last_synced: string
}

export type ConflictResolutionItem = {
  metric: string
  sources_compared: string[]
  discrepancy_rate: string
  resolution_strategy: string
}

export type DataQualityResponse = {
  health: DatabaseHealth
  audits: MetadataCompletenessAudit[]
  formulas: MetricFormulaDoc[]
  external_sources?: ExternalSourceCoverage[]
  source_conflicts?: ConflictResolutionItem[]
}

// 8. Semantic Search
export type SemanticSearchItem = {
  entity_type: string
  entity_id: number
  title: string
  subtitle?: string | null
  year?: number | null
  venue?: string | null
  citations?: number | null
  relevance_score: number
  match_type: string
  href: string
}

export type SemanticSearchResponse = {
  query: string
  total_results: number
  papers: SemanticSearchItem[]
  researchers: SemanticSearchItem[]
  institutions: SemanticSearchItem[]
  topics: SemanticSearchItem[]
  top_matches: SemanticSearchItem[]
}

export type AssistantStatus = 'answered' | 'ambiguous' | 'not_found' | 'insufficient_evidence' | 'outside_scope' | 'unavailable'
export type AssistantResponse = {
  status: AssistantStatus
  answer: string
  request_id: string
  limitation_code?: string | null
  sources: { kind: 'author' | 'venue' | 'paper' | 'topic'; id: number; title: string; href: string; detail?: string | null; abstract?: string | null }[]
  calculations: { description: string; filters: Record<string, unknown>; database_version: string; result: Record<string, unknown> }[]
  claims: { claim_id: string; text: string; source_refs: string[]; calculation_refs: number[] }[]
  is_all_papers?: boolean
  export_query?: string | null
}

// 9. Predictive Research Forecasting Engine
export type TopicForecast = {
  topic_id: number
  topic_name: string
  category: string
  publication_growth: number
  growth_acceleration: number
  researcher_inflow: number
  new_researchers_count: number
  citation_momentum: number
  venue_adoption_level: string
  collaboration_expansion: number
  opportunity_score: number
  trend_status: string
  forecast_summary: string
  strategic_recommendation: string
}

export type BreakoutResearcher = {
  author_id: number
  name: string
  momentum_score: number
  velocity_multiplier: number
  primary_topic: string
  papers: number
  citations: number
  career_stage: string
  acceleration_reason: string
}

export type ForecastOverviewResponse = {
  forecast_horizon: string
  total_topics_monitored: number
  macro_outlook: string
  emerging_fields: TopicForecast[]
  declining_fields: TopicForecast[]
  accelerating_fields: TopicForecast[]
  breakout_researchers: BreakoutResearcher[]
}

// 10. Paper Citation Lineage & Idea Evolution
export type LineageNode = {
  id: string
  publication_id: number
  title: string
  year: number
  authors: string[]
  venue?: string | null
  citations: number
  influential_citations: number
  topic?: string | null
  impact_score: number
  era: string
  role: string
}

export type LineageEdge = {
  source: string
  target: string
  citation_year: number
  citation_strength: number
  influence_type: string
}

export type LineageFoundationalRoot = {
  publication_id: number
  title: string
  year: number
  lead_author: string
  citations: number
  centrality_score: number
  why_foundational: string
}

export type PaperLineageResponse = {
  target_publication_id: number
  target_title: string
  target_year: number
  total_ancestors: number
  total_descendants: number
  foundational_roots: LineageFoundationalRoot[]
  lineage_summary: string
  nodes: LineageNode[]
  edges: LineageEdge[]
  eras: { era: string; count: number; color: string }[]
}

const GET_CACHE_TTL_MS = 60_000
const GET_CACHE_MAX_ENTRIES = 128
const getCache = new Map<string, { expiresAt: number; value: unknown }>()

export async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const cached = getCache.get(path)
  if (cached && cached.expiresAt > Date.now()) {
    getCache.delete(path)
    getCache.set(path, cached)
    return cached.value as T
  }
  if (cached) getCache.delete(path)

  const res = await fetch(`${API}${path}`, { signal })
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${res.status}). Please try again.`)
  }
  const value = await res.json() as T
  getCache.set(path, { expiresAt: Date.now() + GET_CACHE_TTL_MS, value })
  while (getCache.size > GET_CACHE_MAX_ENTRIES) {
    getCache.delete(getCache.keys().next().value as string)
  }
  return value
}

export async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal
  })
  if (!res.ok) {
    const data = await res.json().catch(() => null)
    throw new Error(typeof data?.detail === 'string' ? data.detail : `Request failed (${res.status}).`)
  }
  return res.json()
}

export const api = {
  assistantQuery: (query: string, signal?: AbortSignal) => post<AssistantResponse>('/api/assistant/query', { query }, signal),
  assistantQueryStream: async (
    query: string,
    onInit: (initData: { status: AssistantStatus; request_id: string; sources: AssistantResponse['sources']; calculations: AssistantResponse['calculations']; is_all_papers?: boolean; export_query?: string | null }) => void,
    onToken: (token: string) => void,
    onStatus?: (status: string) => void,
    signal?: AbortSignal
  ) => {
    const res = await fetch(`${API}/api/assistant/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
      signal,
    })
    if (!res.ok) {
      throw new Error(`Stream request failed: ${res.statusText}`)
    }
    const reader = res.body?.getReader()
    if (!reader) throw new Error('No readable stream available')
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data: ')) {
          try {
            const data = JSON.parse(trimmed.slice(6))
            if (data.type === 'status' && onStatus) {
              onStatus(data.message)
            } else if (data.type === 'init') {
              onInit(data)
            } else if (data.type === 'token') {
              onToken(data.token)
            }
          } catch {
            // ignore partial chunk json errors
          }
        }
      }
    }
  },
  exportAssistantCatalog: async (query: string, format: 'xlsx' | 'csv' = 'xlsx'): Promise<void> => {
    const urlParam = encodeURIComponent(query)
    const res = await fetch(`${API}/api/assistant/export-catalog?query=${urlParam}&format=${format}`)
    if (!res.ok) {
      throw new Error(`Failed to download ${format.toUpperCase()} catalog: ${res.statusText}`)
    }
    const blob = await res.blob()
    const blobUrl = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    const safeName = query.replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 40).replace(/^_+|_+$/g, '') || 'papers'
    a.download = `dblp_${safeName}.${format}`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(blobUrl)
    document.body.removeChild(a)
  },
  exportAssistantExcel: async (query: string): Promise<void> => {
    const urlParam = encodeURIComponent(query)
    const res = await fetch(`${API}/api/assistant/export-catalog?query=${urlParam}&format=xlsx`)
    if (!res.ok) {
      throw new Error(`Failed to download Excel catalog: ${res.statusText}`)
    }
    const blob = await res.blob()
    const blobUrl = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    const safeName = query.replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 40).replace(/^_+|_+$/g, '') || 'papers'
    a.download = `dblp_${safeName}.xlsx`
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(blobUrl)
    document.body.removeChild(a)
  },
  overview: (signal?: AbortSignal) => get<Overview>('/api/overview', signal),
  timeline: (signal?: AbortSignal) => get<TimelinePoint[]>('/api/publications/timeline', signal),
  publicationGrowth: (signal?: AbortSignal) => get<PublicationGrowthPoint[]>('/api/publications/growth', signal),
  types: (signal?: AbortSignal) => get<PublicationType[]>('/api/publications/types', signal),
  typesTimeline: (signal?: AbortSignal) => get<PublicationTypeTimelinePoint[]>('/api/publications/types/timeline', signal),
  authors: (signal?: AbortSignal) => get<Author[]>('/api/authors/top?limit=10', signal),
  researchersCatalog: (params?: { q?: string; career_stage?: string; min_publications?: number; sort_by?: ResearcherSort; order?: 'asc' | 'desc'; limit?: number; offset?: number }, signal?: AbortSignal) => {
    const q = new URLSearchParams()
    if (params?.q) q.set('q', params.q)
    if (params?.career_stage) q.set('career_stage', params.career_stage)
    if (params?.min_publications) q.set('min_publications', String(params.min_publications))
    if (params?.sort_by) q.set('sort_by', params.sort_by)
    if (params?.order) q.set('order', params.order)
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.offset) q.set('offset', String(params.offset))
    return get<ResearcherCatalogPage>(`/api/authors/catalog?${q}`, signal)
  },
  authorsTop: (limit = 50, signal?: AbortSignal) => get<Author[]>(`/api/authors/top?limit=${limit}`, signal),
  authorsCollaborative: (limit = 50, signal?: AbortSignal) => get<AuthorRankingItem[]>(`/api/authors/collaborative?limit=${limit}`, signal),
  authorsLongestActive: (limit = 50, signal?: AbortSignal) => get<AuthorRankingItem[]>(`/api/authors/longest-active?limit=${limit}`, signal),
  authorsProductivityScatter: (signal?: AbortSignal) => get<AuthorScatterPoint[]>('/api/authors/productivity-scatter', signal),
  venues: (signal?: AbortSignal) => get<Venue[]>('/api/venues/top?limit=10', signal),
  venuesTop: (limit = 50, sort: 'papers' | 'name' = 'papers', order: 'asc' | 'desc' = 'desc', signal?: AbortSignal) => get<Venue[]>(`/api/venues/top?limit=${limit}&sort=${sort}&order=${order}`, signal),
  author: (id: string | number, signal?: AbortSignal) => get<AuthorProfile>(`/api/authors/${id}`, signal),
  venue: (id: string | number, signal?: AbortSignal) => get<VenueProfile>(`/api/venues/${id}`, signal),
  search: (q: string, signal?: AbortSignal) => get<SearchResults>(`/api/search?q=${encodeURIComponent(q)}`, signal),
  authorSuggestions: (q: string, limit = 8, signal?: AbortSignal) => get<Author[]>(`/api/authors/suggest?q=${encodeURIComponent(q)}&limit=${limit}`, signal),
  decades: (signal?: AbortSignal) => get<Decade[]>('/api/trends/decades', signal),
  collaborationEvolution: (signal?: AbortSignal) => get<CollaborationEvolutionPoint[]>('/api/trends/collaboration-evolution', signal),
  teamDistribution: (signal?: AbortSignal) => get<TeamDistribution[]>('/api/trends/team-distribution', signal),
  networkStats: (signal?: AbortSignal) => get<NetworkStats>('/api/network/stats', signal),
  insights: (signal?: AbortSignal) => get<Insights>('/api/insights', signal),
  growth: (kind: 'authors' | 'venues', sort: SortKey, order: Order, offset: number, signal?: AbortSignal) =>
    get<GrowthPage>(`/api/${kind}/${kind === 'authors' ? 'rising' : 'growth'}?sort=${sort}&order=${order}&offset=${offset}&limit=20`, signal),
  venueTrends: (venues: string, signal?: AbortSignal) =>
    get<{ year: number; venue: string; count: number }[]>(`/api/venues/trends?venues=${encodeURIComponent(venues)}`, signal),
  venueHeatmap: (params?: { venues?: string; start_year?: number; end_year?: number }, signal?: AbortSignal) => {
    const q = new URLSearchParams()
    if (params?.venues) q.set('venues', params.venues)
    if (params?.start_year) q.set('start_year', String(params.start_year))
    if (params?.end_year) q.set('end_year', String(params.end_year))
    return get<VenueHeatmapPoint[]>(`/api/venues/heatmap?${q}`, signal)
  },
  graph: (params: URLSearchParams, signal?: AbortSignal) => get<Graph>(`/api/collaboration?${params}`, signal),
  bridge: (source: number, target: number, maxHops = 5, signal?: AbortSignal) => get<BridgeResponse>(`/api/bridge?source=${source}&target=${target}&max_hops=${maxHops}`, signal),

  // Topic Intelligence
  topics: (params?: { sort?: string; order?: string; category?: string; limit?: number }, signal?: AbortSignal) => {
    const q = new URLSearchParams()
    if (params?.sort) q.set('sort', params.sort)
    if (params?.order) q.set('order', params.order)
    if (params?.category) q.set('category', params.category)
    if (params?.limit) q.set('limit', String(params.limit))
    return get<Topic[]>(`/api/topics?${q}`, signal)
  },
  topicTimeline: (params?: { topics?: string; start_year?: number; end_year?: number }, signal?: AbortSignal) => {
    const q = new URLSearchParams()
    if (params?.topics) q.set('topics', params.topics)
    if (params?.start_year) q.set('start_year', String(params.start_year))
    if (params?.end_year) q.set('end_year', String(params.end_year))
    return get<TopicTimelinePoint[]>(`/api/topics/timeline?${q}`, signal)
  },
  topic: (id: string | number, signal?: AbortSignal) => get<TopicProfile>(`/api/topics/${id}`, signal),

  // Institutions
  institutions: (params?: { sort?: string; order?: string; country?: string; type?: string; limit?: number }, signal?: AbortSignal) => {
    const q = new URLSearchParams()
    if (params?.sort) q.set('sort', params.sort)
    if (params?.order) q.set('order', params.order)
    if (params?.country) q.set('country', params.country)
    if (params?.type) q.set('type', params.type)
    if (params?.limit) q.set('limit', String(params.limit))
    return get<Institution[]>(`/api/institutions?${q}`, signal)
  },
  institution: (id: string | number, signal?: AbortSignal) => get<InstitutionProfile>(`/api/institutions/${id}`, signal),

  // Author Momentum & Impact
  authorsMomentum: (params?: { limit?: number; offset?: number; sort_by?: string; order?: string; career_stage?: string }, signal?: AbortSignal) => {
    const q = new URLSearchParams()
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.offset) q.set('offset', String(params.offset))
    if (params?.sort_by) q.set('sort_by', params.sort_by)
    if (params?.order) q.set('order', params.order)
    if (params?.career_stage) q.set('career_stage', params.career_stage)
    return get<AuthorMomentumPage>(`/api/authors/momentum?${q}`, signal)
  },
  authorsMostCited: (limit = 50, signal?: AbortSignal) => get<AuthorImpactItem[]>(`/api/authors/most-cited?limit=${limit}`, signal),
  authorsHighestImpact: (limit = 50, signal?: AbortSignal) => get<AuthorImpactItem[]>(`/api/authors/highest-impact?limit=${limit}`, signal),

  // Publications Search & Detail
  publicationsSearch: (params?: { q?: string; author_id?: number; topic_id?: number; venue_id?: number; start_year?: number; end_year?: number; sort_by?: string; sort_order?: 'asc' | 'desc'; limit?: number; offset?: number }, signal?: AbortSignal) => {
    const q = new URLSearchParams()
    if (params?.q) q.set('q', params.q)
    if (params?.author_id) q.set('author_id', String(params.author_id))
    if (params?.topic_id) q.set('topic_id', String(params.topic_id))
    if (params?.venue_id) q.set('venue_id', String(params.venue_id))
    if (params?.start_year) q.set('start_year', String(params.start_year))
    if (params?.end_year) q.set('end_year', String(params.end_year))
    if (params?.sort_by) q.set('sort_by', params.sort_by)
    if (params?.sort_order) q.set('sort_order', params.sort_order)
    if (params?.limit) q.set('limit', String(params.limit))
    if (params?.offset) q.set('offset', String(params.offset))
    return get<PublicationSearchResponse>(`/api/publications/search?${q}`, signal)
  },
  publication: (id: string | number, signal?: AbortSignal) => get<PublicationDetail>(`/api/publications/${id}`, signal),

  // Strategic Intelligence — Impact, Career, Similarity
  authorImpact: (id: string | number, signal?: AbortSignal) => get<ImpactProfile>(`/api/authors/${id}/impact`, signal),
  authorCareer: (id: string | number, signal?: AbortSignal) => get<CareerIntelligence>(`/api/authors/${id}/career`, signal),
  authorSimilar: (id: string | number, limit = 6, signal?: AbortSignal) => get<SimilarResearcher[]>(`/api/authors/${id}/similar?limit=${limit}`, signal),
  authorsFieldNormalized: (limit = 50, fieldId?: number, signal?: AbortSignal) =>
    get<FieldNormalizedAuthor[]>(`/api/authors/field-normalized?limit=${limit}${fieldId ? `&field_id=${fieldId}` : ''}`, signal),

  // Field Intelligence
  fields: (signal?: AbortSignal) => get<FieldStatistics[]>('/api/fields', signal),
  fieldDefinitions: (signal?: AbortSignal) => get<ResearchField[]>('/api/fields/definitions', signal),
  fieldDetail: (id: string | number, signal?: AbortSignal) => get<{ field: FieldStatistics; topics: any[]; top_venues: Venue[]; top_institutions: any[] }>(`/api/fields/${id}`, signal),

  // Benchmarking Mode
  benchmarkPresets: (signal?: AbortSignal) => get<BenchmarkPreset[]>('/api/benchmark/presets', signal),
  benchmarkCompare: (params: { type: string; entity1: string; entity2: string; topic_id?: number }, signal?: AbortSignal) => {
    const q = new URLSearchParams({ type: params.type, entity1: params.entity1, entity2: params.entity2 })
    if (params.topic_id) q.set('topic_id', String(params.topic_id))
    return get<BenchmarkReport>(`/api/benchmark/compare?${q}`, signal)
  },

  // Data Quality & Trust
  dataQuality: (signal?: AbortSignal) => get<DataQualityResponse>('/api/data-quality', signal),
  dataQualityHealth: (signal?: AbortSignal) => get<DatabaseHealth>('/api/data-quality/health', signal),
  dataQualityTransparency: (signal?: AbortSignal) => get<MetricFormulaDoc[]>('/api/data-quality/transparency', signal),

  // Predictive Research Forecasting
  forecastOverview: (signal?: AbortSignal) => get<ForecastOverviewResponse>('/api/forecast/overview', signal),
  topicForecast: (id: string | number, signal?: AbortSignal) => get<TopicForecast>(`/api/forecast/topic/${id}`, signal),
  breakoutResearchers: (limit = 10, signal?: AbortSignal) => get<BreakoutResearcher[]>(`/api/forecast/breakout-researchers?limit=${limit}`, signal),

  // Paper Citation Lineage
  publicationLineage: (id: string | number, signal?: AbortSignal) => get<PaperLineageResponse>(`/api/publications/${id}/lineage`, signal),

  // Semantic Hybrid Search
  semanticSearch: (query: string, limit = 10, signal?: AbortSignal) =>
    get<SemanticSearchResponse>(`/api/search/semantic?q=${encodeURIComponent(query)}&limit=${limit}`, signal)
}
