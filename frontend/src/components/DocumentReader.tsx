import { useState, useEffect, useMemo, useCallback } from 'react'
import {
  ArrowLeft, BookPlus, CheckCircle, Loader, AlertCircle, FileText,
  File, Image, Presentation, Table, ZoomIn, ZoomOut, Copy, Check,
  ChevronLeft, ChevronRight, BookOpen, StickyNote, ClipboardList,
  GraduationCap, ScrollText, MessageSquare
} from 'lucide-react'
import { Document, Page, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import 'react-pdf/dist/Page/TextLayer.css'
import { DocumentChat } from './DocumentChat'
import * as api from '../api'
import type { StudentDocumentDetail } from '../api'

// Set up pdf.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`

interface Props {
  docId: string
  courseId?: string
  onBack: () => void
  onStatusChange?: () => void
}

const DOC_TYPE_LABEL: Record<string, { label: string; icon: typeof FileText; color: string }> = {
  textbook:    { label: 'Textbook', icon: BookOpen, color: 'text-purple-400' },
  slides:      { label: 'Slides', icon: Presentation, color: 'text-orange-400' },
  notes:       { label: 'Notes', icon: StickyNote, color: 'text-blue-400' },
  rubric:      { label: 'Rubric', icon: ClipboardList, color: 'text-pink-400' },
  assignment:  { label: 'Assignment', icon: FileText, color: 'text-emerald-400' },
  exam:        { label: 'Exam', icon: GraduationCap, color: 'text-red-400' },
  syllabus:    { label: 'Syllabus', icon: ScrollText, color: 'text-amber-400' },
  image:       { label: 'Image', icon: Image, color: 'text-purple-300' },
  spreadsheet: { label: 'Spreadsheet', icon: Table, color: 'text-green-400' },
  docs:        { label: 'Document', icon: File, color: 'text-blue-300' },
  other:       { label: 'Document', icon: FileText, color: 'text-text-400' },
}

const FILE_TYPE_CONFIG: Record<string, { icon: typeof FileText; color: string; bg: string }> = {
  pdf:  { icon: FileText, color: 'text-red-500', bg: 'bg-red-500/10' },
  docx: { icon: File, color: 'text-blue-500', bg: 'bg-blue-500/10' },
  doc:  { icon: File, color: 'text-blue-500', bg: 'bg-blue-500/10' },
  pptx: { icon: Presentation, color: 'text-orange-500', bg: 'bg-orange-500/10' },
  xlsx: { icon: Table, color: 'text-green-500', bg: 'bg-green-500/10' },
  png:  { icon: Image, color: 'text-purple-500', bg: 'bg-purple-500/10' },
  jpg:  { icon: Image, color: 'text-purple-500', bg: 'bg-purple-500/10' },
  jpeg: { icon: Image, color: 'text-purple-500', bg: 'bg-purple-500/10' },
}

function getFileConfig(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  return FILE_TYPE_CONFIG[ext] || { icon: FileText, color: 'text-text-400', bg: 'bg-bg-200' }
}

function isPdfFile(filename: string): boolean {
  return filename.toLowerCase().endsWith('.pdf')
}

function isImageFile(filename: string): boolean {
  const ext = filename.split('.').pop()?.toLowerCase() || ''
  return ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)
}

// ── PDF Viewer (slides or textbook mode) ──

