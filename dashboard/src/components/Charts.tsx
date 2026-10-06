import { ChartTooltip } from './ChartTooltip'
import { useState } from 'react'
import {
 Bar, BarChart, Brush, CartesianGrid, Line, LineChart,
 ResponsiveContainer, Tooltip, XAxis, YAxis, Scatter, ScatterChart,
 ZAxis, ReferenceLine, ComposedChart, PieChart, Pie, Cell
} from 'recharts'
import type {
 TimelinePoint, Venue, PublicationType, CollaborationEvolutionPoint,
 TeamDistribution, Decade, Collaborator, AuthorProductivityPoint,
 GrowthRow, Author, PublicationGrowthPoint, PublicationTypeTimelinePoint,
 VenueHeatmapPoint, CollabWeightBucket
} from '../api'
import { compact, full, percent } from './MetricCard'
import { DataTable } from './DataTable'

export function TimelineChart({data,growth=false,showToggle=false}:{data:TimelinePoint[];growth?:boolean;showToggle?:boolean}) {
 const [table,setTable]=useState(false)
 const [internalGrowth,setInternalGrowth]=useState(growth)
 const isGrowth = showToggle ? internalGrowth : growth
 return <><div className="chart-tools">
  <span>{isGrowth?'Year-over-year change (%)':'Publications per calendar year'}</span>
  <div style={{display:'flex',gap:'10px',alignItems:'center'}}>
   {showToggle&&<div className="segmented"><button aria-pressed={!internalGrowth} onClick={()=>setInternalGrowth(false)}>Volume</button><button aria-pressed={internalGrowth} onClick={()=>setInternalGrowth(true)}>Growth %</button></div>}
   <button className="text-button" onClick={()=>setTable(!table)}>{table?'Show chart':'Show data table'}</button>
  </div>
 </div>
  {data.length===0?<p className="empty-state">No dated publications available.</p>:table?<DataTable rows={data} rowKey={r=>r.year} caption="Annual publication activity" columns={[{key:'year',label:'Year',render:r=>r.year,value:r=>r.year},{key:'count',label:'Papers',render:r=>full(r.count),value:r=>r.count,numeric:true},{key:'growth',label:'Growth',render:r=>percent(r.growth_rate),value:r=>r.growth_rate,numeric:true}]}/>:<div className="intelligence-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={data} margin={{left:0,right:18,top:12,bottom:0}}><CartesianGrid vertical={false} stroke="var(--grid)"/><XAxis dataKey="year" minTickGap={35} tickLine={false} axisLine={false}/><YAxis width={62} tickFormatter={isGrowth?n=>`${Math.floor(Number(n))}%`:compact} tickLine={false} axisLine={false}/><Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} formatter={(v:any)=>isGrowth?`${Math.floor(Number(v))}%`:full(Number(v))} labelFormatter={v=>`Year ${v}`} contentStyle={{background:'var(--panel)',borderColor:'var(--line)',color:'var(--text)'}}/><Line type="monotone" dataKey={isGrowth?'growth_rate':'count'} name={isGrowth?'Growth':'Publications'} stroke="var(--accent-dark)" strokeWidth={2.5} dot={data.length<15} activeDot={{r:5}} isAnimationActive={false}/>{data.length>15&&<Brush dataKey="year" height={24} stroke="var(--muted)" fill="var(--paper)" travellerWidth={8}/>}</LineChart></ResponsiveContainer></div>}</>
}

export function VenueChart({data}:{data:Venue[]}) {
 return data.length?<div className="venue-chart"><ResponsiveContainer width="100%" height={Math.max(220,data.length*34)}><BarChart data={data} layout="vertical" margin={{left:0,right:20}}><XAxis type="number" tickFormatter={compact} axisLine={false} tickLine={false}/><YAxis type="category" dataKey="name" width={135} tick={{fontSize:11}} tickFormatter={(v:string)=>v.length>20?v.slice(0,19)+'…':v} axisLine={false} tickLine={false}/><Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} formatter={(v:any)=>full(Number(v))} contentStyle={{background:'var(--panel)',borderColor:'var(--line)'}}/><Bar dataKey="papers" name="Publications" fill="var(--accent)" barSize={17} isAnimationActive={false}/></BarChart></ResponsiveContainer></div>:<p className="empty-state">No venue records available.</p>
}

