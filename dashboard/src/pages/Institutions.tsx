import { useState } from 'react'
import { api, type Institution } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { DataTable } from '../components/DataTable'
import { ExportToolbar } from '../components/ExportToolbar'
import { full, compact } from '../components/MetricCard'

const TYPES = ['All', 'University', 'Corporate Lab', 'Research Institute']
const COUNTRIES = ['All', 'United States', 'China', 'United Kingdom', 'Switzerland', 'Germany', 'Singapore', 'Canada', 'France', 'Japan', 'South Korea', 'Australia']

export default function Institutions() {
  const [type, setType] = useState('All')
  const [country, setCountry] = useState('All')
  const [sort, setSort] = useState<'publication_count' | 'citation_count' | 'h_index'>('publication_count')
  const [order, setOrder] = useState<'asc' | 'desc'>('desc')

  const state = useResource(`institutions:${type}:${country}:${sort}:${order}`, () =>
    api.institutions({
      type: type === 'All' ? undefined : type,
      country: country === 'All' ? undefined : country,
      sort,
      order,
      limit: 50
    })
  )

  const institutions = state.data ?? []

  return (
    <>
      <PageHeader
        title="Research institutions"
        description="Benchmark premier global universities and corporate research labs by publications, citations, and institutional h-index."
      />

      <div className="filter-controls-strip">
        <label>
          Institution Type:
          <select value={type} onChange={e => setType(e.target.value)}>
            {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>

        <label>
          Country / Region:
          <select value={country} onChange={e => setCountry(e.target.value)}>
            {COUNTRIES.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </label>

        <label>
          Rank By:
          <select value={sort} onChange={e => { setSort(e.target.value as typeof sort); setOrder('desc') }}>
            <option value="publication_count">Publication Volume</option>
            <option value="citation_count">Total Citations</option>
            <option value="h_index">Institutional h-index</option>
          </select>
        </label>
      </div>

      <ChartCard
        title="Global Research Institution Leaderboard"
        description="Top institutions ranked by computer science bibliographic output and scholarly impact."
        action={
          <ExportToolbar
            title={`institutions-${type}-${country}`}
            data={institutions}
            columns={[
              { key: 'name', label: 'Institution' },
              { key: 'short_name', label: 'Short Name' },
              { key: 'country', label: 'Country' },
              { key: 'type', label: 'Type' },
              { key: 'publication_count', label: 'Papers' },
              { key: 'citation_count', label: 'Citations' },
              { key: 'h_index', label: 'h-index' }
            ]}
          />
        }
      >
        {!state.data ? (
          <ResourceState {...state} />
        ) : (
          <DataTable<Institution>
            rows={institutions}
            rowKey={i => i.institution_id}
            caption="Institution rankings"
            sort={{ key: sort === 'publication_count' ? 'papers' : sort === 'citation_count' ? 'citations' : 'h_index', order }}
            onSort={key => {
              const next = key === 'papers' ? 'publication_count' : key === 'citations' ? 'citation_count' : key === 'h_index' ? 'h_index' : null
              if (!next) return
              if (sort === next) setOrder(current => current === 'desc' ? 'asc' : 'desc')
              else { setSort(next); setOrder('desc') }
            }}
            columns={[
              { key: 'rank', label: 'Rank', render: (_, i) => i + 1 },
              {
                key: 'name',
                label: 'Institution',
                render: i => (
                  <div className="institution-cell">
                    <a className="institution-table-link" href={`/institutions/${i.institution_id}`}>
                      <strong>{i.name}</strong>
                    </a>
                    <span className="institution-meta-pill">
                      {i.country} · {i.type}
                    </span>
                  </div>
                ),
                value: i => i.name
              },
              {
                key: 'papers',
                label: 'Indexed Papers',
                render: i => full(i.publication_count),
                value: i => i.publication_count,
                numeric: true
              },
              {
                key: 'citations',
                label: 'Total Citations',
                render: i => compact(i.citation_count),
                value: i => i.citation_count,
                numeric: true
              },
              {
                key: 'h_index',
                label: 'h-index',
                render: i => <span className="h-index-badge">{i.h_index}</span>,
                value: i => i.h_index,
                numeric: true
              },
              {
                key: 'action',
                label: 'Profile',
                render: i => (
                  <a className="text-link" href={`/institutions/${i.institution_id}`}>
                    View Profile →
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