function PdfViewer({ docId, docType, pageCount }: { docId: string; docType: string | null; pageCount: number | null }) {
  const [fileUrl, setFileUrl] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [numPages, setNumPages] = useState<number>(pageCount || 0)
  const [currentPage, setCurrentPage] = useState(1)
  const [scale, setScale] = useState(docType === 'slides' ? 1.2 : 1.0)
  const isSlides = docType === 'slides'

  // Fetch the file blob
  useEffect(() => {
    let objectUrl: string | null = null
    api.fetchDocumentFileBlob(docId)
      .then(blob => {
        objectUrl = URL.createObjectURL(blob)
        setFileUrl(objectUrl)
      })
      .catch(e => setLoadError(e.message))
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [docId])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        setCurrentPage(p => Math.min(numPages, p + 1))
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        setCurrentPage(p => Math.max(1, p - 1))
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [numPages])

  const onDocLoad = useCallback(({ numPages: n }: { numPages: number }) => {
    setNumPages(n)
  }, [])

  if (loadError) {
    return (
      <div className="text-center py-20">
        <AlertCircle className="w-8 h-8 mx-auto text-text-500 mb-3" />
        <p className="text-text-400 text-sm">Could not load file: {loadError}</p>
      </div>
    )
  }

  if (!fileUrl) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader className="w-6 h-6 text-accent animate-spin" />
      </div>
    )
  }

  if (isSlides) {
    // ── Slide mode: one page at a time, centered, 16:10-ish ──
    return (
      <div className="flex flex-col items-center gap-4 py-6 px-4">
        {/* Slide */}
        <div className="bg-bg-0 rounded-2xl shadow-lg border border-bg-300 overflow-hidden">
          <Document file={fileUrl} onLoadSuccess={onDocLoad} loading="">
            <Page
              pageNumber={currentPage}
              scale={scale}
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          </Document>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-4">
          <button
            onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
            disabled={currentPage <= 1}
            className="p-2.5 rounded-xl bg-bg-0 border border-bg-300 hover:bg-bg-200 text-text-300 hover:text-text-100 transition-all disabled:opacity-30"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>

          {/* Page dots or counter */}
          {numPages <= 30 ? (
            <div className="flex items-center gap-1.5">
              {Array.from({ length: numPages }, (_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentPage(i + 1)}
                  className={`w-2 h-2 rounded-full transition-all ${
                    i + 1 === currentPage ? 'bg-accent scale-125' : 'bg-bg-300 hover:bg-text-500'
                  }`}
                />
              ))}
            </div>
          ) : (
            <span className="text-sm text-text-400 tabular-nums">
              {currentPage} / {numPages}
            </span>
          )}

          <button
            onClick={() => setCurrentPage(p => Math.min(numPages, p + 1))}
            disabled={currentPage >= numPages}
            className="p-2.5 rounded-xl bg-bg-0 border border-bg-300 hover:bg-bg-200 text-text-300 hover:text-text-100 transition-all disabled:opacity-30"
          >
            <ChevronRight className="w-5 h-5" />
          </button>

          <div className="w-px h-5 bg-bg-300 mx-1" />

          {/* Zoom */}
          <button
            onClick={() => setScale(s => Math.max(0.5, s - 0.15))}
            className="p-1.5 rounded-lg hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-[11px] text-text-500 w-10 text-center">{Math.round(scale * 100)}%</span>
          <button
            onClick={() => setScale(s => Math.min(3, s + 0.15))}
            className="p-1.5 rounded-lg hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
        </div>

        <p className="text-[10px] text-text-500">Arrow keys to navigate</p>
      </div>
    )
  }

  // ── Scrollable mode (textbook, assignment, etc.): all pages stacked ──
  return (
    <div className="flex flex-col items-center gap-4 py-6 px-4">
      {/* Zoom controls */}
      <div className="sticky top-2 z-10 flex items-center gap-2 bg-bg-0/90 backdrop-blur-md rounded-xl border border-bg-300 px-3 py-1.5 shadow-sm">
        <button
          onClick={() => setScale(s => Math.max(0.5, s - 0.15))}
          className="p-1 rounded-lg hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <span className="text-[11px] text-text-500 w-10 text-center">{Math.round(scale * 100)}%</span>
        <button
          onClick={() => setScale(s => Math.min(3, s + 0.15))}
          className="p-1 rounded-lg hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <div className="w-px h-4 bg-bg-300 mx-1" />
        <span className="text-[11px] text-text-500">{numPages} pages</span>
      </div>

      {/* Pages */}
      <Document file={fileUrl} onLoadSuccess={onDocLoad} loading="">
        {Array.from({ length: numPages }, (_, i) => (
          <div key={i} className="mb-4 bg-bg-0 rounded-xl shadow-sm border border-bg-300 overflow-hidden">
            <Page
              pageNumber={i + 1}
              scale={scale}
              renderTextLayer={true}
              renderAnnotationLayer={true}
            />
          </div>
        ))}
      </Document>
    </div>
  )
}

// ── Image Viewer ──

function ImageViewer({ docId }: { docId: string }) {
  const [imageUrl, setImageUrl] = useState<string | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | null = null
    api.fetchDocumentFileBlob(docId)
      .then(blob => {
        objectUrl = URL.createObjectURL(blob)
        setImageUrl(objectUrl)
      })
      .catch(e => setLoadError(e.message))
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl) }
  }, [docId])

  if (loadError) {
    return (
      <div className="text-center py-20">
        <AlertCircle className="w-8 h-8 mx-auto text-text-500 mb-3" />
        <p className="text-text-400 text-sm">Could not load image</p>
      </div>
    )
  }

  if (!imageUrl) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader className="w-6 h-6 text-accent animate-spin" />
      </div>
    )
  }

  return (
    <div className="flex items-center justify-center py-8 px-4">
      <img
        src={imageUrl}
        alt="Uploaded document"
        className="max-w-full max-h-[80vh] rounded-2xl shadow-lg border border-bg-300 object-contain"
      />
    </div>
  )
}

