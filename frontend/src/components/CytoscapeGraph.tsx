import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
import type { GraphPayload } from '../types'

interface Props {
  graph: GraphPayload | null
  source: string | null
  target: string | null
  highlightedPath: string[] | null
  exploredNodes?: string[]
  congestedEdgeIds?: Set<string>
  closedEdgeIds?: Set<string>
  onNodeClick?: (nodeId: string) => void
  onEdgeClick?: (edgeId: string) => void
  onHoverNode?: (nodeId: string | null) => void
  onHoverEdge?: (edgeId: string | null) => void
  showExplored?: boolean
}

export default function CytoscapeGraph({ graph, source, target, highlightedPath, exploredNodes, congestedEdgeIds, closedEdgeIds, onNodeClick, onEdgeClick, onHoverNode, onHoverEdge, showExplored }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  useEffect(() => {
    if (!containerRef.current || !graph) return

    const nodes = graph.nodes.map(n => ({
      data: { id: n.id, label: n.id, r: n.r, c: n.c }
    }))
    const edges = graph.edges.map(e => ({
      data: { id: e.id, source: e.source, target: e.target, weight: e.weight, original: e.original_weight, closed: e.closed }
    }))

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...nodes, ...edges],
      style: [
        {
          selector: 'node',
          style: {
            'background-color': '#8a94a6',
            'width': 14,
            'height': 14,
            'label': 'data(id)',
            'font-size': '7px',
            'color': '#6b7280',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 7,
            'font-family': 'ui-monospace, monospace',
            'border-width': 0,
          }
        },
        {
          selector: 'node.source',
          style: {
            'background-color': '#16a34a',
            'width': 18,
            'height': 18,
            'border-width': 3,
            'border-color': '#ffffff',
            'border-style': 'solid' as any,
            'z-index': 10,
          }
        },
        {
          selector: 'node.target',
          style: {
            'background-color': '#dc2626',
            'width': 18,
            'height': 18,
            'border-width': 3,
            'border-color': '#ffffff',
            'border-style': 'solid' as any,
            'z-index': 10,
          }
        },
        {
          selector: 'node.highlighted',
          style: {
            'background-color': '#1d4ed8',
            'width': 16,
            'height': 16,
            'border-width': 2,
            'border-color': '#dbeafe',
          }
        },
        {
          selector: 'node.explored',
          style: {
            'background-color': '#f59e0b',
            'width': 10,
            'height': 10,
            'opacity': 0.85,
          }
        },
        {
          selector: 'edge',
          style: {
            'width': 1.2,
            'line-color': '#d1d5db',
            'opacity': 0.7,
            'curve-style': 'straight',
            'label': 'data(weight)',
            'font-size': '6px',
            'color': '#9ca3af',
            'text-rotation': 'autorotate',
            'text-background-color': '#ffffff',
            'text-background-opacity': 0.8,
            'text-background-padding': '1px',
            'font-family': 'ui-monospace, monospace',
          }
        },
        {
          selector: 'edge.congested',
          style: {
            'line-color': '#f59e0b',
            'width': 2.2,
            'opacity': 0.95,
            'line-style': 'solid',
          }
        },
        {
          selector: 'edge.closed',
          style: {
            'line-color': '#ef4444',
            'width': 2,
            'line-style': 'dashed',
            'opacity': 0.35,
            'label': '× closed',
            'color': '#ef4444',
          }
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#1d4ed8',
            'width': 3.2,
            'opacity': 1,
            'z-index': 5,
          }
        },
      ],
      layout: {
        name: 'preset',
        positions: (node: any) => {
          const r = node.data('r')
          const c = node.data('c')
          return { x: c * 52 + 40, y: r * 52 + 40 }
        },
        fit: true,
        padding: 18,
      } as any,
      minZoom: 0.2,
      maxZoom: 3,
      wheelSensitivity: 0.2,
    })

    // interactions
    cy.on('tap', 'node', (evt) => {
      const id = evt.target.id()
      onNodeClick?.(id)
    })
    cy.on('tap', 'edge', (evt) => {
      const id = evt.target.id()
      onEdgeClick?.(id)
    })
    cy.on('mouseover', 'node', (evt) => onHoverNode?.(evt.target.id()))
    cy.on('mouseout', 'node', () => onHoverNode?.(null))
    cy.on('mouseover', 'edge', (evt) => onHoverEdge?.(evt.target.id()))
    cy.on('mouseout', 'edge', () => onHoverEdge?.(null))

    cyRef.current = cy

    // apply classes after creation
    updateClasses(cy)

    return () => {
      cy.destroy()
    }
  }, [graph])

  // update classes when props change without recreating
  useEffect(() => {
    if (!cyRef.current) return
    updateClasses(cyRef.current)
  }, [source, target, highlightedPath, exploredNodes, congestedEdgeIds, closedEdgeIds, showExplored])

  function updateClasses(cy: cytoscape.Core) {
    cy.nodes().removeClass('source target highlighted explored')
    cy.edges().removeClass('highlighted congested closed')

    if (source) cy.getElementById(source).addClass('source')
    if (target) cy.getElementById(target).addClass('target')

    if (highlightedPath && highlightedPath.length > 1) {
      for (let i = 0; i < highlightedPath.length; i++) {
        const nid = highlightedPath[i]
        if (cy.getElementById(nid).length) cy.getElementById(nid).addClass('highlighted')
        if (i < highlightedPath.length - 1) {
          const u = highlightedPath[i]
          const v = highlightedPath[i + 1]
          // find edge id connecting u-v
          const edgeId = `${u}__${v}`
          const rev = `${v}__${u}`
          let edge = cy.getElementById(edgeId)
          if (!edge.length) edge = cy.getElementById(rev)
          if (edge.length) edge.addClass('highlighted')
          else {
            // fallback: find by source/target
            cy.edges().forEach(e => {
              const s = e.data('source')
              const t = e.data('target')
              if ((s === u && t === v) || (s === v && t === u)) e.addClass('highlighted')
            })
          }
        }
      }
    }

    if (showExplored && exploredNodes) {
      exploredNodes.forEach(nid => {
        const el = cy.getElementById(nid)
        if (el.length) el.addClass('explored')
      })
    }

    if (congestedEdgeIds) {
      congestedEdgeIds.forEach(eid => {
        const el = cy.getElementById(eid)
        if (el.length) el.addClass('congested')
      })
    }
    if (closedEdgeIds) {
      closedEdgeIds.forEach(eid => {
        const el = cy.getElementById(eid)
        if (el.length) el.addClass('closed')
      })
    }
  }

  const fit = () => cyRef.current?.fit(undefined, 20)
  const zoomIn = () => cyRef.current && cyRef.current.zoom(cyRef.current.zoom() * 1.25)
  const zoomOut = () => cyRef.current && cyRef.current.zoom(cyRef.current.zoom() * 0.8)
  const reset = () => { cyRef.current?.fit(undefined, 20); cyRef.current?.center() }

  return (
    <div className="relative border border-[#e7e5e0] bg-white rounded-[8px] overflow-hidden">
      <div ref={containerRef} className="cy-container" />
      <div className="absolute top-3 left-3 flex gap-1.5">
        <button onClick={zoomIn} className="w-7 h-7 bg-white border border-[#e7e5e0] rounded text-xs hover:bg-gray-50">＋</button>
        <button onClick={zoomOut} className="w-7 h-7 bg-white border border-[#e7e5e0] rounded text-xs hover:bg-gray-50">－</button>
        <button onClick={fit} className="px-2.5 h-7 bg-white border border-[#e7e5e0] rounded text-[11px] font-medium hover:bg-gray-50">Fit</button>
        <button onClick={reset} className="px-2.5 h-7 bg-white border border-[#e7e5e0] rounded text-[11px] font-medium hover:bg-gray-50">Reset</button>
      </div>
      <div className="absolute bottom-3 right-3 bg-white/95 border border-[#e7e5e0] rounded-md px-3 py-2 text-[10px] leading-3 mono">
        <div className="font-semibold text-[#111827] mb-1.5">LEGEND</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 rounded-full bg-[#16a34a] inline-block"></span> Source</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-3 h-3 rounded-full bg-[#dc2626] inline-block"></span> Destination</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-4 h-[3px] bg-[#1d4ed8] inline-block"></span> Optimal route</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-4 h-[2px] bg-[#f59e0b] inline-block"></span> Congested</div>
        <div className="flex items-center gap-2 mb-1"><span className="w-4 h-[2px] border-t border-dashed border-[#ef4444] inline-block"></span> Closed</div>
        <div className="flex items-center gap-2"><span className="w-3 h-3 rounded-full bg-[#d1d5db] inline-block"></span> Intersection</div>
      </div>
    </div>
  )
}
