import { useRef, useCallback, useMemo, useEffect, forwardRef, useImperativeHandle } from 'react'
import ForceGraph3D from 'react-force-graph-3d'
import type { ForceGraphMethods } from 'react-force-graph-3d'
import SpriteText from 'three-spritetext'
import * as THREE from 'three'

interface GraphNode {
  id: string
  name: string
  type: 'student' | 'memory' | 'concept'
  // Student fields
  engagement?: string | null
  total_interactions?: number | null
  avg_confusion?: number | null
  // Memory fields
  memory_type?: string | null
  content?: string | null
  concepts?: string[] | null
  confusion_score?: number | null
  sentiment?: string | null
  // Concept fields
  avg_mastery?: number | null
  student_count?: number | null
  times_struggled?: number | null
  mastery_label?: string | null
}

interface GraphEdge {
  source: string
  target: string
  type: 'student_memory' | 'shared_concept' | 'concept_student' | 'concept_concept'
  weight?: number | null
}

export type GraphFilterType = 'all' | 'students' | 'struggle' | 'question' | 'insight' | 'breakthrough'
export type GraphTopology = 'student' | 'concept' | 'distributed'

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  width: number
  height: number
  filter?: GraphFilterType
  topology?: GraphTopology
  onStudentClick?: (studentId: string, studentName: string) => void
}

export interface ConceptGraph3DHandle {
  zoomToNode: (nodeId: string) => void
  zoomToFit: () => void
}

/** Student node color based on engagement level */
export function studentColor(engagement: string | null | undefined): string {
  switch (engagement) {
    case 'high': return '#44ff88'
    case 'medium': return '#ffd700'
    case 'low': return '#ff8c00'
    case 'inactive': return '#ff4444'
    default: return '#8888ff'
  }
}

/** Memory node color based on type */
function memoryColor(type: string | null | undefined, confusion: number): string {
  if (confusion > 0.6) return '#ff4444'  // high confusion — red
  switch (type) {
    case 'struggle': return '#ff6b6b'
    case 'breakthrough': return '#44ff88'
    case 'question': return '#ffd700'
    case 'insight': return '#44ddff'
    default: return '#8888cc'
  }
}

/** Concept node color based on mastery level */
function conceptColor(mastery: number): string {
  if (mastery >= 0.75) return '#44ff88'
  if (mastery >= 0.55) return '#44ddff'
  if (mastery >= 0.35) return '#ffd700'
  if (mastery >= 0.2) return '#ff8c00'
  return '#ff6b6b'
}

/** Sentiment indicator */
function sentimentIcon(sentiment: string | null | undefined): string {
  switch (sentiment) {
    case 'frustrated': return ' &#x26A0;'
    case 'confused': return ' ?'
    case 'confident': return ' &#x2713;'
    default: return ''
  }
}