export function PublicationTypeChart({data}:{data:PublicationType[]}) {
 const total = data.reduce((s,d)=>s+d.count,0) || 1
 const chartData = data.map(d=>({
  name: d.type ? d.type.charAt(0).toUpperCase() + d.type.slice(1) : 'Unspecified',
  count: d.count,
  share: Math.floor(d.count / total * 100)
 }))
 return <div className="intelligence-chart" style={{height:Math.max(200,chartData.length*38)}}><ResponsiveContainer width="100%" height="100%"><BarChart data={chartData} layout="vertical" margin={{left:10,right:24,top:6,bottom:6}}><CartesianGrid horizontal={false} stroke="var(--grid)"/><XAxis type="number" tickFormatter={compact} axisLine={false} tickLine={false}/><YAxis type="category" dataKey="name" width={110} tick={{fontSize:11}} axisLine={false} tickLine={false}/><Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} formatter={(v:any,name:any)=>[name==='share'?`${v}%`:full(Number(v)),name==='share'?'Share':'Publications']} contentStyle={{background:'var(--panel)',borderColor:'var(--line)',color:'var(--text)'}}/><Bar dataKey="count" name="count" fill="var(--accent)" barSize={16} radius={[0,3,3,0]} isAnimationActive={false}/></BarChart></ResponsiveContainer></div>
}

export function CollaborationEvolutionChart({data,onSelectYear}:{data:CollaborationEvolutionPoint[];onSelectYear?: (year:number)=>void}) {
 const [mode,setMode]=useState<'team_size'|'authors_vs_papers'>('team_size')
 return <div>
  <div className="chart-tools">
   <span>{mode==='team_size'?'Mean authors per paper (team expansion over time)':'Publications vs. distinct researchers per year'}</span>
   <div className="segmented">
    <button aria-pressed={mode==='team_size'} onClick={()=>setMode('team_size')}>Team size</button>
    <button aria-pressed={mode==='authors_vs_papers'} onClick={()=>setMode('authors_vs_papers')}>Volume vs. Authors</button>
   </div>
  </div>
  <div className="intelligence-chart">
   <ResponsiveContainer width="100%" height="100%">
    {mode==='team_size'?(
     <LineChart data={data} onClick={(state:any)=>{if(onSelectYear && state?.activeLabel) onSelectYear(Number(state.activeLabel))}} margin={{left:0,right:20,top:12,bottom:0}}>
      <CartesianGrid vertical={false} stroke="var(--grid)"/>
      <XAxis dataKey="year" minTickGap={35} tickLine={false} axisLine={false}/>
      <YAxis domain={['auto','auto']} width={50} tickLine={false} axisLine={false} tickFormatter={n=>Number(n).toFixed(1)}/>
      <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} formatter={(v:any)=>[Number(v).toFixed(2)+' authors/paper','Average team size']} labelFormatter={v=>`Year ${v}`} contentStyle={{background:'var(--panel)',borderColor:'var(--line)',color:'var(--text)'}}/>
      <Line type="monotone" dataKey="average_authors_per_paper" stroke="var(--accent-dark)" strokeWidth={2.5} dot={false} activeDot={{r:5}} isAnimationActive={false}/>
      <Brush dataKey="year" height={24} stroke="var(--muted)" fill="var(--paper)" travellerWidth={8}/>
     </LineChart>
    ):(
     <LineChart data={data} onClick={(state:any)=>{if(onSelectYear && state?.activeLabel) onSelectYear(Number(state.activeLabel))}} margin={{left:0,right:20,top:12,bottom:0}}>
      <CartesianGrid vertical={false} stroke="var(--grid)"/>
      <XAxis dataKey="year" minTickGap={35} tickLine={false} axisLine={false}/>
      <YAxis width={62} tickFormatter={compact} tickLine={false} axisLine={false}/>
      <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} formatter={(v:any,name:any)=>[full(Number(v)),name==='publications'?'Publications':'Distinct Researchers']} labelFormatter={v=>`Year ${v}`} contentStyle={{background:'var(--panel)',borderColor:'var(--line)',color:'var(--text)'}}/>
      <Line type="monotone" dataKey="publications" name="publications" stroke="var(--accent)" strokeWidth={2} dot={false} isAnimationActive={false}/>
      <Line type="monotone" dataKey="unique_authors" name="unique_authors" stroke="var(--color-network-node)" strokeWidth={2} dot={false} isAnimationActive={false}/>
      <Brush dataKey="year" height={24} stroke="var(--muted)" fill="var(--paper)" travellerWidth={8}/>
     </LineChart>
    )}
   </ResponsiveContainer>
  </div>
 </div>
}

