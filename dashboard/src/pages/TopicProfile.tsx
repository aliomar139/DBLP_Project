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
import { BoardButton } from '../components/BoardButton'

export default function TopicProfile({ id }: { id: string }) {
  const state = useResource(`topic:${id}`, s => api.topic(id, s))
  const topic = state.data

  if (!topic) {
    return <ResourceState {...state} />
  }

  return (
    <>
      <PageHeader
        title={topic.topic_name}
        description={topic.description}
      >
        <BoardButton item={{ key: `topic:${topic.topic_id}`, type: 'topic', id: topic.topic_id, title: topic.topic_name, subtitle: topic.category, href: `/topics/${topic.topic_id}` }} />
      </PageHeader>

      <div className="metric-strip">
        <MetricCard label="Category" value={topic.category} detail="Computer science field" />
        <MetricCard label="Indexed Papers" value={compact(topic.publication_count)} detail={`${full(topic.publication_count)} total`} />
        <MetricCard
          label="10-Year Growth"
          value={topic.growth_rate !== null && topic.growth_rate !== undefined ? `${topic.growth_rate > 0 ? '+' : ''}${Math.floor(topic.growth_rate)}%` : 'N/A'}
          detail="2016–2025 vs. earlier"
        />
        <MetricCard
          label="Active Period"
          value={`${topic.first_seen_year ?? 'N/A'} to ${topic.latest_activity_year ?? 'N/A'}`}
          detail={`${(topic.latest_activity_year ?? 2025) - (topic.first_seen_year ?? 2000) + 1} active years`}
        />
      </div>

      {/* Historical Output Trajectory */}
      <ChartCard
        title={`Annual Publication Volume in ${topic.topic_name}`}
        description="Historical production trajectory from first indexed works to present."
        action={
          <ExportToolbar
            title={`topic-${topic.topic_name}-history`}
            data={topic.yearly_growth}
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
            <BarChart data={topic.yearly_growth} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
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
        {/* Top Researchers in this Topic */}
        <ChartCard
          title="Leading Researchers in this Domain"
          description={`Researchers with the most papers about ${topic.topic_name}.`}
        >
          <DataTable<Author>
            rows={topic.top_researchers}
            rowKey={a => a.author_id}
            caption="Top researchers in topic"
            columns={[
              { key: 'rank', label: 'Rank', render: (_, i) => i + 1 },
              { key: 'name', label: 'Researcher', render: a => <a href={`/authors/${a.author_id}`}>{a.name}</a>, value: a => a.name },
              { key: 'papers', label: 'Domain Papers', render: a => full(a.papers), value: a => a.papers, numeric: true },
              { key: 'action', label: 'Action', render: a => <a className="text-link" href={`/authors/${a.author_id}`}>Profile →</a> }
            ]}
          />
        </ChartCard>

        {/* Top Institutions in this Topic */}
        <ChartCard
          title="Leading Research Institutions"
          description={`Global universities and corporate research labs spearheading ${topic.topic_name}.`}
        >
          <DataTable<{ institution_id: number; name: string; short_name: string; country: string; papers: number }>
            rows={topic.top_institutions}
            rowKey={i => i.institution_id}
            caption="Top institutions in topic"
            columns={[
              { key: 'rank', label: 'Rank', render: (_, i) => i + 1 },
              {
                key: 'name',
                label: 'Institution',
                render: i => (
                  <div>
                    <a href={`/institutions/${i.institution_id}`}><strong>{i.short_name}</strong></a>
                    <small style={{ display: 'block', color: 'var(--muted)', fontSize: '11px' }}>{i.country}</small>
                  </div>
                ),
                value: i => i.short_name
              },
              { key: 'papers', label: 'Papers', render: i => full(i.papers), value: i => i.papers, numeric: true },
              { key: 'action', label: 'Action', render: i => <a className="text-link" href={`/institutions/${i.institution_id}`}>View →</a> }
            ]}
          />
        </ChartCard>
      </div>

      <div className="two-col" style={{ marginTop: '24px' }}>
        {/* Top Venues in this Topic */}
        <ChartCard
          title="Main publication venues"
          description="Top journals and conferences publishing work in this field."
        >
          <DataTable<Venue>
            rows={topic.top_venues}
            rowKey={v => v.venue_id}
            caption="Top venues in topic"
            columns={[
              { key: 'rank', label: 'Rank', render: (_, i) => i + 1 },
              { key: 'name', label: 'Venue', render: v => <a href={`/venues/${v.venue_id}`}>{v.name}</a>, value: v => v.name },
              { key: 'papers', label: 'Indexed Papers', render: v => full(v.papers), value: v => v.papers, numeric: true }
            ]}
          />
        </ChartCard>

        {/* Related & Co-occurring Topics */}
        <ChartCard
          title="Related Research Areas"
          description="Frequently co-studied computer science domains and interdisciplinary crossovers."
        >
          <div className="related-topics-grid">
            {topic.related_topics.map(rt => (
              <a key={rt.topic_id} className="related-topic-card" href={`/topics/${rt.topic_id}`}>
                <span className="related-topic-name">{rt.topic_name}</span>
                <span className="related-topic-category">{rt.category}</span>
                <small className="related-topic-papers">{full(rt.shared_papers)} shared papers</small>
              </a>
            ))}
          </div>
        </ChartCard>
      </div>
    </>
  )
}