export const ConceptGraph3D = forwardRef<ConceptGraph3DHandle, Props>(
  function ConceptGraph3D({ nodes, edges, width, height, filter = 'all', topology = 'student', onStudentClick }, ref) {
    const fgRef = useRef<ForceGraphMethods | undefined>(undefined)
    // d3-force mutates these node objects in-place, adding x/y/z positions
    const nodesRef = useRef<any[]>([])

    const isDistributed = topology === 'distributed'

    const graphData = useMemo(() => ({
      nodes: nodes.map(n => {
        if (n.type === 'concept') {
          return {
            id: n.id,
            name: n.name,
            nodeType: 'concept' as const,
            val: 8,
            color: conceptColor(n.avg_mastery ?? 0),
            avgMastery: n.avg_mastery ?? 0,
            studentCount: n.student_count ?? 0,
            timesStruggled: n.times_struggled ?? 0,
            masteryLabel: n.mastery_label ?? '',
          }
        }
        if (n.type === 'student') {
          return {
            id: n.id,
            name: n.name,
            nodeType: 'student' as const,
            val: isDistributed ? 3 : (topology === 'concept' ? 3 : 6),
            color: studentColor(n.engagement),
            engagement: n.engagement,
            totalInteractions: n.total_interactions ?? 0,
            avgConfusion: n.avg_confusion ?? 0,
          }
        }
        return {
          id: n.id,
          name: n.content ?? n.name,
          nodeType: 'memory' as const,
          val: isDistributed ? 2 : 1.5,
          color: memoryColor(n.memory_type, n.confusion_score ?? 0),
          memoryType: n.memory_type,
          concepts: n.concepts,
          confusionScore: n.confusion_score ?? 0,
          sentiment: n.sentiment,
        }
      }),
      links: edges.map(e => ({
        source: e.source,
        target: e.target,
        edgeType: e.type,
        weight: e.weight ?? null,
      })),
    }), [nodes, edges, isDistributed, topology])

    // Keep a live reference to the node objects d3-force mutates
    nodesRef.current = graphData.nodes

    // Visibility based on filter — keeps force layout stable
    const isNodeVisible = useCallback((node: any): boolean => {
      if (filter === 'all') return true
      if (node.nodeType === 'student') return true
      if (filter === 'students') return false
      return node.memoryType === filter
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
      const distance = node.nodeType === 'student' ? 150 : 80
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

      // Add exponential fog — softens the void when zoomed in
      const scene = (fg as any).scene?.()
      if (scene) {
        scene.fog = new THREE.FogExp2('#0a0a1a', 0.0006)
      }

      // Subtle bloom post-processing
      try {
        const composer = (fg as any).postProcessingComposer?.()
        if (composer) {
          import('three/examples/jsm/postprocessing/UnrealBloomPass.js').then(
            ({ UnrealBloomPass }) => {
              const bloom = new UnrealBloomPass(
                undefined as any,
                0.6,   // strength — gentle glow
                0.3,   // radius
                0.88,  // threshold — only brightest colors bloom
              )
              composer.addPass(bloom)
            }
          ).catch(() => {})
        }
      } catch {
        // postProcessingComposer may not be available
      }
    }, [])

    const handleNodeClick = useCallback((node: any) => {
      const distance = node.nodeType === 'student' ? 150 : 80
      const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z)
      fgRef.current?.cameraPosition(
        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio },
        node,
        1000,
      )
      if (node.nodeType === 'student' && onStudentClick) {
        onStudentClick(node.id, node.name)
      }
    }, [onStudentClick])

    if (nodes.length === 0) {
      return (
        <div
          className="flex items-center justify-center text-text-500 text-sm"
          style={{ width, height }}
        >
          No data yet — students need to start chatting
        </div>
      )
    }

    // Custom 3D objects per node type + topology
    const renderNode = useCallback((node: any) => {
      // ── Concept hub nodes (octahedron + label) ──
      if (node.nodeType === 'concept') {
        const group = new THREE.Group()

        const geo = new THREE.OctahedronGeometry(6, 1)
        const mat = new THREE.MeshBasicMaterial({
          color: node.color,
          transparent: true,
          opacity: 0.8,
          wireframe: false,
        })
        group.add(new THREE.Mesh(geo, mat))

        // Wireframe overlay
        const wireMat = new THREE.MeshBasicMaterial({
          color: node.color,
          transparent: true,
          opacity: 0.25,
          wireframe: true,
        })
        group.add(new THREE.Mesh(geo, wireMat))

        // Name label
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

      // ── Student nodes ──
      if (node.nodeType === 'student') {
        const isHub = topology === 'student'
        const radius = isHub ? 6 : 3.5
        const group = new THREE.Group()

        const geo = new THREE.SphereGeometry(radius, 24, 24)
        const mat = new THREE.MeshBasicMaterial({
          color: node.color,
          transparent: true,
          opacity: 0.85,
        })
        group.add(new THREE.Mesh(geo, mat))

        // Ring only when student is a hub
        if (isHub) {
          const ringGeo = new THREE.RingGeometry(radius + 1.5, radius + 2.5, 32)
          const ringMat = new THREE.MeshBasicMaterial({
            color: node.color,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide,
          })
          group.add(new THREE.Mesh(ringGeo, ringMat))
        }

        // Name label — always show for student nodes
        const label = new SpriteText(node.name)
        label.color = node.color
        label.textHeight = isHub ? 3.5 : 2.5
        label.fontWeight = '600'
        label.backgroundColor = 'rgba(0,0,0,0.6)'
        label.padding = [1.5, 3]
        label.borderRadius = 2
        label.position.y = radius + 5
        group.add(label)

        return group
      }

      // ── Memory nodes ──
      const radius = isDistributed ? 2.5 : 1.8
      const geo = new THREE.SphereGeometry(radius, 12, 12)
      const mat = new THREE.MeshBasicMaterial({
        color: node.color,
        transparent: true,
        opacity: isDistributed ? 0.85 : 0.7,
      })
      return new THREE.Mesh(geo, mat)
    }, [topology, isDistributed])

    return (
      <ForceGraph3D
        ref={fgRef}
        graphData={graphData}
        width={width}
        height={height}
        backgroundColor="rgba(0,0,0,0)"
        // Visibility
        nodeVisibility={isNodeVisible}
        linkVisibility={isLinkVisible}
        // Custom node rendering
        nodeThreeObject={renderNode}
        nodeLabel={(node: any) => {
          if (node.nodeType === 'concept') {
            return `<div style="background:rgba(0,0,0,0.9);color:#fff;padding:8px 12px;border-radius:8px;font-size:13px;max-width:240px;line-height:1.5;border:1px solid ${node.color}">
            <b style="color:${node.color}">${node.name}</b><br/>
            Mastery: ${node.masteryLabel}<br/>
            ${node.studentCount} students<br/>
            ${node.timesStruggled} times struggled
          </div>`
          }
          if (node.nodeType === 'student') {
            return `<div style="background:rgba(0,0,0,0.9);color:#fff;padding:8px 12px;border-radius:8px;font-size:13px;max-width:240px;line-height:1.5;border:1px solid ${node.color}">
            <b style="color:${node.color}">${node.name}</b><br/>
            Engagement: ${node.engagement ?? 'unknown'}<br/>
            Interactions: ${node.totalInteractions}<br/>
            Avg Confusion: ${Math.round(node.avgConfusion * 100)}%
          </div>`
          }
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
          if (link.edgeType === 'concept_student') return 1.2
          if (link.edgeType === 'student_memory') return isDistributed ? 0.8 : 1.5
          return 0.3
        }}
        linkOpacity={0.35}
        linkColor={(link: any) => {
          if (link.edgeType === 'concept_concept') return '#9966ff'
          if (link.edgeType === 'concept_student') return '#44ddff'
          if (link.edgeType === 'student_memory') return '#4488ff'
          return '#553388'
        }}
        linkDirectionalParticles={(link: any) => {
          if (link.edgeType === 'concept_student') return 1
          if (link.edgeType === 'student_memory' && !isDistributed) return 2
          return 0
        }}
        linkDirectionalParticleWidth={1.2}
        linkDirectionalParticleSpeed={0.004}
        linkDirectionalParticleColor={() => '#88ccff'}
        // Interaction
        onNodeClick={handleNodeClick}
        enableNodeDrag={true}
        enableNavigationControls={true}
        showNavInfo={false}
      />
    )
  }
)
