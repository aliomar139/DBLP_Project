import { ChartTooltip } from '../components/ChartTooltip'
import { useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, Legend
} from 'recharts'
import { api, type Topic, type TopicTimelinePoint } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { DataTable } from '../components/DataTable'
import { ExportToolbar } from '../components/ExportToolbar'
import { full, compact } from '../components/MetricCard'

const CATEGORIES = [
  'All',
  'Artificial Intelligence',
  'Systems & Architecture',
  'Security & Cryptography',
  'Data & Information',
  'Networks & Communications',
  'Software Engineering',
  'Theory & Algorithms',
  'Interdisciplinary'
]

const COLORS = ['#d76b38', '#2563eb', '#059669', '#7c3aed', '#db2777', '#d97706', '#0891b2', '#475569']

export default function Topics() {
  const [category, setCategory] = useState('All')
  const [sort, setSort] = useState<'growth_rate' | 'publication_count' | 'topic_name'>('growth_rate')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')
  const [selectedTopicIds, setSelectedTopicIds] = useState<number[]>([1, 2, 4, 15, 17]) // LLMs, Vision, GNNs, Security, Blockchain

  const topicsState = useResource(`topics:${category}:${sort}:${order}`, () =>
    api.topics({ category: category === 'All' ? undefined : category, sort, order, limit: 50 })
  )

  const timelineState = useResource(`topics:timeline:${selectedTopicIds.join(',')}`, () =>
    api.topicTimeline({ topics: selectedTopicIds.join(','), start_year: 1990, end_year: 2025 })
  )

  const topics = topicsState.data ?? []
  const timelinePoints = timelineState.data ?? []

  // Pivot timeline points by year: { year, TopicA: count, TopicB: count }
  const yearMap: Record<number, Record<string, number | string>> = {}
  const topicNames = Array.from(new Set(timelinePoints.map(p => p.topic_name)))

  timelinePoints.forEach(p => {
    if (!yearMap[p.year]) {
      yearMap[p.year] = { year: p.year }
    }
    yearMap[p.year][p.topic_name] = p.count
  })
  const chartData = Object.values(yearMap).sort((a, b) => Number(a.year) - Number(b.year))

  const toggleTopic = (id: number) => {
    if (selectedTopicIds.includes(id)) {
      if (selectedTopicIds.length > 1) {
        setSelectedTopicIds(selectedTopicIds.filter(t => t !== id))
      }
    } else {
      if (selectedTopicIds.length < 8) {
        setSelectedTopicIds([...selectedTopicIds, id])
      }
    }
  }

  return (
    <>
      <PageHeader
        title="Research topics"
        description="Explore computer science topics, see which ones are growing, and review their publication history."
      />

      {/* Interactive Topic Timeline */}
      <ChartCard
        title="Topic activity from 1990 to 2025"
        description="Comparative annual publication volume across computer science research topics. Toggle active topics using the selectors below."
        action={
          <div className="topic-selector-chips" aria-label="Toggle active topics">
            {topics.slice(0, 10).map(t => {
              const active = selectedTopicIds.includes(t.topic_id)
              return (
                <button
                  key={t.topic_id}
                  className={`topic-chip ${active ? 'active' : ''}`}
                  onClick={() => toggleTopic(t.topic_id)}
                >
                  {t.topic_name}
                </button>
              )
            })}
          </div>
        }
      >
        {!timelineState.data ? (
          <ResourceState {...timelineState} />
        ) : (
          <div className="chart" style={{ height: 380 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 10, right: 30, left: 10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--line)" />
                <XAxis dataKey="year" stroke="var(--muted)" tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }} />
                <YAxis
                  stroke="var(--muted)"
                  tick={{ fontSize: 11, fontFamily: 'var(--font-mono)' }}
                  tickFormatter={v => compact(v)}
                />
                <Tooltip content={props => <ChartTooltip {...props} />} cursor={{stroke: 'var(--muted)', strokeDasharray: '2 2'}}
                  contentStyle={{ background: 'var(--panel)', borderColor: 'var(--line)', borderRadius: 0, fontFamily: 'var(--font-mono)', fontSize: 12 }}
                  formatter={(val: unknown) => [full(Number(val)), 'Papers']}
                />
                <Legend wrapperStyle={{ fontSize: 12, paddingTop: 10 }} />
                {topicNames.map((name, i) => (
                  <Line
                    key={name}
                    type="monotone"
                    dataKey={name}
                    stroke={COLORS[i % COLORS.length]}
                    strokeWidth={2}
                    dot={false}
                    activeDot={{ r: 5 }}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </ChartCard>

      {/* Category Filter Pills */}
      <div className="category-pill-strip" role="tablist" aria-label="Research Areas">
        {CATEGORIES.map(cat => (
          <button
            key={cat}
            className={`category-pill ${category === cat ? 'active' : ''}`}
            onClick={() => setCategory(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Topic Growth Ranking */}
      <ChartCard
        title="Topic Growth & Volume Leaderboard"
        description="Computer science fields ranked by 10-year momentum (2016–2025 vs. earlier output) and total indexed publications."
        action={
          <ExportToolbar
            title={`topic-intelligence-${category}`}
            data={topics}
            columns={[
              { key: 'topic_name', label: 'Research Area' },
              { key: 'category', label: 'Category' },
              { key: 'publication_count', label: 'Total Papers' },
              { key: 'growth_rate', label: 'Growth Rate %' },
              { key: 'first_seen_year', label: 'First Seen' },
              { key: 'latest_activity_year', label: 'Latest Year' }
            ]}
          />
        }
      >
        {!topicsState.data ? (
          <ResourceState {...topicsState} />
        ) : (
          <DataTable<Topic>
            rows={topics}
            rowKey={t => t.topic_id}
            caption="Topic Growth Leaderboard"
            sort={{ key: sort === 'growth_rate' ? 'growth' : sort === 'publication_count' ? 'papers' : 'name', order }}
            onSort={key => {
              const next = key === 'growth' ? 'growth_rate' : key === 'papers' ? 'publication_count' : key === 'name' ? 'topic_name' : null
              if (!next) return
              if (sort === next) setOrder(current => current === 'desc' ? 'asc' : 'desc')
              else { setSort(next); setOrder('desc') }
            }}
            columns={[
              { key: 'rank', label: 'Rank', render: (_, i) => i + 1 },
              {
                key: 'name',
                label: 'Research Area',
                render: t => (
                  <div>
                    <a className="topic-table-link" href={`/topics/${t.topic_id}`}>
                      <strong>{t.topic_name}</strong>
                    </a>
                    <span className="topic-table-category">{t.category}</span>
                  </div>
                ),
                value: t => t.topic_name
              },
              {
                key: 'growth',
                label: '10-Year Growth',
                render: t => (
                  <span className={`growth-tag ${t.growth_rate && t.growth_rate > 0 ? 'growth-pos' : 'growth-neg'}`}>
                    {t.growth_rate !== null && t.growth_rate !== undefined ? `${t.growth_rate > 0 ? '+' : ''}${Math.floor(t.growth_rate)}%` : 'N/A'}
                  </span>
                ),
                value: t => Math.floor(t.growth_rate ?? 0),
                numeric: true
              },
              {
                key: 'papers',
                label: 'Indexed Papers',
                render: t => full(t.publication_count),
                value: t => t.publication_count,
                numeric: true
              },
              {
                key: 'span',
                label: 'Active Span',
                render: t => `${t.first_seen_year ?? 'N/A'} to ${t.latest_activity_year ?? 'N/A'}`,
                value: t => t.first_seen_year ?? 0
              },
              {
                key: 'action',
                label: 'Intelligence',
                render: t => (
                  <a className="text-link" href={`/topics/${t.topic_id}`}>
                    Topic Profile →
                  </a>
                )
              }
            ]}
          />
        )}
      </ChartCard>
    </>
  )
}

