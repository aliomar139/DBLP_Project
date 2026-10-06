import { ChartTooltip } from '../components/ChartTooltip'
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid
} from 'recharts'
import { api, type Author, type Venue } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { MetricCard, full, compact } from '../components/MetricCard'
import { DataTable } from '../components/DataTable'
import { ExportToolbar } from '../components/ExportToolbar'

export default function InstitutionProfile({ id }: { id: string }) {
  const state = useResource(`institution:${id}`, s => api.institution(id, s))
  const inst = state.data

  if (!inst) {
    return <ResourceState {...state} />
  }

  return (
    <>
      <PageHeader
        title={inst.name}
        description={`${inst.type} located in ${inst.country} (${inst.short_name}). Computer science research profile.`}
      />

      <div className="metric-strip">
        <MetricCard label="Institution Type" value={inst.type} detail={inst.country} />
        <MetricCard label="Indexed Papers" value={compact(inst.publication_count)} detail={`${full(inst.publication_count)} total`} />
        <MetricCard label="Total Citations" value={compact(inst.citation_count)} detail={`${full(inst.citation_count)} citations`} />
        <MetricCard label="Institutional h-index" value={inst.h_index} detail="Hirsch index" />
      </div>

      {/* Historical Output Chart */}
      <ChartCard
        title="Annual Publication Output"
        description="Historical publication production tracked across the DBLP indexed corpus."
        action={
          <ExportToolbar
            title={`${inst.short_name}-publication-history`}
            data={inst.yearly_activity}
            columns={[
              { key: 'year', label: 'Year' },
              { key: 'count', label: 'Papers' },
              { key: 'growth_rate', label: 'YoY Growth %' }
            ]}
          />
        }
      >
        <div className="chart" style={{ height: 320 }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={inst.yearly_activity} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" vertical={false} />
              <XAxis dataKey="year" stroke="var(--muted)" tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }} />
              <YAxis stroke="var(--muted)" tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }} tickFormatter={v => compact(v)} />
              <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}}
                contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)', borderRadius: 0, fontFamily: 'var(--font-mono)', fontSize: 12 }}
                formatter={(val: unknown) => [full(Number(val)), 'Papers']}
              />
              <Bar dataKey="count" fill="var(--accent)" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </ChartCard>

      <div className="two-col" style={{ marginTop: '24px' }}>
        {/* Top Scholars */}
        <ChartCard
          title="Top Contributing Researchers"
          description="Most prolific scholars affiliated with this institution."
        >
          <DataTable<Author>
            rows={inst.top_researchers}
            rowKey={a => a.author_id}
            caption="Top researchers in institution"
            columns={[
              { key: 'rank', label: 'Rank', render: (_, i) => i + 1 },
              { key: 'name', label: 'Researcher', render: a => <a href={`/authors/${a.author_id}`}>{a.name}</a>, value: a => a.name },
              { key: 'papers', label: 'Indexed Papers', render: a => full(a.papers), value: a => a.papers, numeric: true },
              { key: 'action', label: 'Action', render: a => <a className="text-link" href={`/authors/${a.author_id}`}>Profile →</a> }
            ]}
          />
        </ChartCard>

        {/* Top Research Domains */}
        <ChartCard
          title="Primary Research Strengths"
          description="Computer science topics with the most papers from this institution."
        >
          <div className="topic-strength-list">
            {inst.top_topics.map((t, idx) => (
              <div key={t.topic_id} className="topic-strength-item">
                <span className="strength-rank">#{idx + 1}</span>
                <div className="strength-info">
                  <a href={`/topics/${t.topic_id}`}><strong>{t.topic_name}</strong></a>
                  <small>{t.category}</small>
                </div>
                <strong className="strength-count">{full(t.papers)} papers</strong>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>

      <div className="two-col" style={{ marginTop: '24px' }}>
        {/* Top Publication Venues */}
        <ChartCard
          title="Primary Publication Venues"
          description="Journals and conferences preferred by researchers at this institution."
        >
          <DataTable<Venue>
            rows={inst.top_venues}
            rowKey={v => v.venue_id}
            caption="Top venues"
            columns={[
              { key: 'rank', label: 'Rank', render: (_, i) => i + 1 },
              { key: 'name', label: 'Venue', render: v => <a href={`/venues/${v.venue_id}`}>{v.name}</a>, value: v => v.name },
              { key: 'papers', label: 'Papers', render: v => full(v.papers), value: v => v.papers, numeric: true }
            ]}
          />
        </ChartCard>

        {/* Collaborating Partner Institutions */}
        <ChartCard
          title="Global Collaboration Network"
          description="Frequent institutional research co-authorship partners."
        >
          <DataTable<{ institution_id: number; name: string; short_name: string; country: string; shared_papers: number }>
            rows={inst.collaborating_institutions}
            rowKey={i => i.institution_id}
            caption="Collaborating institutions"
            columns={[
              { key: 'rank', label: 'Rank', render: (_, i) => i + 1 },
              {
                key: 'name',
                label: 'Partner Institution',
                render: i => (
                  <div>
                    <a href={`/institutions/${i.institution_id}`}><strong>{i.short_name}</strong></a>
                    <small style={{ display: 'block', color: 'var(--muted)', fontSize: '11px' }}>{i.country}</small>
                  </div>
                ),
                value: i => i.short_name
              },
              { key: 'shared', label: 'Shared Papers', render: i => full(i.shared_papers), value: i => i.shared_papers, numeric: true },
              { key: 'action', label: 'Action', render: i => <a className="text-link" href={`/institutions/${i.institution_id}`}>View →</a> }
            ]}
          />
        </ChartCard>
      </div>
    </>
  )
}

