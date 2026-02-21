import { useState, useRef, useEffect } from 'react'
import type { ChatMessage } from '../hooks/useInstructorChat'
import type { SourceRef } from '../api'
import { InstructorWidgets } from './InstructorWidgetRenderer'

function SourcesCollapsible({ sources }: { sources: SourceRef[] }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-1">
      <button
        onClick={() => setOpen(p => !p)}
        className="flex items-center gap-1 text-[9px] text-white/20 hover:text-white/40 transition-colors"
      >
        <svg
          width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          className={`transition-transform ${open ? 'rotate-90' : ''}`}
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
        {sources.length} source{sources.length !== 1 ? 's' : ''}
      </button>
      {open && (
        <div className="mt-1 space-y-0.5 pl-2 border-l border-white/5">
          {sources.map((src, i) => (
            <div key={i} className="text-[9px] text-white/30">
              <span className="text-white/45">{src.label}</span>
              {src.student_name && <span className="text-white/25"> — {src.student_name}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

interface TaggedStudent {
  id: string
  name: string
}

interface Props {
  isOpen: boolean
  onClose: () => void
  taggedStudents: TaggedStudent[]
  onRemoveTag: (studentId: string) => void
  onClearAllTags: () => void
  messages: ChatMessage[]
  loading: boolean
  onSend: (question: string) => void
  courseId?: string
}

export function InstructorChat({ isOpen, onClose, taggedStudents, onRemoveTag, onClearAllTags, messages, loading, onSend, courseId }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = () => {
    if (!input.trim() || loading) return
    onSend(input.trim())
    setInput('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  if (!isOpen) return null

  return (
    <div className="absolute top-16 left-4 z-20 w-[420px] max-h-[70vh] flex flex-col bg-black/80 backdrop-blur-xl rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
        <span className="text-xs font-medium text-white/60">
          {taggedStudents.length > 0
            ? `${taggedStudents.length} student${taggedStudents.length > 1 ? 's' : ''} tagged`
            : 'Ask about your students'}
        </span>
        <button
          onClick={onClose}
          className="text-white/30 hover:text-white/70 transition-colors text-lg leading-none"
        >
          &times;
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3 min-h-[120px] max-h-[50vh]">
        {messages.length === 0 && !loading && (
          <div className="text-white/20 text-xs text-center py-8">
            {taggedStudents.length > 0
              ? `Ask anything about the tagged student${taggedStudents.length > 1 ? 's' : ''}...`
              : 'Click students in the roster or graph to tag them, then ask questions...'}
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i}>
            <div className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-[13px] leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-[#4488ff]/20 text-white/90 rounded-br-md'
                    : 'bg-white/5 text-white/80 rounded-bl-md'
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>
              </div>
            </div>
            {msg.role === 'assistant' && msg.widgets && msg.widgets.length > 0 && (
              <InstructorWidgets widgets={msg.widgets} courseId={courseId} />
            )}
            {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
              <SourcesCollapsible sources={msg.sources} />
            )}
          </div>
        ))}
        {loading && (
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

      {/* Context Tags */}
      {taggedStudents.length > 0 && (
        <div className="px-3 pt-2">
          <div className="flex items-center gap-1.5 flex-wrap">
            {taggedStudents.map(student => (
              <span
                key={student.id}
                className="inline-flex items-center gap-1 bg-[#4488ff]/15 text-[#88bbff] text-[11px] font-medium rounded-md px-2 py-1 border border-[#4488ff]/20"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-[#4488ff]" />
                {student.name}
                <button
                  onClick={() => onRemoveTag(student.id)}
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
                onClick={onClearAllTags}
                className="text-[10px] text-white/25 hover:text-white/50 transition-colors ml-1"
              >
                clear all
              </button>
            )}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="px-3 pb-3 pt-1">
        <div className="flex items-end gap-2 bg-white/5 rounded-xl border border-white/10 px-3 py-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              taggedStudents.length === 1
                ? `Ask about ${taggedStudents[0].name}...`
                : taggedStudents.length > 1
                ? `Ask about ${taggedStudents.length} students...`
                : 'Which students are struggling with SQL?'
            }
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
            onClick={send}
            disabled={!input.trim() || loading}
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
  )
}
