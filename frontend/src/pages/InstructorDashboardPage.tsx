import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { storeAuth, listCourses, getIntegrationStatus } from '../api'
import type { Course, IntegrationStatus } from '../api'
import { Icons } from '../components/ClaudeChatInput'
import { ConceptGraph3D } from '../components/ConceptGraph3D'
import type { ConceptGraph3DHandle, GraphFilterType, GraphTopology } from '../components/ConceptGraph3D'
import { InstructorChat } from '../components/InstructorChat'
import { InstructorWidgets } from '../components/InstructorWidgetRenderer'
import { StudentRoster } from '../components/StudentRoster'
import { useInstructorChat } from '../hooks/useInstructorChat'
import { useMetaChat } from '../hooks/useMetaChat'
import { CalendarSetup } from '../components/CalendarSetup'
import { ActionCard } from '../components/ActionCard'
import { GmailModal, GoogleDocsModal, CalendarEventModal, LMSAnnouncementModal } from '../components/ToolModals'
import { GradebookSyncModal } from '../components/GradebookSyncModal'

interface DashboardSummary {
  course_id: string
  course_name: string
  student_count: number
}

interface GraphNode {
  id: string
  name: string
  type: 'student' | 'memory'
  engagement?: string | null
  total_interactions?: number | null
  avg_confusion?: number | null
  memory_type?: string | null
  content?: string | null
  concepts?: string[] | null
  confusion_score?: number | null
  sentiment?: string | null
}

interface GraphEdge {
  source: string
  target: string
  type: 'student_memory' | 'shared_concept'
}

interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface TaggedStudent {
  id: string
  name: string
}

// ── Source type icons ──
const SOURCE_ICONS: Record<string, string> = {
  enrollment: '👥',
  student_profile: '📊',
  concept_mastery: '🧠',
  routing: '🔀',
}

