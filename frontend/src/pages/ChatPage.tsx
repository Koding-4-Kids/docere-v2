import { useState, useRef, useEffect } from 'react'
import { Sidebar } from '../components/Sidebar'
import { FocusPage } from './FocusPage'
import { ClaudeChatInput, Icons } from '../components/ClaudeChatInput'
import { MessageBubble } from '../components/MessageBubble'
import { StudyPanel } from '../components/StudyPanel'
import { useTheme } from '../hooks/useTheme'
import { useAuth } from '../AuthContext'
import { MeetingScheduler } from '../components/MeetingScheduler'
import { NotesEditor } from '../components/NotesEditor'
import * as api from '../api'
import type { StudyArtifact, MeetingAction, Widget, StreamDoneMeta } from '../api'

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
  { label: 'Explain a concept', desc: 'Break down ideas step by step', prompt: 'Explain the concept of ' },
  { label: 'Help me study', desc: 'Flashcards, guides, and quizzes', prompt: 'Help me study for ' },
  { label: 'Review my work', desc: 'Get feedback on assignments', prompt: 'Can you review my work on ' },
  { label: 'Practice problems', desc: 'Generate practice questions', prompt: 'Give me practice problems for ' },
]

// Keywords that hint the student wants notes (routes to notes panel)
// Keywords that hint the student wants study materials (artifact will route to correct panel)
const STUDY_KEYWORDS = /\b(flashcard|flash card|study guide|make me slides|create slides|make me flashcards|create flashcards|generate flashcards|generate slides|generate a study guide|study material)\b/i

