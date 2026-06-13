import { useRef, useCallback, useMemo, useEffect, forwardRef, useImperativeHandle } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import type { ForceGraphMethods } from 'react-force-graph-3d'
import SpriteText from 'three-spritetext'
import * as THREE from 'three'
import type { MemoryGraphNode, MemoryGraphEdge } from '../api'

export type MemoryFilterType = 'all' | 'memories' | 'concepts' | 'documents' | 'struggle' | 'breakthrough'

interface Props {
  nodes: MemoryGraphNode[]
  edges: MemoryGraphEdge[]
  width: number
  height: number
  filter?: MemoryFilterType
  onNodeClick?: (node: MemoryGraphNode) => void
}

export interface StudentMemoryGraphHandle {
  zoomToNode: (nodeId: string) => void
  zoomToFit: () => void
}

// ── Colors ──

function memoryColor(type: string | null | undefined, confusion: number): string {
  if (confusion > 0.6) return '#ff4444'
  switch (type) {
    case 'struggle': return '#ff6b6b'
    case 'breakthrough': return '#44ff88'
    case 'question': return '#ffd700'
    case 'insight': return '#44ddff'
    default: return '#8888cc'
  }
}

function conceptColor(mastery: number): string {
  if (mastery >= 0.8) return '#44ff88'
  if (mastery >= 0.5) return '#44ddff'
  if (mastery >= 0.35) return '#ffd700'
  if (mastery >= 0.2) return '#ff8c00'
  return '#ff6b6b'
}

const DOC_TYPE_COLORS: Record<string, string> = {
  textbook: '#a78bfa',    // purple
  slides: '#fb923c',      // orange
  notes: '#60a5fa',       // blue
  rubric: '#f472b6',      // pink
  assignment: '#34d399',   // emerald
  exam: '#f87171',        // red
  syllabus: '#fbbf24',    // amber
  image: '#c084fc',       // purple lighter
  spreadsheet: '#4ade80', // green
  docs: '#93c5fd',        // blue lighter
  other: '#9ca3af',       // gray
}

function docColor(docType: string | null | undefined): string {
  return DOC_TYPE_COLORS[docType || 'other'] || DOC_TYPE_COLORS.other
}

function sentimentIcon(sentiment: string | null | undefined): string {
  switch (sentiment) {
    case 'frustrated': return ' &#x26A0;'
    case 'confused': return ' ?'
    case 'confident': return ' &#x2713;'
    default: return ''
  }
}

