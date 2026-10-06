import { useEffect, useState } from 'react'
import { api, type Venue } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { MetricCard, full } from '../components/MetricCard'
import { TimelineChart, VenueComparisonChart, VenueTopAuthorsChart } from '../components/Charts'
import { DataTable } from '../components/DataTable'
import { BoardButton } from '../components/BoardButton'

export default function VenueProfile({ id }: { id: string }) {
 const state = useResource(`venue:${id}`, s => api.venue(id, s))
 const [recent, setRecent] = useState(false)
 const [compareVenue, setCompareVenue] = useState<string>('')
 const [compareData, setCompareData] = useState<{ year: number; venue: string; count: number }[]>([])
 const [compareLoading, setCompareLoading] = useState(false)
 const [popularVenues, setPopularVenues] = useState<Venue[]>([])

 useEffect(() => {
  api.venues().then(setPopularVenues).catch(() => {})
 }, [])

 const v = state.data
 const last = v?.last_publication_year ?? new Date().getFullYear()

 useEffect(() => {
  if (!v || !compareVenue) {
   setCompareData([])
   return
  }
  setCompareLoading(true)
  const controller = new AbortController()
  api.venueTrends(`${v.name},${compareVenue}`, controller.signal)
   .then(data => { setCompareData(data); setCompareLoading(false) })
   .catch(err => { if (err.name !== 'AbortError') setCompareLoading(false) })
  return () => controller.abort()
 }, [v?.name, compareVenue])

 if (!v) return <ResourceState {...state} />

 const peers = popularVenues.filter(p => p.name !== v.name).slice(0, 6)

 return <>
  <a className="breadcrumb" href="/venues">← Venues</a>
 <PageHeader title={v.name} description="Publication history, leading researchers, and comparisons with other venues.">
  <BoardButton item={{ key: `venue:${v.id}`, type: 'venue', id: v.id, title: v.name, subtitle: 'Publication venue', href: `/venues/${v.id}` }} />
 </PageHeader>

  <div className="metric-strip">
   <MetricCard label="Publications" value={full(v.total_publications)} detail="All indexed records" />
   <MetricCard label="Years active" value={`${v.active_years} yrs`} detail={`${v.first_publication_year ?? 'N/A'} to ${v.last_publication_year ?? 'N/A'}. Recorded output`} />
   <MetricCard label="Researchers" value={full(v.author_count)} detail="Distinct authors publishing here" />
   <MetricCard label="Peak output" value={v.peak_year ? String(v.peak_year) : 'N/A'} detail={v.peak_publications ? `${full(v.peak_publications)} papers in peak year` : 'N/A'} />
  </div>

  <ChartCard 
   title="How has this venue evolved?" 
   description="Annual publication volume and year-over-year growth trajectory. Toggle view or inspect the last decade." 
   action={
    <div className="segmented">
     <button aria-pressed={!recent} onClick={() => setRecent(false)}>Full history</button>
     <button aria-pressed={recent} onClick={() => setRecent(true)}>Last decade</button>
    </div>
   }
  >
   <TimelineChart key={String(recent)} data={v.yearly_growth.filter(p => !recent || p.year >= last - 9)} showToggle />
   <p className="method-note">Current and future publication years may be incomplete.</p>
  </ChartCard>

  <div className="discovery-grid">
   <ChartCard title="Who publishes here?" description="Leading researchers by total publication volume within this venue.">
    <VenueTopAuthorsChart data={v.top_authors} />
    <DataTable rows={v.top_authors} rowKey={r => r.author_id} caption="Top researchers at this venue" columns={[
     { key: 'name', label: 'Researcher', render: r => <a href={`/authors/${r.author_id}`}>{r.name}</a>, value: r => r.name },
     { key: 'papers', label: 'Venue publications', render: r => full(r.papers), value: r => r.papers, numeric: true },
     { key: 'share', label: 'Venue share', render: r => `${r.venue_share ?? 0}%`, numeric: true }
    ]} />
   </ChartCard>

   <ChartCard 
    title="Compare with another venue" 
    description="Select a benchmark venue to compare publication trajectories side-by-side."
    action={
     compareVenue ? (
      <button className="text-button" onClick={() => setCompareVenue('')}>Clear comparison</button>
     ) : undefined
    }
   >
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px', alignItems: 'center' }}>
     <span style={{ fontSize: '11px', color: 'var(--muted)' }}>Compare with:</span>
     {peers.map(p => (
      <button 
       key={p.venue_id} 
       style={{ fontSize: '11px', padding: '4px 8px' }}
       aria-pressed={compareVenue === p.name}
       onClick={() => setCompareVenue(compareVenue === p.name ? '' : p.name)}
      >
       {p.name}
      </button>
     ))}
    </div>

    {compareLoading ? (
<div className="resource-state" style={{ minHeight: '200px' }}>Loading comparison...</div>
    ) : compareData.length > 0 ? (
     <VenueComparisonChart data={compareData} />
    ) : (
     <p className="empty-state">Choose a benchmark venue above to compare publication timelines.</p>
    )}
   </ChartCard>
  </div>
 </>
}
