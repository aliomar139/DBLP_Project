import { useEffect, useState } from 'react'
import {
  api,
  type PublicationItem,
  type Topic,
  type Overview,
  type PublicationSearchResponse
} from '../api'
import { ChartCard, PageHeader } from '../components/ChartCard'
import { MetricCard, full } from '../components/MetricCard'
import { DataTable } from '../components/DataTable'
import { ExportToolbar } from '../components/ExportToolbar'
import { ShareViewButton } from '../components/ShareViewButton'
import { useDebouncedValue } from '../hooks/useDebouncedValue'

const PRESET_QUERIES = [
  { label: 'All Seminal Works', q: '', topic_id: undefined },
  { label: 'Transformers & LLMs', q: 'attention transformer neural', topic_id: undefined },
  { label: 'Databases', q: 'relational database distributed query', topic_id: undefined },
  { label: 'Quantum Computing', q: 'quantum computing qubits circuits', topic_id: undefined },
  { label: 'Distributed Systems', q: 'distributed operating system consensus', topic_id: undefined },
  { label: 'Cryptography', q: 'cryptography encryption zero knowledge', topic_id: undefined }
]

export default function Papers() {
  const initialParams = new URLSearchParams(location.search)
  const [searchQuery, setSearchQuery] = useState(initialParams.get('q') ?? '')
  const debouncedQuery = useDebouncedValue(searchQuery.trim())
  const [authorQuery, setAuthorQuery] = useState(initialParams.get('author') ?? '')
  const debouncedAuthorQuery = useDebouncedValue(authorQuery.trim())
  const [selectedAuthorId, setSelectedAuthorId] = useState<number | undefined>(initialParams.get('author_id') ? Number(initialParams.get('author_id')) : undefined)
  const [authorSuggestions, setAuthorSuggestions] = useState<{ author_id: number; name: string; papers: number }[]>([])
  const [selectedTopic, setSelectedTopic] = useState<number | undefined>(initialParams.get('topic_id') ? Number(initialParams.get('topic_id')) : undefined)
  const [selectedEra, setSelectedEra] = useState<string>(initialParams.get('era') ?? 'all')
  const [sortBy, setSortBy] = useState<'citations' | 'year' | 'title'>((initialParams.get('sort_by') as 'citations' | 'year' | 'title') || 'citations')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>((initialParams.get('sort_order') as 'asc' | 'desc') || 'desc')
  const [offset, setOffset] = useState(Number(initialParams.get('offset') || 0))
  const [limit, setLimit] = useState(Number(initialParams.get('limit') || 20))
  const [filtersOpen, setFiltersOpen] = useState(false)

  const [corpus,setCorpus] = useState<Overview>()
  const [topics, setTopics] = useState<Topic[]>([])
  const [searchRes, setSearchRes] = useState<PublicationSearchResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (debouncedAuthorQuery.length < 2 || selectedAuthorId) { setAuthorSuggestions([]); return }
    const controller = new AbortController()
    api.authorSuggestions(debouncedAuthorQuery, 8, controller.signal).then(setAuthorSuggestions).catch(() => {})
    return () => controller.abort()
  }, [debouncedAuthorQuery, selectedAuthorId])

  // Load topics list for the filter dropdown
  useEffect(() => {
    api.overview().then(setCorpus).catch(()=>{})
    api.topics()
      .then(setTopics)
      .catch(() => {})
  }, [])

  // Calculate year range from selected era
  let startYear: number | undefined
  let endYear: number | undefined
  if (selectedEra === '2026') {
    startYear = 2026
    endYear = 2026
  } else if (selectedEra === '2020-2026' || selectedEra === '2020+') {
    startYear = 2020
    endYear = 2026
  } else if (selectedEra === 'advance') {
    startYear = 2027
  } else if (selectedEra === '2010-2020') {
    startYear = 2010
    endYear = 2019
  } else if (selectedEra === '2000-2010') {
    startYear = 2000
    endYear = 2009
  } else if (selectedEra === 'pre-2000') {
    endYear = 1999
  }

  // Fetch publications
  useEffect(() => {
    setLoading(true)
    setError(null)
    const controller = new AbortController()

    api.publicationsSearch(
      {
        q: debouncedQuery || undefined,
        author_id: selectedAuthorId,
        topic_id: selectedTopic,
        start_year: startYear,
        end_year: endYear,
        sort_by: sortBy,
        sort_order: sortOrder,
        limit,
        offset
      },
      controller.signal
    )
      .then(res => {
        if (!controller.signal.aborted) {
          setSearchRes(res)
          setLoading(false)
        }
      })
      .catch((err: Error) => {
        if (!controller.signal.aborted) {
          setError(err.message || 'Failed to retrieve publications')
          setLoading(false)
        }
      })

    return () => controller.abort()
  }, [debouncedQuery, selectedAuthorId, selectedEra, selectedTopic, sortBy, sortOrder, offset, limit])

  const total = searchRes?.total ?? 0

  useEffect(() => {
    const params = new URLSearchParams()
    if (searchQuery) params.set('q', searchQuery)
    if (authorQuery) params.set('author', authorQuery)
    if (selectedAuthorId) params.set('author_id', String(selectedAuthorId))
    if (selectedTopic) params.set('topic_id', String(selectedTopic))
    if (selectedEra !== 'all') params.set('era', selectedEra)
    if (sortBy !== 'citations') params.set('sort_by', sortBy)
    if (sortOrder !== 'desc') params.set('sort_order', sortOrder)
    if (limit !== 20) params.set('limit', String(limit))
    if (offset) params.set('offset', String(offset))
    const next = `${location.pathname}${params.toString() ? `?${params}` : ''}`
    if (next !== `${location.pathname}${location.search}`) history.replaceState({}, '', next)
  }, [searchQuery, authorQuery, selectedAuthorId, selectedTopic, selectedEra, sortBy, sortOrder, offset, limit])

  useEffect(() => {
    const restore = () => {
      const params = new URLSearchParams(location.search)
      setSearchQuery(params.get('q') ?? '')
      setAuthorQuery(params.get('author') ?? '')
      setSelectedAuthorId(params.get('author_id') ? Number(params.get('author_id')) : undefined)
      setSelectedTopic(params.get('topic_id') ? Number(params.get('topic_id')) : undefined)
      setSelectedEra(params.get('era') ?? 'all')
      setSortBy((params.get('sort_by') as 'citations' | 'year' | 'title') || 'citations')
      setSortOrder((params.get('sort_order') as 'asc' | 'desc') || 'desc')
      setOffset(Number(params.get('offset') || 0))
      setLimit(Number(params.get('limit') || 20))
    }
    window.addEventListener('popstate', restore)
    return () => window.removeEventListener('popstate', restore)
  }, [])

  return (
    <div className="papers-page">
      <PageHeader
        title="Papers"
        description="Search and inspect 8.7M Computer Science publications: analyze citation trajectories, trace idea lineages, filter by research field, and explore foundational roots."
      >
        <ShareViewButton />
        <ExportToolbar title="dblp-publications-catalog" showPrint={true} />
      </PageHeader>

      {/* Metric Strip */}
      <div className="metric-strip">
        <MetricCard label="Papers" value={corpus ? full(corpus.total_publications) : "N/A"} detail="Papers in the computer science records" />
        <MetricCard label="Publication venues" value={corpus ? full(corpus.total_venues) : "N/A"} detail="Conferences and journals" />
        <MetricCard label="Years covered" value={corpus ? `${corpus.first_year} to ${corpus.last_year}` : "N/A"} detail={corpus ? `${corpus.active_years} years with publications` : "Loading publication dates"} />
        <MetricCard label="Matching papers" value={full(total)} detail="Papers that match your filters" />
      </div>

      {/* Filter and Search Bar */}
      <div className="papers-filter-controls">
        <div className="papers-search-input-box">
          <span className="search-symbol">⌕</span>
          <input
            type="search"
            className="papers-search-field"
            aria-label="Search publication titles"
            placeholder="Search paper titles by keyword"
            value={searchQuery}
            onChange={e => {
              setSearchQuery(e.target.value)
              setOffset(0)
            }}
          />
          {searchQuery && (
            <button
              type="button"
              className="papers-clear-btn"
              aria-label="Clear publication search"
              onClick={() => {
                setSearchQuery('')
                setOffset(0)
              }}
            >
              ✕
            </button>
          )}
        </div>

        <button className="filter-toggle" aria-expanded={filtersOpen} aria-controls="paper-filters" onClick={() => setFiltersOpen(!filtersOpen)}>Filters {filtersOpen ? "−" : "+"}</button>
        <div id="paper-filters" className="papers-dropdowns-row" data-open={filtersOpen}>
          <label className="select-label author-filter-label">
            <span>Researcher:</span>
            <div className="author-filter-control">
              <input
                type="search"
                placeholder="Search by author name"
                value={authorQuery}
                onKeyDown={e => {
                  if (e.key === 'Enter' && authorSuggestions[0]) {
                    e.preventDefault()
                    const author = authorSuggestions[0]
                    setAuthorQuery(author.name)
                    setSelectedAuthorId(author.author_id)
                    setAuthorSuggestions([])
                    setOffset(0)
                  }
                }}
                onChange={e => { setAuthorQuery(e.target.value); setSelectedAuthorId(undefined); setOffset(0) }}
              />
              {authorSuggestions.length > 0 && <div className="author-suggestions">
                {authorSuggestions.map(author => <button type="button" key={author.author_id} onClick={() => { setAuthorQuery(author.name); setSelectedAuthorId(author.author_id); setAuthorSuggestions([]); setOffset(0) }}>
                  <span>{author.name}</span><small>{author.papers.toLocaleString()} papers</small>
                </button>)}
              </div>}
            </div>
          </label>
          <label className="select-label">
            <span>Research Discipline:</span>
            <select
              value={selectedTopic ?? ''}
              onChange={e => {
                setSelectedTopic(e.target.value ? Number(e.target.value) : undefined)
                setOffset(0)
              }}
            >
              <option value="">All CS Topics ({topics.length})</option>
              {topics.map(t => (
                <option key={t.topic_id} value={t.topic_id}>
                  {t.topic_name} ({t.category})
                </option>
              ))}
            </select>
          </label>

          <label className="select-label">
            <span>Time Horizon:</span>
            <select
              value={selectedEra}
              onChange={e => {
                setSelectedEra(e.target.value)
                setOffset(0)
              }}
            >
              <option value="all">All Historical Eras (1936–2027)</option>
              <option value="2026">Current Year (2026)</option>
              <option value="2020-2026">Recent Frontier (2020–2026)</option>
              <option value="advance">Forthcoming / Advance (2027+)</option>
              <option value="2010-2020">Deep Learning Era (2010–2019)</option>
              <option value="2000-2010">Web & Data Era (2000–2009)</option>
              <option value="pre-2000">Foundational Era (Pre-2000)</option>
            </select>
          </label>

          <label className="select-label">
            <span>Rank By:</span>
            <select
              value={sortBy}
              onChange={e => {
                setSortBy(e.target.value as 'citations' | 'year')
                setSortOrder('desc')
                setOffset(0)
              }}
            >
              <option value="citations">Most Cited Papers</option>
              <option value="recent">Most Recent Publications</option>
            </select>
          </label>
        </div>

        {/* Quick-Filter Preset Chips */}
        <div className="papers-preset-chips" aria-label="Curated research queries">
          <span className="chips-label">Presets:</span>
          {PRESET_QUERIES.map(p => (
            <button
              key={p.label}
              type="button"
              className={`preset-chip ${searchQuery === p.q && selectedTopic === p.topic_id ? 'is-active' : ''}`}
              onClick={() => {
                setSearchQuery(p.q)
                setSelectedTopic(p.topic_id)
                setOffset(0)
              }}
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {(searchQuery || selectedAuthorId || selectedTopic || selectedEra !== 'all') && <div className="active-filters" aria-label="Active publication filters">
        {searchQuery && <button onClick={()=>{setSearchQuery('');setOffset(0)}}>Keyword: {searchQuery} ×</button>}
        {selectedAuthorId && <button onClick={()=>{setAuthorQuery('');setSelectedAuthorId(undefined);setOffset(0)}}>Author: {authorQuery} ×</button>}
        {selectedTopic && <button onClick={()=>{setSelectedTopic(undefined);setOffset(0)}}>Topic: {topics.find(t=>t.topic_id===selectedTopic)?.topic_name} ×</button>}
        {selectedEra !== 'all' && <button onClick={()=>{setSelectedEra('all');setOffset(0)}}>Era: {selectedEra} ×</button>}
        <button onClick={()=>{setSearchQuery('');setAuthorQuery('');setSelectedAuthorId(undefined);setSelectedTopic(undefined);setSelectedEra('all');setOffset(0)}}>Clear filters</button>
      </div>}
      {/* Main Results Table */}
      <ChartCard
        title="Publication records"
        description={
          total > 0
            ? `Displaying ${offset + 1}–${Math.min(offset + limit, total)} of ${total.toLocaleString()} publications.`
            : 'No matching publications found.'
        }
      >
        {loading && (
          <div className="resource-state" style={{ minHeight: '200px' }}>
            <span className="loading-spinner" />
            <p>Searching the publication records and calculating rankings...</p>
          </div>
        )}

        {error && !loading && (
          <div className="resource-state error">
            <p>{error}</p>
          </div>
        )}

        {!loading && !error && searchRes && (
          <>
            <DataTable<PublicationItem>
              className="papers-table"
              rows={searchRes.items}
              rowKey={p => p.publication_id}
              caption="Publications Catalog"
              pagination={{total, offset, limit, onChange:(next,size)=>{setOffset(next);setLimit(size)}}}
              sort={{ key: sortBy, order: sortOrder }}
              onSort={key => {
                if (key !== 'citations' && key !== 'year' && key !== 'title') return
                if (sortBy === key) setSortOrder(current => current === 'desc' ? 'asc' : 'desc')
                else { setSortBy(key); setSortOrder('desc') }
                setOffset(0)
              }}
              columns={[
                {
                  key: 'rank',
                  label: '#',
                  width: '38px',
                  render: (_, i) => <span className="numeric-rank">{offset + i + 1}</span>
                },
                {
                  key: 'title',
                  label: 'Publication Title',
                  render: p => (
                    <div className="paper-table-title-cell">
                      <a className="paper-table-link" href={`/papers/${p.publication_id}`}>
                        <strong>{p.title}</strong>
                      </a>
                      <div className="paper-table-submeta">
                        {p.type && <span className="paper-type-tag" data-type={p.type?.toLowerCase()}>{p.type}</span>}
                        {p.venue_name && (
                          <a className="paper-venue-link" href={p.venue_id ? `/venues/${p.venue_id}` : undefined}>
                            {p.venue_name}
                          </a>
                        )}
                      </div>
                    </div>
                  ),
                  value: p => p.title
                },
                {
                  key: 'authors',
                  label: 'Authors',
                  width: '180px',
                  render: p => (
                    <div className="paper-table-authors">
                      {p.authors.length ? (
                        p.authors.map(a => (
                          <a key={a.author_id} className="author-table-pill" href={`/authors/${a.author_id}`}>
                            {a.name}
                          </a>
                        ))
                      ) : (
                        <span style={{ color: 'var(--muted)', fontSize: '11px' }}>N/A</span>
                      )}
                    </div>
                  )
                },
                {
                  key: 'year',
                  label: 'Year',
                  width: '64px',
                  render: p => <span className="numeric">{p.year ?? 'N/A'}</span>,
                  value: p => p.year ?? 0,
                  numeric: true
                },
                {
                  key: 'citations',
                  label: 'Citations',
                  width: '80px',
                  render: p => (
                    <div className="numeric-citations">
                      <strong>{full(p.citations)}</strong>
                    </div>
                  ),
                  value: p => p.citations,
                  numeric: true
                },
                {
                  key: 'topics',
                  label: 'Field / Topic',
                  width: '115px',
                  render: p => (
                    <div className="paper-table-topics">
                      {p.topics && p.topics.length ? (
                        p.topics.slice(0, 2).map(t => (
                          <a key={t.topic_id} className="topic-table-pill" href={`/topics/${t.topic_id}`}>
                            {t.topic_name}
                          </a>
                        ))
                      ) : (
                        <span style={{ color: 'var(--muted)', fontSize: '11px' }}>General CS</span>
                      )}
                    </div>
                  )
                },
                {
                  key: 'action',
                  label: 'Lineage',
                  width: '135px',
                  align: 'right',
                  render: p => (
                    <a className="paper-inspect-link-btn" href={`/papers/${p.publication_id}`}>
                      Inspect Lineage →
                    </a>
                  )
                }
              ]}
            />

          </>
        )}
      </ChartCard>
    </div>
  )
}