export function TeamDistributionChart({data,onSelectCategory}:{data:TeamDistribution[];onSelectCategory?: (category:string)=>void}) {
 return <div className="intelligence-chart" style={{height:180}}><ResponsiveContainer width="100%" height="100%"><BarChart data={data} onClick={(state:any)=>{if(onSelectCategory && state?.activePayload?.[0]?.payload?.category) onSelectCategory(state.activePayload[0].payload.category)}} layout="vertical" margin={{left:10,right:24,top:6,bottom:6}}><CartesianGrid horizontal={false} stroke="var(--grid)"/><XAxis type="number" unit="%" domain={[0,60]} tickLine={false} axisLine={false}/><YAxis type="category" dataKey="category" width={120} tick={{fontSize:11}} tickLine={false} axisLine={false}/><Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} formatter={(v:any,_,entry:any)=>[entry.payload.percentage+'% ('+full(entry.payload.count)+' papers)','Share']} contentStyle={{background:'var(--panel)',borderColor:'var(--line)',color:'var(--text)'}}/><Bar dataKey="percentage" name="Share" fill="var(--accent-dark)" barSize={16} radius={[0,3,3,0]} isAnimationActive={false}/></BarChart></ResponsiveContainer></div>
}

export function DecadeBarChart({ data, metric = 'publications', onSelectDecade }: { data: Decade[]; metric?: 'publications' | 'authors' | 'average_authors_per_paper'; onSelectDecade?: (decade:number)=>void }) {
 const labels: Record<string, string> = {
  publications: 'Publications',
  authors: 'Researchers',
  average_authors_per_paper: 'Authors per paper'
 }
 const isAvg = metric === 'average_authors_per_paper'
 return <div className="intelligence-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={data} onClick={(state:any)=>{if(onSelectDecade && state?.activePayload?.[0]?.payload?.decade) onSelectDecade(Number(state.activePayload[0].payload.decade))}} margin={{ right: 18, top: 20 }}><CartesianGrid vertical={false} stroke="var(--grid)"/><XAxis dataKey="decade" tickFormatter={n => `${n}s`} axisLine={false} tickLine={false}/><YAxis tickFormatter={isAvg ? n => Number(n).toFixed(1) : compact} width={62} domain={isAvg ? ['auto', 'auto'] : [0, 'auto']} axisLine={false} tickLine={false}/><Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} labelFormatter={n => `${n}s`} formatter={(v: any) => [Number(v).toLocaleString('en-US', { maximumFractionDigits: 2 }), labels[metric] || 'Count']} contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)' }}/><Bar dataKey={metric} name={labels[metric] || 'Value'} fill="var(--accent)" maxBarSize={60} isAnimationActive={false}/></BarChart></ResponsiveContainer></div>
}

