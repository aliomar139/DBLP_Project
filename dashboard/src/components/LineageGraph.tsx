import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { PaperLineageResponse, LineageNode } from '../api'

type LineageGraphProps = {
  lineage: PaperLineageResponse
}

export function LineageGraph({ lineage }: LineageGraphProps) {
  const [viewMode, setViewMode] = useState<'graph' | 'timeline'>('graph')
  const [selectedNode, setSelectedNode] = useState<LineageNode | null>(() => {
    return lineage.nodes.find(n => n.role === 'target') || lineage.nodes[0] || null
  })
  const [hoveredNode, setHoveredNode] = useState<{
    node: LineageNode
    x: number
    y: number
  } | null>(null)

  const svgRef = useRef<SVGSVGElement | null>(null)
  const minimapRef = useRef<SVGSVGElement | null>(null)
  const controls = useRef<{ zoom: (factor: number) => void; reset: () => void; stabilize: () => void } | null>(null)
  const [stable, setStable] = useState(false)

  const eraColor = (era: string) => {
    switch (era) {
      case 'Pre-2000': return '#64748b'
      case '2000-2010': return '#0284c7'
      case '2010-2020': return '#7c3aed'
      case '2020+': return '#d97706'
      default: return '#6b7280'
    }
  }

  // D3 Force Graph Simulation
  useEffect(() => {
    if (viewMode !== 'graph' || !svgRef.current || !lineage.nodes.length) return

    const width = 840
    const height = 480

    const svg = d3.select(svgRef.current)
    svg.selectAll('*').remove()

    // Defs: Arrowhead markers
    const defs = svg.append('defs')
    defs.append('marker')
      .attr('id', 'lineage-arrow')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 22)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', 'var(--muted, #94a3b8)')

    defs.append('marker')
      .attr('id', 'lineage-arrow-active')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 22)
      .attr('refY', 0)
      .attr('markerWidth', 7)
      .attr('markerHeight', 7)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', 'var(--accent-dark, #9c4524)')

    const g = svg.append('g').attr('class', 'lineage-canvas')
    let currentZoom = 1

    // Zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.4, 3])
      .filter(event => event.type !== 'wheel' && !event.button)
      .on('start', () => setHoveredNode(null))
      .on('zoom', e => {
        currentZoom = e.transform.k
        g.attr('transform', e.transform)
        nodeLabels.attr('opacity', (d: any) => d.role === 'target' ? 1 : Math.min(1, 0.25 + currentZoom * 0.5))
          .text((d: any) => d.role === 'target' || currentZoom > 1.7 ? d.title : (d.title.length > 20 ? `${d.title.slice(0, 19)}…` : d.title))
      })
    svg.call(zoom)
    setStable(false)
    const mini = d3.select(minimapRef.current)
    mini.selectAll('*').remove()

    // Deep clone data for D3 simulation
    const nodes = lineage.nodes.map(d => ({ ...d }))
    const nodeMap = new Map(nodes.map(n => [n.id, n]))
    const edges = lineage.edges
      .filter(e => nodeMap.has(e.source) && nodeMap.has(e.target))
      .map(e => ({
        ...e,
        source: nodeMap.get(e.source)!,
        target: nodeMap.get(e.target)!
      }))

    // Simulation with directional X bias (older on left, newer on right)
    const simulation = d3.forceSimulation(nodes as any)
      .force('link', d3.forceLink<any, any>(edges as any).id((d: any) => d.id).distance(110))
      .force('charge', d3.forceManyBody().strength(-240))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('x', d3.forceX((d: any) => {
        // Bias target to center, ancestors to left, descendants to right
        if (d.role === 'target') return width / 2
        if (d.role === 'ancestor' || d.role === 'foundational') return width / 4
        return (width * 3) / 4
      }).strength(0.4))
      .force('y', d3.forceY(height / 2).strength(0.15))
      .force('collision', d3.forceCollide().radius(28))

    controls.current = {
      zoom: factor => svg.transition().duration(250).call(zoom.scaleBy, factor),
      reset: () => svg.transition().duration(350).call(zoom.transform, d3.zoomIdentity),
      stabilize: () => {
        simulation.alpha(0)
        simulation.stop()
        const minX = d3.min(nodes, n => (n as any).x ?? width / 2) ?? width / 2
        const maxX = d3.max(nodes, n => (n as any).x ?? width / 2) ?? width / 2
        const minY = d3.min(nodes, n => (n as any).y ?? height / 2) ?? height / 2
        const maxY = d3.max(nodes, n => (n as any).y ?? height / 2) ?? height / 2
        const scale = Math.max(0.4, Math.min(1.2, (width - 120) / Math.max(1, maxX - minX), (height - 120) / Math.max(1, maxY - minY)))
        const centerX = (minX + maxX) / 2
        const centerY = (minY + maxY) / 2
        const transform = d3.zoomIdentity
          .translate(width / 2 - centerX * scale, height / 2 - centerY * scale)
          .scale(scale)
        svg.transition().duration(350).call(zoom.transform, transform)
        setStable(true)
      }
    }

    // Draw Edges
    const link = g.append('g')
      .attr('class', 'lineage-edges')
      .selectAll('line')
      .data(edges)
      .join('line')
      .attr('stroke', 'var(--line, #cbd5e1)')
      .attr('stroke-opacity', 0.75)
      .attr('stroke-width', (d: any) => Math.min(3.5, Math.max(1.2, d.citation_strength * 2.5)))
      .attr('marker-end', 'url(#lineage-arrow)')

    // Draw Nodes
    const node = g.append('g')
      .attr('class', 'lineage-nodes')
      .selectAll('g')
      .data(nodes)
      .join('g')
      .attr('class', (d: any) => `lineage-node-group role-${d.role}`)
      .attr('cursor', 'pointer')
      .attr('tabindex', 0)
      .attr('role', 'button')
      .attr('aria-label', (d: any) => `${d.title}, ${d.year}, ${d.role}. Inspect paper`)
      .on('keydown', (event, d: any) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          const orig = lineage.nodes.find(n => n.id === d.id) || d
          setSelectedNode(orig)
        }
      })
      .call(
        (d3.drag<any, any>()
          .on('start', (e, d) => {
            setHoveredNode(null)
            link.attr('stroke', 'var(--line, #cbd5e1)').attr('stroke-opacity', 0.75).attr('marker-end', 'url(#lineage-arrow)')
            node.attr('opacity', 1)
            if (!e.active) simulation.alphaTarget(0.3).restart()
            d.fx = d.x
            d.fy = d.y
          })
          .on('drag', (e, d) => {
            d.fx = e.x
            d.fy = e.y
          })
          .on('end', (e, d) => {
            if (!e.active) simulation.alphaTarget(0)
            d.fx = null
            d.fy = null
          })) as any
      )
      .on('click', (_, d: any) => {
        const orig = lineage.nodes.find(n => n.id === d.id) || d
        setSelectedNode(orig)
      })
      .on('mouseenter', (event, d: any) => {
        const orig = lineage.nodes.find(n => n.id === d.id) || d
        const box = svgRef.current?.parentElement
        if (box) {
          const rect = box.getBoundingClientRect()
          setHoveredNode({
            node: orig,
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
          })
        }

        // Highlight connected citation links & neighbor nodes
        const connectedNodeIds = new Set<string>([d.id])
        edges.forEach((e: any) => {
          if (e.source.id === d.id) connectedNodeIds.add(e.target.id)
          if (e.target.id === d.id) connectedNodeIds.add(e.source.id)
        })

        link
          .attr('stroke', (e: any) => (e.source.id === d.id || e.target.id === d.id) ? 'var(--accent-dark, #9c4524)' : 'var(--line, #cbd5e1)')
          .attr('stroke-opacity', (e: any) => (e.source.id === d.id || e.target.id === d.id) ? 1 : 0.12)
          .attr('stroke-width', (e: any) => (e.source.id === d.id || e.target.id === d.id) ? Math.min(4.5, Math.max(2.4, e.citation_strength * 3.5)) : 1)
          .attr('marker-end', (e: any) => (e.source.id === d.id || e.target.id === d.id) ? 'url(#lineage-arrow-active)' : 'url(#lineage-arrow)')

        node
          .attr('opacity', (n: any) => connectedNodeIds.has(n.id) ? 1 : 0.25)
      })
      .on('mousemove', (event, d: any) => {
        const orig = lineage.nodes.find(n => n.id === d.id) || d
        const box = svgRef.current?.parentElement
        if (box) {
          const rect = box.getBoundingClientRect()
          setHoveredNode(prev => prev ? {
            ...prev,
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
          } : { node: orig, x: event.clientX - rect.left, y: event.clientY - rect.top })
        }
      })
      .on('mouseleave', () => {
        setHoveredNode(null)
        link
          .attr('stroke', 'var(--line, #cbd5e1)')
          .attr('stroke-opacity', 0.75)
          .attr('stroke-width', (d: any) => Math.min(3.5, Math.max(1.2, d.citation_strength * 2.5)))
          .attr('marker-end', 'url(#lineage-arrow)')

        node
          .attr('opacity', 1)
      })

    // Node aria-labels and the in-app card replace the browser's native tooltip.
    node.append('title').text((d: any) =>
      `${d.title} (${d.year})\n${d.authors.join(', ')}\nVenue: ${d.venue || 'N/A'}\nCitations: ${d.citations?.toLocaleString() ?? 0} · Influential: ${d.influential_citations?.toLocaleString() ?? 0}\nRole: ${d.role}`
    )
    node.selectAll('title').remove()

    // Node Outer Ring (Golden / Accent for Target)
    node.filter((d: any) => d.role === 'target')
      .append('circle')
      .attr('r', 21)
      .attr('fill', 'none')
      .attr('stroke', 'var(--accent, #d76b38)')
      .attr('stroke-width', 2.5)
      .attr('stroke-dasharray', '4 2')

    // Node Circles
    node.append('circle')
      .attr('class', 'node-circle')
      .attr('r', (d: any) => {
        if (d.role === 'target') return 14
        const cit = d.citations || 10
        return Math.min(16, Math.max(8, Math.log2(cit) * 1.5))
      })
      .attr('fill', (d: any) => {
        if (d.role === 'target') return 'var(--accent, #d76b38)'
        return eraColor(d.era)
      })
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 2)

    // Keep a compact paper name under every node, with its year on a second line.
    const nodeLabels = node.append('text')
      .attr('dy', 28)
      .attr('text-anchor', 'middle')
      .attr('font-size', '8px')
      .attr('font-family', 'var(--font-mono)')
      .attr('fill', 'var(--text)')
      .attr('paint-order', 'stroke')
      .attr('stroke', 'var(--panel)')
      .attr('stroke-width', 2.5)
      .attr('stroke-linejoin', 'round')
      .attr('font-weight', (d: any) => d.role === 'target' ? '700' : '500')
      .text((d: any) => d.title.length > 20 ? `${d.title.slice(0, 19)}…` : d.title)

    nodeLabels.append('tspan')
      .attr('x', 0)
      .attr('dy', 11)
      .attr('font-size', '8px')
      .attr('font-weight', '500')
      .text((d: any) => `${d.year}`)

    // Minimap Nodes
    const miniNodes = mini.selectAll('circle')
      .data(nodes)
      .join('circle')
      .attr('r', (d: any) => d.role === 'target' ? 8 : 5)
      .attr('fill', (d: any) => d.role === 'target' ? 'var(--accent, #d76b38)' : eraColor(d.era))
      .attr('opacity', 0.8)

    // Ticking
    simulation.on('tick', () => {
      link
        .attr('x1', (d: any) => d.source.x)
        .attr('y1', (d: any) => d.source.y)
        .attr('x2', (d: any) => d.target.x)
        .attr('y2', (d: any) => d.target.y)

      node.attr('transform', (d: any) => `translate(${d.x},${d.y})`)
      miniNodes.attr('cx', (d: any) => d.x).attr('cy', (d: any) => d.y)
    })

    return () => {
      simulation.stop()
      controls.current = null
    }
  }, [viewMode, lineage])

  return (
    <div className="lineage-container">
      {/* Controls & Mode Switcher */}
      <div className="lineage-toolbar">
        <div className="lineage-modes-toggle">
          <button
            type="button"
            className={`lineage-mode-btn ${viewMode === 'graph' ? 'active' : ''}`}
            aria-pressed={viewMode === 'graph'}
            onClick={() => setViewMode('graph')}
          >
            Force graph
          </button>
          <button
            type="button"
            className={`lineage-mode-btn ${viewMode === 'timeline' ? 'active' : ''}`}
            aria-pressed={viewMode === 'timeline'}
            onClick={() => setViewMode('timeline')}
          >
            Timeline
          </button>
        </div>

        <div className="lineage-legend-strip">
          {lineage.eras.map(e => (
            <span key={e.era} className="lineage-legend-item">
              <span className="lineage-legend-dot" style={{ backgroundColor: e.color }} />
              <span>{e.era} ({e.count})</span>
            </span>
          ))}
          <span className="lineage-legend-item">
            <span className="lineage-legend-dot" style={{ backgroundColor: 'var(--accent, #d76b38)' }} />
            <strong>Target Paper</strong>
          </span>
        </div>
      </div>

      <div className="lineage-layout-grid">
        {/* Main View Area */}
        <div className="lineage-visual-panel">
          {viewMode === 'graph' ? (
            <div className="lineage-canvas-box">
              {/* Floating Graph Controls */}
              <div className="lineage-floating-controls" role="group" aria-label="Lineage graph zoom and layout controls">
                <button
                  type="button"
                  onClick={() => controls.current?.zoom(1.3)}
                  title="Zoom in"
                  aria-label="Zoom in"
                >
                  +
                </button>
                <button
                  type="button"
                  onClick={() => controls.current?.zoom(1 / 1.3)}
                  title="Zoom out"
                  aria-label="Zoom out"
                >
                  −
                </button>
                <button
                  type="button"
                  onClick={() => controls.current?.reset()}
                  title="Reset view and centering"
                  aria-label="Reset view"
                >
                  ⟲ Reset
                </button>
                <button
                  type="button"
                  disabled={stable}
                  onClick={() => controls.current?.stabilize()}
                  title="Stabilize physics layout"
                  aria-label="Stabilize layout"
                >
                  {stable ? '✓ Stabilized' : 'Stabilize'}
                </button>
              </div>

              <span className="lineage-canvas-hint">Drag a node to explore <span aria-hidden="true">·</span> scroll to move the page</span>

              <svg
                ref={svgRef}
                className="lineage-svg"
                viewBox="0 0 840 480"
                role="group"
                aria-label="Citation lineage graph. Hover any node to view paper summary; click to inspect dossier."
              />

              {/* Minimap Overview */}
              <div className="lineage-minimap-wrap" aria-hidden="true">
                <span className="minimap-label">OVERVIEW</span>
                <svg ref={minimapRef} className="lineage-minimap" viewBox="0 0 840 480" />
              </div>

              {/* Interactive Node Hover Tooltip Card */}
              {hoveredNode && (
                <div
                  className="lineage-hover-tooltip"
                  style={{
                    left: `${Math.min(Math.max(12, hoveredNode.x + 14), 840 - 295)}px`,
                    top: `${hoveredNode.y > 280 ? Math.max(10, hoveredNode.y - 190) : hoveredNode.y + 14}px`,
                  }}
                  role="tooltip"
                  aria-hidden="true"
                >
                  <div className="tooltip-header">
                    <span className={`tooltip-role-tag role-${hoveredNode.node.role}`}>
                      {hoveredNode.node.role === 'target'
                        ? 'Selected paper'
                        : hoveredNode.node.role === 'foundational'
                        ? 'Foundational paper'
                        : hoveredNode.node.role === 'ancestor'
                        ? '⬅️ Cited Ancestor'
                        : '➡️ Citing Descendant'}
                    </span>
                    <span className="tooltip-era-pill" style={{ color: eraColor(hoveredNode.node.era) }}>
                      <span className="tooltip-era-dot" style={{ backgroundColor: eraColor(hoveredNode.node.era) }} />
                      {hoveredNode.node.era}
                    </span>
                  </div>

                  <h5 className="tooltip-paper-title">{hoveredNode.node.title}</h5>

                  <p className="tooltip-paper-meta">
                    <strong>{hoveredNode.node.year}</strong> · {hoveredNode.node.venue || 'Indexed Computer Science Venue'}
                  </p>

                  <p className="tooltip-paper-authors">
                    <strong>Authors:</strong> {hoveredNode.node.authors.slice(0, 3).join(', ')}
                    {hoveredNode.node.authors.length > 3 && ` +${hoveredNode.node.authors.length - 3} more`}
                  </p>

                  <div className="tooltip-metrics-row">
                    <div className="tooltip-metric">
                      <span className="tooltip-metric-label">Citations</span>
                      <strong className="tooltip-metric-val">{hoveredNode.node.citations.toLocaleString()}</strong>
                    </div>
                    <div className="tooltip-metric">
                      <span className="tooltip-metric-label">Influential</span>
                      <strong className="tooltip-metric-val">{hoveredNode.node.influential_citations.toLocaleString()}</strong>
                    </div>
                    <div className="tooltip-metric">
                      <span className="tooltip-metric-label">Impact</span>
                      <strong className="tooltip-metric-val">{Math.floor(hoveredNode.node.impact_score)}/100</strong>
                    </div>
                  </div>

                  <div className="tooltip-footer">
                    <span>Click node to pin in dossier</span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            /* Chronological Timeline Mode */
            <div className="lineage-timeline-view">
              {lineage.nodes
                .slice()
                .sort((a, b) => a.year - b.year)
                .map(n => (
                  <div
                    key={n.id}
                    role="button"
                    tabIndex={0}
                    onKeyDown={e => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault()
                        setSelectedNode(n)
                      }
                    }}
                    className={`lineage-timeline-item ${n.role === 'target' ? 'is-target' : ''} ${selectedNode?.id === n.id ? 'is-selected' : ''}`}
                    onClick={() => setSelectedNode(n)}
                  >
                    <div className="timeline-node-marker" style={{ borderColor: n.role === 'target' ? 'var(--accent, #d76b38)' : eraColor(n.era) }}>
                      <span className="timeline-dot" style={{ backgroundColor: n.role === 'target' ? 'var(--accent, #d76b38)' : eraColor(n.era) }} />
                    </div>
                    <div className="timeline-node-content">
                      <div className="timeline-node-header">
                        <span className="timeline-year-pill">{n.year}</span>
                        <span className={`timeline-role-badge role-${n.role}`}>
                          {n.role === 'target'
                            ? 'Target Paper'
                            : n.role === 'foundational'
                            ? 'Foundational Root'
                            : n.role === 'ancestor'
                            ? 'Ancestor (Cited)'
                            : 'Descendant (Cites)'}
                        </span>
                        <span className="timeline-citations-pill">{n.citations.toLocaleString()} citations</span>
                      </div>
                      <h4 className="timeline-paper-title">{n.title}</h4>
                      <p className="timeline-paper-meta">
                        {n.venue || 'Indexed Computer Science Venue'} · {n.authors.join(', ')}
                      </p>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>

        {/* Selected Paper Dossier Panel */}
        <div className="lineage-dossier-panel">
          {selectedNode ? (
            <div className="dossier-card">
              <div className="dossier-header">
                <span className={`dossier-role-tag role-${selectedNode.role}`}>
                  {selectedNode.role === 'target'
                    ? 'Focal Research Paper'
                    : selectedNode.role === 'foundational'
                    ? 'Foundational Root'
                    : selectedNode.role === 'ancestor'
                    ? 'Prior Ancestor'
                    : 'Follow-up Extension'}
                </span>
                <span className="dossier-era-pill" style={{ color: eraColor(selectedNode.era) }}>
                  {selectedNode.era}
                </span>
              </div>
              <h3 className="dossier-title">{selectedNode.title}</h3>
              <p className="dossier-meta">
                <strong>Published:</strong> {selectedNode.year} ({selectedNode.venue || 'Computer Science'})
              </p>
              <p className="dossier-authors">
                <strong>Authors:</strong> {selectedNode.authors.join(', ')}
              </p>

              <div className="dossier-stats-grid">
                <div className="dossier-stat">
                  <span>Citations</span>
                  <strong>{selectedNode.citations.toLocaleString()}</strong>
                </div>
                <div className="dossier-stat">
                  <span>Influential</span>
                  <strong>{selectedNode.influential_citations.toLocaleString()}</strong>
                </div>
                <div className="dossier-stat">
                  <span>Scientific Topic</span>
                  <strong>{selectedNode.topic || 'General CS'}</strong>
                </div>
                <div className="dossier-stat">
                  <span>Impact Index</span>
                  <strong>{Math.floor(selectedNode.impact_score)}/100</strong>
                </div>
              </div>

              {selectedNode.role !== 'target' && (
                <a className="dossier-open-link" href={`/papers/${selectedNode.publication_id}`}>
                  Inspect Full Paper Profile →
                </a>
              )}
            </div>
          ) : (
            <p className="dossier-empty">Select an item to inspect its citation history.</p>
          )}

          {/* Foundational Roots Highlight Box */}
          {lineage.foundational_roots.length > 0 && (
            <div className="foundational-roots-card">
              <h4 className="roots-card-title">Foundational roots</h4>
              <div className="roots-list">
                {lineage.foundational_roots.map(root => (
                  <div key={root.publication_id} className="root-item">
                    <a href={`/papers/${root.publication_id}`} className="root-item-title">
                      {root.title} ({root.year})
                    </a>
                    <span className="root-why">{root.why_foundational}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
