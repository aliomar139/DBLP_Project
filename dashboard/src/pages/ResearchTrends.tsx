import { ChartTooltip } from '../components/ChartTooltip'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type Decade } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { MetricCard, compact, full } from '../components/MetricCard'
import { TimelineChart, CollaborationEvolutionChart } from '../components/Charts'
import { DataTable } from '../components/DataTable'

export default function ResearchTrends() {
 const state = useResource('trends', async s => {
  const [timeline, decades, collaborationEvolution] = await Promise.all([
   api.timeline(s),
   api.decades(s),
   api.collaborationEvolution(s)
  ])
  return { timeline, decades, collaborationEvolution }
 })

 const [decade, setDecade] = useState(2020)
 const [metric, setMetric] = useState<'publications' | 'authors' | 'venues' | 'average_authors_per_paper'>('publications')
 const [growth, setGrowth] = useState(false)

 if (!state.data) return <><PageHeader title="Research across generations." description="Compare decades, track publication growth, and examine how teams have changed."/><ResourceState {...state}/></>
 const { timeline, decades, collaborationEvolution } = state.data
 const d = decades.find(d => d.decade === decade)!
 const labels = { publications: 'Publications', authors: 'Researchers', venues: 'Venues', average_authors_per_paper: 'Authors per paper' }

 return <>
  <PageHeader title="Research across generations." description="Compare decades, track publication growth, and examine how teams have changed." />

  <div className="period-picker" role="group" aria-label="Select decade">
   {decades.map(d => <button key={d.decade} aria-pressed={decade === d.decade} onClick={() => setDecade(d.decade)}>{d.decade}s</button>)}
  </div>
  <p className="method-note">{decade}s: records through {d.observed_through ?? 'no observed year'}. The 2020s are an incomplete period; current and future-dated records are included in these totals.</p>

  <div className="metric-strip">
   <MetricCard label="Publications" value={full(d.publications)} />
   <MetricCard label="Researchers" value={full(d.authors)} detail="Unique within the decade" />
   <MetricCard label="Venues" value={full(d.venues)} />
   <MetricCard label="Authors per paper" value={d.average_authors_per_paper.toFixed(2)} />
  </div>

  <ChartCard title="How do the decades compare?" description="Choose a measure to compare the same unit across all five decades." action={<label className="select-label">Compare<select value={metric} onChange={e => setMetric(e.target.value as typeof metric)}>{Object.entries(labels).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>}>
   <div className="intelligence-chart">
    <ResponsiveContainer width="100%" height="100%">
     <BarChart data={decades} margin={{ right: 18, top: 20 }}>
      <CartesianGrid vertical={false} stroke="var(--grid)" />
      <XAxis dataKey="decade" tickFormatter={n => `${n}s`} axisLine={false} tickLine={false} />
      <YAxis tickFormatter={compact} width={62} axisLine={false} tickLine={false} />
      <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} labelFormatter={n => `${n}s`} formatter={v => Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 })} contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)' }} />
      <Bar dataKey={metric} name={labels[metric]} fill="var(--accent)" maxBarSize={76} isAnimationActive={false} />
     </BarChart>
    </ResponsiveContainer>
   </div>
   <details className="methodology">
    <summary>View comparison data</summary>
    <DataTable<Decade> rows={decades} rowKey={r => r.decade} caption="Decade comparison" columns={[
     { key: 'decade', label: 'Decade', render: r => `${r.decade}s` },
     ...Object.entries(labels).map(([key, label]) => ({ key, label, numeric: true, render: (r: Decade) => Number(r[key as keyof Decade]).toLocaleString('en-US', { maximumFractionDigits: 2 }) }))
    ]} />
   </details>
  </ChartCard>

  <ChartCard title="Research teams and collaboration" description="Yearly changes in the average number of authors per paper and the size of the research community from 1970 to 2025.">
   <CollaborationEvolutionChart data={collaborationEvolution} />
  </ChartCard>

  <ChartCard title="When did publication growth change?" description="Full annual history. Growth compares each year with the preceding calendar year." action={<div className="segmented"><button aria-pressed={!growth} onClick={() => setGrowth(false)}>Publications</button><button aria-pressed={growth} onClick={() => setGrowth(true)}>Growth %</button></div>}>
   <TimelineChart key={String(growth)} data={timeline} growth={growth} />
   <p className="method-note">A missing or zero prior-year count has no growth percentage. Recent-year declines may reflect incomplete indexing.</p>
  </ChartCard>
 </>
}
