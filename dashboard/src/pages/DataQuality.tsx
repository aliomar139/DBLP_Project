import { useEffect, useState } from 'react'
import { api, type DataQualityResponse } from '../api'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { MetricCard, full } from '../components/MetricCard'
import { ExportToolbar } from '../components/ExportToolbar'

export default function DataQuality() {
  const [data, setData] = useState<DataQualityResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setError(null)
    api.dataQuality(controller.signal)
      .then(value => { if (!controller.signal.aborted) setData(value) })
      .catch(err => { if (!controller.signal.aborted) setError(err.message || 'Failed to load data quality telemetry') })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [attempt])

if (loading) return <div className="resource-state">Checking the database...</div>
if (error || !data) return <div className="resource-state error" role="alert"><p>{error || 'Data quality information is unavailable.'}</p><button type="button" onClick={() => setAttempt(value => value + 1)}>Try again</button></div>

  const { health, audits, source_conflicts = [] } = data

  return (
    <div className="data-quality-page">
      <PageHeader
        title="Data quality"
        description="Check how complete the records are, where they came from, and how the calculated measures work."
      >
        <ExportToolbar title="dblp-data-quality-report" showPrint={true} />
      </PageHeader>

      {/* Database Vital Signs Metric Strip */}
      <div className="metric-strip">
        <MetricCard label="Indexed Publications" value={full(health.total_publications)} detail="Indexed bibliography records" />
        <MetricCard label="Computer Scientists" value={full(health.total_authors)} detail="Distinct indexed author identities" />
<MetricCard label="Publication venues" value={full(health.total_venues)} detail="Proceedings and journals" />
        <MetricCard label="Collaboration Ties" value={full(health.total_collaborations)} detail="Recorded co-authorship edges" />
        <MetricCard label="Historical Span" value={health.active_years_span} detail="Publication-year coverage" />
      </div>

      {/* Metadata Completeness Audits */}
      <ChartCard
        title="Metadata completeness"
        description="See which fields are complete, which values are missing, and how well records link to one another."
      >
        <div className="dq-audit-grid">
          {audits.map(a => (
            <div key={a.metric} className="dq-audit-row">
              <div className="dq-audit-info">
                <span className="dq-audit-dim">{a.dimension}</span>
                <strong className="dq-audit-name">{a.metric}</strong>
              </div>
              <div className="dq-audit-bar-wrapper">
                <div className="dq-audit-bar-bg" role="meter" aria-label={a.metric} aria-valuemin={0} aria-valuemax={100} aria-valuenow={a.completeness_percentage}>
                  <div
                    className={`dq-audit-bar-fill ${a.status.toLowerCase()}`}
                    style={{ width: `${a.completeness_percentage}%` }}
                  />
                </div>
                <span className="dq-audit-pct">{a.completeness_percentage.toFixed(1)}%</span>
              </div>
              <span className={`dq-audit-status status-${a.status.toLowerCase()}`}>
                {a.status.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      </ChartCard>

      {/* Multi-Source Discrepancy & Conflict Resolution */}
      {source_conflicts.length > 0 && (
        <ChartCard
        title="Conflicting records"
        description="See how the system handles differences between research indexes."
        >
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Research measure</th>
                  <th>Compared External Sources</th>
                  <th>Empirical Discrepancy Rate</th>
                  <th>How differences are handled</th>
                </tr>
              </thead>
              <tbody>
                {source_conflicts.map((sc, idx) => (
                  <tr key={idx}>
                    <td>
                      <strong>{sc.metric}</strong>
                    </td>
                    <td>
                      <div className="dq-sources-chips">
                        {sc.sources_compared.map(s => (
                          <span key={s} className="dq-source-chip">{s}</span>
                        ))}
                      </div>
                    </td>
                    <td className="numeric">
                      <span className="dq-discrepancy-pill">{sc.discrepancy_rate}</span>
                    </td>
                    <td>
                      <span className="dq-resolution-text">{sc.resolution_strategy}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </ChartCard>
      )}

    </div>
  )
}