// ── Text Fallback (notes, rubric, etc.) ──

function TextViewer({ text, fontSize, docType }: { text: string; fontSize: number; docType: string | null }) {
  if (docType === 'notes') {
    return (
      <div className="py-8 px-4">
        <div className="max-w-2xl mx-auto bg-amber-50 dark:bg-amber-500/5 rounded-2xl border border-amber-200/50 dark:border-amber-500/15 shadow-sm px-8 sm:px-10 py-8">
          <div
            className="text-text-200 leading-relaxed whitespace-pre-wrap"
            style={{ fontSize: `${fontSize}px`, lineHeight: '1.8' }}
          >
            {text}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto py-8 px-4">
      <div className="bg-bg-0 rounded-2xl shadow-sm border border-bg-300 px-8 sm:px-12 py-10">
        <div
          className="text-text-200 leading-relaxed whitespace-pre-wrap font-sans"
          style={{ fontSize: `${fontSize}px`, lineHeight: '1.7' }}
        >
          {text}
        </div>
      </div>
    </div>
  )
}

// ── Main DocumentReader ──

export function DocumentReader({ docId, courseId, onBack, onStatusChange }: Props) {
  const [doc, setDoc] = useState<StudentDocumentDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [fontSize, setFontSize] = useState(15)
  const [copied, setCopied] = useState(false)
  const [chatOpen, setChatOpen] = useState(false)

  useEffect(() => {
    setLoading(true)
    api.getDocument(docId)
      .then(setDoc)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [docId])

  // Poll while processing
  useEffect(() => {
    if (!doc || doc.status !== 'processing') return
    const interval = setInterval(async () => {
      try {
        const status = await api.getDocumentStatus(docId)
        if (status.status !== 'processing') {
          setDoc(prev => prev ? { ...prev, status: status.status, chunk_count: status.chunk_count } : prev)
          onStatusChange?.()
          clearInterval(interval)
        }
      } catch {}
    }, 2000)
    return () => clearInterval(interval)
  }, [doc?.status, docId, onStatusChange])

  const handleConfirm = async () => {
    setConfirming(true)
    setError(null)
    try {
      await api.confirmDocument(docId)
      setDoc(prev => prev ? { ...prev, status: 'processing' } : prev)
      onStatusChange?.()
    } catch (e: any) {
      setError(e.message)
    } finally {
      setConfirming(false)
    }
  }

  const handleCopy = async () => {
    if (!doc?.extracted_text) return
    await navigator.clipboard.writeText(doc.extracted_text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3">
        <Loader className="w-6 h-6 text-accent animate-spin" />
        <p className="text-sm text-text-500">Loading document...</p>
      </div>
    )
  }

  if (!doc) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-3">
        <AlertCircle className="w-8 h-8 text-text-500" />
        <p className="text-sm text-text-400">Document not found</p>
        <button onClick={onBack} className="text-sm text-accent hover:underline">Go back</button>
      </div>
    )
  }

  const fileCfg = getFileConfig(doc.filename)
  const FileIcon = fileCfg.icon
  const docTypeCfg = DOC_TYPE_LABEL[doc.doc_type || 'other'] || DOC_TYPE_LABEL.other
  const DocTypeIcon = docTypeCfg.icon
  const canRenderPdf = isPdfFile(doc.filename) && doc.has_file
  const canRenderImage = isImageFile(doc.filename) && doc.has_file
  // Show text controls only when we're in text fallback mode
  const showTextControls = !canRenderPdf && !canRenderImage && !!doc.extracted_text

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="px-6 py-3 border-b border-bg-300 flex items-center gap-3 shrink-0">
        <button
          onClick={onBack}
          className="p-2 rounded-xl hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>

        <div className={`w-8 h-8 rounded-lg ${fileCfg.bg} flex items-center justify-center shrink-0`}>
          <FileIcon className={`w-4 h-4 ${fileCfg.color}`} />
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text-200 truncate">{doc.filename}</p>
          <div className="flex items-center gap-2 mt-0.5">
            <span className={`flex items-center gap-1 text-[11px] font-medium ${docTypeCfg.color}`}>
              <DocTypeIcon className="w-3 h-3" />
              {docTypeCfg.label}
            </span>
            {doc.page_count && (
              <span className="text-[11px] text-text-500">{doc.page_count} pages</span>
            )}
            {doc.status === 'completed' && doc.chunk_count > 0 && (
              <span className="text-[11px] text-text-500">{doc.chunk_count} chunks</span>
            )}
          </div>
        </div>

        {/* Text controls — only for non-PDF text fallback */}
        {showTextControls && (
          <div className="flex items-center gap-1 mr-2">
            <button
              onClick={() => setFontSize(s => Math.max(12, s - 1))}
              className="p-1.5 rounded-lg hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
            >
              <ZoomOut className="w-4 h-4" />
            </button>
            <span className="text-[11px] text-text-500 w-6 text-center">{fontSize}</span>
            <button
              onClick={() => setFontSize(s => Math.min(24, s + 1))}
              className="p-1.5 rounded-lg hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
            >
              <ZoomIn className="w-4 h-4" />
            </button>
            <div className="w-px h-4 bg-bg-300 mx-1" />
            <button
              onClick={handleCopy}
              className="p-1.5 rounded-lg hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
            >
              {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
        )}

        {/* Copy for PDF mode */}
        {canRenderPdf && doc.extracted_text && (
          <button
            onClick={handleCopy}
            className="p-1.5 rounded-lg hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors mr-2"
            title="Copy extracted text"
          >
            {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
          </button>
        )}

        {/* Chat toggle */}
        {courseId && (
          <button
            onClick={() => setChatOpen(!chatOpen)}
            className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium transition-all mr-1 ${
              chatOpen
                ? 'bg-accent/15 text-accent'
                : 'bg-bg-200 text-text-400 hover:text-text-200 hover:bg-bg-300'
            }`}
          >
            <MessageSquare className="w-3.5 h-3.5" />
            Ask
          </button>
        )}

        {/* Status / Action button */}
        {doc.status === 'uploaded' && (
          <button
            onClick={handleConfirm}
            disabled={confirming}
            className="flex items-center gap-2 px-4 py-2 rounded-xl bg-accent text-white text-xs font-medium hover:bg-accent-hover transition-colors disabled:opacity-40"
          >
            {confirming ? (
              <Loader className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <BookPlus className="w-3.5 h-3.5" />
            )}
            Add to Memory
          </button>
        )}
        {doc.status === 'processing' && (
          <span className="flex items-center gap-2 px-4 py-2 rounded-xl bg-blue-500/10 text-blue-400 text-xs font-medium">
            <Loader className="w-3.5 h-3.5 animate-spin" />
            Indexing...
          </span>
        )}
        {doc.status === 'completed' && (
          <span className="flex items-center gap-2 px-4 py-2 rounded-xl bg-green-500/10 text-green-500 text-xs font-medium">
            <CheckCircle className="w-3.5 h-3.5" />
            In Memory
          </span>
        )}
        {doc.status === 'failed' && (
          <span className="flex items-center gap-2 px-4 py-2 rounded-xl bg-red-500/10 text-red-400 text-xs font-medium">
            <AlertCircle className="w-3.5 h-3.5" />
            Failed
          </span>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mx-6 mt-3 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-500 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar bg-bg-200/50 relative">
        {/* PDF — render original file */}
        {canRenderPdf && (
          <PdfViewer docId={docId} docType={doc.doc_type} pageCount={doc.page_count} />
        )}

        {/* Image — render original file */}
        {canRenderImage && (
          <ImageViewer docId={docId} />
        )}

        {/* Non-PDF, non-image — text fallback */}
        {!canRenderPdf && !canRenderImage && (
          <>
            {doc.extracted_text ? (
              <TextViewer text={doc.extracted_text} fontSize={fontSize} docType={doc.doc_type} />
            ) : doc.status === 'processing' ? (
              <div className="text-center py-20">
                <div className="w-16 h-16 mx-auto rounded-2xl bg-blue-500/10 flex items-center justify-center mb-4">
                  <Loader className="w-8 h-8 text-blue-400 animate-spin" />
                </div>
                <p className="text-text-300 font-medium">Processing document...</p>
                <p className="text-text-500 text-sm mt-2">Extracting text and building index.</p>
              </div>
            ) : (
              <div className="text-center py-20">
                <div className="w-16 h-16 mx-auto rounded-2xl bg-bg-200 flex items-center justify-center mb-4">
                  <FileText className="w-8 h-8 text-text-500" />
                </div>
                <p className="text-text-400 text-sm">No text extracted from this document.</p>
              </div>
            )}
          </>
        )}

        {/* Chat dropdown — floating over content, same style as instructor graph chat */}
        <DocumentChat
          isOpen={chatOpen}
          onClose={() => setChatOpen(false)}
          courseId={courseId || ''}
          docId={docId}
          docName={doc.filename}
          docType={doc.doc_type}
        />
      </div>
    </div>
  )
}
