import { useState } from 'react'
import { api, type Venue } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { GrowthRanking } from '../components/GrowthRanking'
import { VenueActivityHeatmap } from '../components/Charts'
import { DataTable } from '../components/DataTable'
import { full } from '../components/MetricCard'
import { ExportToolbar } from '../components/ExportToolbar'

export default function Venues() {
  const [tab, setTab] = useState<'matrix' | 'heatmap' | 'volume'>('matrix')
  const [volumeSort, setVolumeSort] = useState<'papers' | 'name'>('papers')
  const [volumeOrder, setVolumeOrder] = useState<'asc' | 'desc'>('desc')
  const heatmapState = useResource('venues:heatmap:default', () => api.venueHeatmap({ start_year: 2005, end_year: 2025 }))
  const volumeState = useResource(`venues:top:50:${volumeSort}:${volumeOrder}`, () => api.venuesTop(50, volumeSort, volumeOrder))

  const onSelectVenue = (venueName: string) => {
    const v = volumeState.data?.find(x => x.name.toLowerCase() === venueName.toLowerCase())
    if (v) {
      window.history.pushState({}, '', `/venues/${v.venue_id}`)
      window.dispatchEvent(new PopStateEvent('popstate'))
    }
  }

  return (
    <>
      <PageHeader
        title="Publication venues"
        description="Compare publication volume over time and explore the conferences, journals, and repositories in the records."
      />

      <div className="author-tabs" role="tablist" aria-label="Venue Views">
        <button aria-pressed={tab === 'matrix'} onClick={() => setTab('matrix')}>Growth Matrix & Rising Venues</button>
        <button aria-pressed={tab === 'heatmap'} onClick={() => setTab('heatmap')}>Activity Heatmap (2005–2025)</button>
        <button aria-pressed={tab === 'volume'} onClick={() => setTab('volume')}>Largest Venues by Volume</button>
      </div>

      {tab === 'matrix' && (
        <GrowthRanking kind="venues" />
      )}

      {tab === 'heatmap' && (
        <ChartCard
          title="Venue Activity Heatmap (2005–2025)"
          description="Annual paper counts for the 12 largest conferences, journals, and repositories. Select a venue to inspect it."
        >
          {!heatmapState.data ? (
            <ResourceState {...heatmapState} />
          ) : (
            <VenueActivityHeatmap data={heatmapState.data} onSelectVenue={onSelectVenue} />
          )}
        </ChartCard>
      )}

      {tab === 'volume' && (
        <ChartCard
          title="Largest Publication Venues"
          description="Top 50 venues ranked by total all-time publication volume."
          action={
            <ExportToolbar
              title="largest-venues"
              data={volumeState.data}
              columns={[
                { key: 'name', label: 'Venue' },
                { key: 'papers', label: 'Indexed Papers' }
              ]}
            />
          }
        >
          {!volumeState.data ? (
            <ResourceState {...volumeState} />
          ) : (
            <DataTable<Venue>
              rows={volumeState.data}
              rowKey={r => r.venue_id}
              caption="Largest publication venues"
              sort={{ key: volumeSort, order: volumeOrder }}
              onSort={key => {
                if (key !== 'papers' && key !== 'name') return
                if (volumeSort === key) setVolumeOrder(current => current === 'desc' ? 'asc' : 'desc')
                else { setVolumeSort(key); setVolumeOrder('desc') }
              }}
              columns={[
                { key: 'rank', label: 'Rank', render: (_, i) => i + 1 },
                { key: 'name', label: 'Venue', render: r => <a href={`/venues/${r.venue_id}`}>{r.name}</a>, value: r => r.name },
                { key: 'papers', label: 'Indexed Papers', render: r => full(r.papers), value: r => r.papers, numeric: true },
                { key: 'action', label: 'Action', render: r => <a className="text-link" href={`/venues/${r.venue_id}`}>View Venue Profile →</a> }
              ]}
            />
          )}
        </ChartCard>
      )}
    </>
  )
}