export function AuthorProductivityChart({ data }: { data: AuthorProductivityPoint[] }) {
 const [view, setView] = useState<'stack' | 'team_size'>('stack')
 return <div>
  <div className="chart-tools">
   <span>{view === 'stack' ? 'Solo publications vs. collaborative publications' : 'Mean co-author team size over career'}</span>
   <div className="segmented">
    <button aria-pressed={view === 'stack'} onClick={() => setView('stack')}>Solo vs. Team</button>
    <button aria-pressed={view === 'team_size'} onClick={() => setView('team_size')}>Avg Co-authors</button>
   </div>
  </div>
  <div className="intelligence-chart">
   <ResponsiveContainer width="100%" height="100%">
    {view === 'stack' ? (
     <BarChart data={data} margin={{ left: 0, right: 18, top: 12, bottom: 0 }}>
      <CartesianGrid vertical={false} stroke="var(--grid)" />
      <XAxis dataKey="year" minTickGap={30} tickLine={false} axisLine={false} />
      <YAxis width={55} tickFormatter={compact} tickLine={false} axisLine={false} />
      <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} 
       formatter={(v: any, name: any) => [full(Number(v)), name === 'solo_papers' ? 'Solo Papers' : 'Collaborative Papers']} 
       labelFormatter={v => `Year ${v}`} 
       contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)', color: 'var(--text)' }}
      />
      <Bar dataKey="collaborative_papers" name="collaborative_papers" stackId="a" fill="var(--accent)" isAnimationActive={false} />
      <Bar dataKey="solo_papers" name="solo_papers" stackId="a" fill="var(--color-network-node)" isAnimationActive={false} />
      {data.length > 15 && <Brush dataKey="year" height={24} stroke="var(--muted)" fill="var(--paper)" travellerWidth={8} />}
     </BarChart>
    ) : (
     <LineChart data={data} margin={{ left: 0, right: 18, top: 12, bottom: 0 }}>
      <CartesianGrid vertical={false} stroke="var(--grid)" />
      <XAxis dataKey="year" minTickGap={30} tickLine={false} axisLine={false} />
      <YAxis width={50} tickLine={false} axisLine={false} domain={['auto', 'auto']} tickFormatter={n => Number(n).toFixed(1)} />
      <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} 
       formatter={(v: any) => [`${Number(v).toFixed(2)} co-authors`, 'Average Co-authors']} 
       labelFormatter={v => `Year ${v}`} 
       contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)', color: 'var(--text)' }}
      />
      <Line type="monotone" dataKey="avg_coauthors" stroke="var(--accent-dark)" strokeWidth={2.5} dot={data.length < 15} isAnimationActive={false} />
      {data.length > 15 && <Brush dataKey="year" height={24} stroke="var(--muted)" fill="var(--paper)" travellerWidth={8} />}
     </LineChart>
    )}
   </ResponsiveContainer>
  </div>
 </div>
}

export function CollaboratorStrengthChart({ data }: { data: Collaborator[] }) {
 const top10 = data.slice(0, 10)
 return top10.length ? (
  <div className="venue-chart">
   <ResponsiveContainer width="100%" height={Math.max(220, top10.length * 34)}>
    <BarChart data={top10} layout="vertical" margin={{ left: 0, right: 30 }}>
     <XAxis type="number" tickFormatter={compact} axisLine={false} tickLine={false} />
     <YAxis type="category" dataKey="name" width={135} tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.length > 20 ? v.slice(0, 19) + '…' : v} axisLine={false} tickLine={false} />
     <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} 
      formatter={(v: any, _, entry: any) => [
       `${full(Number(v))} shared papers (${entry.payload.coauthorship_share ?? 0}% of career)`,
       'Collaboration strength'
      ]}
      contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)' }}
     />
     <Bar dataKey="shared_papers" name="Shared papers" fill="var(--color-network-node)" barSize={17} isAnimationActive={false} />
    </BarChart>
   </ResponsiveContainer>
  </div>
 ) : <p className="empty-state">No collaborators recorded.</p>
}

const VENUE_PALETTE = ['var(--accent)', 'var(--accent-dark)', 'var(--color-network-node)', '#0284c7', '#7c3aed', '#db2777', '#059669', '#d97706']

export function VenueComparisonChart({ data }: { data: { year: number; venue: string; count: number }[] }) {
 const venues = Array.from(new Set(data.map(d => d.venue)))
 const yearsMap = new Map<number, any>()
 data.forEach(d => {
  if (!yearsMap.has(d.year)) yearsMap.set(d.year, { year: d.year })
  yearsMap.get(d.year)[d.venue] = d.count
 })
 const chartData = Array.from(yearsMap.values()).sort((a, b) => a.year - b.year)

 return <div className="intelligence-chart" style={{ height: 320 }}>
  <ResponsiveContainer width="100%" height="100%">
   <LineChart data={chartData} margin={{ left: 0, right: 20, top: 12, bottom: 0 }}>
    <CartesianGrid vertical={false} stroke="var(--grid)" />
    <XAxis dataKey="year" minTickGap={35} tickLine={false} axisLine={false} />
    <YAxis width={62} tickFormatter={compact} tickLine={false} axisLine={false} />
    <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} 
     formatter={(v: any, name: any) => [full(Number(v)), name]}
     labelFormatter={v => `Year ${v}`}
     contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)', color: 'var(--text)' }}
    />
    {venues.map((v, i) => (
     <Line 
      key={v} 
      type="monotone" 
      dataKey={v} 
      stroke={VENUE_PALETTE[i % VENUE_PALETTE.length]} 
      strokeWidth={2} 
      dot={false} 
      isAnimationActive={false} 
     />
    ))}
    {chartData.length > 15 && <Brush dataKey="year" height={24} stroke="var(--muted)" fill="var(--paper)" travellerWidth={8} />}
   </LineChart>
  </ResponsiveContainer>
 </div>
}

