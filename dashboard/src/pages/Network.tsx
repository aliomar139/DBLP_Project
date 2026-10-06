import { useEffect, useState } from 'react'
import { api, type GraphNode } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { NetworkGraph } from '../components/NetworkGraph'
import { NetworkStrengthHistogram } from '../components/Charts'
import { SearchBar } from '../components/SearchBar'
import { DataTable } from '../components/DataTable'
import { MetricCard, compact, full } from '../components/MetricCard'

export default function Network({ search }: { search: string }) {
 const initialParams = new URLSearchParams(search)
 const author = initialParams.get('author') ?? ''
 const [limit, setLimit] = useState(initialParams.get('limit') ?? '50')
 const [weight, setWeight] = useState(initialParams.get('min_weight') ?? '1')
 const [start, setStart] = useState(initialParams.get('start_year') ?? '')
 const [end, setEnd] = useState(initialParams.get('end_year') ?? '')
 const [years, setYears] = useState({ start: initialParams.get('start_year') ?? '', end: initialParams.get('end_year') ?? '' })
 const [yearError, setYearError] = useState('')
 const [highlight, setHighlight] = useState(initialParams.get('highlight') ?? '')
 const [inspectedNode, setInspectedNode] = useState<GraphNode | null>(null)
 const [trail, setTrail] = useState<{ id: string; name: string }[]>([])

 const macroState = useResource('network:stats', api.networkStats)
 const netStats = macroState.data

 const params = new URLSearchParams({ limit, min_weight: weight })
 if (author) params.set('author_id', author)
 if (years.start) params.set('start_year', years.start)
 if (years.end) params.set('end_year', years.end)

 const state = useResource(`graph:${params}`, s => api.graph(params, s))
 const g = state.data
 const center = g?.nodes.find(n => n.id === g.center_id)

 useEffect(() => {
  const params = new URLSearchParams(search)
  const nextStart = params.get('start_year') ?? ''
  const nextEnd = params.get('end_year') ?? ''
  setLimit(params.get('limit') ?? '50')
  setWeight(params.get('min_weight') ?? '1')
  setStart(nextStart)
  setEnd(nextEnd)
  setYears({ start: nextStart, end: nextEnd })
  setHighlight(params.get('highlight') ?? '')
 }, [search])

 useEffect(() => {
  const params = new URLSearchParams()
  if (author) params.set('author', author)
  if (limit !== '50') params.set('limit', limit)
  if (weight !== '1') params.set('min_weight', weight)
  if (years.start) params.set('start_year', years.start)
  if (years.end) params.set('end_year', years.end)
  if (highlight) params.set('highlight', highlight)
  const next = `${location.pathname}${params.size ? `?${params}` : ''}`
  if (`${location.pathname}${location.search}` !== next) history.replaceState({}, '', next)
 }, [author, limit, weight, years, highlight])

 useEffect(() => {
  if (center) {
   setTrail(prev => {
    if (prev.some(t => t.id === center.id)) return prev
    return [...prev.slice(-4), { id: center.id, name: center.name }]
   })
  }
 }, [center?.id, center?.name])

 const choose = (id: string) => {
  const params = new URLSearchParams()
  params.set('author', id)
  if (limit !== '50') params.set('limit', limit)
  if (weight !== '1') params.set('min_weight', weight)
  if (years.start) params.set('start_year', years.start)
  if (years.end) params.set('end_year', years.end)
  if (highlight) params.set('highlight', highlight)
  window.history.pushState({}, '', `/network?${params}`)
  window.dispatchEvent(new PopStateEvent('popstate'))
  setHighlight('')
  setInspectedNode(null)
 }

 const openProfile = (node: GraphNode) => {
  setInspectedNode(node)
  window.history.pushState({}, '', `/authors/${node.id}`)
  window.dispatchEvent(new PopStateEvent('popstate'))
 }

 // Graph analytics
 const maxWeight = g?.edges.length ? Math.max(...g.edges.map(e => e.weight)) : 0
 const avgWeight = g?.edges.length ? (g.edges.reduce((s, e) => s + e.weight, 0) / g.edges.length).toFixed(1) : '0'
 const matchingHighlightCount = highlight && g ? g.nodes.filter(n => n.name.toLowerCase().includes(highlight.toLowerCase())).length : 0

 return <>
  <PageHeader 
   title="Follow the collaboration." 
   description="Traverse computer science coauthorship networks, inspect tie strengths, and explore research communities."
  />

  {netStats && (
   <div className="metric-strip">
    <MetricCard label="Total Collaborations" value={compact(netStats.total_collaborations)} detail={`${full(netStats.total_collaborations)} undirected ties`} />
    <MetricCard label="Active Researchers" value={compact(netStats.total_researchers)} detail="Indexed co-authors" />
    <MetricCard label="Average Co-authors" value={netStats.avg_collaborators_per_researcher.toFixed(1)} detail="Mean collaborators / researcher" />
    <MetricCard label="Strongest tie" value={netStats.strongest_pair ? `${netStats.strongest_pair.weight} papers` : 'N/A'} detail={netStats.strongest_pair ? `${netStats.strongest_pair.author1} and ${netStats.strongest_pair.author2}` : undefined} />
   </div>
  )}

  {trail.length > 1 && (
   <nav className="network-trail" aria-label="Exploration trail">
    <span>Exploration trail:</span>
    {trail.map((t, idx) => (
     <span key={t.id} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
      {idx > 0 && <span aria-hidden="true">→</span>}
      <button 
       style={{ background: t.id === g?.center_id ? 'var(--paper-2)' : undefined }}
       onClick={() => choose(t.id)}
      >
       {t.name}
      </button>
     </span>
    ))}
   </nav>
  )}

  <section className="network-controls" aria-label="Network controls">
   <SearchBar label="Search to center network on a researcher" onAuthor={a => choose(String(a.author_id))} />
   
   <div className="filter-row">
    <label>
     Minimum shared papers
     <select value={weight} onChange={e => setWeight(e.target.value)}>
      {[1, 2, 5, 10, 25, 50].map(n => <option key={n} value={n}>{n}+ shared papers</option>)}
     </select>
    </label>
    <label>
     Max nodes in view
     <select value={limit} onChange={e => setLimit(e.target.value)}>
      {[25, 50, 100, 250, 500].map(n => <option key={n} value={n}>{n} nodes</option>)}
     </select>
    </label>
    <label>
     Highlight visible node
     <input 
      type="search" 
      value={highlight} 
      onChange={e => setHighlight(e.target.value)} 
      placeholder="Type a researcher name" 
     />
     {highlight && <small style={{ color: 'var(--accent-dark)' }}>{matchingHighlightCount} matching</small>}
    </label>
   </div>

   <form className="year-filters" onSubmit={e => {
    e.preventDefault()
    if (start && end && Number(start) > Number(end)) {
     setYearError('Start year must not exceed end year')
     return
    }
    setYearError('')
    setYears({ start, end })
   }}>
    <label>
     From year
     <input type="number" min="1800" max="2100" placeholder="Earliest" value={start} onChange={e => setStart(e.target.value)} />
    </label>
    <label>
     Through year
     <input type="number" min="1800" max="2100" placeholder="Latest" value={end} onChange={e => setEnd(e.target.value)} />
    </label>
    <button type="submit">Apply year bounds</button>
    <button type="button" className="text-button" onClick={() => { setStart(''); setEnd(''); setYears({ start: '', end: '' }); setYearError('') }}>
     Clear years
    </button>
   </form>
   {yearError && <p role="alert" className="validation-error">{yearError}</p>}
  </section>

  {!g ? (
   <ResourceState {...state} />
  ) : (
   <ChartCard 
    title={center ? `Collaboration cluster around ${center.name}` : 'Collaboration network'} 
    description={`${g.nodes.length} nodes · ${g.edges.length} relationships · ${full(g.matching_collaborators)} total matching collaborators`} 
    action={<a className="text-link" href={`/authors/${g.center_id}`}>View center profile →</a>}
   >
    <div className="network-stats-strip">
     <div className="network-stat-item">
      <span>Visible Nodes</span>
      <strong>{g.nodes.length}</strong>
     </div>
     <div className="network-stat-item">
      <span>Active Ties</span>
      <strong>{g.edges.length}</strong>
     </div>
     <div className="network-stat-item">
      <span>Max Shared Papers</span>
      <strong>{maxWeight}</strong>
     </div>
     <div className="network-stat-item">
      <span>Avg Shared Papers</span>
      <strong>{avgWeight}</strong>
     </div>
    </div>

    <p className="method-note">
     {g.truncated ? 'Showing the strongest relationships within the node limit. ' : 'All qualifying coauthorship relationships shown. '}
     Edges represent {years.start || years.end ? `${years.start || 'earliest'}–${years.end || 'latest'} publications` : 'all years'}; node metrics use the full career.
    </p>

    {g.edges.length === 0 && (
     <p className="empty-state">No collaborators match these filters. Lower the minimum shared paper threshold or broaden the year range.</p>
    )}

    <NetworkGraph 
     graph={g} 
     highlight={highlight} 
     onSelectNode={openProfile}
     onCenterNode={id => choose(id)}
    />

    {inspectedNode && (
     <div className="network-inspector">
      <div className="network-inspector-info">
       <strong>{inspectedNode.name}</strong>
       <span>{full(inspectedNode.publications)} total papers · {full(inspectedNode.collaborators)} all-time collaborators</span>
      </div>
      <div className="network-inspector-actions">
       {inspectedNode.id !== g.center_id && (
        <button onClick={() => choose(inspectedNode.id)}>Center network here</button>
       )}
       <a className="button-link" href={`/authors/${inspectedNode.id}`}>Open profile →</a>
       <button className="text-button" onClick={() => setInspectedNode(null)}>Dismiss</button>
      </div>
     </div>
    )}

    <details className="methodology" style={{ marginTop: '20px' }}>
     <summary>Browse network researchers table</summary>
     <DataTable 
      rows={g.nodes.filter(n => !highlight || n.name.toLowerCase().includes(highlight.toLowerCase()))} 
      rowKey={n => n.id} 
      caption="Network researchers" 
      columns={[
       { key: 'name', label: 'Researcher', render: n => <a href={`/authors/${n.id}`}>{n.name}</a>, value: n => n.name },
       { key: 'papers', label: 'Career papers', render: n => full(n.publications), numeric: true },
       { key: 'collaborators', label: 'Collaborators', render: n => full(n.collaborators), numeric: true },
       { key: 'explore', label: 'Action', render: n => (
        n.id !== g.center_id ? (
         <button className="text-button" onClick={() => choose(n.id)}>Center here</button>
        ) : (
         <span style={{ color: 'var(--accent-dark)', fontWeight: 600 }}>Current center</span>
        )
       )}
      ]} 
     />
    </details>
   </ChartCard>
  )}

  {netStats && netStats.weight_distribution.length > 0 && (
   <ChartCard 
    title="Global Collaboration Tie Persistence" 
    description="Distribution of shared publication frequency across all 32.5M scientific partnerships. Demonstrates network persistence: 68.2% of ties are single-paper partnerships, while only 1.4% persist for 11+ papers."
   >
    <NetworkStrengthHistogram data={netStats.weight_distribution} />
    <DataTable 
     rows={netStats.weight_distribution} 
     rowKey={r => r.bucket} 
     caption="Collaboration tie distribution" 
     columns={[
      { key: 'bucket', label: 'Collaboration Tie Strength', render: r => r.bucket },
      { key: 'count', label: 'Co-authorship Pairs', render: r => full(r.count), numeric: true },
      { key: 'percentage', label: 'Community Share', render: r => `${r.percentage ?? 0}%`, numeric: true }
     ]} 
    />
   </ChartCard>
  )}
 </>
}
