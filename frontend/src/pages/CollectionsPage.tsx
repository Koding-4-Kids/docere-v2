import { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import {
  X, Upload, FileText, Trash2, AlertCircle, Loader,
  Link, BookOpen, Search, Grid3X3, List, File, Image, Presentation,
  Table, Eye, Plus
} from 'lucide-react'
import { DocumentReader } from '../components/DocumentReader'
import * as api from '../api'
import type { StudentDocument } from '../api'

interface Props {
  courseId: string
  onClose: () => void
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

const FILE_TYPE_CONFIG: Record<string, { icon: typeof FileText; color: string; bg: string; label: string }> = {
  pdf:  { icon: FileText, color: 'text-red-500', bg: 'bg-red-500/10', label: 'PDF' },
  docx: { icon: File, color: 'text-blue-500', bg: 'bg-blue-500/10', label: 'DOCX' },
  doc:  { icon: File, color: 'text-blue-500', bg: 'bg-blue-500/10', label: 'DOC' },
  pptx: { icon: Presentation, color: 'text-orange-500', bg: 'bg-orange-500/10', label: 'PPTX' },
  xlsx: { icon: Table, color: 'text-green-500', bg: 'bg-green-500/10', label: 'XLSX' },
  png:  { icon: Image, color: 'text-purple-500', bg: 'bg-purple-500/10', label: 'PNG' },
  jpg:  { icon: Image, color: 'text-purple-500', bg: 'bg-purple-500/10', label: 'JPG' },
  jpeg: { icon: Image, color: 'text-purple-500', bg: 'bg-purple-500/10', label: 'JPEG' },
  txt:  { icon: FileText, color: 'text-text-400', bg: 'bg-bg-200', label: 'TXT' },
  md:   { icon: FileText, color: 'text-text-400', bg: 'bg-bg-200', label: 'MD' },
  html: { icon: FileText, color: 'text-amber-500', bg: 'bg-amber-500/10', label: 'HTML' },
}

function getFileConfig(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  return FILE_TYPE_CONFIG[ext] || { icon: FileText, color: 'text-text-400', bg: 'bg-bg-200', label: ext.toUpperCase() || 'FILE' }
}

const STATUS_CONFIG = {
  uploaded:   { color: 'bg-yellow-500', label: 'Preview', pulse: false },
  processing: { color: 'bg-blue-500', label: 'Indexing', pulse: true },
  completed:  { color: 'bg-green-500', label: 'Ready', pulse: false },
  failed:     { color: 'bg-red-500', label: 'Failed', pulse: false },
}

type ViewMode = 'grid' | 'list'

export function CollectionsPage({ courseId, onClose }: Props) {
  const [docs, setDocs] = useState<StudentDocument[]>([])
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [activeDocId, setActiveDocId] = useState<string | null>(null)
  const [urlInput, setUrlInput] = useState('')
  const [showUrlInput, setShowUrlInput] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [viewMode, setViewMode] = useState<ViewMode>('grid')
  const [dragOver, setDragOver] = useState(false)
  const [, setContextMenu] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const contextRef = useRef<HTMLDivElement>(null)

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
    const interval = setInterval(loadDocs, 3000)
    return () => clearInterval(interval)
  }, [docs, loadDocs])

  // Close context menu on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (contextRef.current && !contextRef.current.contains(e.target as Node)) {
        setContextMenu(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Fake upload progress
  useEffect(() => {
    if (!uploading) { setUploadProgress(0); return }
    setUploadProgress(10)
    const interval = setInterval(() => {
      setUploadProgress(prev => prev >= 90 ? 90 : prev + Math.random() * 15)
    }, 300)
    return () => clearInterval(interval)
  }, [uploading])

  const handleUpload = async (file: File) => {
    setError(null)
    setUploading(true)
    try {
      const result = await api.uploadDocument(courseId, file)
      setUploadProgress(100)
      await loadDocs()
      setTimeout(() => setActiveDocId(result.doc_id), 200)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }

  const handleUrlSubmit = async () => {
    if (!urlInput.trim()) return
    setError(null)
    setUploading(true)
    try {
      const result = await api.uploadDocumentFromUrl(courseId, urlInput.trim())
      setUrlInput('')
      setShowUrlInput(false)
      await loadDocs()
      setActiveDocId(result.doc_id)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (e: React.MouseEvent, docId: string) => {
    e.stopPropagation()
    setContextMenu(null)
    try {
      await api.deleteDocument(docId)
      if (activeDocId === docId) setActiveDocId(null)
      setDocs(prev => prev.filter(d => d.id !== docId))
    } catch (e: any) {
      setError(e.message)
    }
  }

  const filteredDocs = useMemo(() => {
    if (!searchQuery.trim()) return docs
    const q = searchQuery.toLowerCase()
    return docs.filter(d => d.filename.toLowerCase().includes(q))
  }, [docs, searchQuery])

  const stats = useMemo(() => ({
    total: docs.length,
    ready: docs.filter(d => d.status === 'completed').length,
    totalSize: docs.reduce((sum, d) => sum + d.file_size_bytes, 0),
  }), [docs])

  // Document reader view
  if (activeDocId) {
    return (
      <div className="fixed inset-0 z-50 bg-bg-0 flex flex-col">
        <DocumentReader
          docId={activeDocId}
          courseId={courseId}
          onBack={() => setActiveDocId(null)}
          onStatusChange={loadDocs}
        />
      </div>
    )
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-bg-0 flex flex-col"
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={e => { if (e.currentTarget === e.target) setDragOver(false) }}
      onDrop={handleDrop}
    >
      {/* Drag overlay */}
      {dragOver && (
        <div className="absolute inset-0 z-50 bg-accent/5 border-2 border-dashed border-accent/40 rounded-2xl m-4 flex items-center justify-center backdrop-blur-sm">
          <div className="text-center">
            <Upload className="w-12 h-12 mx-auto text-accent mb-3" />
            <p className="text-lg font-medium text-accent">Drop to upload</p>
            <p className="text-sm text-text-400 mt-1">PDF, DOCX, PPTX, images</p>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="px-6 py-4 border-b border-bg-300 shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-accent/10 flex items-center justify-center">
            <BookOpen className="w-5 h-5 text-accent" />
          </div>
          <div className="flex-1">
            <h1 className="text-lg font-semibold text-text-100">My Collections</h1>
            <p className="text-xs text-text-500">
              {stats.total} document{stats.total !== 1 ? 's' : ''}
              {stats.total > 0 && (
                <> &middot; {stats.ready} ready &middot; {formatFileSize(stats.totalSize)}</>
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-xl hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Toolbar */}
        {docs.length > 0 && (
          <div className="flex items-center gap-3 mt-4">
            <div className="flex-1 relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-text-500" />
              <input
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search documents..."
                className="w-full bg-bg-200 rounded-xl pl-9 pr-4 py-2 text-sm text-text-200 placeholder:text-text-500 outline-none focus:ring-2 focus:ring-accent/20 transition-all"
              />
            </div>
            <div className="flex items-center bg-bg-200 rounded-xl p-1">
              <button
                onClick={() => setViewMode('grid')}
                className={`p-1.5 rounded-lg transition-colors ${viewMode === 'grid' ? 'bg-bg-0 text-text-200 shadow-sm' : 'text-text-500 hover:text-text-300'}`}
              >
                <Grid3X3 className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={`p-1.5 rounded-lg transition-colors ${viewMode === 'list' ? 'bg-bg-0 text-text-200 shadow-sm' : 'text-text-500 hover:text-text-300'}`}
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-6">
        <div className="max-w-5xl mx-auto">
          {/* Upload area */}
          <div className="flex gap-3 mb-6">
            <button
              onClick={() => fileRef.current?.click()}
              className="flex-1 flex items-center gap-3 px-5 py-4 rounded-2xl border-2 border-dashed border-bg-300 hover:border-accent/30 hover:bg-accent/5 transition-all cursor-pointer group"
            >
              {uploading ? (
                <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center shrink-0">
                  <Loader className="w-5 h-5 text-accent animate-spin" />
                </div>
              ) : (
                <div className="w-10 h-10 rounded-xl bg-bg-200 group-hover:bg-accent/10 flex items-center justify-center shrink-0 transition-colors">
                  <Plus className="w-5 h-5 text-text-400 group-hover:text-accent transition-colors" />
                </div>
              )}
              <div className="text-left">
                <p className="text-sm font-medium text-text-200">
                  {uploading ? 'Uploading...' : 'Upload Document'}
                </p>
                <p className="text-xs text-text-500">PDF, DOCX, PPTX, images up to 500MB</p>
              </div>
              <input
                ref={fileRef}
                type="file"
                accept=".pdf,.docx,.pptx,.xlsx,.html,.htm,.txt,.md,.png,.jpg,.jpeg"
                onChange={e => { const f = e.target.files?.[0]; if (f) handleUpload(f); if (fileRef.current) fileRef.current.value = '' }}
                className="hidden"
              />
            </button>

            <button
              onClick={() => setShowUrlInput(!showUrlInput)}
              className={`flex items-center gap-3 px-5 py-4 rounded-2xl border-2 border-dashed transition-all cursor-pointer group ${
                showUrlInput ? 'border-accent/30 bg-accent/5' : 'border-bg-300 hover:border-accent/30 hover:bg-accent/5'
              }`}
            >
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition-colors ${
                showUrlInput ? 'bg-accent/10' : 'bg-bg-200 group-hover:bg-accent/10'
              }`}>
                <Link className={`w-5 h-5 transition-colors ${showUrlInput ? 'text-accent' : 'text-text-400 group-hover:text-accent'}`} />
              </div>
              <div className="text-left">
                <p className="text-sm font-medium text-text-200">From URL</p>
                <p className="text-xs text-text-500">Paste a link</p>
              </div>
            </button>
          </div>

          {/* Upload progress bar */}
          {uploading && (
            <div className="mb-4 rounded-full overflow-hidden bg-bg-200 h-1.5">
              <div
                className="h-full bg-accent rounded-full transition-all duration-300 ease-out"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          )}

          {/* URL input */}
          {showUrlInput && (
            <div className="mb-6 flex gap-2 animate-fade-in">
              <input
                value={urlInput}
                onChange={e => setUrlInput(e.target.value)}
                placeholder="https://example.com/textbook.pdf"
                className="flex-1 bg-bg-0 border border-bg-300 rounded-xl px-4 py-2.5 text-sm text-text-200 placeholder:text-text-500 outline-none focus:ring-2 focus:ring-accent/20 transition-all"
                onKeyDown={e => e.key === 'Enter' && handleUrlSubmit()}
                autoFocus
              />
              <button
                onClick={handleUrlSubmit}
                disabled={uploading || !urlInput.trim()}
                className="px-5 py-2.5 rounded-xl bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-40"
              >
                Add
              </button>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="mb-4 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-sm flex items-center justify-between animate-fade-in">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{error}</span>
              </div>
              <button onClick={() => setError(null)} className="text-red-400 hover:text-red-500 ml-4 text-xs font-medium">Dismiss</button>
            </div>
          )}

          {/* Empty state */}
          {docs.length === 0 && !uploading && (
            <div className="text-center py-20 animate-fade-in">
              <div className="w-20 h-20 mx-auto rounded-2xl bg-bg-200 flex items-center justify-center mb-4">
                <BookOpen className="w-10 h-10 text-text-500" />
              </div>
              <p className="text-text-300 text-base font-medium">No materials yet</p>
              <p className="text-text-500 text-sm mt-2 max-w-sm mx-auto">
                Upload textbooks, notes, or slides and the tutor will reference them in your conversations.
              </p>
            </div>
          )}

          {/* No search results */}
          {docs.length > 0 && filteredDocs.length === 0 && (
            <div className="text-center py-16">
              <Search className="w-8 h-8 mx-auto text-text-500 mb-3" />
              <p className="text-text-400 text-sm">No documents matching "{searchQuery}"</p>
            </div>
          )}

          {/* Grid view */}
          {viewMode === 'grid' && filteredDocs.length > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
              {filteredDocs.map(doc => {
                const fileCfg = getFileConfig(doc.filename)
                const FileIcon = fileCfg.icon
                const status = STATUS_CONFIG[doc.status]

                return (
                  <button
                    key={doc.id}
                    onClick={() => setActiveDocId(doc.id)}
                    className="group relative flex flex-col rounded-2xl border border-bg-300 bg-bg-0 hover:border-accent/25 hover:shadow-lg hover:shadow-accent/5 transition-all duration-200 text-left overflow-hidden"
                  >
                    {/* File type banner */}
                    <div className={`${fileCfg.bg} px-4 py-6 flex items-center justify-center`}>
                      <FileIcon className={`w-10 h-10 ${fileCfg.color}`} />
                    </div>

                    {/* Status dot */}
                    <div className="absolute top-3 right-3">
                      <div className={`w-2.5 h-2.5 rounded-full ${status.color} ${status.pulse ? 'animate-pulse' : ''}`} />
                    </div>

                    {/* Info */}
                    <div className="px-4 py-3 flex-1 flex flex-col min-h-0">
                      <p className="text-sm font-medium text-text-200 truncate leading-tight">{doc.filename}</p>
                      <div className="flex items-center gap-2 mt-1.5">
                        <span className={`text-[10px] font-semibold px-1.5 py-0.5 rounded-md ${fileCfg.bg} ${fileCfg.color}`}>
                          {fileCfg.label}
                        </span>
                        <span className="text-[11px] text-text-500">{formatFileSize(doc.file_size_bytes)}</span>
                      </div>
                      <p className="text-[11px] text-text-500 mt-1.5">
                        {doc.status === 'completed' && doc.chunk_count > 0 && `${doc.chunk_count} chunks indexed`}
                        {doc.status === 'processing' && 'Indexing...'}
                        {doc.status === 'uploaded' && 'Ready to preview'}
                        {doc.status === 'failed' && (doc.error_message || 'Processing failed')}
                      </p>
                    </div>

                    {/* Hover overlay actions */}
                    <div className="absolute inset-0 bg-bg-0/80 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-center justify-center gap-3 backdrop-blur-sm">
                      <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent/15 text-accent text-xs font-medium">
                        <Eye className="w-3.5 h-3.5" />
                        Open
                      </div>
                      <div
                        onClick={e => handleDelete(e, doc.id)}
                        className="p-2 rounded-lg hover:bg-red-500/15 text-text-400 hover:text-red-400 transition-colors cursor-pointer"
                      >
                        <Trash2 className="w-4 h-4" />
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}

          {/* List view */}
          {viewMode === 'list' && filteredDocs.length > 0 && (
            <div className="space-y-1.5">
              {/* List header */}
              <div className="flex items-center gap-4 px-4 py-2 text-[11px] font-medium text-text-500 uppercase tracking-wider">
                <span className="flex-1">Name</span>
                <span className="w-16 text-right">Size</span>
                <span className="w-20 text-center">Status</span>
                <span className="w-24 text-right">Modified</span>
                <span className="w-8" />
              </div>

              {filteredDocs.map(doc => {
                const fileCfg = getFileConfig(doc.filename)
                const FileIcon = fileCfg.icon
                const status = STATUS_CONFIG[doc.status]

                return (
                  <button
                    key={doc.id}
                    onClick={() => setActiveDocId(doc.id)}
                    className="w-full flex items-center gap-4 px-4 py-3 rounded-xl hover:bg-bg-200 transition-all text-left group"
                  >
                    {/* File icon */}
                    <div className={`w-9 h-9 rounded-lg ${fileCfg.bg} flex items-center justify-center shrink-0`}>
                      <FileIcon className={`w-4.5 h-4.5 ${fileCfg.color}`} />
                    </div>

                    {/* Name + details */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-text-200 truncate">{doc.filename}</p>
                      <p className="text-[11px] text-text-500">
                        {doc.page_count && `${doc.page_count} pages`}
                        {doc.status === 'completed' && doc.chunk_count > 0 && ` · ${doc.chunk_count} chunks`}
                      </p>
                    </div>

                    {/* Size */}
                    <span className="w-16 text-right text-xs text-text-400 shrink-0">
                      {formatFileSize(doc.file_size_bytes)}
                    </span>

                    {/* Status badge */}
                    <div className="w-20 flex justify-center shrink-0">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-lg text-[11px] font-medium ${
                        doc.status === 'completed' ? 'bg-green-500/10 text-green-500' :
                        doc.status === 'processing' ? 'bg-blue-500/10 text-blue-400' :
                        doc.status === 'failed' ? 'bg-red-500/10 text-red-400' :
                        'bg-yellow-500/10 text-yellow-500'
                      }`}>
                        {doc.status === 'processing' && <Loader className="w-3 h-3 animate-spin" />}
                        {status.label}
                      </span>
                    </div>

                    {/* Time */}
                    <span className="w-24 text-right text-xs text-text-500 shrink-0">
                      {doc.created_at ? timeAgo(doc.created_at) : ''}
                    </span>

                    {/* Delete */}
                    <div
                      onClick={e => handleDelete(e, doc.id)}
                      className="w-8 flex justify-center opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
                    >
                      <div className="p-1 rounded-lg hover:bg-red-500/10 text-text-500 hover:text-red-400 transition-colors">
                        <Trash2 className="w-3.5 h-3.5" />
                      </div>
                    </div>
                  </button>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