export function GrowthMatrixScatterChart({ data, onSelect }: { data: GrowthRow[]; onSelect?: (id: number) => void }) {
 const valid = data.filter(d => d.growth_rate !== null && d.historical_publications > 0)
 const maxGrowth = Math.max(...valid.map(d => Math.abs(d.growth_rate!)), 100)

 return <div>
  <div className="chart-tools">
   <span>X: Historical Volume · Y: Recent Growth (%) · Bubble size: Recent Volume</span>
   <span className="coverage">{valid.length} benchmarked venues</span>
  </div>
  <div className="intelligence-chart" style={{ height: 340 }}>
   <ResponsiveContainer width="100%" height="100%">
    <ScatterChart margin={{ left: 10, right: 30, top: 20, bottom: 20 }}>
     <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
     <XAxis 
      type="number" 
      dataKey="historical_publications" 
      name="Historical Papers" 
      tickFormatter={compact} 
      axisLine={false} 
      tickLine={false}
     />
     <YAxis 
      type="number" 
      dataKey="growth_rate" 
      name="Growth Rate" 
      unit="%" 
      domain={['auto', Math.min(maxGrowth, 1500)]} 
      tickFormatter={n => `${Math.floor(Number(n))}%`} 
      axisLine={false} 
      tickLine={false} 
      width={65}
     />
     <ZAxis type="number" dataKey="recent_publications" range={[50, 350]} />
     <ReferenceLine y={0} stroke="var(--line)" />
     <Tooltip cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} content={({ payload }) => {
       if (!payload || !payload.length) return null
       const d = payload[0].payload as GrowthRow
       return <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', padding: '10px 14px', borderRadius: '4px', fontSize: '12px' }}>
        <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--text)' }}>{d.name}</strong>
        <div>Recent: <strong style={{ fontFamily: 'var(--font-mono)' }}>{full(d.recent_publications)}</strong></div>
        <div>Historical: <strong style={{ fontFamily: 'var(--font-mono)' }}>{full(d.historical_publications)}</strong></div>
        <div>Growth: <strong style={{ color: (d.growth_rate ?? 0) >= 0 ? 'var(--color-positive)' : 'var(--color-error)' }}>{d.growth_rate != null ? `${d.growth_rate > 0 ? '+' : ''}${Math.floor(d.growth_rate)}%` : 'N/A'}</strong></div>
       </div>
      }}
     />
     <Scatter 
      name="Venues" 
      data={valid} 
      fill="var(--accent)" 
      onClick={(entry: any) => onSelect && onSelect(entry.id)} 
      cursor="pointer" 
      isAnimationActive={false} 
     />
    </ScatterChart>
   </ResponsiveContainer>
  </div>
 </div>
}

export function VenueTopAuthorsChart({ data }: { data: Author[] }) {
 const top10 = data.slice(0, 10)
 return top10.length ? (
  <div className="venue-chart">
   <ResponsiveContainer width="100%" height={Math.max(220, top10.length * 34)}>
    <BarChart data={top10} layout="vertical" margin={{ left: 0, right: 30 }}>
     <XAxis type="number" tickFormatter={compact} axisLine={false} tickLine={false} />
     <YAxis type="category" dataKey="name" width={135} tick={{ fontSize: 11 }} tickFormatter={(v: string) => v.length > 20 ? v.slice(0, 19) + '…' : v} axisLine={false} tickLine={false} />
     <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} 
      formatter={(v: any, _, entry: any) => [
       `${full(Number(v))} publications (${entry.payload.venue_share ?? 0}% of venue)`,
       'Venue output'
      ]}
      contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)' }}
     />
     <Bar dataKey="papers" name="Publications" fill="var(--accent)" barSize={17} isAnimationActive={false} />
    </BarChart>
   </ResponsiveContainer>
  </div>
 ) : <p className="empty-state">No researcher records available.</p>
}

