import { useState, useEffect, useRef, useCallback } from 'react'
import { X, Upload, FileText, Trash2, CheckCircle, AlertCircle, Loader, Link, File, Image, Presentation, Table, Eye } from 'lucide-react'
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
  pending:    { label: 'Queued', spinning: true },
  processing: { label: 'Indexing', spinning: true },
  completed:  { label: 'Ready', spinning: false },
  failed:     { label: 'Failed', spinning: false },
}

export function DocumentsPanel({ courseId, onClose }: Props) {
  const [docs, setDocs] = useState<StudentDocument[]>([])
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [dragOver, setDragOver] = useState(false)
  const [urlInput, setUrlInput] = useState('')
  const [showUrlInput, setShowUrlInput] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadDocs = useCallback(async () => {
    try {
      const list = await api.listDocuments(courseId)
      setDocs(list)
    } catch {}
  }, [courseId])

  useEffect(() => { loadDocs() }, [loadDocs])

  // Poll for processing docs
  useEffect(() => {
    const hasProcessing = docs.some(d => d.status === 'pending' || d.status === 'processing')
    if (hasProcessing) {
      pollRef.current = setInterval(loadDocs, 3000)
    } else if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [docs, loadDocs])

  const handleUpload = async (file: File) => {
    setError(null)
    setUploading(true)
    try {
      await api.uploadDocument(courseId, file)
      await loadDocs()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleUpload(file)
    if (fileRef.current) fileRef.current.value = ''
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
      await api.uploadDocumentFromUrl(courseId, urlInput.trim())
      setUrlInput('')
      setShowUrlInput(false)
      await loadDocs()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (docId: string) => {
    try {
      await api.deleteDocument(docId)
      setDocs(prev => prev.filter(d => d.id !== docId))
    } catch (e: any) {
      setError(e.message)
    }
  }

  return (
    <div className="w-[380px] shrink-0 border-l border-bg-300 bg-bg-100 flex flex-col animate-slide-in-right">
      {/* Header */}
      <div className="px-4 py-3 border-b border-bg-300 flex items-center gap-3">
        <div className="w-7 h-7 rounded-lg bg-accent/10 flex items-center justify-center">
          <FileText className="w-3.5 h-3.5 text-accent" />
        </div>
        <span className="text-sm font-medium text-text-200 flex-1">My Materials</span>
        <span className="text-[11px] text-text-500 bg-bg-200 px-2 py-0.5 rounded-md">{docs.length}</span>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Upload area */}
      <div className="px-4 pt-4 pb-2">
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all ${
            dragOver
              ? 'border-accent/50 bg-accent/5'
              : 'border-bg-300 hover:border-accent/30 hover:bg-bg-200/50'
          }`}
        >
          {uploading ? (
            <Loader className="w-6 h-6 mx-auto text-accent animate-spin" />
          ) : (
            <Upload className="w-6 h-6 mx-auto text-text-400" />
          )}
          <p className="text-xs text-text-300 mt-2">
            {uploading ? 'Uploading...' : 'Drop files or click to browse'}
          </p>
          <p className="text-[10px] text-text-500 mt-1">
            PDF, DOCX, PPTX, images. Max 50MB.
          </p>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,.docx,.pptx,.xlsx,.html,.htm,.txt,.md,.png,.jpg,.jpeg"
            onChange={handleFileChange}
            className="hidden"
          />
        </div>

        {/* URL input */}
        <div className="mt-2">
          {!showUrlInput ? (
            <button
              onClick={() => setShowUrlInput(true)}
              className="flex items-center gap-1.5 text-[11px] text-accent/60 hover:text-accent transition-colors"
            >
              <Link className="w-3 h-3" />
              Or paste a URL...
            </button>
          ) : (
            <div className="flex gap-2 animate-fade-in">
              <input
                value={urlInput}
                onChange={e => setUrlInput(e.target.value)}
                placeholder="https://example.com/textbook.pdf"
                className="flex-1 bg-bg-0 border border-bg-300 rounded-lg px-3 py-1.5 text-xs text-text-200 placeholder:text-text-500 outline-none focus:ring-2 focus:ring-accent/20 transition-all"
                onKeyDown={e => e.key === 'Enter' && handleUrlSubmit()}
                autoFocus
              />
              <button
                onClick={handleUrlSubmit}
                disabled={uploading || !urlInput.trim()}
                className="px-3 py-1.5 rounded-lg bg-accent text-white text-xs font-medium hover:bg-accent-hover transition-colors disabled:opacity-40"
              >
                Add
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="mx-4 mt-2 px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-2 text-red-400 hover:text-red-500 font-medium">Dismiss</button>
        </div>
      )}

      {/* Document list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-4 py-3 space-y-1.5">
        {docs.length === 0 && !uploading && (
          <div className="text-center py-10">
            <div className="w-12 h-12 mx-auto rounded-xl bg-bg-200 flex items-center justify-center mb-3">
              <FileText className="w-6 h-6 text-text-500" />
            </div>
            <p className="text-xs text-text-400 font-medium">No materials yet</p>
            <p className="text-[11px] text-text-500 mt-1 max-w-[200px] mx-auto">
              Upload documents and the tutor will reference them in conversations.
            </p>
          </div>
        )}

        {docs.map(doc => {
          const fileCfg = getFileConfig(doc.filename)
          const FileIcon = fileCfg.icon
          const config = STATUS_CONFIG[doc.status]
          const isProcessing = doc.status === 'pending' || doc.status === 'processing'

          return (
            <div
              key={doc.id}
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-bg-200 transition-all group"
            >
              <div className={`w-8 h-8 rounded-lg ${fileCfg.bg} flex items-center justify-center shrink-0`}>
                {isProcessing ? (
                  <Loader className={`w-4 h-4 ${fileCfg.color} animate-spin`} />
                ) : (
                  <FileIcon className={`w-4 h-4 ${fileCfg.color}`} />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs text-text-200 truncate font-medium">{doc.filename}</p>
                <p className="text-[10px] text-text-500 flex items-center gap-1">
                  <span className={`font-semibold ${fileCfg.color}`}>{fileCfg.label}</span>
                  <span>&middot;</span>
                  <span>{formatFileSize(doc.file_size_bytes)}</span>
                  {doc.status === 'completed' && doc.chunk_count > 0 && (
                    <><span>&middot;</span><span>{doc.chunk_count} chunks</span></>
                  )}
                  {isProcessing && (
                    <><span>&middot;</span><span className="text-blue-400">{config.label}...</span></>
                  )}
                  {doc.status === 'failed' && (
                    <><span>&middot;</span><span className="text-red-400">{doc.error_message || 'Failed'}</span></>
                  )}
                </p>
              </div>
              <button
                onClick={() => handleDelete(doc.id)}
                className="p-1 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-red-500/10 text-text-500 hover:text-red-400 transition-all"
                title="Delete"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
