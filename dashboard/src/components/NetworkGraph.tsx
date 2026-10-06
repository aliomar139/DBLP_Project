import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'
import type { Graph, GraphNode } from '../api'
import { full } from './MetricCard'

type Node = GraphNode & d3.SimulationNodeDatum
type Edge = d3.SimulationLinkDatum<Node> & { weight: number }

const COMMUNITY_PALETTE = [
  '#d76b38', // 0: Coral accent (core / central)
  '#2563eb', // 1: Blue
  '#059669', // 2: Emerald
  '#7c3aed', // 3: Violet
  '#db2777', // 4: Pink
  '#d97706', // 5: Amber
  '#0891b2', // 6: Cyan
  '#475569', // 7: Slate
]

export function NetworkGraph({
  graph,
  highlight = '',
  compact = false,
  onSelectNode,
  onCenterNode
}: {
  graph: Graph
  highlight?: string
  compact?: boolean
  onSelectNode?: (node: GraphNode) => void
  onCenterNode?: (id: string) => void
}) {
  const ref = useRef<SVGSVGElement>(null)
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null)
  const [selected, setSelected] = useState<GraphNode>()
  const [hovered, setHovered] = useState<{ node: Node; x: number; y: number; sharedWithCenter: number | null } | null>(null)
  const [hoveredEdge, setHoveredEdge] = useState<{ sourceName: string; targetName: string; weight: number; x: number; y: number } | null>(null)

  const handleZoomIn = () => {
    if (ref.current && zoomRef.current) {
      d3.select(ref.current).transition().duration(250).call(zoomRef.current.scaleBy, 1.35)
    }
  }

  const handleZoomOut = () => {
    if (ref.current && zoomRef.current) {
      d3.select(ref.current).transition().duration(250).call(zoomRef.current.scaleBy, 0.74)
    }
  }

  const handleReset = () => {
    if (ref.current && zoomRef.current) {
      d3.select(ref.current).transition().duration(300).call(zoomRef.current.transform, d3.zoomIdentity)
    }
  }

  const handleExportSVG = () => {
    if (!ref.current) return
    const svgEl = ref.current
    const serializer = new XMLSerializer()
    let source = serializer.serializeToString(svgEl)
    if (!source.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
      source = source.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"')
    }
    const svgBlob = new Blob([source], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)
    const link = document.createElement('a')
    link.href = url
    link.download = `collaboration-network-${graph.center_id}.svg`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  useEffect(() => {
    if (!ref.current) return
    const svg = d3.select(ref.current)
    const width = 900
    const height = compact ? 380 : 540
    svg.selectAll('*').remove()
    setSelected(undefined)
    setHovered(null)
    setHoveredEdge(null)

    const nodes: Node[] = graph.nodes.map(n => ({
      ...n,
      ...(n.id === graph.center_id ? { fx: width / 2, fy: height / 2 } : {})
    }))
    const edges: Edge[] = graph.edges.map(e => ({ ...e }))
    const sharedWithCenter = new Map<string, number>()
    graph.edges.forEach(e => {
      if (String(e.source) === graph.center_id) sharedWithCenter.set(String(e.target), e.weight)
      if (String(e.target) === graph.center_id) sharedWithCenter.set(String(e.source), e.weight)
    })
    const maxSharedWithCenter = d3.max(Array.from(sharedWithCenter.values())) || 1
    const nodeSize = (n: Node) => n.id === graph.center_id ? maxSharedWithCenter : (sharedWithCenter.get(n.id) || 1)
    const radius = d3.scaleSqrt().domain([1, maxSharedWithCenter]).range([8, 25])
    const stroke = d3.scaleSqrt().domain([1, d3.max(edges, e => e.weight) || 1]).range([1.2, 6.5])

    const group = svg.append('g')
    let currentZoom = 1
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.3, 5])
      .filter(event => event.type !== 'wheel' && !event.button)
      .on('start', () => setHovered(null))
      .on('zoom', e => {
        currentZoom = e.transform.k
        group.attr('transform', e.transform)
        dots.select('.network-node-label').attr('opacity', (n: Node) => n.id === graph.center_id ? 1 : Math.min(1, 0.18 + currentZoom * 0.55))
          .text((n: Node) => currentZoom > 1.8 || n.id === graph.center_id ? n.name : (n.name.length > 18 ? `${n.name.slice(0, 17)}…` : n.name))
      })
    svg.call(zoom)
    zoomRef.current = zoom

    const lines = group.append('g').selectAll('line').data(edges).join('line')
      .attr('stroke', 'var(--network-edge)')
      .attr('stroke-width', e => stroke(e.weight))
      .attr('stroke-linecap', 'round')
      .attr('pointer-events', 'stroke')

    lines.append('title').text(e => `${e.weight} shared papers`)

    const nodeNames = new Map(nodes.map(n => [n.id, n.name]))
    lines
      .on('mouseenter', (event, e) => {
        const source = typeof e.source === 'object' ? (e.source as Node).id : String(e.source)
        const target = typeof e.target === 'object' ? (e.target as Node).id : String(e.target)
        const box = ref.current?.parentElement
        if (!box) return
        const rect = box.getBoundingClientRect()
        setHovered(null)
        setHoveredEdge({ sourceName: nodeNames.get(source) ?? source, targetName: nodeNames.get(target) ?? target, weight: e.weight, x: event.clientX - rect.left, y: event.clientY - rect.top })
        d3.select(event.currentTarget as SVGLineElement).attr('stroke', 'var(--accent-dark, #9c4524)').attr('stroke-opacity', 1)
      })
      .on('mousemove', (event) => {
        const box = ref.current?.parentElement
        if (!box) return
        const rect = box.getBoundingClientRect()
        setHoveredEdge(prev => prev ? { ...prev, x: event.clientX - rect.left, y: event.clientY - rect.top } : prev)
      })
      .on('mouseleave', (event) => {
        setHoveredEdge(null)
        d3.select(event.currentTarget as SVGLineElement).attr('stroke', 'var(--network-edge)').attr('stroke-opacity', 0.8)
      })

    const dots = group.append('g').selectAll<SVGGElement, Node>('g').data(nodes).join('g')
      .attr('class', 'network-node')
      .attr('tabindex', 0)
      .attr('role', 'button')
      .attr('aria-label', n => `${n.name}, ${full(n.publications)} publications, ${full(n.collaborators)} collaborators.`)

    // Community color or central highlight
    dots.append('circle')
      .attr('r', n => radius(nodeSize(n)))
      .attr('fill', n => {
        if (n.id === graph.center_id) return 'var(--network-center)'
        if (n.community_id !== undefined && n.community_id !== null) {
          return COMMUNITY_PALETTE[n.community_id % COMMUNITY_PALETTE.length]
        }
        return 'var(--network-neighbor)'
      })
      .attr('stroke', n => (n.is_bridge ? '#f59e0b' : 'var(--bg-canvas)'))
      .attr('stroke-width', n => (n.is_bridge ? 3.5 : 2))

    // Bridge scholar indicator ring
    dots.filter(n => Boolean(n.is_bridge))
      .append('circle')
      .attr('r', n => radius(nodeSize(n)) + 4)
      .attr('fill', 'none')
      .attr('stroke', '#f59e0b')
      .attr('stroke-width', 1.5)
      .attr('stroke-dasharray', '3 2')

    dots.append('text')
      .attr('class', 'network-node-label')
      .text(n => n.id === graph.center_id ? n.name : (n.name.length > 18 ? `${n.name.slice(0, 17)}…` : n.name))
      .attr('y', n => radius(nodeSize(n)) + 12)
      .attr('text-anchor', 'middle')
      .attr('fill', 'var(--network-text)')
      .attr('opacity', 1)

    dots.on('click', (_, n) => {
      setSelected(n)
      onSelectNode?.(n)
      dots.select('.network-node-label').attr('opacity', 1)
    })

    dots.on('keydown', (event, n) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault()
        setSelected(n)
        onSelectNode?.(n)
      }
    })

    dots.on('focus', (event, n) => {
      dots.select('.network-node-label').attr('opacity', 0.2)
      d3.select(event.currentTarget as SVGGElement).select('.network-node-label').attr('opacity', 1).text(n.name)
    })

    dots
      .on('mouseenter', (event, n) => {
        dots.select('.network-node-label').attr('opacity', 1)
        const box = ref.current?.parentElement
        if (box) {
          const rect = box.getBoundingClientRect()
          const centerEdge = n.id === graph.center_id
            ? null
            : graph.edges.find(e => {
              const source = String(e.source)
              const target = String(e.target)
              return (source === n.id && target === graph.center_id) || (target === n.id && source === graph.center_id)
            })
          setHovered({
            node: n,
            x: event.clientX - rect.left,
            y: event.clientY - rect.top,
            sharedWithCenter: centerEdge?.weight ?? null
          })
        }

        const connectedIds = new Set<string>([n.id])
        edges.forEach(e => {
          const srcId = typeof e.source === 'object' ? (e.source as any).id : e.source
          const tgtId = typeof e.target === 'object' ? (e.target as any).id : e.target
          if (srcId === n.id) connectedIds.add(tgtId)
          if (tgtId === n.id) connectedIds.add(srcId)
        })

        lines
          .attr('stroke', (e: any) => {
            const srcId = typeof e.source === 'object' ? e.source.id : e.source
            const tgtId = typeof e.target === 'object' ? e.target.id : e.target
            return (srcId === n.id || tgtId === n.id) ? 'var(--accent-dark, #9c4524)' : 'var(--network-edge)'
          })
          .attr('stroke-opacity', (e: any) => {
            const srcId = typeof e.source === 'object' ? e.source.id : e.source
            const tgtId = typeof e.target === 'object' ? e.target.id : e.target
            return (srcId === n.id || tgtId === n.id) ? 1 : 0.12
          })

        dots.attr('opacity', (d: any) => connectedIds.has(d.id) ? 1 : 0.25)
      })
      .on('mousemove', (event, n) => {
        const box = ref.current?.parentElement
        if (box) {
          const rect = box.getBoundingClientRect()
          setHovered(prev => prev ? {
            ...prev,
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
          } : { node: n, x: event.clientX - rect.left, y: event.clientY - rect.top, sharedWithCenter: null })
        }
      })
      .on('mouseleave', () => {
        setHovered(null)
        lines
          .attr('stroke', 'var(--network-edge)')
          .attr('stroke-opacity', 0.8)
        dots.attr('opacity', (d: any) => (!highlight || d.name.toLowerCase().includes(highlight.toLowerCase()) ? 1 : 0.18))
        dots.select('.network-node-label').attr('opacity', 1)
      })

    const sim = d3.forceSimulation(nodes)
      .force('link', d3.forceLink<Node, Edge>(edges).id(n => n.id).distance(compact ? 100 : 160))
      .force('charge', d3.forceManyBody().strength(-180))
      .force('collision', d3.forceCollide<Node>().radius(n => radius(nodeSize(n)) + 12))
      .force('x', d3.forceX(width / 2).strength(0.06))
      .force('y', d3.forceY(height / 2).strength(0.1))

    const drag = d3.drag<SVGGElement, Node>()
      .on('start', (event, n) => {
        setHovered(null)
        if (!event.active) sim.alphaTarget(0.2).restart()
        n.fx = n.x
        n.fy = n.y
      })
      .on('drag', (event, n) => {
        if (n.id !== graph.center_id) {
          n.fx = event.x
          n.fy = event.y
        }
      })
      .on('end', (event, n) => {
        if (!event.active) sim.alphaTarget(0)
        if (n.id !== graph.center_id) {
          n.fx = null
          n.fy = null
        }
      })

    dots.call(drag)

    sim.on('tick', () => {
      lines
        .attr('x1', e => (e.source as Node).x ?? 0)
        .attr('y1', e => (e.source as Node).y ?? 0)
        .attr('x2', e => (e.target as Node).x ?? 0)
        .attr('y2', e => (e.target as Node).y ?? 0)
      dots.attr('transform', n => `translate(${n.x ?? 0},${n.y ?? 0})`)
    })

    return () => {
      sim.stop()
      svg.on('.zoom', null)
    }
  }, [graph, compact, onSelectNode])

  useEffect(() => {
    d3.select(ref.current)
      .selectAll<SVGGElement, Node>('.network-node')
      .attr('opacity', n => (!highlight || n.name.toLowerCase().includes(highlight.toLowerCase()) ? 1 : 0.18))
  }, [highlight, graph])

  const selectedEdge = selected
    ? graph.edges.find(e => (e.source === selected.id && e.target === graph.center_id) || (e.target === selected.id && e.source === graph.center_id))
    : null

  return (
    <div className="network-visual" style={{ position: 'relative', overflow: 'hidden' }}>
      <div className="network-toolbar">
        <span>Node size shows papers shared with the center. Line thickness shows pairwise shared papers. Color shows the research group; a gold ring marks a bridge researcher.</span>
        <div className="network-toolbar-actions">
          <button title="Download SVG snapshot" onClick={handleExportSVG}>Export SVG</button>
          <button title="Zoom in" onClick={handleZoomIn}>+</button>
          <button title="Zoom out" onClick={handleZoomOut}>−</button>
          <button title="Reset zoom and center" onClick={handleReset}>Reset</button>
        </div>
      </div>
      <svg
        ref={ref}
        viewBox={`0 0 900 ${compact ? 380 : 540}`}
        preserveAspectRatio="xMidYMid meet"
        style={{ display: 'block', width: '100%', height: compact ? 380 : 540 }}
        aria-label="Researcher collaboration network. Select any node to inspect details or recenter."
      />

      {/* Floating Hover Tooltip */}
      {hovered && (
        <div
          className="graph-hover-tooltip"
          style={{
            left: `${Math.min(Math.max(12, hovered.x + 14), 900 - 295)}px`,
            top: `${hovered.y > (compact ? 220 : 340) ? Math.max(10, hovered.y - 170) : hovered.y + 14}px`,
          }}
          role="tooltip"
          aria-hidden="true"
        >
          <div className="tooltip-header">
            <span className={`tooltip-badge ${hovered.node.id === graph.center_id ? 'role-target' : 'role-ancestor'}`}>
              {hovered.node.id === graph.center_id ? 'Network center' : (hovered.node.is_bridge ? 'Bridge researcher' : 'Co-author')}
            </span>
            {hovered.node.community_label && (
              <span className="tooltip-era-pill">
                {hovered.node.community_label}
              </span>
            )}
          </div>

          <h5 className="tooltip-title">{hovered.node.name}</h5>

          <p className="tooltip-subtext">
            {hovered.node.is_bridge ? 'Connects multiple distinct research communities.' : 'Indexed co-authorship collaboration node.'}
          </p>

          <div className="tooltip-metrics-row">
            <div className="tooltip-metric">
              <span className="tooltip-metric-label">Publications</span>
              <strong className="tooltip-metric-val">{full(hovered.node.publications)}</strong>
            </div>
            <div className="tooltip-metric">
              <span className="tooltip-metric-label">Collaborators</span>
              <strong className="tooltip-metric-val">{full(hovered.node.collaborators)}</strong>
            </div>
            <div className="tooltip-metric">
              <span className="tooltip-metric-label">Shared with center</span>
              <strong className="tooltip-metric-val">
                {hovered.node.id === graph.center_id ? 'Center' : full(hovered.sharedWithCenter ?? 0)}
              </strong>
            </div>
          </div>

          <div className="tooltip-footer">
            <span>Click to pin a researcher. Select one to center the network.</span>
          </div>
        </div>
      )}

      {hoveredEdge && (
        <div
          className="graph-hover-tooltip"
          style={{
            left: `${Math.min(Math.max(12, hoveredEdge.x + 14), 900 - 295)}px`,
            top: `${hoveredEdge.y > (compact ? 220 : 340) ? Math.max(10, hoveredEdge.y - 135) : hoveredEdge.y + 14}px`,
          }}
          role="tooltip"
        >
          <div className="tooltip-header"><span className="tooltip-badge role-target">Collaboration tie</span></div>
          <h5 className="tooltip-title">{hoveredEdge.sourceName} ↔ {hoveredEdge.targetName}</h5>
          <p className="tooltip-subtext">These researchers coauthored <strong>{full(hoveredEdge.weight)} {hoveredEdge.weight === 1 ? 'paper' : 'papers'}</strong> in the selected network range.</p>
          <div className="tooltip-footer">Line thickness represents collaboration strength.</div>
        </div>
      )}

      {graph.communities && graph.communities.length > 0 && (
        <div className="community-legend" aria-label="Detected Research Communities">
          <span className="community-legend-title">Communities:</span>
          {graph.communities.map((c, idx) => (
            <span key={c.community_id} className="community-legend-item">
              <i style={{ background: COMMUNITY_PALETTE[idx % COMMUNITY_PALETTE.length] }} />
              <span>{c.label}</span>
              <small>({c.size})</small>
            </span>
          ))}
        </div>
      )}
      <div className="network-readout" aria-live="polite">
        {selected ? (
          <>
            <div>
              <strong>{selected.name}</strong>
              {selected.is_bridge && <span className="bridge-tag">Bridge Researcher</span>}
              <span className="community-tag">{selected.community_label ?? 'Cluster'}</span>
            </div>
            <span>
              {full(selected.publications)} papers · {full(selected.collaborators)} collaborators
              {selected.pagerank ? ` · PageRank: ${selected.pagerank}` : ''}
              {selected.pagerank !== undefined && selected.pagerank !== null ? ` · PageRank: ${Number(selected.pagerank).toFixed(3)}` : ''}
              {selectedEdge && ` · ${selectedEdge.weight} shared with center`}
            </span>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
              {selected.id !== graph.center_id && onCenterNode && (
                <button className="text-button" onClick={() => onCenterNode(selected.id)}>Center here</button>
              )}
              <a href={`/authors/${selected.id}`}>Open profile →</a>
            </div>
          </>
        ) : (
        <span>Select or hover a researcher to inspect connections. Drag to move the graph. Scroll or use the plus and minus buttons to zoom.</span>
        )}
      </div>
    </div>
  )
}
