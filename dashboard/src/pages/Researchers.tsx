import { useEffect, useState } from 'react'
import {
  api,
  type Overview,
  type ResearcherCatalogItem,
  type ResearcherCatalogPage,
  type ResearcherSort
} from '../api'
import { ChartCard, PageHeader } from '../components/ChartCard'
import { DataTable } from '../components/DataTable'
import { ExportToolbar } from '../components/ExportToolbar'
import { ShareViewButton } from '../components/ShareViewButton'
import { MetricCard, full } from '../components/MetricCard'
import { useDebouncedValue } from '../hooks/useDebouncedValue'
import './Researchers.css'

type CareerStage = 'All' | 'Early-Career' | 'Mid-Career' | 'Senior'

const SORT_PRESETS: { label: string; key: ResearcherSort }[] = [
  { label: 'Most cited', key: 'total_citations' },
  { label: 'Most published', key: 'papers' },
  { label: 'Highest h-index', key: 'h_index' },
  { label: 'Citation velocity', key: 'citation_velocity' }
]

function highlightedName(name: string, query: string) {
  if (!query) return name
  const index = name.toLocaleLowerCase().indexOf(query.toLocaleLowerCase())
  if (index < 0) return name
  return <>{name.slice(0, index)}<mark>{name.slice(index, index + query.length)}</mark>{name.slice(index + query.length)}</>
}

