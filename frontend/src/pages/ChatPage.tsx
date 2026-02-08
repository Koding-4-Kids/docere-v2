import { useState, useRef, useEffect } from 'react'
import { Sidebar } from '../components/Sidebar'
import { CourseSelector } from '../components/CourseSelector'
import { ClaudeChatInput, Icons } from '../components/ClaudeChatInput'
import { MessageBubble } from '../components/MessageBubble'
import { useTheme } from '../hooks/useTheme'
import { useAuth } from '../AuthContext'
import { Pencil, BookOpen, Code, Lightbulb } from 'lucide-react'
import * as api from '../api'

interface LocalMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
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

// Temporary mock courses until the courses API is wired up
const FALLBACK_COURSES: Course[] = [
  { id: '1', name: 'Calculus I', courseCode: 'MATH 121' },
  { id: '2', name: 'Intro to Computer Science', courseCode: 'CS 101' },
  { id: '3', name: 'Organic Chemistry', courseCode: 'CHEM 251' },
]

export function ChatPage() {
  const { dark, toggle } = useTheme()
  const { user, logout } = useAuth()
  const [conversations, setConversations] = useState<LocalConversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null)
  const [courses] = useState<Course[]>(FALLBACK_COURSES)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const activeConv = conversations.find(c => c.id === activeConvId)

  // Load existing conversations on mount
  useEffect(() => {
    api.listConversations().then(serverConvs => {
      const mapped: LocalConversation[] = serverConvs.map(c => ({
        id: c.id,
        title: c.title || 'New conversation',
        courseId: c.course_id,
        courseName: courses.find(cr => cr.id === c.course_id)?.name || 'Course',
        lastMessageAt: c.last_message_at,
        messages: [],
      }))
      setConversations(mapped)
    }).catch(() => {
      // Backend might not be running — that's OK for dev
    })
  }, [courses])

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
                  })),
                }
              : c
          )
        )
      }).catch(() => {})
    }
  }, [activeConvId, conversations])

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeConv?.messages.length])

  const handleNewConversation = () => {
    setActiveConvId(null)
    setSelectedCourseId(null)
    setError(null)
  }

  const handleSelectCourse = (courseId: string) => {
    setSelectedCourseId(courseId)
  }

  const handleSendMessage = async (content: string, _files?: File[]) => {
    if (!selectedCourseId && !activeConv) return
    setError(null)

    const courseId = activeConv?.courseId || selectedCourseId!
    const course = courses.find(c => c.id === courseId)

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

        // Send message to the new conversation
        setIsLoading(true)
        const response = await api.sendMessage(serverConv.id, content)

        setConversations(prev =>
          prev.map(c =>
            c.id === serverConv.id
              ? {
                  ...c,
                  messages: [
                    ...c.messages,
                    { id: response.message.id, role: 'assistant', content: response.message.content },
                  ],
                }
              : c
          )
        )
        setIsLoading(false)
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

      setConversations(prev =>
        prev.map(c =>
          c.id === activeConvId
            ? {
                ...c,
                messages: [
                  ...c.messages,
                  { id: response.message.id, role: 'assistant', content: response.message.content },
                ],
              }
            : c
        )
      )
      setIsLoading(false)
    } catch (err) {
      setIsLoading(false)
      setError(err instanceof Error ? err.message : 'Failed to send message')
    }
  }

  // Determine what to show in the main area
  const showCourseSelector = !activeConvId && !selectedCourseId
  const showEmptyChat = !activeConvId && selectedCourseId
  const showChat = !!activeConvId

  return (
    <div className="flex h-screen bg-bg-0 text-text-100">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations.map(c => ({
          id: c.id,
          title: c.title,
          courseName: c.courseName,
          lastMessageAt: c.lastMessageAt,
        }))}
        activeId={activeConvId}
        onSelect={setActiveConvId}
        onNew={handleNewConversation}
        onLogout={logout}
        userEmail={user?.email || ''}
        dark={dark}
        toggleTheme={toggle}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Error banner */}
        {error && (
          <div className="px-6 py-2 bg-red-500/10 border-b border-red-500/20 text-red-600 text-sm flex items-center justify-between">
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
          <div className="flex-1 flex flex-col">
            <div className="flex-1 flex items-center justify-center">
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
              </div>
            </div>
            <div className="pb-4">
              <ClaudeChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
            </div>
          </div>
        )}

        {/* Active conversation */}
        {showChat && activeConv && (
          <div className="flex-1 flex flex-col">
            {/* Header */}
            <div className="px-6 py-3 border-b border-bg-300 flex items-center gap-2">
              <span className="text-xs font-medium text-accent bg-accent/10 px-2 py-0.5 rounded-full">
                {activeConv.courseName}
              </span>
              <span className="text-sm text-text-300 truncate">{activeConv.title}</span>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto custom-scrollbar px-6 py-4">
              <div className="max-w-2xl mx-auto">
                {activeConv.messages.map(msg => (
                  <MessageBubble key={msg.id} role={msg.role} content={msg.content} />
                ))}
                {isLoading && (
                  <div className="flex justify-start gap-2 mb-4">
                    <div className="w-6 h-6 shrink-0 mt-1">
                      <Icons.Logo className="w-6 h-6" />
                    </div>
                    <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-bg-200 text-text-400 text-sm">
                      <span className="inline-flex gap-1">
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
            <div className="pb-4">
              <ClaudeChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
