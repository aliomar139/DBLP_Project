import { lazy, Suspense, useEffect, useState } from 'react'
import { api, type Overview as Corpus } from './api'
import { compact } from './components/MetricCard'
import { InteractionProvider } from './components/InteractionContext'
import { FilterChips } from './components/FilterChips'
const CommandPalette = lazy(() => import('./components/CommandPalette').then(m => ({ default: m.CommandPalette })))

const Overview = lazy(() => import('./pages/Overview'))
const Topics = lazy(() => import('./pages/Topics'))
const TopicProfile = lazy(() => import('./pages/TopicProfile'))
const AuthorProfile = lazy(() => import('./pages/AuthorProfile'))
const Researchers = lazy(() => import('./pages/Researchers'))
const VenueProfile = lazy(() => import('./pages/VenueProfile'))
const Institutions = lazy(() => import('./pages/Institutions'))
const InstitutionProfile = lazy(() => import('./pages/InstitutionProfile'))
const PaperDetail = lazy(() => import('./pages/PaperDetail'))
const Papers = lazy(() => import('./pages/Papers'))
const Network = lazy(() => import('./pages/Network'))
const DataQuality = lazy(() => import('./pages/DataQuality'))
const Venues = lazy(() => import('./pages/Venues'))
const ResearchBoard = lazy(() => import('./pages/ResearchBoard'))
const Assistant = lazy(() => import('./pages/Assistant'))

const links = [
  ['/', 'Overview'],
  ['/board', 'Research Board'],
  ['/papers', 'Publications'],
  ['/authors', 'Researchers'],
  ['/institutions', 'Institutions'],
  ['/venues', 'Venues'],
  ['/network', 'Network'],
  ['/topics', 'Topics'],
  ['/data-quality', 'Data Quality & Trust'],
  ['/assistant', 'Research Assistant'],
]