export default function Researchers() {
  const initialParams = new URLSearchParams(location.search)
  const [query, setQuery] = useState(initialParams.get('q') ?? '')
  const debouncedQuery = useDebouncedValue(query.trim())
  const [careerStage, setCareerStage] = useState<CareerStage>((initialParams.get('career_stage') as CareerStage) || 'All')
  const [minPublications, setMinPublications] = useState(Number(initialParams.get('min_publications') || 1))
  const [sortBy, setSortBy] = useState<ResearcherSort>((initialParams.get('sort_by') as ResearcherSort) || 'total_citations')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>((initialParams.get('order') as 'asc' | 'desc') || 'desc')
  const [offset, setOffset] = useState(Number(initialParams.get('offset') || 0))
  const [limit, setLimit] = useState(Number(initialParams.get('limit') || 20))
  const [filtersOpen, setFiltersOpen] = useState(false)
  const [corpus, setCorpus] = useState<Overview>()
  const [results, setResults] = useState<ResearcherCatalogPage | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    api.overview(controller.signal).then(setCorpus).catch(() => {})
    return () => controller.abort()
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    api.researchersCatalog({
      q: debouncedQuery || undefined,
      career_stage: careerStage,
      min_publications: minPublications,
      sort_by: sortBy,
      order: sortOrder,
      limit,
      offset
    }, controller.signal)
      .then(data => {
        if (!controller.signal.aborted) {
          setResults(data)
          setLoading(false)
        }
      })
      .catch((err: Error) => {
        if (!controller.signal.aborted) {
          setError(err.message || 'The researcher catalogue could not be loaded. Try again.')
          setLoading(false)
        }
      })
    return () => controller.abort()
  }, [debouncedQuery, careerStage, minPublications, sortBy, sortOrder, offset, limit])

  const total = results?.total ?? 0
  const hasFilters = Boolean(query || careerStage !== 'All' || minPublications !== 1)

  useEffect(() => {
    const params = new URLSearchParams()
    if (query) params.set('q', query)
    if (careerStage !== 'All') params.set('career_stage', careerStage)
    if (minPublications !== 1) params.set('min_publications', String(minPublications))
    if (sortBy !== 'total_citations') params.set('sort_by', sortBy)
    if (sortOrder !== 'desc') params.set('order', sortOrder)
    if (limit !== 20) params.set('limit', String(limit))
    if (offset) params.set('offset', String(offset))
    const next = `${location.pathname}${params.toString() ? `?${params}` : ''}`
    if (next !== `${location.pathname}${location.search}`) history.replaceState({}, '', next)
  }, [query, careerStage, minPublications, sortBy, sortOrder, offset, limit])

  useEffect(() => {
    const restore = () => {
      const params = new URLSearchParams(location.search)
      setQuery(params.get('q') ?? '')
      setCareerStage((params.get('career_stage') as CareerStage) || 'All')
      setMinPublications(Number(params.get('min_publications') || 1))
      setSortBy((params.get('sort_by') as ResearcherSort) || 'total_citations')
      setSortOrder((params.get('order') as 'asc' | 'desc') || 'desc')
      setOffset(Number(params.get('offset') || 0))
      setLimit(Number(params.get('limit') || 20))
    }
    window.addEventListener('popstate', restore)
    return () => window.removeEventListener('popstate', restore)
  }, [])

  const resetFilters = () => {
    setQuery('')
    setCareerStage('All')
    setMinPublications(1)
    setOffset(0)
  }

  const changeSort = (key: ResearcherSort) => {
    if (sortBy === key) setSortOrder(current => current === 'desc' ? 'asc' : 'desc')
    else {
      setSortBy(key)
      setSortOrder(key === 'name' ? 'asc' : 'desc')
    }
    setOffset(0)
  }

  return (
    <div className="researchers-page">
      <PageHeader
        title="Researchers"
        description="Browse computer science researchers by publication record and citation evidence, or search for a specific name."
      >
        <ShareViewButton />
        <ExportToolbar title="dblp-researchers-catalog" showPrint={true} />
      </PageHeader>

      <div className="metric-strip">
        <MetricCard label="Researchers" value={corpus ? full(corpus.total_authors) : 'N/A'} detail="Distinct indexed author identities" />
        <MetricCard label="Publications" value={corpus ? full(corpus.total_publications) : 'N/A'} detail="Corpus records connected to researchers" />
        <MetricCard label="Matching researchers" value={full(total)} detail="Names and filters in the current result set" />
        <MetricCard
          label="Visible records"
          value={total ? `${offset + 1}–${Math.min(offset + limit, total)}` : '0'}
          detail={`Sorted ${sortOrder === 'desc' ? 'high to low' : 'low to high'}`}
        />
      </div>

      <section className="papers-filter-controls" aria-label="Researcher search and filters">
        <div className="papers-search-input-box">
          <span className="search-symbol" aria-hidden="true">⌕</span>
          <input
            type="search"
            className="papers-search-field"
            aria-label="Search researchers by name"
            placeholder="Search researchers by name"
            value={query}
            onChange={event => { setQuery(event.target.value); setOffset(0) }}
          />
          {query && (
            <button className="papers-clear-btn" type="button" aria-label="Clear researcher search" onClick={() => setQuery('')}>
              ×
            </button>
          )}
        </div>

        <button
          className="filter-toggle"
          type="button"
          aria-expanded={filtersOpen}
          aria-controls="researcher-filters"
          onClick={() => setFiltersOpen(current => !current)}
        >
          Filters {filtersOpen ? '−' : '+'}
        </button>

        <div id="researcher-filters" className="papers-dropdowns-row researcher-dropdowns" data-open={filtersOpen}>
          <label className="select-label">
            <span>Career stage</span>
            <select value={careerStage} onChange={event => { setCareerStage(event.target.value as CareerStage); setOffset(0) }}>
              <option value="All">All career stages</option>
              <option value="Early-Career">Early-career</option>
              <option value="Mid-Career">Mid-career</option>
              <option value="Senior">Senior</option>
            </select>
          </label>
          <label className="select-label">
            <span>Minimum publications</span>
            <select value={minPublications} onChange={event => { setMinPublications(Number(event.target.value)); setOffset(0) }}>
              <option value={1}>At least 1</option>
              <option value={5}>At least 5</option>
              <option value={10}>At least 10</option>
              <option value={25}>At least 25</option>
              <option value={50}>At least 50</option>
            </select>
          </label>
          <label className="select-label">
            <span>Sort direction</span>
            <select value={sortOrder} onChange={event => { setSortOrder(event.target.value as 'asc' | 'desc'); setOffset(0) }}>
              <option value="desc">Highest first</option>
              <option value="asc">Lowest first</option>
            </select>
          </label>
        </div>

        <div className="papers-preset-chips" aria-label="Researcher ranking presets">
          <span className="chips-label">Rank by:</span>
          {SORT_PRESETS.map(preset => (
            <button
              key={preset.key}
              type="button"
              className={`preset-chip ${sortBy === preset.key ? 'is-active' : ''}`}
              onClick={() => { setSortBy(preset.key); setSortOrder('desc'); setOffset(0) }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </section>

      {hasFilters && (
        <div className="active-filters" aria-label="Active researcher filters">
          {query && <button type="button" title={`Remove name filter: ${query}`} onClick={() => setQuery('')}>Name: {query.length > 24 ? `${query.slice(0, 24)}…` : query} ×</button>}
          {careerStage !== 'All' && <button type="button" onClick={() => { setCareerStage('All'); setOffset(0) }}>Career: {careerStage} ×</button>}
          {minPublications !== 1 && <button type="button" onClick={() => { setMinPublications(1); setOffset(0) }}>Minimum: {minPublications} papers ×</button>}
          <button type="button" onClick={resetFilters}>Clear filters</button>
        </div>
      )}

      <ChartCard
        title="Researcher records"
        description={total ? `Displaying ${offset + 1}–${Math.min(offset + limit, total)} of ${full(total)} researchers.` : 'No researchers match this selection.'}
      >
        <span className="sr-only" aria-live="polite">
          {loading ? 'Loading researcher records.' : `${full(total)} researchers found.`}
        </span>
        {loading && (
          <div className="resource-state researchers-loading" role="status">
            <span className="loading-spinner" />
            <p>Loading researcher records…</p>
          </div>
        )}

        {error && !loading && (
          <div className="resource-state error" role="alert">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && results && (
          <DataTable<ResearcherCatalogItem>
            className="papers-table researchers-table"
            rows={results.items}
            rowKey={researcher => researcher.author_id}
            caption="Researchers catalogue"
            pagination={{ total, offset, limit, onChange: (nextOffset, nextLimit) => { setOffset(nextOffset); setLimit(nextLimit) } }}
            sort={{ key: sortBy, order: sortOrder }}
            onSort={key => {
              if (['name', 'papers', 'total_citations', 'h_index', 'avg_citations_per_paper', 'citation_velocity'].includes(key)) {
                changeSort(key as ResearcherSort)
              }
            }}
            columns={[
              {
                key: 'rank',
                label: '#',
                width: '46px',
                render: (_, index) => <span className="numeric-rank">{offset + index + 1}</span>
              },
              {
                key: 'name',
                label: 'Researcher',
                minWidth: '230px',
                render: researcher => (
                  <div className="researcher-identity">
                    <a href={`/authors/${researcher.author_id}`}>{highlightedName(researcher.name, debouncedQuery)}</a>
                    <span>{researcher.institution || researcher.primary_topic || 'Affiliation not available'}</span>
                  </div>
                ),
                value: researcher => researcher.name
              },
              {
                key: 'papers',
                label: 'Publications',
                width: '104px',
                render: researcher => full(researcher.papers),
                value: researcher => researcher.papers,
                numeric: true
              },
              {
                key: 'total_citations',
                label: 'Citations',
                width: '100px',
                render: researcher => <strong>{full(researcher.total_citations)}</strong>,
                value: researcher => researcher.total_citations,
                numeric: true
              },
              {
                key: 'h_index',
                label: 'h-index',
                width: '82px',
                render: researcher => full(researcher.h_index),
                value: researcher => researcher.h_index,
                numeric: true
              },
              {
                key: 'avg_citations_per_paper',
                label: 'Cites / paper',
                width: '112px',
                render: researcher => researcher.avg_citations_per_paper.toFixed(1),
                value: researcher => researcher.avg_citations_per_paper,
                numeric: true
              },
              {
                key: 'citation_velocity',
                label: 'Cites / year',
                width: '104px',
                render: researcher => full(Math.round(researcher.citation_velocity)),
                value: researcher => researcher.citation_velocity,
                numeric: true
              },
              {
                key: 'career',
                label: 'Career',
                width: '126px',
                render: researcher => (
                  <div className="researcher-career">
                    <span>{researcher.career_stage || 'Not classified'}</span>
                    {researcher.career_span ? <small>{researcher.career_span} active years</small> : null}
                  </div>
                )
              },
              {
                key: 'profile',
                label: 'Profile',
                width: '104px',
                align: 'right',
                render: researcher => <a className="paper-inspect-link-btn" href={`/authors/${researcher.author_id}`}>Open profile →</a>
              }
            ]}
          />
        )}
      </ChartCard>
    </div>
  )
}