export function ResearcherScatterChart({ data, onSelect }: { data: (Author & { collaborators?: number })[]; onSelect?: (id: number) => void }) {
 return <div>
  <div className="chart-tools">
   <span>X: Total Publications · Y: Collaborators · Community positioning</span>
  </div>
  <div className="intelligence-chart" style={{ height: 320 }}>
   <ResponsiveContainer width="100%" height="100%">
    <ScatterChart margin={{ left: 10, right: 30, top: 20, bottom: 20 }}>
     <CartesianGrid stroke="var(--grid)" strokeDasharray="3 3" />
     <XAxis type="number" dataKey="papers" name="Publications" tickFormatter={compact} axisLine={false} tickLine={false} />
     <YAxis type="number" dataKey="collaborators" name="Collaborators" tickFormatter={compact} axisLine={false} tickLine={false} width={60} />
     <Tooltip cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} content={({ payload }) => {
       if (!payload || !payload.length) return null
       const d = payload[0].payload
       return <div style={{ background: 'var(--panel)', border: '1px solid var(--line)', padding: '10px 14px', borderRadius: '4px', fontSize: '12px' }}>
        <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--text)' }}>{d.name}</strong>
        <div>Publications: <strong style={{ fontFamily: 'var(--font-mono)' }}>{full(d.papers)}</strong></div>
        <div>Collaborators: <strong style={{ fontFamily: 'var(--font-mono)' }}>{full(d.collaborators ?? 0)}</strong></div>
       </div>
      }}
     />
     <Scatter name="Researchers" data={data} fill="var(--color-network-node)" onClick={(entry: any) => onSelect && onSelect(entry.author_id)} cursor="pointer" isAnimationActive={false} />
    </ScatterChart>
   </ResponsiveContainer>
  </div>
 </div>
}

export function PublicationGrowthCombinedChart({ data, onSelectYear }: { data: PublicationGrowthPoint[]; onSelectYear?: (year:number)=>void }) {
 const [mode, setMode] = useState<'combined' | 'volume' | 'growth'>('combined')
 return <div>
  <div className="chart-tools">
   <span>{mode === 'combined' ? 'Publication volume (Line, left) vs. YoY growth % (Bars, right)' : mode === 'volume' ? 'Total publications per calendar year' : 'Year-over-year growth percentage'}</span>
   <div className="segmented">
    <button aria-pressed={mode === 'combined'} onClick={() => setMode('combined')}>Combined</button>
    <button aria-pressed={mode === 'volume'} onClick={() => setMode('volume')}>Volume</button>
    <button aria-pressed={mode === 'growth'} onClick={() => setMode('growth')}>Growth %</button>
   </div>
  </div>
  <div className="intelligence-chart" style={{ height: 320 }}>
   <ResponsiveContainer width="100%" height="100%">
    <ComposedChart data={data} onClick={(state:any)=>{if(onSelectYear && state?.activeLabel) onSelectYear(Number(state.activeLabel))}} margin={{ left: 0, right: 38, top: 12, bottom: 0 }}>
     <CartesianGrid vertical={false} stroke="var(--grid)" />
     <XAxis dataKey="year" minTickGap={35} tickLine={false} axisLine={false} />
     <YAxis yAxisId="left" width={62} tickFormatter={compact} tickLine={false} axisLine={false} />
     <YAxis yAxisId="right" orientation="right" width={50} tickFormatter={n => `${Math.floor(Number(n))}%`} tickLine={false} axisLine={false} domain={[-20, 60]} />
     <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} 
      formatter={(v: any, name: any) => [name === 'growth' ? `${Math.floor(Number(v))}%` : full(Number(v)), name === 'growth' ? 'YoY Growth' : 'Publications']} 
      labelFormatter={v => `Year ${v}`} 
      contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)', color: 'var(--text)' }} 
     />
     {(mode === 'combined' || mode === 'growth') && (
      <Bar yAxisId="right" dataKey="growth_percentage" name="growth" fill="oklch(62% 0.15 43 / 0.3)" stroke="var(--accent-dark)" maxBarSize={16} isAnimationActive={false} />
     )}
     {(mode === 'combined' || mode === 'volume') && (
      <Line yAxisId="left" type="monotone" dataKey="publication_count" name="publications" stroke="var(--accent-dark)" strokeWidth={2.5} dot={data.length < 15} isAnimationActive={false} />
     )}
     {data.length > 15 && <Brush dataKey="year" height={24} stroke="var(--muted)" fill="var(--paper)" travellerWidth={8} />}
    </ComposedChart>
   </ResponsiveContainer>
  </div>
 </div>
}