export default function App() {
  const [route, setRoute] = useState(() => ({ path: location.pathname, search: location.search }))
  const [menu, setMenu] = useState(false)
  const [command, setCommand] = useState(false)
  const [corpus, setCorpus] = useState<Corpus>()

  useEffect(() => { document.documentElement.removeAttribute('data-theme') }, [])

  useEffect(() => {
    const controller = new AbortController()
    api.overview(controller.signal).then(setCorpus).catch(() => {})
    const shortcut = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); setCommand(c => !c) }
      if (e.key === 'Escape') setMenu(false)
    }
    document.addEventListener('keydown', shortcut)
    return () => { controller.abort(); document.removeEventListener('keydown', shortcut) }
  }, [])

  const section = links.find(([p]) => p !== '/' && route.path.startsWith(p))
  const currentLabel = section?.[1] ?? (route.path.startsWith('/authors') ? 'Researchers' : 'Corpus overview')

  useEffect(() => {
    const change = () => {
      setRoute({ path: location.pathname, search: location.search })
      setMenu(false)
      window.scrollTo(0, 0)
    }

    const click = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) return
      const link = (e.target as Element).closest<HTMLAnchorElement>('a[href]')
      if (!link || link.target || link.hasAttribute('download')) return
      const url = new URL(link.href)
      if (url.origin !== location.origin || url.hash) return
      e.preventDefault()
      history.pushState({}, '', url.pathname + url.search)
      change()
    }

    window.addEventListener('popstate', change)
    document.addEventListener('click', click)
    return () => {
      window.removeEventListener('popstate', change)
      document.removeEventListener('click', click)
    }
  }, [])

  useEffect(() => {
    document.title = `${links.find(([p]) => p === route.path)?.[1] ?? 'Academic Intelligence'} · DBLP Research Intelligence`
    document.getElementById('page-content')?.focus({ preventScroll: true })
  }, [route.path])

  const author = route.path.match(/^\/authors\/(\d+)\/?$/)
  const venue = route.path.match(/^\/venues\/(\d+)\/?$/)
  const topic = route.path.match(/^\/topics\/(\d+)\/?$/)
  const institution = route.path.match(/^\/institutions\/(\d+)\/?$/)
  const paper = route.path.match(/^\/papers\/(\d+)\/?$/)

  const page = (author && author[1]) ? (
    <AuthorProfile key={author[1]} id={author[1]} />
  ) : (venue && venue[1]) ? (
    <VenueProfile key={venue[1]} id={venue[1]} />
  ) : (topic && topic[1]) ? (
    <TopicProfile key={topic[1]} id={topic[1]} />
  ) : (institution && institution[1]) ? (
    <InstitutionProfile key={institution[1]} id={institution[1]} />
  ) : (paper && paper[1]) ? (
    <PaperDetail key={paper[1]} id={paper[1]} />
  ) : route.path === '/' ? (
    <Overview />
  ) : route.path === '/papers' ? (
    <Papers />
  ) : route.path === '/authors' ? (
    <Researchers />
  ) : route.path === '/topics' ? (
    <Topics />
  ) : route.path === '/board' ? (
    <ResearchBoard />
  ) : route.path === '/assistant' ? (
    <Assistant />
  ) : route.path === '/institutions' ? (
    <Institutions />
  ) : route.path === '/venues' ? (
    <Venues />
  ) : route.path === '/network' ? (
    <Network search={route.search} />
  ) : route.path === '/data-quality' ? (
    <DataQuality />
  ) : (
    <div className="resource-state">
      <h1>Page not found</h1>
      <a href="/">Back to overview</a>
    </div>
  )

  return (
    <InteractionProvider>
    <div className="app-shell">
      <a className="skip-link" href="#page-content">Skip to main content</a>
      <header className="app-header">
        <a className="product-brand" href="/" aria-label="DBLP Research Intelligence home">
          <span className="brand-symbol">D</span>
          <span>DBLP<span className="brand-subtitle">Research Intelligence</span></span>
        </a>
        <nav className="header-breadcrumb" aria-label="Breadcrumb"><a href="/">Intelligence</a><span aria-hidden="true">/</span><span>{currentLabel}</span>{/^\/[^/]+\/\d+/.test(route.path) && <><span aria-hidden="true">/</span><span>Dossier</span></>}</nav>
        <div className="corpus-ticker" aria-label="Corpus totals">{corpus ? <><span>{compact(corpus.total_publications)} papers</span><span>{compact(corpus.total_authors)} researchers</span><span>{compact(corpus.total_venues)} venues</span></> : <span>Corpus totals unavailable</span>}</div>
        <button className="command-trigger" onClick={() => setCommand(true)} aria-haspopup="dialog" aria-label="Search all research. Use Control or Command K"><span>Search</span><kbd>Ctrl K or Command K</kbd></button>
        <button
          className="menu-toggle"
          aria-expanded={menu}
          aria-controls="primary-navigation"
          onClick={() => setMenu(!menu)}
        >
          Menu
        </button>
      </header>

      {command && <Suspense fallback={null}><CommandPalette pages={links} onClose={() => setCommand(false)} /></Suspense>}
      <div className="app-layout">
        <aside className={`sidebar ${menu ? 'is-open' : ''}`}>
          <div className="sidebar-sticky">
            <nav id="primary-navigation" aria-label="Main navigation">
              {links.map(([path, label], index) => (<div key={path}>{[2, 6].includes(index) && <span className="nav-group">{index === 2 ? 'Corpus' : 'Workspace'}</span>}
                <a
                  key={path}
                  href={path}
                  aria-current={(path === '/' ? route.path === '/' : route.path.startsWith(path)) ? 'page' : undefined}
                >
                  <span>{label}</span>
                  <span aria-hidden="true">↗</span>
                </a></div>
              ))}
            </nav>
            <div className="sidebar-footer">
              <p className="sidebar-note">Use the records to support research decisions.</p>
              <span className="data-label">DBLP indexed records</span>
            </div>
          </div>
        </aside>

        <main className="page-content" id="page-content" tabIndex={-1}>
          <FilterChips />
          <Suspense fallback={<div className="resource-state" role="status">Loading research data...</div>}>
            {page}
          </Suspense>
          <footer className="app-footer">
            <span>DBLP / Research Intelligence</span>
            <span>Trends, people, institutions, impact, and networks</span>
          </footer>
        </main>
      </div>
    </div>
    </InteractionProvider>
  )
}