export const StudentMemoryGraph = forwardRef<StudentMemoryGraphHandle, Props>(
  function StudentMemoryGraph({ nodes, edges, width, height, filter = 'all', onNodeClick }, ref) {
    const fgRef = useRef<ForceGraphMethods | undefined>(undefined)
    const nodesRef = useRef<any[]>([])

    const graphData = useMemo(() => ({
      nodes: nodes.map(n => {
        if (n.type === 'concept') {
          return {
            id: n.id,
            name: n.name,
            nodeType: 'concept' as const,
            rawType: n.type,
            val: 8,
            color: conceptColor(n.mastery_level ?? 0),
            masteryLevel: n.mastery_level ?? 0,
            masteryLabel: n.mastery_label ?? '',
            timesPracticed: n.times_practiced ?? 0,
            timesStruggled: n.times_struggled ?? 0,
            _raw: n,
          }
        }
        if (n.type === 'document') {
          return {
            id: n.id,
            name: n.filename || n.name,
            nodeType: 'document' as const,
            rawType: n.type,
            val: 5,
            color: docColor(n.doc_type),
            docType: n.doc_type,
            status: n.status,
            pageCount: n.page_count,
            chunkCount: n.chunk_count,
            _raw: n,
          }
        }
        // memory
        return {
          id: n.id,
          name: n.content ?? n.name,
          nodeType: 'memory' as const,
          rawType: n.type,
          val: 2,
          color: memoryColor(n.memory_type, n.confusion_score ?? 0),
          memoryType: n.memory_type,
          concepts: n.concepts,
          confusionScore: n.confusion_score ?? 0,
          sentiment: n.sentiment,
          _raw: n,
        }
      }),
      links: edges.map(e => ({
        source: e.source,
        target: e.target,
        edgeType: e.type,
        weight: e.weight ?? null,
      })),
    }), [nodes, edges])

    nodesRef.current = graphData.nodes

    // Visibility
    const isNodeVisible = useCallback((node: any): boolean => {
      if (filter === 'all') return true
      if (filter === 'memories') return node.nodeType === 'memory' || node.nodeType === 'concept'
      if (filter === 'concepts') return node.nodeType === 'concept'
      if (filter === 'documents') return node.nodeType === 'document' || node.nodeType === 'concept'
      if (filter === 'struggle') return node.nodeType === 'concept' || node.memoryType === 'struggle'
      if (filter === 'breakthrough') return node.nodeType === 'concept' || node.memoryType === 'breakthrough'
      return true
    }, [filter])

    const isLinkVisible = useCallback((link: any): boolean => {
      if (filter === 'all') return true
      const src = typeof link.source === 'object' ? link.source : nodesRef.current.find((n: any) => n.id === link.source)
      const tgt = typeof link.target === 'object' ? link.target : nodesRef.current.find((n: any) => n.id === link.target)
      if (!src || !tgt) return false
      return isNodeVisible(src) && isNodeVisible(tgt)
    }, [filter, isNodeVisible])

    const zoomToNode = useCallback((nodeId: string) => {
      const fg = fgRef.current
      if (!fg) return
      const node = nodesRef.current.find((n: any) => n.id === nodeId)
      if (!node || node.x === undefined) return
      const distance = node.nodeType === 'concept' ? 150 : 100
      const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z)
      fg.cameraPosition(
        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
        node,
        1000,
      )
    }, [])

    const zoomToFit = useCallback(() => {
      fgRef.current?.zoomToFit(800, 60)
    }, [])

    useImperativeHandle(ref, () => ({ zoomToNode, zoomToFit }), [zoomToNode, zoomToFit])

    // Scene setup: fog + bloom
    useEffect(() => {
      const fg = fgRef.current
      if (!fg) return

      const scene = (fg as any).scene?.()
      if (scene) {
        scene.fog = new THREE.FogExp2('#0a0a1a', 0.0006)
      }

      try {
        const composer = (fg as any).postProcessingComposer?.()
        if (composer) {
          import('three/examples/jsm/postprocessing/UnrealBloomPass.js').then(
            ({ UnrealBloomPass }) => {
              const bloom = new UnrealBloomPass(
                undefined as any,
                0.6,
                0.3,
                0.88,
              )
              composer.addPass(bloom)
            }
          ).catch(() => {})
        }
      } catch {}
    }, [])

    const handleNodeClick = useCallback((node: any) => {
      const distance = node.nodeType === 'concept' ? 150 : 100
      const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z)
      fgRef.current?.cameraPosition(
        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
        node,
        1000,
      )
      if (onNodeClick && node._raw) {
        onNodeClick(node._raw)
      }
    }, [onNodeClick])

    if (nodes.length === 0) {
      return (
        <div
          className="flex items-center justify-center text-white/40 text-sm"
          style={{ width, height }}
        >
          Start chatting to build your memory map
        </div>
      )
    }

    // Custom 3D objects
    const renderNode = useCallback((node: any) => {
      // ── Concept nodes (octahedron + label) ──
      if (node.nodeType === 'concept') {
        const group = new THREE.Group()

        const geo = new THREE.OctahedronGeometry(6, 1)
        const mat = new THREE.MeshBasicMaterial({
          color: node.color,
          transparent: true,
          opacity: 0.8,
        })
        group.add(new THREE.Mesh(geo, mat))

        // Wireframe
        const wireMat = new THREE.MeshBasicMaterial({
          color: node.color,
          transparent: true,
          opacity: 0.25,
          wireframe: true,
        })
        group.add(new THREE.Mesh(geo, wireMat))

        // Label
        const label = new SpriteText(node.name)
        label.color = node.color
        label.textHeight = 3.5
        label.fontWeight = '700'
        label.backgroundColor = 'rgba(0,0,0,0.7)'
        label.padding = [2, 4]
        label.borderRadius = 3
        label.position.y = 11
        group.add(label)

        return group
      }

      // ── Document nodes (box + label) ──
      if (node.nodeType === 'document') {
        const group = new THREE.Group()

        // Box shape to represent documents
        const geo = new THREE.BoxGeometry(5, 6, 1.5)
        const mat = new THREE.MeshBasicMaterial({
          color: node.color,
          transparent: true,
          opacity: 0.85,
        })
        group.add(new THREE.Mesh(geo, mat))

        // Edge wireframe
        const edges = new THREE.EdgesGeometry(geo)
        const lineMat = new THREE.LineBasicMaterial({
          color: node.color,
          transparent: true,
          opacity: 0.4,
        })
        group.add(new THREE.LineSegments(edges, lineMat))

        // Doc type label
        const typeLabel = node.docType || 'doc'
        const label = new SpriteText(typeLabel.toUpperCase())
        label.color = node.color
        label.textHeight = 2
        label.fontWeight = '600'
        label.backgroundColor = 'rgba(0,0,0,0.6)'
        label.padding = [1, 2]
        label.borderRadius = 2
        label.position.y = 7
        group.add(label)

        return group
      }

      // ── Memory nodes (spheres) ──
      const radius = 2.5
      const geo = new THREE.SphereGeometry(radius, 12, 12)
      const mat = new THREE.MeshBasicMaterial({
        color: node.color,
        transparent: true,
        opacity: 0.75,
      })
      return new THREE.Mesh(geo, mat)
    }, [])

    return (
      <ForceGraph3D
        ref={fgRef}
        graphData={graphData}
        width={width}
        height={height}
        backgroundColor="rgba(0,0,0,0)"
        nodeVisibility={isNodeVisible}
        linkVisibility={isLinkVisible}
        nodeThreeObject={renderNode}
        nodeLabel={(node: any) => {
          if (node.nodeType === 'concept') {
            return `<div style="background:rgba(0,0,0,0.9);color:#fff;padding:8px 12px;border-radius:8px;font-size:13px;max-width:240px;line-height:1.5;border:1px solid ${node.color}">
              <b style="color:${node.color}">${node.name}</b><br/>
              Mastery: ${node.masteryLabel}<br/>
              Practiced: ${node.timesPracticed} times<br/>
              Struggled: ${node.timesStruggled} times
            </div>`
          }
          if (node.nodeType === 'document') {
            return `<div style="background:rgba(0,0,0,0.9);color:#fff;padding:8px 12px;border-radius:8px;font-size:13px;max-width:280px;line-height:1.5;border:1px solid ${node.color}">
              <span style="color:${node.color};text-transform:uppercase;font-size:10px;font-weight:600">${node.docType || 'document'}</span><br/>
              <b>${node.name}</b><br/>
              ${node.pageCount ? `${node.pageCount} pages` : ''}
              ${node.chunkCount ? ` · ${node.chunkCount} chunks` : ''}
              ${node.status === 'processing' ? '<br/><span style="color:#60a5fa">Indexing...</span>' : ''}
            </div>`
          }
          // Memory
          const conceptTags = node.concepts?.length
            ? `<br/><span style="color:#88ccff">${node.concepts.slice(0, 4).join(', ')}</span>`
            : ''
          return `<div style="background:rgba(0,0,0,0.9);color:#fff;padding:8px 12px;border-radius:8px;font-size:12px;max-width:260px;line-height:1.5;border:1px solid ${node.color}">
            <span style="color:${node.color};text-transform:uppercase;font-size:10px">${node.memoryType ?? 'memory'}${sentimentIcon(node.sentiment)}</span><br/>
            ${node.name}${conceptTags}
          </div>`
        }}
        // Links
        linkWidth={(link: any) => {
          if (link.edgeType === 'concept_concept') return 1
          if (link.edgeType === 'memory_concept') return 1.2
          if (link.edgeType === 'doc_concept') return 1.5
          if (link.edgeType === 'memory_memory') return 0.6
          return 0.5
        }}
        linkOpacity={0.3}
        linkColor={(link: any) => {
          if (link.edgeType === 'concept_concept') return '#9966ff'
          if (link.edgeType === 'memory_concept') return '#4488ff'
          if (link.edgeType === 'doc_concept') return '#a78bfa'
          if (link.edgeType === 'memory_memory') return '#553388'
          return '#444466'
        }}
        linkDirectionalParticles={(link: any) => {
          if (link.edgeType === 'doc_concept') return 2
          if (link.edgeType === 'memory_concept') return 1
          return 0
        }}
        linkDirectionalParticleWidth={1.2}
        linkDirectionalParticleSpeed={0.004}
        linkDirectionalParticleColor={() => '#88ccff'}
        onNodeClick={handleNodeClick}
        enableNodeDrag={true}
        enableNavigationControls={true}
        showNavInfo={false}
      />
    )
  }
)
