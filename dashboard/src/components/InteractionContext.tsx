import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type ExplorationFilter = {
  key: string
  value: string
  label: string
}

type InteractionContextValue = {
  filters: ExplorationFilter[]
  setFilter: (key: string, value: string, label?: string) => void
  removeFilter: (key: string) => void
  clearFilters: () => void
  viewState: (key: string, fallback?: string) => string | undefined
  setViewState: (key: string, value: string) => void
  shareView: () => Promise<void>
  notify: (message: string) => void
}

const InteractionContext = createContext<InteractionContextValue | null>(null)
const FILTER_PREFIX = 'filter_'
const VIEW_PREFIX = 'view_'

function readSearch() {
  return new URLSearchParams(window.location.search)
}

function labelFor(key: string, value: string) {
  const names: Record<string, string> = {
    year: 'Year',
    type: 'Type',
    venue: 'Venue',
    researcher: 'Researcher',
    topic: 'Topic',
    decade: 'Decade'
  }
  return `${names[key] ?? key}: ${value}`
}

function readFilters() {
  const search = readSearch()
  return Array.from(search.entries())
    .filter(([key]) => key.startsWith(FILTER_PREFIX))
    .map(([key, value]) => {
      const filterKey = key.slice(FILTER_PREFIX.length)
      return { key: filterKey, value, label: labelFor(filterKey, value) }
    })
}

function writeSearch(mutator: (search: URLSearchParams) => void, mode: 'replace' | 'push' = 'replace') {
  const url = new URL(window.location.href)
  mutator(url.searchParams)
  const nextUrl = `${url.pathname}${url.search}${url.hash}`
  if (mode === 'push') window.history.pushState({}, '', nextUrl)
  else window.history.replaceState({}, '', nextUrl)
  window.dispatchEvent(new Event('viewstatechange'))
}

export function InteractionProvider({ children }: { children: ReactNode }) {
  const [filters, setFilters] = useState<ExplorationFilter[]>(readFilters)
  const [toast, setToast] = useState('')

  useEffect(() => {
    const sync = () => setFilters(readFilters())
    window.addEventListener('popstate', sync)
    window.addEventListener('viewstatechange', sync)
    return () => {
      window.removeEventListener('popstate', sync)
      window.removeEventListener('viewstatechange', sync)
    }
  }, [])

  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(() => setToast(''), 2800)
    return () => window.clearTimeout(timer)
  }, [toast])

  const value = useMemo<InteractionContextValue>(() => ({
    filters,
    setFilter: (key, filterValue, label) => {
      writeSearch(search => search.set(`${FILTER_PREFIX}${key}`, filterValue), 'push')
      setFilters(readFilters())
      setToast(label ?? labelFor(key, filterValue))
    },
    removeFilter: key => {
      writeSearch(search => search.delete(`${FILTER_PREFIX}${key}`), 'push')
      setFilters(readFilters())
    },
    clearFilters: () => {
      writeSearch(search => Array.from(search.keys()).filter(key => key.startsWith(FILTER_PREFIX)).forEach(key => search.delete(key)), 'push')
      setFilters([])
    },
    viewState: (key, fallback) => readSearch().get(`${VIEW_PREFIX}${key}`) ?? fallback,
    setViewState: (key, viewValue) => writeSearch(search => search.set(`${VIEW_PREFIX}${key}`, viewValue)),
    shareView: async () => {
      try {
        await navigator.clipboard.writeText(window.location.href)
        setToast('Shareable view URL copied')
      } catch {
        setToast('Copy unavailable — use the browser URL')
      }
    },
    notify: message => setToast(message)
  }), [filters])

  return <InteractionContext.Provider value={value}>
    {children}
    {toast && <div className="interaction-toast" role="status" aria-live="polite">{toast}</div>}
  </InteractionContext.Provider>
}

export function useInteraction() {
  const context = useContext(InteractionContext)
  if (!context) throw new Error('useInteraction must be used within InteractionProvider')
  return context
}
