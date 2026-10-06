import { useEffect, useRef, useState } from 'react'
import { api, type Author, type SearchResults, type SemanticSearchResponse } from '../api'
import { full } from './MetricCard'

export function SearchBar({
  onAuthor,
  label = 'Search researchers, venues, and papers...',
  authorOnly = false
}: {
  onAuthor?: (author: Author) => void
  label?: string
  authorOnly?: boolean
}) {
  const [q, setQ] = useState('')
  const [data, setData] = useState<SearchResults>()
  const [semanticData, setSemanticData] = useState<SemanticSearchResponse>()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<'all' | 'authors' | 'venues' | 'papers' | 'semantic'>('all')
  const root = useRef<HTMLDivElement>(null)
  const semanticMode = tab === 'semantic'

  useEffect(() => {
    setData(undefined)
    setSemanticData(undefined)
    setError('')
    setBusy(false)
    if (q.trim().length < (authorOnly ? 1 : 2)) return

    const controller = new AbortController()
    setBusy(true)

    const timer = setTimeout(() => {
      if (semanticMode) {
        api.semanticSearch(q.trim(), 10, controller.signal)
          .then(sd => {
            if (!controller.signal.aborted) {
              setSemanticData(sd)
              setBusy(false)
            }
          })
          .catch((e: Error) => {
            if (!controller.signal.aborted) {
              setError(e.message)
              setBusy(false)
            }
          })
      } else {
        const request = authorOnly
          ? api.authorSuggestions(q.trim(), 8, controller.signal).then(authors => ({ authors, venues: [], papers_available: false }))
          : api.search(q.trim(), controller.signal)
        request
          .then(d => {
            if (!controller.signal.aborted) {
              setData(d)
              setBusy(false)
            }
          })
          .catch((e: Error) => {
            if (!controller.signal.aborted) {
              setError(e.message)
              setBusy(false)
            }
          })
      }
    }, 250)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [q, semanticMode, authorOnly])

  const showAuthors = (tab === 'all' || tab === 'authors') && (!onAuthor || tab === 'authors' || tab === 'all')
  const showVenues = !onAuthor && (tab === 'all' || tab === 'venues')
  const showPapers = !onAuthor && (tab === 'all' || tab === 'papers')

  return (
    <div
      className="unified-search"
      ref={root}
      onBlur={e => {
        if (!e.currentTarget.contains(e.relatedTarget as Node)) setOpen(false)
      }}
      onKeyDown={e => {
        if (e.key === 'Escape') setOpen(false)
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          const items = Array.from(root.current?.querySelectorAll<HTMLElement>('.search-popover a, .search-popover button') ?? [])
          if (items.length) {
            e.preventDefault()
            const current = items.indexOf(document.activeElement as HTMLElement)
            items[(current + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus()
          }
        }
      }}
    >
      <label>
        <span className="sr-only">{label}</span>
        <span aria-hidden="true" className="search-symbol">⌕</span>
        <input
          type="search"
          value={q}
          maxLength={120}
          placeholder={label}
          onFocus={() => setOpen(true)}
          onChange={e => {
            setQ(e.target.value)
            setOpen(true)
          }}
          aria-expanded={open && q.trim().length >= 2}
          aria-controls={onAuthor ? 'researcher-results' : 'global-results'}
          aria-busy={busy}
        />
      </label>

      {open && q.trim().length >= 2 && (
        <div
          className="search-popover"
          id={onAuthor ? 'researcher-results' : 'global-results'}
          role="region"
          aria-label="Search results"
          aria-live="polite"
          onMouseDown={e => e.preventDefault()}
        >
          {busy && <p className="search-status" role="status">Searching research records...</p>}
          {error && <p className="search-error" role="alert">{error}</p>}

          {!onAuthor && (
            <div className="search-category-tabs" role="group" aria-label="Search categories">
              <button className={tab === 'all' ? 'active' : ''} onClick={() => setTab('all')}>All</button>
              <button className={tab === 'authors' ? 'active' : ''} onClick={() => setTab('authors')}>Researchers ({data?.authors.length ?? 0})</button>
              <button className={tab === 'venues' ? 'active' : ''} onClick={() => setTab('venues')}>Venues ({data?.venues.length ?? 0})</button>
              <button className={tab === 'papers' ? 'active' : ''} onClick={() => setTab('papers')}>Papers ({data?.papers?.length ?? 0})</button>
              <button className={`semantic-tab-btn ${tab === 'semantic' ? 'active' : ''}`} onClick={() => setTab('semantic')}>Meaning-based search</button>
            </div>
          )}

          <div className="search-scroll-area">
            {tab === 'semantic' && (
              <div className="search-group" role="group" aria-label="Meaning-based matches">
                <h3>Meaning-based matches</h3>
                {semanticData && semanticData.top_matches.length ? (
                  semanticData.top_matches.map((item, idx) => (
                    <a
                      className="search-result search-result-paper"
                      key={`${item.entity_type}-${item.entity_id}-${idx}`}
                      href={item.href}
                      onClick={() => {
                        setOpen(false)
                        setQ('')
                      }}
                    >
                      <div className="semantic-result-header" style={{ display: 'flex', justifyContent: 'space-between', width: '100%', gap: '8px' }}>
                        <span className="paper-title">{item.title}</span>
                        <div className="semantic-match-meta" style={{ display: 'flex', gap: '4px', flexShrink: 0 }}>
                          <span className="semantic-pill">{Math.round(item.relevance_score * 100)}%</span>
                          <span className={`semantic-badge badge-${item.match_type.toLowerCase()}`}>
                            {item.match_type}
                          </span>
                        </div>
                      </div>
                      <small className="paper-meta">
                        <span className="semantic-entity-tag">[{item.entity_type}]</span>
                        {item.year ? ` ${item.year} · ` : ' '}
                        {item.venue ? `${item.venue} · ` : ''}
                        {item.subtitle || ''}
                        {item.citations !== null && item.citations !== undefined ? ` · ${item.citations} citations` : ''}
                      </small>
                    </a>
                  ))
                ) : busy ? (
                  <p className="search-status">Finding matches by meaning...</p>
                ) : (
                  <p className="search-empty">No semantic matches found for this query.</p>
                )}
              </div>
            )}

            {data && showAuthors && (
              <div className="search-group" role="group" aria-label="Researchers">
                <h3>Researchers</h3>
                {data.authors.length ? (
                  data.authors.map(a =>
                    onAuthor ? (
                      <button
                        className="search-result"
                        key={a.author_id}
                        onClick={() => {
                          onAuthor(a)
                          setOpen(false)
                          setQ(a.name)
                        }}
                      >
                        <span>{a.name}</span>
                        <small>{full(a.papers)} papers</small>
                      </button>
                    ) : (
                      <a
                        className="search-result"
                        key={a.author_id}
                        href={`/authors/${a.author_id}`}
                        onClick={() => {
                          setOpen(false)
                          setQ('')
                        }}
                      >
                        <span>{a.name}</span>
                        <small>{full(a.papers)} papers</small>
                      </a>
                    )
                  )
                ) : (
                  <p className="search-empty">No matching researchers.</p>
                )}
              </div>
            )}

            {data && showVenues && (
              <div className="search-group" role="group" aria-label="Venues">
                <h3>Venues</h3>
                {data.venues.length ? (
                  data.venues.map(v => (
                    <a
                      className="search-result"
                      key={v.venue_id}
                      href={`/venues/${v.venue_id}`}
                      onClick={() => {
                        setOpen(false)
                        setQ('')
                      }}
                    >
                      <span>{v.name}</span>
                      <small>{full(v.papers)} papers</small>
                    </a>
                  ))
                ) : (
                  <p className="search-empty">No matching venues.</p>
                )}
              </div>
            )}

            {data && showPapers && (
              <div className="search-group" role="group" aria-label="Publications">
                <h3>Publications</h3>
                {data.papers && data.papers.length ? (
                  data.papers.map(p => (
                    <a
                      className="search-result search-result-paper"
                      key={p.publication_id}
                      href={`/papers/${p.publication_id}`}
                      onClick={() => {
                        setOpen(false)
                        setQ('')
                      }}
                    >
                      <span className="paper-title">{p.title}</span>
                      <small className="paper-meta">
                        {p.year ?? 'N/A'} · {p.venue_name ?? 'Indexed publication'} · {p.citations} citations
                      </small>
                    </a>
                  ))
                ) : (
                  <p className="search-empty">No matching publications.</p>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