const TYPE_COLORS: Record<string, string> = {
 article: '#d97706',
 inproceedings: '#0284c7',
 incollection: '#7c3aed',
 book: '#059669',
 phdthesis: '#db2777',
 mastersthesis: '#ea580c',
 unspecified: '#64748b'
}

export function PublicationTypeDonutChart({ data, onSelectType }: { data: PublicationType[]; onSelectType?: (type:string)=>void }) {
 const total = data.reduce((s, d) => s + d.count, 0) || 1
 const chartData = data.map(d => ({
  name: d.type ? d.type.charAt(0).toUpperCase() + d.type.slice(1) : 'Unspecified',
  rawType: d.type ? d.type.toLowerCase() : 'unspecified',
  count: d.count,
  share: Math.floor(d.count / total * 100)
 }))

 return <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
  <div style={{ width: '100%', height: 220 }}>
   <ResponsiveContainer width="100%" height="100%">
    <PieChart>
     <Pie 
      data={chartData} 
      onClick={(entry:any)=>{if(onSelectType && entry?.rawType) onSelectType(entry.rawType)}}
      dataKey="count" 
      nameKey="name" 
      cx="50%" 
      cy="50%" 
      innerRadius={55} 
      outerRadius={85} 
      paddingAngle={3}
      isAnimationActive={false}
     >
      {chartData.map(entry => (
       <Cell key={entry.name} fill={TYPE_COLORS[entry.rawType] || '#94a3b8'} />
      ))}
     </Pie>
     <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} 
      formatter={(v: any, _, entry: any) => [
       `${full(Number(v))} papers (${entry.payload.share}%)`, 
       entry.payload.name
      ]} 
      contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)', color: 'var(--text)' }} 
     />
    </PieChart>
   </ResponsiveContainer>
  </div>
  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 14px', justifyContent: 'center', fontSize: '11px', marginTop: '8px' }}>
   {chartData.map(item => (
    <div key={item.name} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
     <span style={{ width: 9, height: 9, borderRadius: '50%', background: TYPE_COLORS[item.rawType] || '#94a3b8' }} />
     <span>{item.name}: <strong>{item.share}%</strong></span>
    </div>
   ))}
  </div>
 </div>
}

export function PublicationTypeTimelineChart({ data }: { data: PublicationTypeTimelinePoint[] }) {
 const types = Array.from(new Set(data.map(d => d.type || 'unspecified')))
 const yearsMap = new Map<number, any>()
 data.forEach(d => {
  if (!yearsMap.has(d.year)) yearsMap.set(d.year, { year: d.year })
  yearsMap.get(d.year)[d.type || 'unspecified'] = d.count
 })
 const chartData = Array.from(yearsMap.values()).sort((a, b) => a.year - b.year)

 return <div className="intelligence-chart" style={{ height: 280 }}>
  <ResponsiveContainer width="100%" height="100%">
   <LineChart data={chartData} margin={{ left: 0, right: 20, top: 12, bottom: 0 }}>
    <CartesianGrid vertical={false} stroke="var(--grid)" />
    <XAxis dataKey="year" minTickGap={35} tickLine={false} axisLine={false} />
    <YAxis width={62} tickFormatter={compact} tickLine={false} axisLine={false} />
    <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} 
     formatter={(v: any, name: any) => [full(Number(v)), String(name).toUpperCase()]} 
     labelFormatter={v => `Year ${v}`} 
     contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)', color: 'var(--text)' }} 
    />
    {types.map(t => (
     <Line 
      key={t} 
      type="monotone" 
      dataKey={t} 
      stroke={TYPE_COLORS[t.toLowerCase()] || '#94a3b8'} 
      strokeWidth={2} 
      dot={false} 
      isAnimationActive={false} 
     />
    ))}
    {chartData.length > 15 && <Brush dataKey="year" height={24} stroke="var(--muted)" fill="var(--paper)" travellerWidth={8} />}
   </LineChart>
  </ResponsiveContainer>
 </div>
}

