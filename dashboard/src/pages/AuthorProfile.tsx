import { api, type SimilarResearcher } from '../api'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useResource } from '../hooks/useResource'
import { ChartCard, PageHeader, ResourceState } from '../components/ChartCard'
import { MetricCard, full, compact } from '../components/MetricCard'
import { TimelineChart, VenueChart, AuthorProductivityChart, CollaboratorStrengthChart } from '../components/Charts'
import { DataTable } from '../components/DataTable'
import { NetworkGraph } from '../components/NetworkGraph'
import { ExportToolbar } from '../components/ExportToolbar'
import { BoardButton } from '../components/BoardButton'

export default function AuthorProfile({ id }: { id: string }) {
  const state = useResource(`author:${id}`, s => api.author(id, s))
  const similarState = useResource(`author:similar:${id}`, s => api.authorSimilar(id, 4, s))
  const papersState = useResource(`author:papers:${id}`, s => api.publicationsSearch({ author_id: Number(id), sort_by: 'year', sort_order: 'desc', limit: 25 }, s))

  if (!state.data) return <ResourceState {...state} />
  const a = state.data
  const imp = a.impact_profile
  const career = a.career_intelligence
  const showResearcherRating = (_profile: NonNullable<typeof imp>) => false

  return (
    <>
      <a className="breadcrumb" href="/authors">← Researchers</a>
      <PageHeader
        title={a.name}
        description={
          a.institution ? (
            <span>
              Affiliated with{' '}
              <a className="text-link" href={`/institutions/${a.institution_id}`}>
                <strong>{a.institution}</strong>
              </a>
              . Career trajectory, multi-dimensional impact, publication venues, and collaboration network.
            </span>
          ) : (
            'Career trajectory, multi-dimensional impact, publication venues, and collaboration network.'
          )
        }
      >
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <BoardButton item={{ key: `researcher:${a.id}`, type: 'researcher', id: a.id, title: a.name, subtitle: a.institution ?? 'Researcher', href: `/authors/${a.id}` }} />
          <ExportToolbar title={`researcher-${a.name}`} showPrint={true} />
          <a className="button-link" href={`/network?author=${id}`}>Explore full network →</a>
        </div>
      </PageHeader>

      {/* Primary Research Topics */}
      {a.primary_topics && a.primary_topics.length > 0 && (
        <div className="author-topic-chips" aria-label="Research Domains">
          <span className="topic-chips-label">Research Focus:</span><span className="topic-chips-list">
          {a.primary_topics.map(t => (
            <a key={t.topic_id} className="author-topic-badge" href={`/topics/${t.topic_id}`}>
              {t.topic_name} <small>({t.publication_count} papers)</small>
            </a>
          ))}</span>
        </div>
      )}

      {/* Researcher ratings are omitted; the profile below shows publication and citation evidence. */}
      {null}
      {imp && showResearcherRating(imp) && (
        <div className="impact-intelligence-banner">
          <div className="impact-dimensions-grid">
            <div className="impact-dimension-card">
              <div className="dimension-header">
                <span className="dim-name">Academic Impact</span>
                <strong className="dim-val">{Math.floor(imp.academic_impact)}/100</strong>
              </div>
              <div className="dim-progress-bar">
                <div className="dim-progress-fill academic" style={{ width: `${Math.floor(imp.academic_impact)}%` }} />
              </div>
              <small className="dim-sub">{compact(imp.raw_metrics.total_citations)} cites · h-index: {imp.raw_metrics.h_index}</small>
            </div>

            <div className="impact-dimension-card">
              <div className="dimension-header">
                <span className="dim-name">Technology & Industry</span>
                <strong className="dim-val">{Math.floor(imp.technology_impact)}/100</strong>
              </div>
              <div className="dim-progress-bar">
                <div className="dim-progress-fill technology" style={{ width: `${Math.floor(imp.technology_impact)}%` }} />
              </div>
              <small className="dim-sub">~{imp.raw_metrics.industry_references.toLocaleString()} industry refs · {imp.raw_metrics.patent_citations_est} patent ties</small>
            </div>

            <div className="impact-dimension-card">
              <div className="dimension-header">
                <span className="dim-name">Open Science Dissemination</span>
                <strong className="dim-val">{Math.floor(imp.open_science_impact)}/100</strong>
              </div>
              <div className="dim-progress-bar">
                <div className="dim-progress-fill open-science" style={{ width: `${Math.floor(imp.open_science_impact)}%` }} />
              </div>
              <small className="dim-sub">{imp.raw_metrics.open_preprints} open preprints (CoRR/arXiv)</small>
            </div>

            <div className="impact-dimension-card">
              <div className="dimension-header">
                <span className="dim-name">Influence Growth Velocity</span>
                <strong className="dim-val">{Math.floor(imp.influence_growth)}/100</strong>
              </div>
              <div className="dim-progress-bar">
                <div className="dim-progress-fill growth" style={{ width: `${Math.floor(imp.influence_growth)}%` }} />
              </div>
              <small className="dim-sub">+{Math.floor(imp.raw_metrics.citation_velocity)} / yr velocity</small>
            </div>
          </div>

          <div className="impact-drivers-box">
            <span className="impact-drivers-title">Primary Scientific Impact Drivers:</span>
            <ul className="impact-drivers-list">
              {imp.main_drivers.map((driver, idx) => (
                <li key={idx}>
                  <span className="driver-bullet">✓</span> {driver}
                </li>
              ))}
            </ul>

            <details className="impact-methodology-details">
              <summary>View Methodology & Calibration Transparency</summary>
              <p>{imp.methodology}</p>
            </details>
          </div>
        </div>
      )}

      {/* Metric Strip */}
      <div className="metric-strip author-profile-metrics">
        <MetricCard label="Publications" value={full(a.total_publications)} detail={`${a.total_collaborative_papers} collaborative · ${a.total_solo_papers} solo`} />
        <MetricCard label="Total Citations" value={compact(a.total_citations ?? 0)} detail={`${full(a.total_citations ?? 0)} calibrated cites`} />
        <MetricCard label="Hirsch index" value={a.h_index ?? 0} detail={`h-index · ${Math.floor(a.citation_velocity ?? 0)} / yr velocity`} />
        <MetricCard label="Collaborators" value={full(a.collaborator_count)} detail={`${full(a.collaboration_strength)} shared ties`} />
        <MetricCard label="Career span" value={`${a.career_duration} yrs`} detail={`${a.first_publication_year ?? 'N/A'} to ${a.last_publication_year ?? 'N/A'}`} />
      </div>

      <nav className="author-section-jumps" aria-label="Profile sections">
        {[
          ...(career ? [['career', 'Career']] : []),
          ...(similarState.data?.length ? [['similar', 'Similar researchers']] : []),
          ['publications', 'Publications'],
          ['papers', 'Papers'],
          ['venues', 'Venues'],
          ['collaborators', 'Collaborators'],
          ['collaboration-graph', 'Collaboration graph']
        ].map(([href, label]) => <a key={href} href={`#${href}`}>{label}</a>)}
      </nav>

      <ChartCard id="papers"
        title="Published papers"
        description={`Recent papers by ${a.name}, ordered from newest to oldest.`}
        action={<a className="text-link" href={`/papers?author=${encodeURIComponent(a.name)}&author_id=${a.id}`}>Search all papers →</a>}
      >
        {!papersState.data ? <ResourceState {...papersState} /> : papersState.data.items.length === 0 ? (
          <p className="empty-state">No papers are available for this researcher.</p>
        ) : (
          <DataTable rows={papersState.data.items} rowKey={r => r.publication_id} caption={`${a.name} publications`} columns={[
            { key: 'title', label: 'Paper', render: r => <a className="text-link" href={`/papers/${r.publication_id}`}>{r.title}</a>, value: r => r.title },
            { key: 'year', label: 'Year', render: r => r.year ?? '—', numeric: true },
            { key: 'venue', label: 'Venue', render: r => r.venue_id ? <a className="text-link" href={`/venues/${r.venue_id}`}>{r.venue_name ?? 'Unknown venue'}</a> : 'Unknown venue' },
            { key: 'citations', label: 'Citations', render: r => full(r.citations), value: r => r.citations, numeric: true }
          ]} />
        )}
        {papersState.data && papersState.data.total > papersState.data.items.length && (
          <p className="table-footnote">Showing the 25 most recent of {full(papersState.data.total)} papers.</p>
        )}
      </ChartCard>

      {/* FEATURE 3: Researcher Career Trajectory & Narrative */}
      {career && (
        <ChartCard id="career"
          title="Researcher career"
          description="Career stages, changes in research topics, and publication history."
          action={
            <span className={`career-stage-tag stage-${career.career_stage.toLowerCase().replace(/\s+/g, '-')}`}>
              {career.career_stage} ({career.career_span_years} Active Years)
            </span>
          }
        >
          <div className="career-narrative-card">
            <div className="career-narrative-quote">
              <span className="narrative-label">Editorial Career Synthesis:</span>
              <p className="narrative-text">{career.narrative}</p>
            </div>

            {/* Breakthrough Moments */}
            {career.breakthrough_moments.length > 0 && (
              <div className="breakthrough-callout-card">
                <span className="breakthrough-badge">MAJOR ACCELERATION DETECTED</span>
                <div className="breakthrough-content">
                  <strong>Year {career.breakthrough_moments[0].year} Breakthrough Apex:</strong>
                  <ul className="breakthrough-signals-list">
                    {career.breakthrough_moments[0].signals.map((sig, sIdx) => (
                      <li key={sIdx}>{sig}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}

            {/* Career Eras & Topic Transitions */}
            {career.topic_transitions.length > 0 && (
              <div className="career-eras-strip">
                <span className="eras-label">Career Eras:</span>
                <div className="eras-timeline">
                  {career.topic_transitions.map((era, eIdx) => (
                    <div key={eIdx} className="era-item">
                      <span className="era-years">{era.start_year}–{era.end_year}</span>
                      <strong className="era-name">{era.era_name}</strong>
                      <span className="era-focus">{era.primary_focus}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </ChartCard>
      )}

      {/* FEATURE 5: Researchers With Similar Scientific Profiles */}
      {similarState.data && similarState.data.length > 0 && (
        <ChartCard id="similar"
          title="Researchers with similar profiles"
          description="Researchers with similar topics, publication venues, collaboration patterns, and career stage."
        >
          <div className="similar-researchers-grid">
            {similarState.data.map(peer => (
              <div key={peer.author_id} className="similar-researcher-card">
                <div className="sim-card-top">
                  <div>
                    <h4 className="sim-peer-name">
                      <a href={`/authors/${peer.author_id}`}>{peer.name}</a>
                    </h4>
                    <span className="sim-peer-inst">{peer.institution}</span>
                  </div>
                  <div className="sim-badge-wrap">
                    <span className="sim-badge">{Math.floor(peer.similarity_score)}% Match</span>
                  </div>
                </div>

                <div className="sim-metrics-mini">
                  <span>{full(peer.papers)} papers</span>
                  <span>{compact(peer.total_citations)} cites</span>
                  <span>h-index: {peer.h_index}</span>
                </div>

                <div className="sim-reasons-list">
                  {peer.reasons.map((r, rIdx) => (
                    <div key={rIdx} className="sim-reason-item">
                      <span className="sim-reason-dot">·</span>
                      <span>{r}</span>
                    </div>
                  ))}
                </div>

                <div className="sim-card-actions">
                  <a className="button-link" href={`/authors/${peer.author_id}`}>View Dossier →</a>
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      )}

      <ChartCard id="publications"
        title="How has this career evolved?"
        description="Annual publication volume and year-over-year trajectory across all active years."
        action={<span className="coverage">Peak output: {Math.max(...a.yearly_activity.map(y => y.count), 0)} papers</span>}
      >
        <TimelineChart data={a.yearly_activity} showToggle />
      </ChartCard>

      <ChartCard
        title="Productivity vs. Collaboration Analysis"
        description="Compare solo work against collaborative team output, and trace changing co-authorship team sizes."
      >
        <AuthorProductivityChart data={a.productivity_breakdown} />
      </ChartCard>

      <div className="discovery-grid">
        <ChartCard id="venues" title="Where does this researcher publish?" description="Ten most frequent venues across the full career.">
          <VenueChart data={a.top_venues} />
          <DataTable rows={a.top_venues} rowKey={r => r.venue_id} caption="Researcher venues" columns={[
            { key: 'name', label: 'Venue', render: r => <a href={`/venues/${r.venue_id}`}>{r.name}</a> },
            { key: 'papers', label: 'Papers', render: r => full(r.papers), numeric: true }
          ]} />
        </ChartCard>

        <ChartCard id="collaborators" title="Who are the strongest collaborators?" description={`Top ${a.collaborators.length} of ${full(a.collaborator_count)} collaborators by shared publications.`}>
          <CollaboratorStrengthChart data={a.collaborators} />
          <DataTable rows={a.collaborators} rowKey={r => r.author_id} caption="Top collaborators" columns={[
            { key: 'name', label: 'Researcher', render: r => <a href={`/authors/${r.author_id}`}>{r.name}</a>, value: r => r.name },
            { key: 'shared', label: 'Shared', render: r => full(r.shared_papers), value: r => r.shared_papers, numeric: true },
            { key: 'share', label: 'Share', render: r => `${Math.floor(r.coauthorship_share ?? 0)}%`, numeric: true },
            { key: 'network', label: 'Network', render: r => <a className="text-link" href={`/network?author=${r.author_id}`}>Explore →</a> }
          ]} />
        </ChartCard>
      </div>

      <ChartCard id="collaboration-graph"
        title="A career through collaboration"
        description="Centered neighborhood network showing the primary collaborator cluster. Click a researcher to open their profile, or hover a connection to see shared-paper strength."
        action={<a className="text-link" href={`/network?author=${id}`}>Open interactive graph →</a>}
      >
        <DeferredPanel><ProfileGraph id={id} /></DeferredPanel>
      </ChartCard>
    </>
  )
}

function DeferredPanel({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (!ref.current || visible) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setVisible(true)
        observer.disconnect()
      }
    }, { rootMargin: '320px' })
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [visible])

  return <div ref={ref}>{visible ? children : <div className="resource-state" role="status">Scroll down to load the collaboration graph.</div>}</div>
}

function ProfileGraph({ id }: { id: string }) {
  const state = useResource(`profile-graph:${id}`, s => api.graph(new URLSearchParams({ author_id: id, limit: '21' }), s))
  if (!state.data) return <ResourceState {...state} />
  return <NetworkGraph
    graph={state.data}
    compact
    onSelectNode={node => {
      window.history.pushState({}, '', `/authors/${node.id}`)
      window.dispatchEvent(new PopStateEvent('popstate'))
    }}
  />
}
