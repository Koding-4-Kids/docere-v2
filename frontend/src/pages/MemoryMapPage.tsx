import { useState, useEffect, useRef, useCallback } from 'react'
import {
  X, Plus, Upload, Link, FileText, Brain, Loader, Trash2, Eye,
  AlertCircle, CheckCircle, File, Image, Presentation, Table
} from 'lucide-react'
import { StudentMemoryGraph, type MemoryFilterType, type StudentMemoryGraphHandle } from '../components/StudentMemoryGraph'
import { DocumentReader } from '../components/DocumentReader'
import * as api from '../api'
import type { MemoryGraphNode, StudentDocument } from '../api'

interface Props {
  courseId: string
  onClose: () => void
}

const FILTER_OPTIONS: { key: MemoryFilterType; label: string; color: string }[] = [
  { key: 'all', label: 'All', color: '#ffffff' },
  { key: 'memories', label: 'Memories', color: '#4488ff' },
  { key: 'concepts', label: 'Concepts', color: '#44ddff' },
  { key: 'documents', label: 'Documents', color: '#a78bfa' },
  { key: 'struggle', label: 'Struggles', color: '#ff6b6b' },
  { key: 'breakthrough', label: 'Breakthroughs', color: '#44ff88' },
]

const DOC_TYPE_CONFIG: Record<string, { icon: typeof FileText; color: string }> = {
  textbook: { icon: FileText, color: 'text-purple-400' },
  slides: { icon: Presentation, color: 'text-orange-400' },
  notes: { icon: File, color: 'text-blue-400' },
  rubric: { icon: FileText, color: 'text-pink-400' },
  assignment: { icon: FileText, color: 'text-emerald-400' },
  exam: { icon: FileText, color: 'text-red-400' },
  syllabus: { icon: FileText, color: 'text-amber-400' },
  image: { icon: Image, color: 'text-purple-300' },
  spreadsheet: { icon: Table, color: 'text-green-400' },
  docs: { icon: File, color: 'text-blue-300' },
  other: { icon: FileText, color: 'text-gray-400' },
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function MemoryMapPage({ courseId, onClose }: Props) {
  const [graphData, setGraphData] = useState<api.MemoryGraphData | null>(null)
  const [graphLoading, setGraphLoading] = useState(true)
  const [filter, setFilter] = useState<MemoryFilterType>('all')
  const [size, setSize] = useState({ width: window.innerWidth, height: window.innerHeight })
  const graphRef = useRef<StudentMemoryGraphHandle>(null)

  // Add memory panel
  const [showAddPanel, setShowAddPanel] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [showUrlInput, setShowUrlInput] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // Document list in panel
  const [docs, setDocs] = useState<StudentDocument[]>([])

  // Selected node detail
  const [selectedNode, setSelectedNode] = useState<MemoryGraphNode | null>(null)

  // Document reader view
  const [activeDocId, setActiveDocId] = useState<string | null>(null)

  // Resize
  useEffect(() => {
    const handler = () => setSize({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener('resize', handler)
    return () => window.removeEventListener('resize', handler)
  }, [])

  // Load graph
  const loadGraph = useCallback(async () => {
    try {
      const data = await api.getMyMemoryGraph(courseId)
      setGraphData(data)
    } catch (e) {
      console.error('Failed to load memory graph', e)
    } finally {
      setGraphLoading(false)
    }
  }, [courseId])

  useEffect(() => { loadGraph() }, [loadGraph])

  // Load docs for the panel
  const loadDocs = useCallback(async () => {
    try {
      const list = await api.listDocuments(courseId)
      setDocs(list)
    } catch {}
  }, [courseId])

  useEffect(() => { loadDocs() }, [loadDocs])

  // Poll for processing docs
  useEffect(() => {
    const hasProcessing = docs.some(d => d.status === 'processing')
    if (!hasProcessing) return
    const interval = setInterval(() => {
      loadDocs()
      loadGraph()
    }, 3000)
    return () => clearInterval(interval)
  }, [docs, loadDocs, loadGraph])

  const handleUpload = async (file: File) => {
    setUploadError(null)
    setUploading(true)
    try {
      await api.uploadDocument(courseId, file)
      // Auto-confirm (skip preview, add directly)
      await loadDocs()
      await loadGraph()
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleUrlSubmit = async () => {
    if (!urlInput.trim()) return
    setUploadError(null)
    setUploading(true)
    try {
      await api.uploadDocumentFromUrl(courseId, urlInput.trim())
      setUrlInput('')
      setShowUrlInput(false)
      await loadDocs()
      await loadGraph()
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const handleDeleteDoc = async (docId: string) => {
    try {
      await api.deleteDocument(docId)
      setDocs(prev => prev.filter(d => d.id !== docId))
      await loadGraph()
    } catch {}
  }

  const handleConfirmDoc = async (docId: string) => {
    try {
      await api.confirmDocument(docId)
      await loadDocs()
      await loadGraph()
    } catch {}
  }

  const handleNodeClick = useCallback((node: MemoryGraphNode) => {
    setSelectedNode(node)
    // If it's a document, also prepare for reader
    if (node.type === 'document') {
      const docId = node.id.replace('doc_', '')
      setActiveDocId(docId)
    }
  }, [])

  // Document reader overlay
  if (activeDocId) {
    return (
      <div className="fixed inset-0 z-50 bg-bg-0 flex flex-col">
        <DocumentReader
          docId={activeDocId}
          courseId={courseId}
          onBack={() => { setActiveDocId(null); setSelectedNode(null) }}
          onStatusChange={() => { loadDocs(); loadGraph() }}
        />
      </div>
    )
  }

  // Stats
  const stats = graphData ? {
    memories: graphData.nodes.filter(n => n.type === 'memory').length,
    concepts: graphData.nodes.filter(n => n.type === 'concept').length,
    documents: graphData.nodes.filter(n => n.type === 'document').length,
  } : { memories: 0, concepts: 0, documents: 0 }

  return (
    <div className="fixed inset-0 z-50 bg-[#0a0a0f] overflow-hidden">
      {/* Graph */}
      {graphLoading ? (
        <div className="flex items-center justify-center h-full">
          <Loader className="w-8 h-8 text-white/30 animate-spin" />
        </div>
      ) : graphData && (
        <StudentMemoryGraph
          ref={graphRef}
          nodes={graphData.nodes}
          edges={graphData.edges}
          width={size.width}
          height={size.height}
          filter={filter}
          onNodeClick={handleNodeClick}
        />
      )}

      {/* Top-left: Back + title */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
        <button
          onClick={onClose}
          className="flex items-center gap-1.5 bg-black/60 backdrop-blur-md rounded-xl px-3 py-2.5 border border-white/10 hover:border-white/25 hover:bg-black/70 transition-all text-[11px] text-white/40 hover:text-white/70"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Back
        </button>
        <div className="bg-black/60 backdrop-blur-md rounded-xl px-4 py-2.5 border border-white/10">
          <div className="flex items-center gap-2">
            <Brain className="w-4 h-4 text-purple-400" />
            <div>
              <h1 className="text-sm font-medium text-white/90">My Memory</h1>
              <p className="text-[10px] text-white/40">
                {stats.memories} memories · {stats.concepts} concepts · {stats.documents} docs
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Top-right: Filters */}
      <div className="absolute top-4 right-4 z-10 flex flex-col gap-2 items-end">
        {/* Filter pills */}
        <div className="bg-black/60 backdrop-blur-md rounded-xl px-2 py-1.5 border border-white/10 flex items-center gap-1">
          {FILTER_OPTIONS.map(f => {
            const active = filter === f.key
            return (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                  active
                    ? 'bg-white/15 text-white/90'
                    : 'text-white/40 hover:text-white/70 hover:bg-white/5'
                }`}
              >
                <span
                  className="inline-block w-2 h-2 rounded-full"
                  style={{ backgroundColor: active ? f.color : `${f.color}66` }}
                />
                {f.label}
              </button>
            )
          })}
        </div>

        {/* Add memory button */}
        <button
          onClick={() => setShowAddPanel(!showAddPanel)}
          className={`flex items-center gap-2 px-4 py-2.5 rounded-xl border transition-all text-[12px] font-medium ${
            showAddPanel
              ? 'bg-purple-500/20 border-purple-500/40 text-purple-300'
              : 'bg-black/60 backdrop-blur-md border-white/10 text-white/60 hover:text-white/80 hover:border-white/25'
          }`}
        >
          <Plus className="w-4 h-4" />
          Add Memory
        </button>
      </div>

      {/* Add Memory Panel — right side */}
      {showAddPanel && (
        <div className="absolute top-28 right-4 z-10 w-[320px] bg-black/80 backdrop-blur-xl rounded-2xl border border-white/10 overflow-hidden animate-fade-in">
          {/* Panel header */}
          <div className="px-4 py-3 border-b border-white/10 flex items-center gap-2">
            <Plus className="w-4 h-4 text-purple-400" />
            <span className="text-sm font-medium text-white/80 flex-1">Add to Memory</span>
            <button
              onClick={() => setShowAddPanel(false)}
              className="p-1 rounded-lg hover:bg-white/10 text-white/40 hover:text-white/70 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          {/* Upload section */}
          <div className="px-4 py-3 space-y-3">
            {/* File upload */}
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              className="w-full flex items-center gap-3 px-3 py-3 rounded-xl border border-dashed border-white/15 hover:border-purple-500/40 hover:bg-purple-500/5 transition-all text-left group"
            >
              {uploading ? (
                <Loader className="w-5 h-5 text-purple-400 animate-spin shrink-0" />
              ) : (
                <Upload className="w-5 h-5 text-white/30 group-hover:text-purple-400 transition-colors shrink-0" />
              )}
              <div>
                <p className="text-xs text-white/70 font-medium">Upload Document</p>
                <p className="text-[10px] text-white/30">PDF, DOCX, PPTX, images</p>
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,.pptx,.xlsx,.html,.htm,.txt,.md,.png,.jpg,.jpeg"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); if (fileRef.current) fileRef.current.value = '' }}
                className="hidden"
              />
            </button>

            {/* URL input */}
            {!showUrlInput ? (
              <button
                onClick={() => setShowUrlInput(true)}
                className="w-full flex items-center gap-3 px-3 py-3 rounded-xl border border-dashed border-white/15 hover:border-purple-500/40 hover:bg-purple-500/5 transition-all text-left group"
              >
                <Link className="w-5 h-5 text-white/30 group-hover:text-purple-400 transition-colors shrink-0" />
                <div>
                  <p className="text-xs text-white/70 font-medium">From URL</p>
                  <p className="text-[10px] text-white/30">Paste a link to a document</p>
                </div>
              </button>
            ) : (
              <div className="space-y-2">
                <input
                  value={urlInput}
                  onChange={e => setUrlInput(e.target.value)}
                  placeholder="https://example.com/textbook.pdf"
                  className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white/80 placeholder:text-white/25 outline-none focus:border-purple-500/40 transition-all"
                  onKeyDown={e => e.key === 'Enter' && handleUrlSubmit()}
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => { setShowUrlInput(false); setUrlInput('') }}
                    className="px-3 py-1.5 rounded-lg text-white/40 hover:text-white/70 text-xs transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleUrlSubmit}
                    disabled={uploading || !urlInput.trim()}
                    className="flex-1 px-3 py-1.5 rounded-lg bg-purple-500/20 text-purple-300 text-xs font-medium hover:bg-purple-500/30 transition-colors disabled:opacity-40"
                  >
                    {uploading ? 'Adding...' : 'Add'}
                  </button>
                </div>
              </div>
            )}

            {/* Error */}
            {uploadError && (
              <div className="px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-[11px] flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span className="flex-1">{uploadError}</span>
                <button onClick={() => setUploadError(null)} className="text-red-400/60 hover:text-red-400 font-medium">x</button>
              </div>
            )}
          </div>

          {/* Document list */}
          {docs.length > 0 && (
            <div className="border-t border-white/10">
              <div className="px-4 py-2">
                <p className="text-[10px] text-white/30 uppercase tracking-wider font-medium">Documents ({docs.length})</p>
              </div>
              <div className="max-h-[300px] overflow-y-auto custom-scrollbar px-2 pb-3 space-y-1">
                {docs.map(doc => {
                  const ext = doc.filename.split('.').pop()?.toLowerCase() || ''
                  const docTypeCfg = DOC_TYPE_CONFIG[ext] || DOC_TYPE_CONFIG.other
                  const Icon = docTypeCfg.icon

                  return (
                    <div
                      key={doc.id}
                      className="flex items-center gap-2.5 px-2 py-2 rounded-xl hover:bg-white/5 transition-all group"
                    >
                      <Icon className={`w-4 h-4 ${docTypeCfg.color} shrink-0`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-[11px] text-white/70 truncate">{doc.filename}</p>
                        <p className="text-[10px] text-white/30">
                          {formatFileSize(doc.file_size_bytes)}
                          {doc.status === 'completed' && doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
                          {doc.status === 'processing' && (
                            <span className="text-blue-400"> · Indexing...</span>
                          )}
                          {doc.status === 'uploaded' && (
                            <span className="text-yellow-400"> · Pending</span>
                          )}
                        </p>
                      </div>

                      {/* Actions */}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {doc.status === 'uploaded' && (
                          <button
                            onClick={() => handleConfirmDoc(doc.id)}
                            className="p-1 rounded-lg hover:bg-green-500/15 text-green-400 transition-colors"
                            title="Add to collection"
                          >
                            <CheckCircle className="w-3.5 h-3.5" />
                          </button>
                        )}
                        <button
                          onClick={() => setActiveDocId(doc.id)}
                          className="p-1 rounded-lg hover:bg-white/10 text-white/40 hover:text-white/70 transition-colors"
                          title="View"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDeleteDoc(doc.id)}
                          className="p-1 rounded-lg hover:bg-red-500/15 text-white/30 hover:text-red-400 transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Selected node detail — bottom center */}
      {selectedNode && selectedNode.type !== 'document' && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-10 bg-black/80 backdrop-blur-xl rounded-2xl border border-white/10 px-5 py-4 max-w-md animate-fade-in">
          <div className="flex items-start gap-3">
            <div>
              {selectedNode.type === 'concept' && (
                <>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider font-medium mb-1">Concept</p>
                  <p className="text-sm text-white/90 font-medium">{selectedNode.name}</p>
                  <div className="flex items-center gap-3 mt-2 text-[11px] text-white/50">
                    <span>Mastery: <span className="text-white/80">{selectedNode.mastery_label}</span></span>
                    <span>Practiced: <span className="text-white/80">{selectedNode.times_practiced}x</span></span>
                    <span>Struggled: <span className="text-white/80">{selectedNode.times_struggled}x</span></span>
                  </div>
                </>
              )}
              {selectedNode.type === 'memory' && (
                <>
                  <p className="text-[10px] uppercase tracking-wider font-medium mb-1" style={{
                    color: selectedNode.memory_type === 'struggle' ? '#ff6b6b' :
                           selectedNode.memory_type === 'breakthrough' ? '#44ff88' :
                           selectedNode.memory_type === 'question' ? '#ffd700' :
                           selectedNode.memory_type === 'insight' ? '#44ddff' : '#8888cc'
                  }}>
                    {selectedNode.memory_type || 'memory'}
                  </p>
                  <p className="text-sm text-white/80 leading-relaxed">{selectedNode.content || selectedNode.name}</p>
                  {selectedNode.concepts && selectedNode.concepts.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {selectedNode.concepts.map(c => (
                        <span key={c} className="px-2 py-0.5 rounded-md bg-white/10 text-[10px] text-white/50">{c}</span>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="p-1 rounded-lg hover:bg-white/10 text-white/30 hover:text-white/60 transition-colors shrink-0"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