export function VenueActivityHeatmap({ data, onSelectVenue }: { data: VenueHeatmapPoint[]; onSelectVenue?: (venue: string) => void }) {
 if (!data.length) return <p className="empty-state">No venue heatmap data available.</p>
 const venues = Array.from(new Set(data.map(d => d.venue)))
 const years = Array.from(new Set(data.map(d => d.year))).sort((a, b) => a - b)
 const max = Math.max(...data.map(d => d.count), 1)

 const matrix = new Map<string, Map<number, number>>()
 data.forEach(d => {
  if (!matrix.has(d.venue)) matrix.set(d.venue, new Map())
  matrix.get(d.venue)!.set(d.year, d.count)
 })

 return <div className="venue-heatmap-container">
  <div className="venue-heatmap-table-wrap">
   <table className="venue-heatmap-table">
    <thead>
     <tr>
      <th className="venue-heatmap-corner">Venue</th>
      {years.map(y => (
       <th key={y} className="venue-heatmap-year">{String(y).slice(2)}</th>
      ))}
     </tr>
    </thead>
    <tbody>
     {venues.map(v => (
      <tr key={v}>
       <td className="venue-heatmap-label" title={v}>
        {onSelectVenue ? (
         <button className="text-button venue-name-btn" onClick={() => onSelectVenue(v)}>{v}</button>
        ) : (
         <span>{v}</span>
        )}
       </td>
       {years.map(y => {
        const count = matrix.get(v)?.get(y) || 0
        const intensity = count === 0 ? 0 : Math.min(1, Math.max(0.12, count / max))
        return (
         <td 
          key={y} 
          className="venue-heatmap-cell" 
          style={{
           background: count === 0 ? 'var(--paper-2)' : `oklch(62% 0.15 43 / ${intensity})`,
           color: intensity > 0.65 ? '#fff' : 'var(--text)'
          }}
          title={`${v} (${y}): ${full(count)} papers`}
         >
          {count > 0 ? (count >= 1000 ? `${(count / 1000).toFixed(1)}k` : count) : '·'}
         </td>
        )
       })}
      </tr>
     ))}
    </tbody>
   </table>
  </div>
  <div className="heatmap-legend" style={{ marginTop: '12px' }}>
   <span>Low volume</span>
   <div className="legend-gradient" />
   <span>Peak volume ({full(max)} papers/yr)</span>
  </div>
 </div>
}

export function NetworkStrengthHistogram({ data }: { data: CollabWeightBucket[] }) {
 return <div className="intelligence-chart" style={{ height: 220 }}>
  <ResponsiveContainer width="100%" height="100%">
   <BarChart data={data} margin={{ left: 0, right: 20, top: 12, bottom: 0 }}>
    <CartesianGrid vertical={false} stroke="var(--grid)" />
    <XAxis dataKey="bucket" axisLine={false} tickLine={false} />
    <YAxis width={65} tickFormatter={compact} axisLine={false} tickLine={false} />
    <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}} 
     formatter={(v: any, _, entry: any) => [
      `${full(Number(v))} collaborations (${entry.payload.percentage ?? 0}%)`, 
      `${full(Number(v))} collaborations (${Math.floor(entry.payload.percentage ?? 0)}%)`, 
      'Tie count'
     ]} 
     contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)', color: 'var(--text)' }} 
    />
    <Bar dataKey="count" name="Ties" fill="var(--color-network-node)" barSize={34} radius={[3, 3, 0, 0]} isAnimationActive={false} />
   </BarChart>
  </ResponsiveContainer>
 </div>
}
