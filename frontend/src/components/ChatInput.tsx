import { useState, useRef, useEffect } from 'react'
import { ArrowUp, Plus } from 'lucide-react'

interface ChatInputProps {
  onSend: (message: string) => void
  disabled?: boolean
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [message, setMessage] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
    }
  }, [message])

  const handleSend = () => {
    if (!message.trim() || disabled) return
    onSend(message.trim())
    setMessage('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const hasContent = message.trim().length > 0

  return (
    <div className="w-full max-w-2xl mx-auto px-4 pb-4">
      <div className="flex flex-col rounded-2xl border border-bg-300 dark:border-transparent bg-bg-0 dark:bg-bg-200 shadow-[0_0_15px_rgba(0,0,0,0.08)] hover:shadow-[0_0_20px_rgba(0,0,0,0.12)] focus-within:shadow-[0_0_25px_rgba(0,0,0,0.15)] transition-shadow">
        <div className="flex flex-col px-3 pt-3 pb-2 gap-2">
          {/* Input */}
          <div className="relative">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={e => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask Docere anything..."
              className="w-full bg-transparent border-0 outline-none text-text-100 text-[15px] placeholder:text-text-400 resize-none overflow-hidden py-1 pl-1 leading-relaxed"
              rows={1}
              disabled={disabled}
            />
          </div>

          {/* Action Bar */}
          <div className="flex items-center justify-between">
            <button className="p-1.5 rounded-lg text-text-400 hover:text-text-200 hover:bg-bg-200 transition-colors">
              <Plus className="w-5 h-5" />
            </button>

            <button
              onClick={handleSend}
              disabled={!hasContent || disabled}
              className={`p-1.5 rounded-xl transition-colors ${
                hasContent && !disabled
                  ? 'bg-accent text-white hover:bg-accent-hover'
                  : 'bg-accent/30 text-white/60 cursor-default'
              }`}
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <p className="text-center text-xs text-text-500 mt-3">
        Docere can make mistakes. Always verify important information.
      </p>
    </div>
  )
}
