import { useState, useRef, useEffect } from 'react'
import { Sidebar } from '../components/Sidebar'
import { FlashcardReview } from '../components/FlashcardReview'
import { FocusPage } from './FocusPage'
import { useFlashcardDueCounts } from '../hooks/useFlashcardDueCounts'
import { CourseSelector } from '../components/CourseSelector'
import { ClaudeChatInput, Icons } from '../components/ClaudeChatInput'
import { MessageBubble } from '../components/MessageBubble'
import { StudyPanel } from '../components/StudyPanel'
import { useTheme } from '../hooks/useTheme'
import { useAuth } from '../AuthContext'
import { Pencil, BookOpen, Code, Lightbulb, FileText, Menu, Sun, Moon } from 'lucide-react'
import { MeetingScheduler } from '../components/MeetingScheduler'
import * as api from '../api'
import type { StudyArtifact, MeetingAction, Widget } from '../api'

interface LocalMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  artifact?: StudyArtifact | null
  action?: MeetingAction | null
  widgets?: Widget[] | null
}

interface LocalConversation {
  id: string
  title: string
  courseId: string
  courseName: string
  lastMessageAt: string
  messages: LocalMessage[]
}

interface Course {
  id: string
  name: string
  courseCode: string
}

const QUICK_ACTIONS = [
  { label: 'Write', icon: Pencil, prompt: 'Help me write ' },
  { label: 'Learn', icon: BookOpen, prompt: 'Explain the concept of ' },
  { label: 'Code', icon: Code, prompt: 'Help me code ' },
  { label: 'Study', icon: Lightbulb, prompt: 'Help me study for ' },
]

// Keywords that hint the student wants study materials
const STUDY_KEYWORDS = /\b(flashcard|flash card|study guide|study notes|make me notes|create notes|make me slides|create slides|make me flashcards|create flashcards|generate notes|generate flashcards|generate slides|generate a study guide|study material)\b/i

