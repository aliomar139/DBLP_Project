import { useState } from 'react'
import { api } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { MetricCard, compact, full } from '../components/MetricCard'
import {
  PublicationGrowthCombinedChart, PublicationTypeDonutChart,
  PublicationTypeTimelineChart, CollaborationEvolutionChart,
  TeamDistributionChart, DecadeBarChart
} from '../components/Charts'
import { DataTable } from '../components/DataTable'
import { useInteraction } from '../components/InteractionContext'
import { QuickPreview } from '../components/QuickPreview'

export default function Overview() {
 const state = useResource('overview', async s => {
  const [overview, growth, authors, venues, types, typesTimeline, decades, collaborationEvolution, teamDistribution] = await Promise.all([
   api.overview(s),
   api.publicationGrowth(s),
   api.authors(s),
   api.venues(s),
   api.types(s),
   api.typesTimeline(s),
   api.decades(s),
   api.collaborationEvolution(s),
   api.teamDistribution(s)
  ])
  return { overview, growth, authors, venues, types, typesTimeline, decades, collaborationEvolution, teamDistribution }
 })

 const [decadeMetric, setDecadeMetric] = useState<'publications' | 'authors' | 'average_authors_per_paper'>('publications')
 const { setFilter, viewState, setViewState } = useInteraction()
 const savedDecadeMetric = viewState('overview-decade-metric') as typeof decadeMetric | undefined
 const selectedDecadeMetric = savedDecadeMetric ?? decadeMetric
 const chooseDecadeMetric = (metric: typeof decadeMetric) => { setDecadeMetric(metric); setViewState('overview-decade-metric', metric) }

 if (!state.data) return <><PageHeader title="Research landscape" description="Follow the people, publication venues, and collaborations shaping computer science."/><ResourceState {...state}/></>
 const { overview: o, growth, authors, venues, types, typesTimeline, decades, collaborationEvolution, teamDistribution } = state.data

 return <>
  <PageHeader title="Research overview" description="Explore papers, researchers, venues, and collaboration networks in the DBLP records.">
   <span className="coverage">Indexed publication years: {o.first_year ?? 'N/A'} to {o.last_year ?? 'N/A'}. {full(o.total_publications)} total records. <a className="text-link" href="/data-quality">View data notes</a></span>
  </PageHeader>

  <div className="metric-strip">
   <MetricCard label="Publications" value={compact(o.total_publications)} detail={`${full(o.total_publications)} indexed records`} history={growth.slice(-5).map(p => p.publication_count)} />
   <MetricCard label="Researchers" value={compact(o.total_authors)} detail="Distinct author identities" />
   <MetricCard label="Venues" value={full(o.total_venues)} detail="Journals, proceedings & repositories" />
   <MetricCard label="Authors per paper" value={(o.average_authors_per_paper ?? 0).toFixed(2)} detail="Mean across indexed publications" />
  </div>

  <ChartCard title="How has research output changed?" description="See yearly paper counts and the change from one year to the next. Use the chart controls to focus on a time period.">
   <PublicationGrowthCombinedChart data={growth} onSelectYear={year => setFilter('year', String(year), `Year: ${year}`)} />
  </ChartCard>

  <div className="discovery-grid">
   <ChartCard title="How has collaboration changed?" description="See the average number of authors per paper and how the research community has grown from 1970 to 2025." action={<a className="text-link" href="/network">View collaboration network</a>}>
    <CollaborationEvolutionChart data={collaborationEvolution} onSelectYear={year => setFilter('year', String(year), `Year: ${year}`)} />
   </ChartCard>
   <ChartCard title="Team size distribution" description="Breakdown of indexed papers by authorship count: solo, duo, small team, or large consortium.">
    <TeamDistributionChart data={teamDistribution} onSelectCategory={category => setFilter('team_size', category, `Team size: ${category}`)} />
    <DataTable rows={teamDistribution} rowKey={r => r.category} caption="Authorship distribution" columns={[
     { key: 'category', label: 'Team size', render: r => r.category },
     { key: 'count', label: 'Papers', render: r => full(r.count), numeric: true },
     { key: 'percentage', label: 'Share', render: r => `${r.percentage}%`, numeric: true }
    ]} />
   </ChartCard>
  </div>

  <ChartCard title="Decade comparison (1950s–2020s)" description="Compare research output, researcher population, and team sizes across eight generational cohorts." action={<div className="segmented"><button aria-pressed={selectedDecadeMetric === 'publications'} onClick={() => chooseDecadeMetric('publications')}>Papers</button><button aria-pressed={selectedDecadeMetric === 'authors'} onClick={() => chooseDecadeMetric('authors')}>Researchers</button><button aria-pressed={selectedDecadeMetric === 'average_authors_per_paper'} onClick={() => chooseDecadeMetric('average_authors_per_paper')}>Team size</button></div>}>
    <DecadeBarChart data={decades} metric={selectedDecadeMetric} onSelectDecade={decade => setFilter('decade', String(decade), `Decade: ${decade}s`)} />
   <details className="methodology" style={{ marginTop: '16px' }}>
    <summary>View decade cohort data</summary>
    <DataTable rows={decades} rowKey={r => r.decade} caption="Decade metrics" columns={[
     { key: 'decade', label: 'Decade', render: r => `${r.decade}s` },
     { key: 'publications', label: 'Publications', render: r => full(r.publications), numeric: true },
     { key: 'authors', label: 'Researchers', render: r => full(r.authors), numeric: true },
     { key: 'venues', label: 'Venues', render: r => full(r.venues), numeric: true },
     { key: 'average_authors_per_paper', label: 'Authors / paper', render: r => r.average_authors_per_paper.toFixed(2), numeric: true }
    ]} />
   </details>
  </ChartCard>

  <div className="discovery-grid">
   <ChartCard title="Most prolific researchers" description="All-time publication volume; a starting point for exploring careers.">
    <DataTable rows={authors} rowKey={r => r.author_id} caption="Most prolific researchers" columns={[
     { key: 'name', label: 'Researcher', render: r => <QuickPreview href={`/authors/${r.author_id}`} kind="Researcher" detail={`${full(r.papers)} indexed papers`}>{r.name}</QuickPreview>, value: r => r.name },
     { key: 'papers', label: 'Papers', render: r => full(r.papers), value: r => r.papers, numeric: true }
    ]} />
   </ChartCard>
   <ChartCard title="Where research is published" description="Largest indexed venues by volume. Open a venue to explore its history." action={<a className="text-link" href="/venues">Venue rankings →</a>}>
    <DataTable rows={venues} rowKey={r => r.venue_id} caption="Largest venues" columns={[
     { key: 'name', label: 'Venue', render: r => <QuickPreview href={`/venues/${r.venue_id}`} kind="Venue" detail={`${full(r.papers)} indexed papers`}>{r.name}</QuickPreview>, value: r => r.name },
     { key: 'papers', label: 'Papers', render: r => full(r.papers), value: r => r.papers, numeric: true }
    ]} />
   </ChartCard>
  </div>

  <ChartCard title="Publication types" description="See how articles, conference papers, and books are distributed from 1970 to 2025.">
   <div className="discovery-grid" style={{ alignItems: 'flex-start' }}>
    <div>
     <h4 style={{ margin: '0 0 10px', fontSize: '13px', color: 'var(--muted)' }}>Format Share Breakdown</h4>
     <PublicationTypeDonutChart data={types} onSelectType={type => setFilter('type', type, `Type: ${type}`)} />
    </div>
    <div>
     <h4 style={{ margin: '0 0 10px', fontSize: '13px', color: 'var(--muted)' }}>Annual Evolution by Format (1970–2025)</h4>
     <PublicationTypeTimelineChart data={typesTimeline} />
    </div>
   </div>
   <details className="methodology" style={{ marginTop: '16px' }}>
    <summary>View format distribution data table</summary>
    <DataTable rows={types} rowKey={r => r.type ?? 'unspecified'} caption="Publication types" columns={[
     { key: 'type', label: 'Record type', render: r => r.type ? r.type.toUpperCase() : 'UNSPECIFIED', value: r => r.type },
     { key: 'count', label: 'Publications', render: r => full(r.count), value: r => r.count, numeric: true },
     { key: 'share', label: 'Share', render: r => `${(r.count / Math.max(o.total_publications, 1) * 100).toFixed(1)}%`, numeric: true }
    ]} />
   </details>
  </ChartCard>

  <aside className="research-note">
   <h2>Read activity in context.</h2>
   <p>Publication counts and coauthorship describe research activity. Explore the underlying careers and venues before drawing conclusions about influence or quality.</p>
  </aside>
 </>
}
