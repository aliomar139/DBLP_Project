import { useEffect, useRef, useState } from 'react'
import { api } from '../api'

type Hit = { href: string; title: string; kind: string }
let topicsSession: ReturnType<typeof api.topics> | null = null
function loadSessionTopics() {
 if (!topicsSession) topicsSession = api.topics().catch(error => { topicsSession = null; throw error })
 return topicsSession
}
export function CommandPalette({ pages, onClose }: { pages: string[][]; onClose: () => void }) {
 const dialog = useRef<HTMLDialogElement>(null)
 const [query, setQuery] = useState('')
 const [hits, setHits] = useState<Hit[]>([])
 const [status, setStatus] = useState('')
 useEffect(() => {
  const previous = document.activeElement as HTMLElement
  dialog.current?.showModal()
  return () => { previous?.focus() }
 }, [])
 useEffect(() => {
  setHits([])
  if (query.trim().length < 2) { setStatus('Type at least two characters to search the corpus.'); return }
  const controller = new AbortController()
  setStatus('Searching the records...')
  const timer = setTimeout(async () => {
   try {
    const [result, topics] = await Promise.all([api.search(query.trim(), controller.signal), loadSessionTopics()])
    if (controller.signal.aborted) return
    setHits([
     ...result.authors.slice(0, 6).map(a => ({ href: `/authors/${a.author_id}`, title: a.name, kind: 'Researcher' })),
     ...result.papers?.slice(0, 6).map(p => ({ href: `/papers/${p.publication_id}`, title: p.title, kind: 'Paper' })) ?? [],
     ...topics.filter(t => t.topic_name.toLowerCase().includes(query.trim().toLowerCase())).slice(0, 6).map(t => ({href:`/topics/${t.topic_id}`,title:t.topic_name,kind:'Topic'})),
     ...result.venues.slice(0, 6).map(v => ({ href: `/venues/${v.venue_id}`, title: v.name, kind: 'Venue' }))
    ])
    setStatus('Search complete.')
   } catch { if (!controller.signal.aborted) setStatus('Corpus search unavailable. Page navigation is still available.') }
  }, 250)
  return () => { clearTimeout(timer); controller.abort() }
 }, [query])
 const destinations = pages.filter(([, title]) => title.toLowerCase().includes(query.toLowerCase()))
 return <dialog ref={dialog} className="command-dialog" aria-labelledby="command-title" onCancel={onClose} onClick={e => { if (e.target === e.currentTarget) onClose() }} onKeyDown={e => {
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return
  const items = Array.from(dialog.current?.querySelectorAll<HTMLElement>('input, .command-results a') ?? [])
  const index = items.indexOf(document.activeElement as HTMLElement)
  e.preventDefault(); items[(index + (e.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length]?.focus()
 }}>
  <div className="command-heading"><h2 id="command-title">Search research intelligence</h2><button onClick={onClose} aria-label="Close command palette">Esc</button></div>
  <label className="sr-only" htmlFor="command-query">Search papers, researchers, venues, topics and pages</label>
  <input autoFocus id="command-query" type="search" placeholder="Find a paper, researcher, topic, or page" value={query} onChange={e => setQuery(e.target.value)} />
  <div className="command-results" aria-busy={status === 'Searching the records...'}>
   {destinations.length > 0 && <div className="command-result-group"><h3>Pages</h3>{destinations.slice(0, 6).map(([href, title]) => <a href={href} key={href} onClick={onClose}><span>{title}</span><small>Page</small></a>)}</div>}
   {(['Researcher','Paper','Topic','Venue'] as const).map(kind => { const group = hits.filter(hit => hit.kind === kind).slice(0, 6); const heading = { Researcher: 'Researchers', Paper: 'Papers', Topic: 'Topics', Venue: 'Venues' }[kind]; return group.length ? <div className="command-result-group" key={kind}><h3>{heading}</h3>{group.map((hit, i) => <a href={hit.href} key={`${hit.href}-${i}`} onClick={onClose}><span>{hit.title}</span><small>{hit.kind}</small></a>)}</div> : null })}
   {status === 'Search complete.' && !hits.length && !destinations.length && <p>No matches. Try a name or a shorter search.</p>}
  </div>
  <p className="command-status" role="status">{status} <span>↑ ↓ navigate · Enter open</span></p>
 </dialog>
}