export function ChatPage() {
  const { dark, toggle } = useTheme()
  const { user, logout } = useAuth()
  const [conversations, setConversations] = useState<LocalConversation[]>([])
  const [activeConvId, setActiveConvId] = useState<string | null>(null)
  const [activeCourseId, setActiveCourseId] = useState<string | null>(null)
  const [courses, setCourses] = useState<Course[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const shouldAutoScroll = useRef(true)
  const artifactStreamedNotes = useRef(false)

  // Study panel state
  const [activeArtifact, setActiveArtifact] = useState<StudyArtifact | null>(null)
  const [isPanelOpen, setIsPanelOpen] = useState(false)
  const [isGeneratingArtifact, setIsGeneratingArtifact] = useState(false)

  // Meeting scheduler state
  const [isMeetingPanelOpen, setIsMeetingPanelOpen] = useState(false)
  const [meetingAction, setMeetingAction] = useState<MeetingAction | null>(null)

  // Focus mode state
  const [isFocusMode, setIsFocusMode] = useState(false)

  // Notes editor state
  const [isNotesOpen, setIsNotesOpen] = useState(false)
  const [notesContent, setNotesContent] = useState('')
  const [isAgentWritingNotes, setIsAgentWritingNotes] = useState(false)
  const [agentWrittenSection, setAgentWrittenSection] = useState<string | null>(null)
  const [isNotesExpanded, setIsNotesExpanded] = useState(false)

  const activeConv = conversations.find(c => c.id === activeConvId)

  // Load/save notes from localStorage per conversation
  useEffect(() => {
    if (activeConvId) {
      const saved = localStorage.getItem(`docere-notes-${activeConvId}`)
      setNotesContent(saved || '')
    } else {
      setNotesContent('')
    }
  }, [activeConvId])

  const handleNotesChange = (value: string) => {
    setNotesContent(value)
    if (activeConvId) {
      localStorage.setItem(`docere-notes-${activeConvId}`, value)
    }
  }

  // Load courses and conversations on mount
  useEffect(() => {
    api.listCourses().then(serverCourses => {
      const mapped = serverCourses.map(c => ({
        id: c.id,
        name: c.name,
        courseCode: c.course_code || '',
      }))
      setCourses(mapped)
      // Auto-select first course if only one
      if (mapped.length === 1) setActiveCourseId(mapped[0].id)
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
    setError(null)
    closePanel()
  }

  const startNewChatForCourse = (courseId: string) => {
    setActiveCourseId(courseId)
    setActiveConvId(null)
    setError(null)
    closePanel()
  }

  const handleDeleteConversation = async (convId: string) => {
    try {
      await api.deleteConversation(convId)
      setConversations(prev => prev.filter(c => c.id !== convId))
      if (activeConvId === convId) {
        setActiveConvId(null)
        closePanel()
      }
    } catch {
      setError('Failed to delete conversation')
    }
  }

  const openArtifact = (artifact: StudyArtifact) => {
    if (artifact.type === 'notes') {
      const newContent = artifact.content || ''
      if (!artifactStreamedNotes.current) {
        if (notesContent.trim() && notesContent !== '<p></p>') {
          handleNotesChange(notesContent.trimEnd() + '\n\n' + newContent)
        } else {
          handleNotesChange(newContent)
        }
      }
      setIsAgentWritingNotes(false)
      setAgentWrittenSection(newContent)
      setIsNotesOpen(true)
      return
    }
    setActiveArtifact(artifact)
    setIsPanelOpen(true)
    setIsGeneratingArtifact(false)
  }

  const closePanel = () => {
    setIsPanelOpen(false)
    setIsGeneratingArtifact(false)
  }

  const openMeetingScheduler = (action?: MeetingAction | null) => {
    closePanel()
    setMeetingAction(action || null)
    setIsMeetingPanelOpen(true)
  }

  const closeMeetingPanel = () => {
    setIsMeetingPanelOpen(false)
  }

  const handleSendMessage = async (content: string) => {
    // Course for new conversations: toggled pill > active conversation > first course
    const courseId = activeCourseId || activeConv?.courseId || (courses.length > 0 ? courses[0].id : null)
    if (!courseId) return
    setError(null)
    shouldAutoScroll.current = true

    const course = courses.find(c => c.id === courseId)

    const isStudyRequest = STUDY_KEYWORDS.test(content)

    try {
      // Continue in current conversation, or create one if none exists
      let convId = activeConvId
      if (!convId) {
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
        convId = serverConv.id
      } else {
        const tempUserMsg: LocalMessage = { id: crypto.randomUUID(), role: 'user', content }
        setConversations(prev =>
          prev.map(c =>
            c.id === convId
              ? { ...c, messages: [...c.messages, tempUserMsg], lastMessageAt: new Date().toISOString() }
              : c
          )
        )
      }

      // Add an empty assistant message placeholder for streaming
      const placeholderId = crypto.randomUUID()
      setConversations(prev =>
        prev.map(c =>
          c.id === convId
            ? { ...c, messages: [...c.messages, { id: placeholderId, role: 'assistant' as const, content: '' }] }
            : c
        )
      )
      setIsLoading(true)

      const targetConvId = convId
      let artifactDetected = false
      let streamedContent = ''
      let artifactBuffer = ''
      let artifactIsNotes = false
      artifactStreamedNotes.current = false
      const baseNotes = notesContent.trim() && notesContent !== '<p></p>' ? notesContent.trimEnd() + '\n\n' : ''

      const currentNotes = notesContent.trim() || undefined
      await api.streamMessage(
        targetConvId,
        content,
        (text: string) => {
          // After artifact fence detected, accumulate into artifact buffer
          if (artifactDetected) {
            artifactBuffer += text

            // Detect if this is a notes artifact
            if (!artifactIsNotes && /"type"\s*:\s*"notes"/.test(artifactBuffer)) {
              artifactIsNotes = true
              setIsAgentWritingNotes(true)
              setAgentWrittenSection(null)
              setIsNotesOpen(true)
            }

            // If notes, stream content progressively into the notes panel
            if (artifactIsNotes) {
              const contentMatch = artifactBuffer.match(/"content"\s*:\s*"/)
              if (contentMatch) {
                const startIdx = contentMatch.index! + contentMatch[0].length
                let partial = artifactBuffer.slice(startIdx)
                // Strip trailing incomplete JSON (closing quote, braces, backticks)
                partial = partial.replace(/"\s*[,}][\s\S]*$/, '').replace(/`+\s*$/, '')
                // Unescape JSON string
                partial = partial.replace(/\\n/g, '\n').replace(/\\"/g, '"').replace(/\\\\/g, '\\').replace(/\\t/g, '\t')
                if (partial) {
                  artifactStreamedNotes.current = true
                  handleNotesChange(baseNotes + partial)
                }
              }
            }
            return
          }

          streamedContent += text

          // Check accumulated content for artifact/action/widget fences
          if (/```(artifact|action|widget)/.test(streamedContent)) {
            artifactDetected = true
            artifactBuffer = streamedContent.split(/```(?:artifact|action|widget)\s*/)[1] || ''
            // Strip everything from the ``` fence onward
            const cleaned = streamedContent.replace(/```(artifact|action|widget)[\s\S]*$/, '').trim()
            setConversations(prev =>
              prev.map(c =>
                c.id === targetConvId
                  ? {
                      ...c,
                      messages: c.messages.map(m =>
                        m.id === placeholderId ? { ...m, content: cleaned } : m
                      ),
                    }
                  : c
              )
            )

            if (/"type"\s*:\s*"notes"/.test(artifactBuffer)) {
              artifactIsNotes = true
              setIsNotesOpen(true)
            }
            return
          }

          setConversations(prev =>
            prev.map(c =>
              c.id === targetConvId
                ? {
                    ...c,
                    messages: c.messages.map(m =>
                      m.id === placeholderId ? { ...m, content: streamedContent } : m
                    ),
                  }
                : c
            )
          )
        },
        (meta: StreamDoneMeta) => {
          setConversations(prev =>
            prev.map(c =>
              c.id === targetConvId
                ? {
                    ...c,
                    messages: c.messages.map(m =>
                      m.id === placeholderId
                        ? {
                            ...m,
                            id: meta.message_id || placeholderId,
                            // Replace streamed content with cleaned text (strips artifact/action blocks)
                            content: meta.chat_text ?? m.content,
                            artifact: meta.artifact,
                            action: meta.action,
                            widgets: meta.widgets,
                          }
                        : m
                    ),
                  }
                : c
            )
          )
          setIsLoading(false)

          if (meta.artifact) {
            openArtifact(meta.artifact)
          } else {
            // No artifact parsed — close StudyPanel if it was opened speculatively
            closePanel()
          }

          if (meta.action?.type === 'meeting_suggestion') {
            openMeetingScheduler(meta.action)
          }
        },
        async (errMsg: string) => {
          setConversations(prev =>
            prev.map(c =>
              c.id === targetConvId
                ? { ...c, messages: c.messages.filter(m => m.id !== placeholderId) }
                : c
            )
          )

          try {
            const response = await api.sendMessage(targetConvId, content, currentNotes)
            const artifact = response.message.artifact || null
            const action = response.message.action || null
            const widgets = response.message.widgets || null

            setConversations(prev =>
              prev.map(c =>
                c.id === targetConvId
                  ? {
                      ...c,
                      messages: [
                        ...c.messages,
                        { id: response.message.id, role: 'assistant' as const, content: response.message.content, artifact, action, widgets },
                      ],
                    }
                  : c
              )
            )
            setIsLoading(false)

            if (artifact) {
              openArtifact(artifact)
            } else if (isStudyRequest) {
              closePanel()
            }
          } catch {
            setIsLoading(false)
            setIsGeneratingArtifact(false)
            if (isStudyRequest) closePanel()
            setError(errMsg)
          }
        },
        currentNotes,
      )
    } catch (err) {
      setIsLoading(false)
      setIsGeneratingArtifact(false)
      if (isStudyRequest) closePanel()
      setError(err instanceof Error ? err.message : 'Failed to send message')
    }
  }

  // Greeting
  const currentHour = new Date().getHours()
  let greeting = 'Good morning'
  if (currentHour >= 12 && currentHour < 18) greeting = 'Good afternoon'
  else if (currentHour >= 18) greeting = 'Good evening'

  const hasMessages = activeConv && activeConv.messages.length > 0

  return (
    <div className="flex h-screen bg-bg-0 text-text-100 relative overflow-hidden">
      {/* Sidebar */}
      <Sidebar
        conversations={conversations.map(c => ({
          id: c.id,
          title: c.title,
          courseName: c.courseName,
          courseId: c.courseId,
          lastMessageAt: c.lastMessageAt,
        }))}
        courses={courses.map(c => ({ id: c.id, name: c.name }))}
        activeId={activeConvId}
        activeCourseId={activeCourseId}
        onSelect={setActiveConvId}
        onNew={handleNewConversation}
        onNewForCourse={startNewChatForCourse}
        onToggleCourse={(id) => setActiveCourseId(id)}
        onDelete={handleDeleteConversation}
        onLogout={logout}
        userEmail={user?.email || ''}
        dark={dark}
        toggleTheme={toggle}
        onOpenFocus={() => setIsFocusMode(true)}
      />

      {/* Main Content — always a chat */}
      <div className="flex-1 flex flex-col min-w-0 min-h-0">
        {/* Error banner */}
        {error && (
          <div className="px-6 py-2 bg-red-500/10 border-b border-red-500/20 text-red-600 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-600 ml-4">
              Dismiss
            </button>
          </div>
        )}

        {/* Scrollable area — messages or empty greeting */}
        <div ref={messagesContainerRef} onScroll={handleMessagesScroll} className="flex-1 overflow-y-auto custom-scrollbar">
          {!hasMessages ? (
            /* ── Empty state: greeting + quick actions ── */
            <div className="flex flex-col items-center justify-center min-h-full py-8 px-6">
              <div className="animate-fade-in w-full max-w-lg">
                <div className="flex flex-col items-center text-center mb-8">
                  <h1 className="text-[22px] font-serif text-text-200 mb-1 tracking-tight">
                    {greeting},{' '}
                    <span className="underline decoration-accent decoration-2 underline-offset-4">
                      {user?.name || 'there'}
                    </span>
                  </h1>
                  <p className="text-[13px] text-text-400 mt-1">
                    {activeCourseId
                      ? `Studying ${courses.find(c => c.id === activeCourseId)?.name} — toggle classes in the sidebar`
                      : 'What can I help you with?'}
                  </p>
                </div>

                {/* Quick Action Buttons */}
                <div className="grid grid-cols-2 gap-2.5 w-full">
                  {QUICK_ACTIONS.map(action => (
                    <button
                      key={action.label}
                      onClick={() => handleSendMessage(action.prompt)}
                      className="group px-4 py-3 rounded-xl border border-bg-300/70 bg-bg-100/50 hover:bg-bg-200 hover:border-accent/30 transition-all text-left"
                    >
                      <div className="text-[13px] text-text-300 group-hover:text-text-100 font-medium transition-colors">
                        {action.label}
                      </div>
                      <div className="text-[11px] text-text-500 group-hover:text-text-400 transition-colors mt-0.5 leading-snug">
                        {action.desc}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            /* ── Messages ── */
            <div className="px-6 py-6">
              <div className="max-w-2xl mx-auto">
                {activeConv!.messages.map(msg => (
                  msg.role === 'assistant' && !msg.content ? null : (
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
                  )
                ))}
                {isLoading && (
                  <div className="flex gap-3 mb-5">
                    <div className="w-7 h-7 shrink-0 mt-1">
                      <Icons.Logo className="w-7 h-7 opacity-70" />
                    </div>
                    <div className="bg-bg-200/70 rounded-2xl rounded-bl-md px-4 py-3">
                      <div className="flex gap-1">
                        <span className="w-1.5 h-1.5 bg-text-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                        <span className="w-1.5 h-1.5 bg-text-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                        <span className="w-1.5 h-1.5 bg-text-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>
            </div>
          )}
        </div>

        {/* Input */}
        <div className="pb-4 pt-2">
          <div className="max-w-2xl mx-auto px-6 mb-1 flex justify-end">
            <button
              onClick={() => setIsNotesOpen(!isNotesOpen)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                isNotesOpen
                  ? 'bg-accent/10 text-accent'
                  : 'text-text-400 hover:text-text-300 hover:bg-bg-200/50'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3.5 h-3.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
              </svg>
              Notes{notesContent.trim() ? ' *' : ''}
            </button>
          </div>
          <ClaudeChatInput onSendMessage={handleSendMessage} disabled={isLoading} />
        </div>
      </div>

      {/* Notes Panel */}
      {isNotesOpen && (
        <NotesEditor
          content={notesContent}
          onChange={handleNotesChange}
          onClose={() => { setIsNotesOpen(false); setIsNotesExpanded(false) }}
          isAgentWriting={isAgentWritingNotes}
          agentWrittenSection={agentWrittenSection}
          onDismissAgentSection={() => setAgentWrittenSection(null)}
          onExplain={() => {
            if (agentWrittenSection) {
              setAgentWrittenSection(null)
              handleSendMessage(`Explain how you came up with these notes — what sources did you pull from, and what was your thought process?\n\nNotes you wrote:\n${agentWrittenSection.slice(0, 500)}`)
            }
          }}
          onRewrite={() => {
            if (agentWrittenSection) {
              setAgentWrittenSection(null)
              handleSendMessage(`Rewrite the notes you just added to my notes panel. Make them clearer and more detailed.`)
            }
          }}
          isExpanded={isNotesExpanded}
          onToggleExpand={() => setIsNotesExpanded(!isNotesExpanded)}
        />
      )}

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

      {/* Focus Mode Overlay */}
      {isFocusMode && (
        <FocusPage onClose={() => setIsFocusMode(false)} />
      )}
    </div>
  )
}