function SourcesSection({ sources }: { sources: { type: string; label: string; student_name?: string | null; detail?: string | null }[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="ml-10 mt-1">
      <button
        onClick={() => setOpen(p => !p)}
        className="flex items-center gap-1 text-[10px] text-white/25 hover:text-white/45 transition-colors"
      >
        <svg
          width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          className={`transition-transform ${open ? 'rotate-90' : ''}`}
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
        {sources.length} source{sources.length !== 1 ? 's' : ''} used
      </button>
      {open && (
        <div className="mt-1.5 space-y-1 pl-3 border-l border-white/5">
          {sources.map((src, i) => (
            <div key={i} className="text-[10px] text-white/35 flex items-start gap-1.5">
              <span>{SOURCE_ICONS[src.type] ?? '📎'}</span>
              <div>
                <span className="text-white/50">{src.label}</span>
                {src.student_name && (
                  <span className="text-white/30 ml-1">— {src.student_name}</span>
                )}
                {src.detail && (
                  <span className="text-white/20 ml-1">({src.detail})</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const QUICK_ACTIONS = [
  { label: "Who's struggling?", prompt: "Which students are struggling and what are they struggling with?" },
  { label: 'Class overview', prompt: 'Give me an overview of how my class is doing overall.' },
  { label: 'At-risk students', prompt: 'Which students are at risk of falling behind and why?' },
  { label: 'Recent activity', prompt: 'Summarize the most recent student activity and engagement patterns.' },
]

const META_QUICK_ACTIONS = [
  { label: 'Cross-class overview', desc: 'See how all your classes compare', prompt: 'Give me an overview of how all my classes are doing. Which class needs the most attention right now?' },
  { label: 'At-risk students', desc: 'Prioritized by urgency across courses', prompt: 'Across all my classes, which students are most at risk and why? Prioritize by urgency.' },
  { label: 'Prep office hours', desc: 'Who to expect and what to focus on', prompt: "Prepare me for office hours today. Which students should I expect, what are they struggling with, and what should I focus on?" },
  { label: 'Weekly digest', desc: 'Trends, changes, and next steps', prompt: "Give me a weekly digest of what happened across all my classes — key trends, notable changes, and what I should focus on next week." },
  { label: 'Generate slides', desc: 'For department meetings or reviews', prompt: 'Create a short slide deck summarizing student performance across all my classes for a department meeting.' },
  { label: 'Common struggles', desc: 'Patterns across all your courses', prompt: 'What concepts are students struggling with the most across all my courses? Are there patterns?' },
]

// ── Tool integration definitions ──
interface ToolIntegration {
  id: string
  name: string
  description: string
  icon: React.ReactNode
  status: 'available' | 'coming_soon'
}

const TOOL_INTEGRATIONS: ToolIntegration[] = [
  {
    id: 'google_calendar',
    name: 'Google Calendar',
    description: 'Office hours, prep time blocks, meeting scheduling',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <rect x="2" y="3" width="20" height="19" rx="2" fill="#4285F4" />
        <rect x="2" y="3" width="20" height="6" rx="2" fill="#1967D2" />
        <rect x="4.5" y="11" width="4" height="3.5" rx="0.5" fill="#fff" fillOpacity="0.9" />
        <rect x="10" y="11" width="4" height="3.5" rx="0.5" fill="#fff" fillOpacity="0.9" />
        <rect x="15.5" y="11" width="4" height="3.5" rx="0.5" fill="#fff" fillOpacity="0.9" />
        <rect x="4.5" y="16" width="4" height="3.5" rx="0.5" fill="#fff" fillOpacity="0.9" />
        <rect x="10" y="16" width="4" height="3.5" rx="0.5" fill="#fff" fillOpacity="0.9" />
        <rect x="7" y="1" width="2" height="4" rx="1" fill="#1967D2" />
        <rect x="15" y="1" width="2" height="4" rx="1" fill="#1967D2" />
      </svg>
    ),
    status: 'available',
  },
  {
    id: 'email',
    name: 'Gmail',
    description: 'Draft emails to students, parents, or admin',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M2 6a2 2 0 0 1 2-4h16a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6z" fill="#EA4335" fillOpacity="0.15" />
        <rect x="2" y="4" width="20" height="16" rx="2" fill="#fff" fillOpacity="0.1" stroke="#EA4335" strokeWidth="1.5" />
        <path d="M2 6l10 7 10-7" stroke="#EA4335" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M2 18l6.5-5.5" stroke="#EA4335" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M22 18l-6.5-5.5" stroke="#EA4335" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
    status: 'available',
  },
  {
    id: 'slack',
    name: 'Slack',
    description: 'Push alerts and weekly digests to channels',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M5.042 15.165a2.528 2.528 0 0 1-2.52 2.523A2.528 2.528 0 0 1 0 15.165a2.527 2.527 0 0 1 2.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 0 1 2.521-2.52 2.527 2.527 0 0 1 2.521 2.52v6.313A2.528 2.528 0 0 1 8.834 24a2.528 2.528 0 0 1-2.521-2.522v-6.313z" fill="#E01E5A" />
        <path d="M8.834 5.042a2.528 2.528 0 0 1-2.521-2.52A2.528 2.528 0 0 1 8.834 0a2.528 2.528 0 0 1 2.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 0 1 2.521 2.521 2.528 2.528 0 0 1-2.521 2.521H2.522A2.528 2.528 0 0 1 0 8.834a2.528 2.528 0 0 1 2.522-2.521h6.312z" fill="#36C5F0" />
        <path d="M18.956 8.834a2.528 2.528 0 0 1 2.522-2.521A2.528 2.528 0 0 1 24 8.834a2.528 2.528 0 0 1-2.522 2.521h-2.522V8.834zm-1.27 0a2.528 2.528 0 0 1-2.523 2.521 2.527 2.527 0 0 1-2.52-2.521V2.522A2.527 2.527 0 0 1 15.163 0a2.528 2.528 0 0 1 2.523 2.522v6.312z" fill="#2EB67D" />
        <path d="M15.163 18.956a2.528 2.528 0 0 1 2.523 2.522A2.528 2.528 0 0 1 15.163 24a2.527 2.527 0 0 1-2.52-2.522v-2.522h2.52zm0-1.27a2.527 2.527 0 0 1-2.52-2.523 2.527 2.527 0 0 1 2.52-2.52h6.314A2.528 2.528 0 0 1 24 15.163a2.528 2.528 0 0 1-2.523 2.523h-6.314z" fill="#ECB22E" />
      </svg>
    ),
    status: 'coming_soon',
  },
  {
    id: 'google_docs',
    name: 'Google Docs',
    description: 'Export reports, guides, and intervention plans',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#4285F4" />
        <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#A1C2FA" />
        <rect x="7" y="12" width="10" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.9" />
        <rect x="7" y="15" width="7" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.9" />
        <rect x="7" y="18" width="9" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.9" />
      </svg>
    ),
    status: 'available',
  },
  {
    id: 'google_sheets',
    name: 'Google Sheets',
    description: 'Gradebook exports, engagement trends, mastery data',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#0F9D58" />
        <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#87CEAC" />
        <rect x="6.5" y="11.5" width="11" height="8" rx="0.5" fill="#fff" fillOpacity="0.9" />
        <line x1="6.5" y1="15.5" x2="17.5" y2="15.5" stroke="#0F9D58" strokeWidth="0.8" />
        <line x1="11" y1="11.5" x2="11" y2="19.5" stroke="#0F9D58" strokeWidth="0.8" />
      </svg>
    ),
    status: 'available',
  },
  {
    id: 'excel',
    name: 'Excel',
    description: 'Download spreadsheets as .xlsx files',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#217346" />
        <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#33C481" />
        <path d="M7.5 12l3 4m0-4l-3 4" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
        <rect x="13" y="12" width="4" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.8" />
        <rect x="13" y="14.5" width="3" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.8" />
        <rect x="13" y="17" width="3.5" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.8" />
      </svg>
    ),
    status: 'available',
  },
  {
    id: 'zoom',
    name: 'Zoom',
    description: 'Schedule group tutoring and office hours',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <rect x="1" y="4" width="22" height="16" rx="4" fill="#2D8CFF" />
        <rect x="3.5" y="7.5" width="10" height="9" rx="1.5" fill="#fff" />
        <path d="M15 10l4.5-2.5v9L15 14v-4z" fill="#fff" />
      </svg>
    ),
    status: 'coming_soon',
  },
  {
    id: 'lms_push',
    name: 'Moodle / Canvas',
    description: 'Post announcements, resources, adjust due dates',
    icon: (
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
        <path d="M12 3L2 9l10 6 10-6-10-6z" fill="#F98012" />
        <path d="M2 9v6l10 6 10-6V9" fill="none" stroke="#F98012" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M7 11.5v5l5 3 5-3v-5" fill="#F98012" fillOpacity="0.3" stroke="#F98012" strokeWidth="1" strokeLinejoin="round" />
        <line x1="20" y1="9" x2="20" y2="17" stroke="#F98012" strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="20" cy="18" r="1" fill="#F98012" />
      </svg>
    ),
    status: 'available',
  },
]

const PINNED_TOOLS_KEY = 'docere_pinned_tools'

function loadPinnedTools(): string[] {
  try {
    const raw = localStorage.getItem(PINNED_TOOLS_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function savePinnedTools(ids: string[]) {
  localStorage.setItem(PINNED_TOOLS_KEY, JSON.stringify(ids))
}

export function InstructorDashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null)
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [view, setView] = useState<'chat' | 'network' | 'settings'>('chat')
  const [graphFilter, setGraphFilter] = useState<GraphFilterType>('all')
  const [graphTopology, setGraphTopology] = useState<GraphTopology>('student')
  const [chatOpen, setChatOpen] = useState(false)
  const [courses, setCourses] = useState<Course[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [taggedStudents, setTaggedStudents] = useState<TaggedStudent[]>([])
  const containerRef = useRef<HTMLDivElement>(null)
  const graphRef = useRef<ConceptGraph3DHandle>(null)
  const [size, setSize] = useState({ width: window.innerWidth, height: window.innerHeight })
  const [courseId, setCourseId] = useState('')
  const [activeMode, setActiveMode] = useState<'course' | 'meta'>('course')
  const [editingDashboard, setEditingDashboard] = useState(false)
  const [pinnedTools, setPinnedTools] = useState<string[]>(loadPinnedTools)
  const [editDraft, setEditDraft] = useState<string[]>([])
  const [draggedIdx, setDraggedIdx] = useState<number | null>(null)
  const [activeToolModal, setActiveToolModal] = useState<string | null>(null)
  const [integrationStatus, setIntegrationStatus] = useState<IntegrationStatus | null>(null)

  // Shared chat state
  const { messages, loading: chatLoading, sendQuestion, sourceFilters, setSourceFilters } = useInstructorChat(courseId)

  // Meta chat state
  const { messages: metaMessages, loading: metaLoading, sendQuestion: metaSend, courseSummaries } = useMetaChat()

  // Chat-first view input state
  const [chatInput, setChatInput] = useState('')
  const [metaInput, setMetaInput] = useState('')
  const chatBottomRef = useRef<HTMLDivElement>(null)
  const metaBottomRef = useRef<HTMLDivElement>(null)
  const chatInputRef = useRef<HTMLTextAreaElement>(null)

  // Track full viewport size
  useEffect(() => {
    const onResize = () => setSize({ width: window.innerWidth, height: window.innerHeight })
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // Load dashboard data for a given course
  const loadDashboard = useCallback((cid: string) => {
    const token = localStorage.getItem('docere_token')
    if (!token) return

    const headers = { Authorization: `Bearer ${token}` }

    Promise.all([
      fetch(`/api/v1/instructor/dashboard/${cid}/summary`, { headers })
        .then(res => {
          if (res.status === 403) throw new Error('Instructor access required')
          if (!res.ok) throw new Error(`HTTP ${res.status}`)
          return res.json()
        }),
      fetch(`/api/v1/instructor/dashboard/${cid}/concept-graph?topology=${graphTopology}`, { headers })
        .then(res => res.ok ? res.json() : { nodes: [], edges: [] })
        .catch(() => ({ nodes: [], edges: [] })),
    ])
      .then(([summaryData, graphResponse]) => {
        setSummary(summaryData)
        setGraphData(graphResponse)
        setLoading(false)
      })
      .catch(err => {
        setError(err instanceof Error ? err.message : 'Failed to load dashboard')
        setLoading(false)
      })
  }, [graphTopology])

  // Switch to a different course
  const switchCourse = useCallback((newCourseId: string) => {
    if (newCourseId === courseId && activeMode === 'course') return
    setActiveMode('course')
    setCourseId(newCourseId)
    setLoading(true)
    setSummary(null)
    setGraphData(null)
    setTaggedStudents([])
    setView('chat')
    // Update URL without full reload
    window.history.pushState(null, '', `/instructor/${newCourseId}`)
    loadDashboard(newCourseId)
  }, [courseId, activeMode, loadDashboard])

  // Switch to meta command center
  const switchToMeta = useCallback(() => {
    setActiveMode('meta')
    setView('chat')
  }, [])

  useEffect(() => {
    // 1. Read auth from hash fragment
    const hash = window.location.hash.substring(1)
    if (hash) {
      const params = new URLSearchParams(hash)
      const token = params.get('token')
      const userId = params.get('user_id')
      const name = params.get('name')
      const role = params.get('role')

      if (token && userId && name && role) {
        storeAuth(token, { id: userId, name, email: null, role })
        window.history.replaceState(null, '', window.location.pathname)
      }
    }

    // 2. Extract course_id from URL
    const pathParts = window.location.pathname.split('/')
    const cid = pathParts[pathParts.length - 1]
    if (!cid) {
      setError('No course specified')
      setLoading(false)
      return
    }
    setCourseId(cid)

    // 3. Fetch courses list + dashboard data
    const token = localStorage.getItem('docere_token')
    if (!token) {
      setError('Not authenticated')
      setLoading(false)
      return
    }

    listCourses().then(setCourses).catch(() => {})
    getIntegrationStatus().then(setIntegrationStatus).catch(() => {})
    loadDashboard(cid)
  }, [loadDashboard])

  // Refetch graph when topology changes
  useEffect(() => {
    if (!courseId) return
    const token = localStorage.getItem('docere_token')
    if (!token) return
    const headers = { Authorization: `Bearer ${token}` }
    fetch(`/api/v1/instructor/dashboard/${courseId}/concept-graph?topology=${graphTopology}`, { headers })
      .then(res => res.ok ? res.json() : { nodes: [], edges: [] })
      .then(data => setGraphData(data))
      .catch(() => {})
  }, [courseId, graphTopology])

  // Auto-scroll chat views
  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    metaBottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [metaMessages])

  // Derive student list from graph data for the roster
  const studentNodes = useMemo(() => {
    if (!graphData) return []
    return graphData.nodes
      .filter(n => n.type === 'student')
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [graphData])

  const toggleStudentTag = useCallback((student: TaggedStudent) => {
    setTaggedStudents(prev => {
      const exists = prev.find(s => s.id === student.id)
      if (exists) return prev.filter(s => s.id !== student.id)
      if (prev.length >= 10) return prev
      return [...prev, student]
    })
  }, [])

  const removeStudentTag = useCallback((studentId: string) => {
    setTaggedStudents(prev => prev.filter(s => s.id !== studentId))
  }, [])

  const clearAllTags = useCallback(() => {
    setTaggedStudents([])
  }, [])

  // Graph node click: add tag (if not already) + open chat
  const handleStudentClick = useCallback((id: string, name: string) => {
    setTaggedStudents(prev => {
      if (prev.find(s => s.id === id)) return prev
      if (prev.length >= 10) return prev
      return [...prev, { id, name }]
    })
    setChatOpen(true)
  }, [])

  const handleZoomToStudent = useCallback((studentId: string) => {
    graphRef.current?.zoomToNode(studentId)
  }, [])

  const handleViewClassroom = useCallback(() => {
    graphRef.current?.zoomToFit()
  }, [])

  // Shared send handler that threads through tagged students
  const handleSend = useCallback((q: string) => {
    sendQuestion(q, taggedStudents)
  }, [sendQuestion, taggedStudents])

  // Chat-first view send
  const handleChatSend = () => {
    if (!chatInput.trim() || chatLoading) return
    handleSend(chatInput.trim())
    setChatInput('')
  }

  const handleChatKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleChatSend()
    }
  }

  // Meta chat send
  const handleMetaSend = () => {
    if (!metaInput.trim() || metaLoading) return
    metaSend(metaInput.trim())
    setMetaInput('')
  }

  const handleMetaKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleMetaSend()
    }
  }

  if (loading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[#0a0a0f]">
        <Icons.Logo className="w-12 h-12 animate-pulse" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-[#0a0a0f] text-text-100">
        <div className="text-center p-8">
          <Icons.Logo className="w-10 h-10 mx-auto mb-4 opacity-50" />
          <h1 className="text-xl font-serif text-text-200 mb-2">Dashboard Error</h1>
          <p className="text-sm text-text-400">{error}</p>
        </div>
      </div>
    )
  }

  // ─── Shared sidebar for chat views ──────────────────────────
  const sidebar = (
    <div className={`h-full flex flex-col border-r border-white/5 bg-white/[0.02] transition-all duration-200 shrink-0 ${sidebarOpen ? 'w-[240px]' : 'w-[52px]'}`}>
      {/* Sidebar header */}
      <div className="flex items-center justify-between px-3 py-4 border-b border-white/5">
        {sidebarOpen && (
          <div className="flex items-center gap-2">
            <Icons.Logo className="w-5 h-5 opacity-70" />
            <span className="text-[11px] font-medium text-white/50">Docere</span>
          </div>
        )}
        <button
          onClick={() => setSidebarOpen(p => !p)}
          className={`text-white/25 hover:text-white/50 transition-colors ${sidebarOpen ? '' : 'mx-auto'}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            {sidebarOpen ? (
              <>
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
              </>
            ) : (
              <>
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* Command Center — always at top */}
      <div className="pt-1 pb-1">
        <button
          onClick={switchToMeta}
          className={`w-full text-left transition-all ${sidebarOpen ? 'px-3 py-3' : 'px-2 py-3'} ${
            activeMode === 'meta'
              ? 'bg-white/[0.08] border-l-2 border-[#4488ff]'
              : 'border-l-2 border-transparent hover:bg-white/[0.04]'
          }`}
        >
          {sidebarOpen ? (
            <div className="flex items-center gap-2.5">
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center ${
                activeMode === 'meta' ? 'bg-[#4488ff]/20' : 'bg-white/5'
              }`}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={activeMode === 'meta' ? '#4488ff' : 'rgba(255,255,255,0.35)'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
                </svg>
              </div>
              <div>
                <div className={`text-[13px] font-medium ${activeMode === 'meta' ? 'text-white/90' : 'text-white/50'}`}>
                  Command Center
                </div>
                <div className="text-[10px] text-white/25">All classrooms</div>
              </div>
            </div>
          ) : (
            <div
              className={`w-7 h-7 rounded-lg flex items-center justify-center mx-auto ${
                activeMode === 'meta' ? 'bg-[#4488ff]/20' : 'bg-white/5'
              }`}
              title="Command Center"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={activeMode === 'meta' ? '#4488ff' : 'rgba(255,255,255,0.35)'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
              </svg>
            </div>
          )}
        </button>
      </div>

      {/* Divider */}
      <div className="mx-3 border-t border-white/5" />

      {/* Course list */}
      {sidebarOpen && (
        <div className="px-3 pt-2 pb-1">
          <span className="text-[10px] font-medium text-white/25 uppercase tracking-wider">Courses</span>
        </div>
      )}
      <div className="flex-1 overflow-y-auto py-1">
        {courses.map(course => {
          const isActive = activeMode === 'course' && course.id === courseId
          return (
            <button
              key={course.id}
              onClick={() => switchCourse(course.id)}
              className={`w-full text-left transition-all ${
                sidebarOpen ? 'px-3 py-2.5' : 'px-2 py-2.5'
              } ${
                isActive
                  ? 'bg-white/[0.08] border-l-2 border-[#4488ff]'
                  : 'border-l-2 border-transparent hover:bg-white/[0.04]'
              }`}
              title={course.name}
            >
              {sidebarOpen ? (
                <div>
                  <div className={`text-[13px] truncate ${isActive ? 'text-white/90' : 'text-white/50'}`}>
                    {course.name}
                  </div>
                  {course.course_code && (
                    <div className="text-[10px] text-white/25 truncate">{course.course_code}</div>
                  )}
                </div>
              ) : (
                <div
                  className={`w-7 h-7 rounded-lg flex items-center justify-center text-[11px] font-bold mx-auto ${
                    isActive ? 'bg-[#4488ff]/20 text-[#4488ff]' : 'bg-white/5 text-white/30'
                  }`}
                >
                  {course.name.charAt(0).toUpperCase()}
                </div>
              )}
            </button>
          )
        })}
        {courses.length === 0 && sidebarOpen && (
          <div className="text-[11px] text-white/20 text-center py-6 px-3">
            No courses yet. Add Docere to a course in your LMS to get started.
          </div>
        )}
      </div>
    </div>
  )

  // ─── Meta Command Center view ─────────────────────────────
  if (view === 'chat' && activeMode === 'meta') {
    const pinnedToolData = pinnedTools
      .map(id => TOOL_INTEGRATIONS.find(t => t.id === id))
      .filter((t): t is ToolIntegration => !!t)

    return (
      <div className="h-screen w-screen bg-[#0a0a0f] flex">
        {sidebar}

        <div className="flex-1 flex flex-col min-w-0">
          {/* Top bar */}
          <div className="flex items-center justify-between px-6 py-3.5 border-b border-white/[0.06]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-xl bg-white/[0.04] flex items-center justify-center">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.45)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" />
                </svg>
              </div>
              <div>
                <h1 className="text-[14px] font-medium text-white/85 leading-tight">
                  Command Center
                </h1>
                <p className="text-[10px] text-white/25">
                  {courses.length} course{courses.length !== 1 ? 's' : ''}
                </p>
              </div>
            </div>
            {/* Edit / Save button */}
            {editingDashboard ? (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => {
                    setEditingDashboard(false)
                    setEditDraft([])
                  }}
                  className="px-3 py-1.5 rounded-lg text-[12px] text-white/35 hover:text-white/60 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={() => {
                    setPinnedTools(editDraft)
                    savePinnedTools(editDraft)
                    setEditingDashboard(false)
                  }}
                  className="px-3.5 py-1.5 rounded-lg bg-[#4488ff]/15 text-[#4488ff]/90 text-[12px] font-medium hover:bg-[#4488ff]/25 transition-colors"
                >
                  Save
                </button>
              </div>
            ) : (
              <button
                onClick={() => {
                  setEditDraft([...pinnedTools])
                  setEditingDashboard(true)
                }}
                className="p-2 rounded-lg text-white/20 hover:text-white/50 hover:bg-white/[0.04] transition-all"
                title="Edit integrations"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
              </button>
            )}
          </div>

          {/* Scrollable content area */}
          <div className="flex-1 overflow-y-auto">

            {/* ── Edit mode: tool picker ── */}
            {editingDashboard && (
              <div className="px-6 pt-6 pb-5 border-b border-white/5">
                <div className="max-w-2xl mx-auto">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="text-[10px] font-medium text-white/20 uppercase tracking-wider">Available Integrations</span>
                    <div className="flex-1 h-px bg-white/[0.04]" />
                    <span className="text-[10px] text-white/15">{editDraft.length} selected</span>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                    {TOOL_INTEGRATIONS.map(tool => {
                      const isPinned = editDraft.includes(tool.id)
                      const pinIdx = editDraft.indexOf(tool.id)
                      return (
                        <button
                          key={tool.id}
                          draggable={isPinned}
                          onDragStart={() => { if (isPinned) setDraggedIdx(pinIdx) }}
                          onDragOver={e => { if (isPinned) e.preventDefault() }}
                          onDrop={() => {
                            if (draggedIdx === null || !isPinned) return
                            const targetIdx = editDraft.indexOf(tool.id)
                            if (draggedIdx === targetIdx) return
                            setEditDraft(prev => {
                              const next = [...prev]
                              const [moved] = next.splice(draggedIdx, 1)
                              next.splice(targetIdx, 0, moved)
                              return next
                            })
                            setDraggedIdx(null)
                          }}
                          onDragEnd={() => setDraggedIdx(null)}
                          onClick={() => {
                            if (tool.status === 'coming_soon') return
                            if (isPinned) {
                              setEditDraft(prev => prev.filter(id => id !== tool.id))
                            } else {
                              setEditDraft(prev => [...prev, tool.id])
                            }
                          }}
                          className={`relative flex flex-col items-center text-center p-4 rounded-2xl border transition-all ${
                            isPinned
                              ? 'bg-white/[0.06] border-white/15 cursor-grab active:cursor-grabbing'
                              : 'bg-white/[0.015] border-white/[0.04] hover:bg-white/[0.04] hover:border-white/10'
                          } ${tool.status === 'coming_soon' ? 'opacity-35 cursor-not-allowed' : ''} ${
                            draggedIdx !== null && isPinned && draggedIdx === pinIdx ? 'opacity-30 scale-95' : ''
                          }`}
                        >
                          <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-2.5 transition-all ${
                            isPinned ? 'bg-white/10' : 'bg-white/[0.03]'
                          }`}>
                            {tool.icon}
                          </div>
                          <div className={`text-[12px] font-medium mb-0.5 ${isPinned ? 'text-white/80' : 'text-white/40'}`}>
                            {tool.name}
                          </div>
                          <div className="text-[10px] text-white/20 leading-snug line-clamp-2">{tool.description}</div>
                          {isPinned && (
                            <div className="absolute top-2.5 right-2.5 w-4 h-4 rounded-full bg-[#4488ff]/20 flex items-center justify-center">
                              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#4488ff" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="20 6 9 17 4 12" />
                              </svg>
                            </div>
                          )}
                          {tool.status === 'coming_soon' && (
                            <span className="absolute top-2.5 right-2.5 text-[8px] text-white/20 bg-white/5 px-1.5 py-0.5 rounded-full">Soon</span>
                          )}
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* ── Dashboard: pinned tools ── */}
            {!editingDashboard && pinnedToolData.length > 0 && (
              <div className="px-6 pt-5 pb-3">
                <div className="max-w-2xl mx-auto">
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-[10px] font-medium text-white/20 uppercase tracking-wider">Integrations</span>
                    <div className="flex-1 h-px bg-white/[0.04]" />
                    <button
                      onClick={() => {
                        setEditDraft([...pinnedTools])
                        setEditingDashboard(true)
                      }}
                      className="text-[10px] text-white/20 hover:text-white/50 transition-colors"
                    >
                      Edit
                    </button>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                    {pinnedToolData.map(tool => {
                      const isComingSoon = tool.status === 'coming_soon'
                      const isGoogleTool = ['google_calendar', 'email', 'google_docs', 'google_sheets'].includes(tool.id)
                      const isLmsTool = tool.id === 'lms_push'
                      const isLocalTool = tool.id === 'excel'
                      const connected = isLocalTool
                        ? true
                        : isGoogleTool
                        ? integrationStatus?.google_connected
                        : isLmsTool
                        ? integrationStatus?.lms_connected
                        : false
                      return (
                        <button
                          key={tool.id}
                          onClick={() => !isComingSoon && setActiveToolModal(tool.id)}
                          disabled={isComingSoon}
                          className={`group flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/10 transition-all ${
                            isComingSoon ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'
                          }`}
                        >
                          <div className="w-8 h-8 rounded-lg bg-white/[0.04] group-hover:bg-white/[0.08] flex items-center justify-center transition-all shrink-0">
                            {tool.icon}
                          </div>
                          <div className="text-left min-w-0">
                            <div className="text-[11px] text-white/50 group-hover:text-white/70 font-medium transition-colors leading-tight truncate">{tool.name}</div>
                            <div className="flex items-center gap-1 mt-0.5">
                              {isComingSoon ? (
                                <span className="text-[9px] text-white/15">Coming soon</span>
                              ) : connected ? (
                                <>
                                  <span className="w-1 h-1 rounded-full bg-emerald-500/60 shrink-0" />
                                  <span className="text-[9px] text-white/20">Connected</span>
                                </>
                              ) : (
                                <>
                                  <span className="w-1 h-1 rounded-full bg-amber-500/60 shrink-0" />
                                  <span className="text-[9px] text-white/20">Not connected</span>
                                </>
                              )}
                            </div>
                          </div>
                        </button>
                      )
                    })}
                  </div>
                </div>
              </div>
            )}

            {/* ── Empty dashboard prompt ── */}
            {!editingDashboard && pinnedToolData.length === 0 && (
              <div className="px-6 pt-5 pb-1">
                <div className="max-w-2xl mx-auto">
                  <button
                    onClick={() => {
                      setEditDraft([...pinnedTools])
                      setEditingDashboard(true)
                    }}
                    className="w-full flex items-center justify-center gap-2 py-3 rounded-xl border border-dashed border-white/[0.08] text-white/20 hover:text-white/40 hover:border-white/15 hover:bg-white/[0.02] transition-all text-[12px]"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                    Add integrations to your dashboard
                  </button>
                </div>
              </div>
            )}

            {/* ── Chat area ── */}
            <div className="px-6 py-6">
              <div className="max-w-2xl mx-auto">
                {metaMessages.length === 0 && !metaLoading && (
                  <div className="flex flex-col items-center justify-center py-10 animate-fade-in">
                    <Icons.Logo className="w-12 h-12 mb-4 opacity-60" />
                    <p className="text-[17px] font-serif text-white/80 mb-1">
                      What would you like to know?
                    </p>
                    <p className="text-[13px] text-white/25 mb-8 text-center max-w-sm">
                      I can see across all your classrooms — ask about trends, prep for meetings, or generate reports.
                    </p>

                    <div className="grid grid-cols-2 gap-2.5 w-full max-w-lg">
                      {META_QUICK_ACTIONS.map(action => (
                        <button
                          key={action.label}
                          onClick={() => metaSend(action.prompt)}
                          className="group px-4 py-3 rounded-xl border border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/15 transition-all text-left"
                        >
                          <div className="text-[13px] text-white/50 group-hover:text-white/80 font-medium transition-colors">
                            {action.label}
                          </div>
                          <div className="text-[11px] text-white/15 group-hover:text-white/30 transition-colors mt-0.5 leading-snug">
                            {action.desc}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {metaMessages.map((msg, i) => (
                  <div key={i} className={`mb-5 ${msg.role === 'user' ? 'flex justify-end' : ''}`}>
                    {msg.role === 'user' ? (
                      <div className="max-w-[80%] rounded-2xl rounded-br-md bg-[#4488ff]/15 text-white/90 px-4 py-3 text-[14px] leading-relaxed">
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      </div>
                    ) : (
                      <>
                        <div className="flex gap-3">
                          <div className="w-7 h-7 shrink-0 mt-1">
                            <Icons.Logo className="w-7 h-7 opacity-70" />
                          </div>
                          <div className="max-w-[80%] rounded-2xl rounded-bl-md bg-white/[0.04] text-white/80 px-4 py-3 text-[14px] leading-relaxed">
                            <div className="whitespace-pre-wrap">{msg.content}</div>
                          </div>
                        </div>
                        {msg.actions && msg.actions.length > 0 && (
                          <div className="ml-10 mt-2 space-y-2 max-w-[80%]">
                            {msg.actions.map((action, j) => (
                              <ActionCard key={j} action={action} />
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ))}

                {metaLoading && (
                  <div className="flex gap-3 mb-5">
                    <div className="w-7 h-7 shrink-0 mt-1">
                      <Icons.Logo className="w-7 h-7 opacity-70" />
                    </div>
                    <div className="bg-white/[0.04] rounded-2xl rounded-bl-md px-4 py-3">
                      <div className="flex gap-1">
                        <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={metaBottomRef} />
              </div>
            </div>
          </div>

          {/* Course summary pills */}
          {courseSummaries.length > 0 && metaMessages.length > 0 && (
            <div className="px-6 border-t border-white/[0.04]">
              <div className="max-w-2xl mx-auto flex items-center gap-2 py-2.5 overflow-x-auto">
                <span className="text-[10px] text-white/20 shrink-0">Jump to:</span>
                {courseSummaries.map(cs => (
                  <button
                    key={cs.course_id}
                    onClick={() => switchCourse(cs.course_id)}
                    className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all border bg-white/[0.02] text-white/35 border-white/[0.06] hover:bg-white/[0.06] hover:text-white/70 hover:border-white/15 shrink-0"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-[#4488ff]/40" />
                    {cs.course_name}
                    <span className="text-white/15">{cs.student_count}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Input */}
          <div className="px-6 pb-5 pt-3 border-t border-white/[0.04]">
            <div className="max-w-2xl mx-auto">
              <div className="flex items-end gap-2 bg-white/[0.03] rounded-2xl border border-white/[0.08] hover:border-white/15 focus-within:border-white/15 px-4 py-3 transition-colors">
                <textarea
                  value={metaInput}
                  onChange={e => setMetaInput(e.target.value)}
                  onKeyDown={handleMetaKeyDown}
                  placeholder="Compare classes, prep meetings, generate reports..."
                  rows={1}
                  className="flex-1 bg-transparent text-white/90 text-[14px] placeholder-white/18 resize-none outline-none max-h-[120px]"
                  style={{ minHeight: '28px' }}
                  onInput={e => {
                    const el = e.target as HTMLTextAreaElement
                    el.style.height = '28px'
                    el.style.height = Math.min(el.scrollHeight, 120) + 'px'
                  }}
                />
                <button
                  onClick={handleMetaSend}
                  disabled={!metaInput.trim() || metaLoading}
                  className="text-[#4488ff] hover:text-[#66aaff] disabled:text-white/10 transition-colors mb-0.5"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="22" y1="2" x2="11" y2="13" />
                    <polygon points="22 2 15 22 11 13 2 9 22 2" />
                  </svg>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Tool Modals */}
        {activeToolModal === 'email' && (
          <GmailModal onClose={() => setActiveToolModal(null)} integrationStatus={integrationStatus} courses={courses} />
        )}
        {activeToolModal === 'google_docs' && (
          <GoogleDocsModal onClose={() => setActiveToolModal(null)} integrationStatus={integrationStatus} courses={courses} />
        )}
        {activeToolModal === 'google_sheets' && (
          <GradebookSyncModal onClose={() => setActiveToolModal(null)} source="google_sheets" integrationStatus={integrationStatus} courses={courses} />
        )}
        {activeToolModal === 'excel' && (
          <GradebookSyncModal onClose={() => setActiveToolModal(null)} source="excel" integrationStatus={integrationStatus} courses={courses} />
        )}
        {activeToolModal === 'google_calendar' && (
          <CalendarEventModal onClose={() => setActiveToolModal(null)} integrationStatus={integrationStatus} courses={courses} />
        )}
        {activeToolModal === 'lms_push' && (
          <LMSAnnouncementModal onClose={() => setActiveToolModal(null)} integrationStatus={integrationStatus} courses={courses} />
        )}
      </div>
    )
  }

  // ─── Course chat view ──────────────────────────────────────
  if (view === 'chat') {
    return (
      <div className="h-screen w-screen bg-[#0a0a0f] flex">
        {sidebar}

        {/* ── Main content ── */}
        <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <div>
              <h1 className="text-sm font-serif text-white/90 leading-tight">
                {summary?.course_name}
              </h1>
              <p className="text-[10px] text-white/35">
                {summary?.student_count} students
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setView('settings')}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] hover:border-white/20 transition-all text-[13px] text-white/50 hover:text-white/80"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
                <line x1="16" y1="2" x2="16" y2="6" />
                <line x1="8" y1="2" x2="8" y2="6" />
                <line x1="3" y1="10" x2="21" y2="10" />
              </svg>
              Office Hours
            </button>
            <button
              onClick={() => setView('network')}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] hover:border-white/20 transition-all text-[13px] text-white/50 hover:text-white/80"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="5" r="3" />
                <circle cx="5" cy="19" r="3" />
                <circle cx="19" cy="19" r="3" />
                <line x1="12" y1="8" x2="5" y2="16" />
                <line x1="12" y1="8" x2="19" y2="16" />
              </svg>
              Network
            </button>
          </div>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-6 py-6">
          <div className="max-w-2xl mx-auto">
            {messages.length === 0 && !chatLoading && (
              <div className="flex flex-col items-center justify-center py-16 animate-fade-in">
                <Icons.Logo className="w-14 h-14 mb-5 opacity-70" />
                <p className="text-lg font-serif text-white/80 mb-1">
                  Hi, how can I help?
                </p>
                <p className="text-sm text-white/30 mb-8">
                  Ask me anything about your classroom
                </p>

                {/* Quick action buttons */}
                <div className="flex flex-wrap justify-center gap-2">
                  {QUICK_ACTIONS.map(action => (
                    <button
                      key={action.label}
                      onClick={() => {
                        sendQuestion(action.prompt, taggedStudents)
                      }}
                      className="px-4 py-2.5 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] hover:border-white/20 transition-all text-[13px] text-white/50 hover:text-white/80"
                    >
                      {action.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`mb-5 ${msg.role === 'user' ? 'flex justify-end' : ''}`}>
                {msg.role === 'user' ? (
                  <div className="max-w-[80%] rounded-2xl rounded-br-md bg-[#4488ff]/15 text-white/90 px-4 py-3 text-[14px] leading-relaxed">
                    <div className="whitespace-pre-wrap">{msg.content}</div>
                  </div>
                ) : (
                  <>
                    <div className="flex gap-3">
                      <div className="w-7 h-7 shrink-0 mt-1">
                        <Icons.Logo className="w-7 h-7 opacity-70" />
                      </div>
                      <div className="max-w-[80%] rounded-2xl rounded-bl-md bg-white/[0.04] text-white/80 px-4 py-3 text-[14px] leading-relaxed">
                        <div className="whitespace-pre-wrap">{msg.content}</div>
                      </div>
                    </div>
                    {msg.widgets && msg.widgets.length > 0 && (
                      <div className="ml-10">
                        <InstructorWidgets widgets={msg.widgets} courseId={courseId} />
                      </div>
                    )}
                    {msg.sources && msg.sources.length > 0 && (
                      <SourcesSection sources={msg.sources} />
                    )}
                  </>
                )}
              </div>
            ))}

            {chatLoading && (
              <div className="flex gap-3 mb-5">
                <div className="w-7 h-7 shrink-0 mt-1">
                  <Icons.Logo className="w-7 h-7 opacity-70" />
                </div>
                <div className="bg-white/[0.04] rounded-2xl rounded-bl-md px-4 py-3">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                    <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                    <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                  </div>
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>
        </div>

        {/* Context Tags */}
        {taggedStudents.length > 0 && (
          <div className="px-6">
            <div className="max-w-2xl mx-auto">
              <div className="flex items-center gap-1.5 flex-wrap pb-2">
                {taggedStudents.map(student => (
                  <span
                    key={student.id}
                    className="inline-flex items-center gap-1 bg-[#4488ff]/15 text-[#88bbff] text-[11px] font-medium rounded-md px-2 py-1 border border-[#4488ff]/20"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-[#4488ff]" />
                    {student.name}
                    <button
                      onClick={() => removeStudentTag(student.id)}
                      className="ml-0.5 text-[#4488ff]/50 hover:text-[#4488ff] transition-colors"
                    >
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </span>
                ))}
                {taggedStudents.length > 1 && (
                  <button
                    onClick={clearAllTags}
                    className="text-[10px] text-white/25 hover:text-white/50 transition-colors ml-1"
                  >
                    clear all
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Source filters */}
        <div className="px-6">
          <div className="max-w-2xl mx-auto flex items-center gap-3 pb-2">
            <span className="text-[10px] text-white/25">Sources:</span>
            {([
              { key: 'profiles' as const, label: 'Profiles', desc: 'engagement, confusion, grades' },
              { key: 'mastery' as const, label: 'Concept Mastery', desc: 'per-concept BKT tracking' },
            ]).map(src => {
              const active = sourceFilters[src.key]
              return (
                <button
                  key={src.key}
                  onClick={() => setSourceFilters(prev => ({ ...prev, [src.key]: !prev[src.key] }))}
                  title={src.desc}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[10px] font-medium transition-all border ${
                    active
                      ? 'bg-white/10 text-white/70 border-white/15'
                      : 'bg-transparent text-white/25 border-white/5 line-through'
                  }`}
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${active ? 'bg-[#44ddff]' : 'bg-white/15'}`} />
                  {src.label}
                </button>
              )
            })}
          </div>
        </div>

        {/* Input */}
        <div className="px-6 pb-5 pt-2">
          <div className="max-w-2xl mx-auto">
            <div className="flex items-end gap-2 bg-white/[0.04] rounded-2xl border border-white/10 px-4 py-3">
              <textarea
                ref={chatInputRef}
                value={chatInput}
                onChange={e => setChatInput(e.target.value)}
                onKeyDown={handleChatKeyDown}
                placeholder={
                  taggedStudents.length === 1
                    ? `Ask about ${taggedStudents[0].name}...`
                    : taggedStudents.length > 1
                    ? `Ask about ${taggedStudents.length} students...`
                    : 'Ask about your students, their struggles, or class patterns...'
                }
                rows={1}
                className="flex-1 bg-transparent text-white/90 text-[14px] placeholder-white/20 resize-none outline-none max-h-[120px]"
                style={{ minHeight: '28px' }}
                onInput={e => {
                  const el = e.target as HTMLTextAreaElement
                  el.style.height = '28px'
                  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
                }}
              />
              <button
                onClick={handleChatSend}
                disabled={!chatInput.trim() || chatLoading}
                className="text-[#4488ff] hover:text-[#66aaff] disabled:text-white/10 transition-colors mb-0.5"
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" />
                  <polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </button>
            </div>
          </div>
        </div>
        </div>{/* close main content */}
      </div>
    )
  }

  // ─── Settings view (calendar + office hours) ────────────────
  if (view === 'settings') {
    return (
      <div className="h-screen w-screen bg-[#0a0a0f] flex flex-col">
        {/* Top bar */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-white/5">
          <div className="flex items-center gap-3">
            <Icons.Logo className="w-7 h-7 opacity-80" />
            <div>
              <h1 className="text-sm font-serif text-white/90 leading-tight">
                Meeting Setup
              </h1>
              <p className="text-[10px] text-white/35">
                Calendar integration & office hours
              </p>
            </div>
          </div>
          <button
            onClick={() => setView('chat')}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl border border-white/10 bg-white/[0.03] hover:bg-white/[0.07] hover:border-white/20 transition-all text-[13px] text-white/50 hover:text-white/80"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="19" y1="12" x2="5" y2="12" />
              <polyline points="12 19 5 12 12 5" />
            </svg>
            Back to Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-8">
          <div className="max-w-lg mx-auto">
            <CalendarSetup courseId={courseId} />
          </div>
        </div>
      </div>
    )
  }

  // ─── Network view (existing dashboard) ─────────────────────
  return (
    <div ref={containerRef} className="h-screen w-screen overflow-hidden bg-[#0a0a0f] relative">
      {/* Graph fills entire screen */}
      {graphData && (
        <ConceptGraph3D
          ref={graphRef}
          nodes={graphData.nodes}
          edges={graphData.edges}
          width={size.width}
          height={size.height}
          filter={graphFilter}
          topology={graphTopology}
          onStudentClick={handleStudentClick}
        />
      )}

      {/* Floating header overlay -- top left */}
      <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
        <button
          onClick={() => setView('chat')}
          className="flex items-center gap-1.5 bg-black/60 backdrop-blur-md rounded-xl px-3 py-2.5 border border-white/10 hover:border-white/25 hover:bg-black/70 transition-all text-[11px] text-white/40 hover:text-white/70"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Chat
        </button>
        <button
          onClick={() => setChatOpen(prev => !prev)}
          className="flex items-center gap-2.5 bg-black/60 backdrop-blur-md rounded-xl px-4 py-2.5 border border-white/10 hover:border-white/25 hover:bg-black/70 transition-all cursor-pointer group"
        >
          <Icons.Logo className="w-6 h-6 opacity-80" />
          <div className="text-left">
            <h1 className="text-sm font-serif text-white/90 leading-tight">
              {summary?.course_name}
            </h1>
            <p className="text-[10px] text-white/40 group-hover:text-white/50 transition-colors">
              {chatOpen ? 'Close chat' : 'Click to query students'}
            </p>
          </div>
          <svg
            className={`w-3.5 h-3.5 text-white/30 ml-1 transition-transform ${chatOpen ? 'rotate-180' : ''}`}
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path fillRule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>
      </div>

      {/* Chat dropdown */}
      <InstructorChat
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
        taggedStudents={taggedStudents}
        onRemoveTag={removeStudentTag}
        onClearAllTags={clearAllTags}
        messages={messages}
        loading={chatLoading}
        onSend={handleSend}
        courseId={courseId}
      />

      {/* Floating controls -- shifted left to make room for roster */}
      <div className="absolute top-4 right-[280px] z-10 flex flex-col gap-2 items-end">
        {/* Topology toggle */}
        <div className="bg-black/60 backdrop-blur-md rounded-xl px-2 py-1.5 border border-white/10 flex items-center gap-1">
          {([
            { key: 'student', label: 'Student-Centric', icon: '●' },
            { key: 'concept', label: 'Concept-Centric', icon: '◆' },
            { key: 'distributed', label: 'Distributed', icon: '⬡' },
          ] as const).map(t => {
            const active = graphTopology === t.key
            return (
              <button
                key={t.key}
                onClick={() => {
                  setGraphTopology(t.key)
                  // Reset filter when switching topology
                  setGraphFilter('all')
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                  active
                    ? 'bg-white/15 text-white/90'
                    : 'text-white/35 hover:text-white/70 hover:bg-white/5'
                }`}
              >
                <span className={active ? 'opacity-100' : 'opacity-40'}>{t.icon}</span>
                {t.label}
              </button>
            )
          })}
        </div>

        {/* Node filter — only for student/distributed topology (concept topology has no memory nodes) */}
        {graphTopology !== 'concept' && (
          <div className="bg-black/60 backdrop-blur-md rounded-xl px-2 py-1.5 border border-white/10 flex items-center gap-1">
            {([
              { key: 'all', label: 'All', color: '#ffffff' },
              { key: 'students', label: 'Students', color: '#8888ff' },
              { key: 'insight', label: 'Insights', color: '#44ddff' },
              { key: 'question', label: 'Questions', color: '#ffd700' },
              { key: 'struggle', label: 'Struggles', color: '#ff6b6b' },
              { key: 'breakthrough', label: 'Breakthroughs', color: '#44ff88' },
            ] as const).map(f => {
              const active = graphFilter === f.key
              return (
                <button
                  key={f.key}
                  onClick={() => setGraphFilter(f.key)}
                  className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[10px] font-medium transition-all ${
                    active
                      ? 'bg-white/15 text-white/90'
                      : 'text-white/40 hover:text-white/70 hover:bg-white/5'
                  }`}
                >
                  <span
                    className={`inline-block rounded-full ${f.key === 'students' || f.key === 'all' ? 'w-2.5 h-2.5' : 'w-2 h-2'}`}
                    style={{ backgroundColor: active ? f.color : `${f.color}66` }}
                  />
                  {f.label}
                </button>
              )
            })}
          </div>
        )}
      </div>

      {/* Student Roster -- right side */}
      <StudentRoster
        students={studentNodes}
        taggedStudents={taggedStudents}
        onToggleTag={toggleStudentTag}
        onZoomToStudent={handleZoomToStudent}
        onViewClassroom={handleViewClassroom}
      />
    </div>
  )
}