export function ChatPage() {
  const { dark, themeMode, setThemeMode, toggle } = useTheme()
  const { user, logout } = useAuth()
  const [conversations, setConversations] = useState<LocalConversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [assignments, setAssignments] = useState<api.AssignmentSummary[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const shouldAutoScroll = useRef(true)

  // Study panel state
  const [activeArtifact, setActiveArtifact] = useState<StudyArtifact | null>(null)
  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [isGeneratingArtifact, setIsGeneratingArtifact] = useState(false)

  // Meeting scheduler state
  const [isMeetingPanelOpen, setIsMeetingPanelOpen] = useState(false)
  const [meetingAction, setMeetingAction] = useState<MeetingAction | null>(null)

  // Flashcard review state
  const [isReviewMode, setIsReviewMode] = useState(false)

  // Focus mode state
  const [isFocusMode, setIsFocusMode] = useState(false)
  const dueCounts = useFlashcardDueCounts()

  const activeConv = conversations.find(c => c.id === activeConvId)

  // Load courses and conversations on mount
  useEffect(() => {
    api.listCourses().then(serverCourses => {
      const mapped = serverCourses.map(c => ({
        id: c.id,
        name: c.name,
        courseCode: c.course_code || '',
      }))
      setCourses(mapped)
      return mapped
    }).then(loadedCourses => {
      return api.listConversations().then(serverConvs => {
        const mapped: LocalConversation[] = serverConvs.map(c => ({
          id: c.id,
          title: c.title || 'New conversation',
          courseId: c.course_id,
          courseName: loadedCourses.find(cr => cr.id === c.course_id)?.name || 'Course',
          lastMessageAt: c.last_message_at,
          messages: [],
        }))
        setConversations(mapped)
      })
    }).catch(() => {})
  }, [])

  // Load messages when selecting a conversation that has none loaded
  useEffect(() => {
    if (!activeConvId) return
    const conv = conversations.find(c => c.id === activeConvId)
    if (conv && conv.messages.length === 0) {
      api.getConversation(activeConvId).then(detail => {
        setConversations(prev =>
          prev.map(c =>
            c.id === activeConvId
              ? {
                  ...c,
                  messages: detail.messages.map(m => ({
                    id: m.id,
                    role: m.role as 'user' | 'assistant',
                    content: m.content,
                    artifact: m.artifact || null,
                    action: m.action || null,
                    widgets: m.widgets || null,
                  })),
                }
              : c
          )
        )
      }).catch(() => {})
    }
  }, [activeConvId, conversations])

  // Track whether user has scrolled up
  const handleMessagesScroll = () => {
    const container = messagesContainerRef.current
    if (!container) return
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    shouldAutoScroll.current = distanceFromBottom < 100
  }

  // Scroll to bottom on new messages or when loading indicator appears
  useEffect(() => {
    if (!shouldAutoScroll.current) return
    const timer = setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, 50)
    return () => clearTimeout(timer)
  }, [activeConv?.messages.length, isLoading])

  // Always scroll to bottom when switching conversations
  useEffect(() => {
    shouldAutoScroll.current = true
    const timer = setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' })
    }, 50)
    return () => clearTimeout(timer)
  }, [activeConvId])

  const handleNewConversation = () => {
    setActiveConvId(null)
    setSelectedCourseId(null)
    setError(null)
    closePanel()
  }

  const handleSelectCourse = (courseId: string) => {
    setSelectedCourseId(courseId)
    api.listAssignments(courseId).then(setAssignments).catch(() => setAssignments([]))
  }

  const handleDeleteConversation = async (convId: string) => {
    try {
      await api.deleteConversation(convId)
      setConversations(prev => prev.filter(c => c.id !== convId))
      if (activeConvId === convId) {
        setActiveConvId(null)
        setSelectedCourseId(null)
        closePanel()
      }
    } catch {
      setError('Failed to delete conversation')
    }
  }

  const openArtifact = (artifact: StudyArtifact) => {
    setActiveArtifact(artifact)
    setIsPanelOpen(true)
    setIsGeneratingArtifact(false)
  }

  const closePanel = () => {
    setIsPanelOpen(false)
    setIsGeneratingArtifact(false)
    // Keep activeArtifact so re-open doesn't flash
  }

  const openMeetingScheduler = (action?: MeetingAction | null) => {
    // Close study panel if open — only one panel at a time
    closePanel()
    setMeetingAction(action || null)
    setIsMeetingPanelOpen(true)
  }

  const closeMeetingPanel = () => {
    setIsMeetingPanelOpen(false)
  }

  const handleSendMessage = async (content: string, _files?: File[]) => {
    if (!selectedCourseId && !activeConv) return
    setError(null)
    shouldAutoScroll.current = true

    const courseId = activeConv?.courseId || selectedCourseId!
    const course = courses.find(c => c.id === courseId)

    // Detect study intent — optimistically open panel
    const isStudyRequest = STUDY_KEYWORDS.test(content)
    if (isStudyRequest) {
      setActiveArtifact(null)
      setIsGeneratingArtifact(true)
      setIsPanelOpen(true)
    }

    try {
      // If no active conversation, create one via API
      if (!activeConvId) {
        const serverConv = await api.createConversation(courseId, content.slice(0, 50))

        const newConv: LocalConversation = {
          id: serverConv.id,
          title: content.slice(0, 50),
          courseId,
          courseName: course?.name || 'Course',
          lastMessageAt: new Date().toISOString(),
          messages: [{ id: crypto.randomUUID(), role: 'user', content }],
        }
        setConversations(prev => [newConv, ...prev])
        setActiveConvId(serverConv.id)

        setIsLoading(true)
        const response = await api.sendMessage(serverConv.id, content)
        const artifact = response.message.artifact || null
        const action = response.message.action || null
        const widgets = response.message.widgets || null

        setConversations(prev =>
          prev.map(c =>
            c.id === serverConv.id
              ? {
                  ...c,
                  messages: [
                    ...c.messages,
                    { id: response.message.id, role: 'assistant', content: response.message.content, artifact, action, widgets },
                  ],
                }
              : c
          )
        )
        setIsLoading(false)

        // Handle artifact result
        if (artifact) {
          openArtifact(artifact)
        } else if (isStudyRequest) {
          closePanel()
        }
        return
      }

      // Add user message to existing conversation immediately (optimistic)
      const tempUserMsg: LocalMessage = { id: crypto.randomUUID(), role: 'user', content }
      setConversations(prev =>
        prev.map(c =>
          c.id === activeConvId
            ? { ...c, messages: [...c.messages, tempUserMsg], lastMessageAt: new Date().toISOString() }
            : c
        )
      )

      // Send to API and get AI response
      setIsLoading(true)
      const response = await api.sendMessage(activeConvId, content)
      const artifact = response.message.artifact || null
      const action = response.message.action || null
      const widgets = response.message.widgets || null

      setConversations(prev =>
        prev.map(c =>
          c.id === activeConvId
            ? {
                ...c,
                messages: [
                  ...c.messages,
                  { id: response.message.id, role: 'assistant', content: response.message.content, artifact, action, widgets },
                ],
              }
            : c
        )
      )
      setIsLoading(false)

      // Handle artifact result
      if (artifact) {
        openArtifact(artifact)
      } else if (isStudyRequest) {
        closePanel()
      }
    } catch (err) {
      setIsLoading(false)
      setIsGeneratingArtifact(false)
      if (isStudyRequest) closePanel()
      setError(err instanceof Error ? err.message : 'Failed to send message')
    }
  }

  // Flashcard helpers
  const totalDueCards = Array.from(dueCounts.values()).reduce((a, b) => a + b, 0)
  const reviewCourseId = activeConv?.courseId || selectedCourseId || (courses.length > 0 ? courses[0].id : null)

  // Determine what to show in the main area
  const showCourseSelector = !activeConvId && !selectedCourseId
  const showEmptyChat = !activeConvId && selectedCourseId
  const showChat = !!activeConvId

  return (
    <div className="flex h-screen bg-bg-0 text-text-100 relative overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations.map(c => ({
          id: c.id,
          title: c.title,
          courseName: c.courseName,
          lastMessageAt: c.lastMessageAt,
        }))}
        activeId={activeConvId}
        onSelect={(id) => {
          setActiveConvId(id)
          setSidebarOpen(false)
        }}
        onNew={() => {
          handleNewConversation()
          setSidebarOpen(false)
        }}
        onDelete={handleDeleteConversation}
        onLogout={logout}
        userName={user?.name || user?.email || 'Student'}
        userEmail={user?.email || ''}
        dark={dark}
        toggleTheme={toggle}
        onOpenFlashcards={() => reviewCourseId && setIsReviewMode(true)}
        flashcardDueCount={totalDueCards}
        onOpenFocus={() => setIsFocusMode(true)}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {/* Top bar: hamburger (mobile only) + logo + theme */}
        <header className="flex h-14 shrink-0 items-center gap-3 px-4 border-b border-bg-300 bg-bg-100 z-30">
          <button
            type="button"
            onClick={() => setSidebarOpen(true)}
            className="min-w-[44px] min-h-[44px] flex items-center justify-center -m-2 rounded-lg text-text-400 hover:text-text-200 hover:bg-bg-200 transition-colors md:hidden"
            aria-label="Open menu"
            aria-expanded={sidebarOpen}
          >
            <Menu className="w-6 h-6" />
          </button>
          <img src="/docere-logo.png" alt="Docere" className="h-7 object-contain flex-1 min-w-0" />
          <button
            type="button"
            onClick={toggle}
            className="min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg text-text-400 hover:text-text-200 hover:bg-bg-200 transition-colors"
            aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          >
            {dark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
          </button>
        </header>

        {/* Error banner */}
        {error && (
          <div className="px-4 md:px-6 py-2 bg-red-500/10 border-b border-red-500/20 text-red-600 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-4">
              Dismiss
            </button>
          </div>
        )}

        {/* Course selector (new conversation, no course picked) */}
        {showCourseSelector && (
          <CourseSelector
            courses={courses}
            userName={user?.name || 'Student'}
            onSelect={handleSelectCourse}
          />
        )}

        {/* Empty chat (course selected, ready to type) */}
        {showEmptyChat && (
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex-1 overflow-y-auto custom-scrollbar">
              <div className="flex flex-col items-center justify-center min-h-full py-8">
                <div className="text-center animate-fade-in">
                  <Icons.Logo className="w-12 h-12 mx-auto mb-4" />
                  <p className="text-xl font-serif text-text-200 mb-1">
                    {courses.find(c => c.id === selectedCourseId)?.name}
                  </p>
                  <p className="text-sm text-text-400">Ask me anything about this course</p>

                  {/* Quick Action Buttons */}
                  <div className="flex flex-wrap justify-center gap-2 mt-6">
                    {QUICK_ACTIONS.map(action => (
                      <button
                        key={action.label}
                        onClick={() => handleSendMessage(action.prompt)}
                        className="flex items-center gap-2 px-4 py-2 rounded-xl border border-bg-300 bg-bg-0 hover:bg-bg-200 hover:border-accent/40 transition-all text-sm text-text-300 hover:text-text-200 group"
                      >
                        <action.icon className="w-4 h-4 text-text-400 group-hover:text-accent transition-colors" />
                        {action.label}
                      </button>
                    ))}
                  </div>

                  {/* Assignments Section */}
                  {assignments.length > 0 && (
                    <div className="mt-8 w-full max-w-md mx-auto text-left">
                      <p className="text-xs uppercase tracking-wider text-text-500 mb-2 px-1">Assignments</p>
                      <div className="space-y-1.5">
                        {assignments.map(a => (
                          <button
                            key={a.id}
                            onClick={() => handleSendMessage(`Help me with the assignment: ${a.title}`)}
                            className="w-full flex items-center gap-3 px-4 py-3 rounded-xl border border-bg-300 bg-bg-0 hover:bg-bg-200 hover:border-accent/40 transition-all text-left group"
                          >
                            <FileText className="w-4 h-4 text-text-400 group-hover:text-accent transition-colors shrink-0" />
                            <span className="text-sm text-text-300 group-hover:text-text-200 truncate">
                              {a.title}
                            </span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
            <div className="pb-4 px-4 md:px-6">
              <ClaudeChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
            </div>
          </div>
        )}

        {/* Active conversation */}
        {showChat && activeConv && (
          <div className="flex-1 flex flex-col min-h-0">
            {/* Header */}
            <div className="px-4 md:px-6 py-3 border-b border-bg-300 flex items-center gap-2">
              <span className="text-xs font-medium text-accent bg-accent/10 px-2 py-0.5 rounded-full">
                {activeConv.courseName}
              </span>
              <span className="text-sm text-text-300 truncate">{activeConv.title}</span>
            </div>

            {/* Messages */}
            <div ref={messagesContainerRef} onScroll={handleMessagesScroll} className="flex-1 overflow-y-auto custom-scrollbar px-4 md:px-6 py-4">
              <div className="max-w-2xl mx-auto">
                {activeConv.messages.map(msg => (
                  <MessageBubble
                    key={msg.id}
                    role={msg.role}
                    content={msg.content}
                    artifact={msg.artifact}
                    action={msg.action}
                    widgets={msg.widgets}
                    onOpenArtifact={openArtifact}
                    onOpenMeetingScheduler={() => openMeetingScheduler(msg.action)}
                  />
                ))}
                {isLoading && (
                  <div className="flex justify-start gap-2 mb-4">
                    <div className="w-6 h-6 shrink-0 mt-1">
                      <Icons.Logo className="w-6 h-6" />
                    </div>
                    <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-bg-200 text-sm">
                      <span className="text-text-300 mr-1.5">
                        {isGeneratingArtifact ? 'Docere is thinking' : 'Thinking'}
                      </span>
                      <span className="inline-flex gap-0.5 text-text-400">
                        <span className="animate-bounce" style={{ animationDelay: '0ms' }}>.</span>
                        <span className="animate-bounce" style={{ animationDelay: '150ms' }}>.</span>
                        <span className="animate-bounce" style={{ animationDelay: '300ms' }}>.</span>
                      </span>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>

            {/* Input */}
            <div className="pb-4 px-4 md:px-6">
              <ClaudeChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
            </div>
          </div>
        )}
      </div>

      {/* Study Materials Panel */}
      {isPanelOpen && (
        <StudyPanel
          artifact={activeArtifact}
          isGenerating={isGeneratingArtifact}
          onClose={closePanel}
        />
      )}

      {/* Meeting Scheduler Panel */}
      {isMeetingPanelOpen && activeConv && (
        <MeetingScheduler
          courseId={activeConv.courseId}
          conversationId={activeConvId}
          action={meetingAction}
          onClose={closeMeetingPanel}
          onBooked={closeMeetingPanel}
        />
      )}

      {/* Flashcard Review Overlay */}
      {isReviewMode && reviewCourseId && (
        <FlashcardReview
          courseId={reviewCourseId}
          onClose={() => setIsReviewMode(false)}
        />
      )}

      {/* Focus Mode Overlay */}
      {isFocusMode && (
        <FocusPage onClose={() => setIsFocusMode(false)} />
      )}
    </div>
  )
}
