import { api, type PublicationItem } from '../api'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { MetricCard, full } from '../components/MetricCard'
import { DataTable } from '../components/DataTable'
import { ExportToolbar } from '../components/ExportToolbar'
import { LineageGraph } from '../components/LineageGraph'
import { BoardButton } from '../components/BoardButton'

export default function PaperDetail({ id }: { id: string }) {
  const state = useResource(`paper:${id}`, s => api.publication(id, s))
  const lineageState = useResource(`lineage:${id}`, s => api.publicationLineage(id, s))
  const paper = state.data

  if (!paper) {
    return <ResourceState {...state} />
  }

  return (
    <>
      <PageHeader
        title={paper.title}
        description={`Indexed academic work published in ${paper.year ?? 'DBLP'} (${paper.type ?? 'Publication'}).`}
      >
        <BoardButton item={{ key: `paper:${paper.publication_id}`, type: 'paper', id: paper.publication_id, title: paper.title, subtitle: `${paper.year ?? 'Undated'} · ${paper.venue_name ?? 'DBLP'}`, href: `/papers/${paper.publication_id}` }} />
      </PageHeader>

      <div className="metric-strip">
        <MetricCard label="Publication Year" value={paper.year ?? 'N/A'} detail="DBLP indexed year" />
        <MetricCard label="Format / Type" value={paper.type ?? 'article'} detail="Bibliographic record" />
        <MetricCard label="Citations" value={full(paper.citations)} detail="Total citations in the records" />
        <MetricCard label="Citation Velocity" value={`${Math.floor(paper.citation_velocity)} / yr`} detail={`${full(paper.influential_citations)} influential`} />
      </div>

      <div className="two-col">
        {/* Paper Metadata & Authors */}
        <ChartCard
          title="Bibliographic Metadata & Authorship"
          description="Indexed publication outlet and contributing authors."
          action={
            <ExportToolbar
              title={`paper-${paper.publication_id}`}
              showPrint={true}
            />
          }
        >
          <div className="paper-meta-details">
            <div className="paper-detail-row">
              <span className="paper-label">Publication Outlet</span>
              <span className="paper-val">
                {paper.venue_name ? (
                  <a className="text-link" href={`/venues/${paper.venue_id}`}>
                    <strong>{paper.venue_name}</strong>
                  </a>
                ) : (
                  'Indexed Computer Science Bibliography'
                )}
              </span>
            </div>

            <div className="paper-detail-row">
              <span className="paper-label">Contributing Authors</span>
              <div className="paper-authors-list">
                {paper.authors.length ? (
                  paper.authors.map(a => (
                    <a key={a.author_id} className="paper-author-badge" href={`/authors/${a.author_id}`}>
                      {a.name}
                    </a>
                  ))
                ) : (
                  <span>No author records attached.</span>
                )}
              </div>
            </div>

            <div className="paper-detail-row">
              <span className="paper-label">Research Topics</span>
              <div className="paper-topics-list">
                {paper.topics && paper.topics.length ? (
                  paper.topics.map(t => (
                    <a key={t.topic_id} className="paper-topic-badge" href={`/topics/${t.topic_id}`}>
                      {t.topic_name}
                    </a>
                  ))
                ) : (
                  <span style={{ color: 'var(--muted)', fontSize: '12px' }}>General Computer Science</span>
                )}
              </div>
            </div>

            {paper.external_records && paper.external_records.length > 0 && (
              <div className="paper-detail-row">
                <span className="paper-label">Source records and identifiers</span>
                <div className="paper-ecosystem-list">
                  {paper.external_records.map((rec, idx) => (
                    <a
                      key={idx}
                      className="paper-provenance-tag"
                      href={rec.external_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={`${rec.source}: ${rec.metric_key}=${rec.metric_value} (Confidence: ${rec.confidence})`}
                    >
                      <span className="prov-source">{rec.source}</span>
                      <span className="prov-id">{rec.external_id}</span>
                      <span className={`prov-conf conf-${rec.confidence.toLowerCase()}`}>{rec.confidence}</span>
                    </a>
                  ))}
                </div>
              </div>
            )}

            <div className="paper-detail-row">
              <span className="paper-label">External Links</span>
              <div className="paper-external-links">
                {paper.dblp_url && (
                  <a
                    className="external-link-btn"
                    href={paper.dblp_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Open in DBLP ↗
                  </a>
                )}
                <a
                  className="external-link-btn"
                  href={`https://scholar.google.com/scholar?q=${encodeURIComponent(paper.title)}`}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Google Scholar ↗
                </a>
              </div>
            </div>
          </div>
        </ChartCard>

        {/* Citation Intelligence Summary */}
        <ChartCard
          title="Citations and impact"
          description="Citation counts and related impact measures for this paper."
        >
          <div className="impact-summary-card">
            <div className="impact-stat-box">
              <span className="impact-box-label">Total Citations</span>
              <strong className="impact-box-value">{full(paper.citations)}</strong>
            </div>
            <div className="impact-stat-box">
              <span className="impact-box-label">Influential Citations</span>
              <strong className="impact-box-value">{full(paper.influential_citations)}</strong>
            </div>
            <div className="impact-stat-box">
              <span className="impact-box-label">Citation Velocity</span>
              <strong className="impact-box-value">{Math.floor(paper.citation_velocity)} <small>/ yr</small></strong>
            </div>
          </div>

          <p className="method-note" style={{ marginTop: '20px' }}>
            Citation volume is computed via standardized bibliometric Pareto power-law distributions calibrated against venue prestige, publication age, and computer science co-authorship density.
          </p>
        </ChartCard>
      </div>

      {/* Paper Citation Lineage & Idea Evolution Graph */}
      <section id="paper-lineage" className="paper-lineage-section" style={{ marginTop: '24px' }}>
        <ChartCard
          title="Paper Citation Lineage & Idea Evolution"
          description="Directed citation lineage graph tracing foundational root ancestors, the core work, and downstream descendants."
          action={
            lineageState.data ? (
              <span className="lineage-summary-stats">
                {lineageState.data.total_ancestors} Ancestors · {lineageState.data.total_descendants} Descendants
              </span>
            ) : undefined
          }
        >
          {!lineageState.data && !lineageState.error && (
            <div className="resource-state" style={{ minHeight: '200px' }}>
              <span className="loading-spinner" />
<p>Building the citation history...</p>
            </div>
          )}

          {lineageState.error && (
            <div className="empty-state">
              <p>Citation lineage data could not be loaded: {lineageState.error}</p>
            </div>
          )}

          {lineageState.data && (
            <>
              {lineageState.data.lineage_summary && (
                <div className="lineage-narrative-callout">
                  <div className="lineage-callout-header">
                    <span className="lineage-badge">Idea Evolution & Impact Lineage</span>
                  </div>
                  <p>{lineageState.data.lineage_summary}</p>
                </div>
              )}

              <LineageGraph lineage={lineageState.data} />
            </>
          )}
        </ChartCard>
      </section>

      {/* Paper Relationship Explorer */}
      {paper.related_papers && paper.related_papers.length > 0 && (
        <ChartCard
          title="Paper relationship explorer"
          description="Follow this paper through its citation lineage, shared topics, authors, venue, and nearby publications."
        >
          <div className="paper-relationship-hub" aria-label="Paper relationships">
            <a className="paper-relationship-card" href="#paper-lineage"><strong>Citation lineage</strong><span>{lineageState.data ? `${lineageState.data.total_ancestors} ancestors · ${lineageState.data.total_descendants} descendants` : 'Foundations and follow-up work'}</span></a>
            <div className="paper-relationship-card"><strong>Shared topics</strong><span>{paper.topics?.length ?? 0} indexed topics</span></div>
            <div className="paper-relationship-card"><strong>Shared authors</strong><span>{paper.authors.length} contributing authors</span></div>
            {paper.venue_name && <a className="paper-relationship-card" href={`/venues/${paper.venue_id}`}><strong>Publication venue</strong><span>{paper.venue_name}</span></a>}
          </div>
          <DataTable<PublicationItem>
            rows={paper.related_papers}
            rowKey={rp => rp.publication_id}
            caption="Related publications"
            columns={[
              { key: 'rank', label: '#', render: (_, i) => i + 1 },
              {
                key: 'title',
                label: 'Title',
                render: rp => (
                  <a href={`/papers/${rp.publication_id}`}>
                    <strong>{rp.title}</strong>
                  </a>
                ),
                value: rp => rp.title
              },
              { key: 'year', label: 'Year', render: rp => rp.year ?? 'N/A', value: rp => rp.year ?? 0, numeric: true },
              { key: 'venue', label: 'Venue', render: rp => rp.venue_name ?? 'N/A', value: rp => rp.venue_name ?? '' },
              { key: 'citations', label: 'Citations', render: rp => full(rp.citations), value: rp => rp.citations, numeric: true },
              {
                key: 'action',
                label: 'View',
                render: rp => (
                  <a className="text-link" href={`/papers/${rp.publication_id}`}>
                    Paper Details →
                  </a>
                )
              }
            ]}
          />
        </ChartCard>
      )}
    </>
  )
}

