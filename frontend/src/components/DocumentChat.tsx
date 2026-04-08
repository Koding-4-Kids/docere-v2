import { useState, useRef, useEffect, useCallback } from 'react'
import * as api from '../api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

interface Props {
  isOpen: boolean
  onClose: () => void
  courseId: string
  docId: string
  docName: string
  docType: string | null
}

const SUGGESTIONS: Record<string, string[]> = {
  slides: ['Summarize these slides', 'What are the key takeaways?', 'Quiz me on this'],
  textbook: ['Explain the main concepts', 'What should I focus on?', 'Create flashcards from this'],
  notes: ['What am I missing?', 'Help me organize these', 'Quiz me on this'],
  assignment: ['Break down the requirements', 'What should I start with?', 'What concepts do I need?'],
  exam: ['What topics should I study?', 'Create a practice test', 'What are the hard parts?'],
  rubric: ['What does this rubric prioritize?', 'How do I get full marks?', 'Summarize the criteria'],
  default: ['Summarize this document', 'What are the key points?', 'Quiz me on this'],
}

export function DocumentChat({ isOpen, onClose, courseId, docId, docName, docType }: Props) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const suggestions = SUGGESTIONS[docType || 'default'] || SUGGESTIONS.default

  useEffect(() => {
    if (isOpen) setTimeout(() => inputRef.current?.focus(), 100)
  }, [isOpen])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const sendMessage = useCallback(async (content: string) => {
    if (!content.trim() || loading) return

    const userMsg: Message = { id: `user-${Date.now()}`, role: 'user', content: content.trim() }
    setMessages(prev => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      let convId = conversationId
      if (!convId) {
        const conv = await api.createConversation(courseId, `About: ${docName}`)
        convId = conv.id
        setConversationId(convId)
      }

      const isFirst = messages.length === 0
      const prefixed = isFirst
        ? `[I'm looking at my uploaded document "${docName}" (${docType || 'document'}). Help me with it.]\n\n${content.trim()}`
        : content.trim()

      const assistantId = `assistant-${Date.now()}`
      setMessages(prev => [...prev, { id: assistantId, role: 'assistant', content: '' }])

      await api.streamMessage(
        convId,
        prefixed,
        (token) => {
          setMessages(prev =>
            prev.map(m => m.id === assistantId ? { ...m, content: m.content + token } : m)
          )
        },
        () => {},
        (err) => {
          setMessages(prev =>
            prev.map(m => m.id === assistantId ? { ...m, content: `Error: ${err}` } : m)
          )
        },
      )
    } catch (e: any) {
      setMessages(prev => [...prev, {
        id: `err-${Date.now()}`,
        role: 'assistant',
        content: `Something went wrong: ${e.message}`,
      }])
    } finally {
      setLoading(false)
    }
  }, [loading, conversationId, courseId, docName, docType, messages.length])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(input)
    }
  }

  if (!isOpen) return null

  return (
    <div className="absolute top-16 right-4 z-20 w-[420px] max-h-[70vh] flex flex-col bg-black/80 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
        <span className="text-xs font-medium text-white/60">Ask about this document</span>
        <button
          onClick={onClose}
          className="text-white/30 hover:text-white/70 transition-colors text-lg leading-none"
        >
          &times;
        </button>
      </div>

      {/* Context tag */}
      <div className="px-3 pt-2">
        <span className="inline-flex items-center gap-1.5 bg-[#a78bfa]/15 text-[#c4b5fd] text-[11px] font-medium rounded-md px-2 py-1 border border-[#a78bfa]/20">
          <span className="w-1.5 h-1.5 rounded-full bg-[#a78bfa]" />
          {docName}
        </span>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[120px] max-h-[50vh]">
        {messages.length === 0 && !loading && (
          <div className="space-y-2 py-4">
            <p className="text-white/20 text-xs text-center mb-3">
              Ask anything about this {docType || 'document'}...
            </p>
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => sendMessage(s)}
                className="w-full text-left px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.06] hover:bg-white/[0.07] hover:border-white/[0.12] text-[12px] text-white/40 hover:text-white/70 transition-all"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
                msg.role === 'user'
                  ? 'bg-[#a78bfa]/20 text-white/90 rounded-br-md'
                  : 'bg-white/5 text-white/80 rounded-bl-md'
              }`}
            >
              {msg.role === 'assistant' && !msg.content && loading ? (
                <div className="flex gap-1">
                  <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              ) : (
                <div className="whitespace-pre-wrap">{msg.content}</div>
              )}
            </div>
          </div>
        ))}

        {loading && messages.length > 0 && messages[messages.length - 1]?.role === 'user' && (
          <div className="flex justify-start">
            <div className="bg-white/5 rounded-2xl rounded-bl-md px-3.5 py-2.5">
              <div className="flex gap-1">
                <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                <span className="w-1.5 h-1.5 bg-white/30 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="px-3 pb-3 pt-1">
        <div className="flex items-end gap-2 bg-white/5 rounded-xl border border-white/10 px-3 py-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question..."
            rows={1}
            className="flex-1 bg-transparent text-white/90 text-[13px] placeholder-white/20 resize-none outline-none max-h-[80px]"
            style={{ minHeight: '24px' }}
            onInput={e => {
              const el = e.target as HTMLTextAreaElement
              el.style.height = '24px'
              el.style.height = Math.min(el.scrollHeight, 80) + 'px'
            }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="text-[#a78bfa] hover:text-[#c4b5fd] disabled:text-white/10 transition-colors mb-0.5"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}
