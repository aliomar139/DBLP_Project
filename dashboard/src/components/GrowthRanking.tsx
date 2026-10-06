import { useState } from 'react'
import { api, type SortKey, type Order } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, ResourceState } from './ChartCard'
import { GrowthMatrixScatterChart } from './Charts'
import { DataTable } from './DataTable'
import { full, percent } from './MetricCard'

export function GrowthRanking({ kind }: { kind: 'authors' | 'venues' }) {
 const [sort, setSort] = useState<SortKey>('growth_rate')
 const [order, setOrder] = useState<Order>('desc')
 const [offset, setOffset] = useState(0)
 const state = useResource(`growth:${kind}:${sort}:${order}:${offset}`, s => api.growth(kind, sort, order, offset, s))
 const data = state.data

 const onSelect = (id: number) => {
  window.history.pushState({}, '', `/${kind}/${id}`)
  window.dispatchEvent(new PopStateEvent('popstate'))
 }

 return <>
  {data && data.items.length > 0 && (
   <ChartCard 
   title={kind === 'venues' ? 'Venue growth' : 'Researcher growth'} 
   description="Compare earlier publication volume with recent growth. Larger bubbles mean more papers in the recent ten years. Select a point to open the profile."
   >
    <GrowthMatrixScatterChart data={data.items} onSelect={onSelect} />
   </ChartCard>
  )}

   <ChartCard 
   title={kind === 'authors' ? 'Rising researchers' : 'Fastest growing venues'} 
   description="Who has increased publication activity in the last ten completed years?"
  >
   {!data ? (
    <ResourceState {...state} />
   ) : (
    <>
     <p className="method-note">
      {data.recent_start}–{data.recent_end} compared with all dated work through {data.historical_end}. At least {data.minimum_recent} recent papers.
     </p>
     <DataTable 
      rows={data.items} 
      rowKey={r => r.id} 
      caption={kind === 'authors' ? 'Rising researcher ranking' : 'Venue growth ranking'} 
      sort={{ key: sort, order }} 
      onSort={key => {
       setSort(key as SortKey)
       setOrder(sort === key && order === 'desc' ? 'asc' : 'desc')
       setOffset(0)
      }} 
      columns={[
       { key: 'name', label: kind === 'authors' ? 'Researcher' : 'Venue', render: (r, i) => (
        <div className="ranked-name">
         <span>{offset + i + 1}</span>
         <a href={`/${kind}/${r.id}`}>{r.name}</a>
        </div>
       )},
       { key: 'historical_publications', label: 'Historical papers', render: r => full(r.historical_publications), numeric: true },
       { key: 'recent_publications', label: 'Recent papers', render: r => full(r.recent_publications), numeric: true },
       { key: 'growth_rate', label: 'Growth', render: r => <span className={r.growth_rate !== null && r.growth_rate > 0 ? 'positive' : ''}>{percent(r.growth_rate)}</span>, numeric: true },
      ]} 
     />
     <div className="pagination">
      <span>{data.total ? `${offset + 1}–${Math.min(offset + 20, data.total)} of ${full(data.total)}` : 'No qualifying records'}</span>
      <div>
       <button disabled={offset === 0} onClick={() => setOffset(n => Math.max(0, n - 20))}>Previous</button>
       <button disabled={offset + 20 >= data.total} onClick={() => setOffset(n => n + 20)}>Next</button>
      </div>
     </div>
     <details className="methodology">
      <summary>How to read this ranking</summary>
      <p>{data.methodology}</p>
      <p>A small earlier count can make a percentage look large. “No baseline” means there are no earlier dated papers, so those rows appear after rows with a defined growth rate. Check the paper count too.</p>
     </details>
    </>
   )}
  </ChartCard>
 </>
}
