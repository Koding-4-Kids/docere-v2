import { useState, useRef, useEffect } from 'react'
import { Sidebar } from '../components/Sidebar'
import { CourseSelector } from '../components/CourseSelector'
import { ClaudeChatInput, Icons } from '../components/ClaudeChatInput'
import { MessageBubble } from '../components/MessageBubble'
import { useTheme } from '../hooks/useTheme'
import { Pencil, BookOpen, Code, Lightbulb } from 'lucide-react'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

interface Conversation {
  id: string
  title: string
  courseId: string
  courseName: string
  lastMessageAt: string
  messages: Message[]
}

// Mock data - replace with API calls
const MOCK_COURSES = [
  { id: '1', name: 'Calculus I', courseCode: 'MATH 121' },
  { id: '2', name: 'Intro to Computer Science', courseCode: 'CS 101' },
  { id: '3', name: 'Organic Chemistry', courseCode: 'CHEM 251' },
]

const QUICK_ACTIONS = [
  { label: 'Write', icon: Pencil, prompt: 'Help me write ' },
  { label: 'Learn', icon: BookOpen, prompt: 'Explain the concept of ' },
  { label: 'Code', icon: Code, prompt: 'Help me code ' },
  { label: 'Study', icon: Lightbulb, prompt: 'Help me study for ' },
]

export function ChatPage() {
  const { dark, toggle } = useTheme()
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [selectedCourseId, setSelectedCourseId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const activeConv = conversations.find(c => c.id === activeConvId)

  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [activeConv?.messages.length])

  const handleNewConversation = () => {
    setActiveConvId(null)
    setSelectedCourseId(null)
  }

  const handleSelectCourse = (courseId: string) => {
    setSelectedCourseId(courseId)
  }

  const handleSendMessage = async (content: string, _files?: File[]) => {
    if (!selectedCourseId && !activeConv) return

    const courseId = activeConv?.courseId || selectedCourseId!
    const course = MOCK_COURSES.find(c => c.id === courseId)

    // If no active conversation, create one
    if (!activeConvId) {
      const newConv: Conversation = {
        id: crypto.randomUUID(),
        title: content.slice(0, 50),
        courseId,
        courseName: course?.name || 'Unknown',
        lastMessageAt: new Date().toISOString(),
        messages: [],
      }
      setConversations(prev => [newConv, ...prev])
      setActiveConvId(newConv.id)

      // Add user message
      const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content }
      newConv.messages.push(userMsg)
      setConversations(prev => prev.map(c => c.id === newConv.id ? { ...newConv } : c))

      // Simulate AI response
      await simulateResponse(newConv.id, content)
      return
    }

    // Add to existing conversation
    const userMsg: Message = { id: crypto.randomUUID(), role: 'user', content }
    setConversations(prev =>
      prev.map(c =>
        c.id === activeConvId
          ? { ...c, messages: [...c.messages, userMsg], lastMessageAt: new Date().toISOString() }
          : c
      )
    )

    await simulateResponse(activeConvId, content)
  }

  const simulateResponse = async (convId: string, _userMessage: string) => {
    setIsLoading(true)

    // TODO: Replace with actual API call to POST /api/v1/chat/conversations/{id}/messages
    await new Promise(resolve => setTimeout(resolve, 1200))

    const assistantMsg: Message = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: "I'm Docere, your AI tutor. I can see your course materials and remember our past conversations. What would you like help with?",
    }

    setConversations(prev =>
      prev.map(c =>
        c.id === convId
          ? { ...c, messages: [...c.messages, assistantMsg] }
          : c
      )
    )
    setIsLoading(false)
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
        dark={dark}
        toggleTheme={toggle}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Course selector (new conversation, no course picked) */}
        {showCourseSelector && (
          <CourseSelector
            courses={MOCK_COURSES}
            userName="Youdahe"
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
                  {MOCK_COURSES.find(c => c.id === selectedCourseId)?.name}
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
