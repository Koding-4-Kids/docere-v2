import { useState, useEffect, useRef } from 'react'
import type { IntegrationStatus, Course, MetaAction } from '../api'
import { executeAction } from '../api'

interface ModalProps {
  onClose: () => void
  integrationStatus: IntegrationStatus | null
  courses: Course[]
}

// ── Shared Modal Shell ──

function ModalShell({ title, icon, onClose, children }: {
  title: string
  icon: React.ReactNode
  onClose: () => void
  children: React.ReactNode
}) {
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div className="relative w-full max-w-lg mx-4 max-h-[85vh] bg-[#0e0e14] rounded-2xl border border-white/10 shadow-2xl overflow-hidden animate-fade-in flex flex-col">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-white/[0.06] shrink-0">
          <div className="w-8 h-8 rounded-xl bg-white/[0.05] flex items-center justify-center">{icon}</div>
          <h2 className="text-[14px] font-medium text-white/80">{title}</h2>
          <button onClick={onClose} className="ml-auto text-white/20 hover:text-white/50 transition-colors text-lg">&times;</button>
        </div>
        <div className="px-5 py-4 overflow-y-auto flex-1">{children}</div>
      </div>
    </div>
  )
}

function NotConnected({ onClose }: { onClose: () => void }) {
  const handleConnect = () => {
    const token = localStorage.getItem('docere_token')
    fetch('/api/v1/calendar/oauth/authorize', {
      headers: { 'Authorization': `Bearer ${token}` },
    })
      .then(r => r.json())
      .then(data => { if (data.url) window.open(data.url, '_blank', 'width=600,height=700') })
      .catch(() => {})
  }
  return (
    <div className="text-center py-6">
      <p className="text-[13px] text-white/40 mb-4">Connect your Google account to use this integration.</p>
      <div className="flex items-center justify-center gap-3">
        <button onClick={handleConnect} className="px-4 py-2 rounded-xl bg-[#4488ff]/15 text-[#4488ff] text-[13px] font-medium hover:bg-[#4488ff]/25 transition-colors">
          Connect Google
        </button>
        <button onClick={onClose} className="px-4 py-2 rounded-xl text-[13px] text-white/30 hover:text-white/50 transition-colors">
          Cancel
        </button>
      </div>
    </div>
  )
}

function SuccessResult({ label, url, onClose }: { label: string; url?: string; onClose: () => void }) {
  return (
    <div className="text-center py-6">
      <div className="w-10 h-10 rounded-full bg-emerald-500/10 flex items-center justify-center mx-auto mb-3">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
      </div>
      <p className="text-[14px] text-white/70 mb-1">{label}</p>
      {url && (
        <a href={url} target="_blank" rel="noopener noreferrer" className="text-[13px] text-[#4488ff]/80 hover:text-[#4488ff] transition-colors underline underline-offset-2">
          Open →
        </a>
      )}
      <div className="mt-4">
        <button onClick={onClose} className="px-4 py-2 rounded-xl text-[13px] text-white/30 hover:text-white/50 transition-colors">Done</button>
      </div>
    </div>
  )
}

// ── AI Tool Agent ──

async function askToolAgent(prompt: string): Promise<{ answer: string; actions: MetaAction[] }> {
  const token = localStorage.getItem('docere_token')
  const res = await fetch('/api/v1/instructor/meta/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify({ question: prompt, history: [] }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const data = await res.json()
  return { answer: data.answer, actions: data.actions || [] }
}

// ── Sparkle icon ──

const SparkleIcon = ({ className = '' }: { className?: string }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M12 3l1.912 5.813a2 2 0 0 0 1.275 1.275L21 12l-5.813 1.912a2 2 0 0 0-1.275 1.275L12 21l-1.912-5.813a2 2 0 0 0-1.275-1.275L3 12l5.813-1.912a2 2 0 0 0 1.275-1.275L12 3z" />
  </svg>
)

// ── AI Prompt Bar ──

function AIPromptBar({ placeholder, onSubmit, loading, suggestions, showSuggestions }: {
  placeholder: string
  onSubmit: (prompt: string) => void
  loading: boolean
  suggestions: string[]
  showSuggestions: boolean
}) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { inputRef.current?.focus() }, [])

  const handleSubmit = () => {
    if (!value.trim() || loading) return
    onSubmit(value.trim())
    setValue('')
  }

  return (
    <div className="space-y-2.5">
      <div className="flex items-center gap-2 bg-white/[0.04] border border-white/[0.08] rounded-xl px-3 py-2.5 focus-within:border-[#4488ff]/30 transition-colors">
        {loading && (
          <div className="flex gap-1 shrink-0">
            <span className="w-1 h-1 bg-[#4488ff]/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1 h-1 bg-[#4488ff]/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1 h-1 bg-[#4488ff]/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
        )}
        <input
          ref={inputRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          placeholder={loading ? 'Drafting with AI...' : placeholder}
          disabled={loading}
          className="flex-1 bg-transparent text-[13px] text-white/80 placeholder-white/20 outline-none disabled:opacity-50"
        />
        <button
          onClick={handleSubmit}
          disabled={!value.trim() || loading}
          className="text-[#4488ff]/70 hover:text-[#4488ff] disabled:text-white/10 transition-colors shrink-0"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        </button>
      </div>
      {showSuggestions && suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {suggestions.map(s => (
            <button
              key={s}
              onClick={() => { setValue(''); onSubmit(s) }}
              disabled={loading}
              className="px-2.5 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06] text-[11px] text-white/30 hover:text-white/60 hover:bg-white/[0.06] hover:border-white/12 transition-all disabled:opacity-30"
            >
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

// ── AI Response Message ──

function AIResponseMessage({ text }: { text: string }) {
  return (
    <div className="flex gap-2.5 my-3 p-3 rounded-xl bg-[#4488ff]/[0.04] border border-[#4488ff]/[0.08]">
      <SparkleIcon className="text-[#4488ff]/50 shrink-0 mt-0.5" />
      <p className="text-[12px] text-white/50 leading-relaxed">{text}</p>
    </div>
  )
}

// ── Separator ──

function OrSeparator() {
  return (
    <div className="flex items-center gap-3 my-3">
      <div className="flex-1 h-px bg-white/[0.04]" />
      <span className="text-[10px] text-white/15">or edit manually</span>
      <div className="flex-1 h-px bg-white/[0.04]" />
    </div>
  )
}

// ── Gmail Modal ──

export function GmailModal({ onClose, integrationStatus }: ModalProps) {
  const [to, setTo] = useState('')
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const icon = (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="4" width="20" height="16" rx="2" fill="#fff" fillOpacity="0.1" stroke="#EA4335" strokeWidth="1.5" />
      <path d="M2 6l10 7 10-7" stroke="#EA4335" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )

  if (!integrationStatus?.google_connected) {
    return <ModalShell title="Send Email" icon={icon} onClose={onClose}><NotConnected onClose={onClose} /></ModalShell>
  }

  if (success) {
    return <ModalShell title="Send Email" icon={icon} onClose={onClose}><SuccessResult label="Email sent!" onClose={onClose} /></ModalShell>
  }

  const handleAI = async (prompt: string) => {
    setAiLoading(true)
    setAiResponse('')
    setError('')
    try {
      const result = await askToolAgent(`Draft an email for me: ${prompt}`)
      setAiResponse(result.answer)
      const action = result.actions.find(a => a.type === 'draft_email')
      if (action) {
        if (action.to) setTo((action.to as string[]).join(', '))
        if (action.subject) setSubject(action.subject as string)
        if (action.body) setBody((action.body as string).replace(/<[^>]*>/g, ''))
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setAiLoading(false)
    }
  }

  const handleSend = async () => {
    if (!to.trim() || !subject.trim()) return
    setSending(true)
    setError('')
    try {
      const recipients = to.split(',').map(e => e.trim()).filter(Boolean)
      const res = await executeAction('draft_email', { to: recipients, subject, body })
      if (!res.success) throw new Error(res.error || 'Failed to send')
      setSuccess(true)
    } catch (e) {
      setError(String(e))
    } finally {
      setSending(false)
    }
  }

  const formEmpty = !to && !subject && !body

  return (
    <ModalShell title="Send Email" icon={icon} onClose={onClose}>
      <AIPromptBar
        placeholder="Describe the email you want to send..."
        onSubmit={handleAI}
        loading={aiLoading}
        suggestions={[
          'Check in with my at-risk students',
          'Remind about the upcoming deadline',
          'Share study resources for struggling concepts',
        ]}
        showSuggestions={formEmpty && !aiResponse}
      />
      {aiResponse && <AIResponseMessage text={aiResponse} />}
      {!aiResponse && !aiLoading && formEmpty && <OrSeparator />}
      <div className="space-y-3 mt-3">
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">To (comma-separated)</label>
          <input value={to} onChange={e => setTo(e.target.value)} placeholder="student@example.com" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors" />
        </div>
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Subject</label>
          <input value={subject} onChange={e => setSubject(e.target.value)} placeholder="Check-in on your progress" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors" />
        </div>
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Body</label>
          <textarea value={body} onChange={e => setBody(e.target.value)} placeholder="Write your message..." rows={5} className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors resize-none" />
        </div>
        {error && <p className="text-[11px] text-red-400/70">{error}</p>}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-[13px] text-white/30 hover:text-white/50 transition-colors">Cancel</button>
          <button onClick={handleSend} disabled={sending || !to.trim() || !subject.trim()} className="px-4 py-2 rounded-xl bg-[#EA4335]/15 text-[#EA4335] text-[13px] font-medium hover:bg-[#EA4335]/25 disabled:opacity-30 transition-colors">
            {sending ? 'Sending...' : 'Send Email'}
          </button>
        </div>
      </div>
    </ModalShell>
  )
}

// ── Google Docs Modal ──

export function GoogleDocsModal({ onClose, integrationStatus }: ModalProps) {
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [resultUrl, setResultUrl] = useState('')

  const icon = (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#4285F4" />
      <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#A1C2FA" />
      <rect x="7" y="12" width="10" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.9" />
      <rect x="7" y="15" width="7" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.9" />
    </svg>
  )

  if (!integrationStatus?.google_connected) {
    return <ModalShell title="Create Document" icon={icon} onClose={onClose}><NotConnected onClose={onClose} /></ModalShell>
  }

  if (resultUrl) {
    return <ModalShell title="Create Document" icon={icon} onClose={onClose}><SuccessResult label="Document created!" url={resultUrl} onClose={onClose} /></ModalShell>
  }

  const handleAI = async (prompt: string) => {
    setAiLoading(true)
    setAiResponse('')
    setError('')
    try {
      const result = await askToolAgent(`Create a Google Doc for me: ${prompt}`)
      setAiResponse(result.answer)
      const action = result.actions.find(a => a.type === 'create_doc')
      if (action) {
        if (action.title) setTitle(action.title as string)
        if (action.content) setContent(action.content as string)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setAiLoading(false)
    }
  }

  const handleCreate = async () => {
    if (!title.trim()) return
    setCreating(true)
    setError('')
    try {
      const res = await executeAction('create_doc', { title, content })
      if (!res.success) throw new Error(res.error || 'Failed')
      setResultUrl(res.result.url as string)
    } catch (e) {
      setError(String(e))
    } finally {
      setCreating(false)
    }
  }

  const formEmpty = !title && !content

  return (
    <ModalShell title="Create Document" icon={icon} onClose={onClose}>
      <AIPromptBar
        placeholder="Describe the document you want to create..."
        onSubmit={handleAI}
        loading={aiLoading}
        suggestions={[
          'Weekly student progress report',
          'Intervention plan for struggling students',
          'Course performance summary for department review',
        ]}
        showSuggestions={formEmpty && !aiResponse}
      />
      {aiResponse && <AIResponseMessage text={aiResponse} />}
      {!aiResponse && !aiLoading && formEmpty && <OrSeparator />}
      <div className="space-y-3 mt-3">
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Document Title</label>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Weekly Student Report" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors" />
        </div>
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Content</label>
          <textarea value={content} onChange={e => setContent(e.target.value)} placeholder="Document content..." rows={8} className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors resize-none font-mono text-[12px]" />
        </div>
        {error && <p className="text-[11px] text-red-400/70">{error}</p>}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-[13px] text-white/30 hover:text-white/50 transition-colors">Cancel</button>
          <button onClick={handleCreate} disabled={creating || !title.trim()} className="px-4 py-2 rounded-xl bg-[#4285F4]/15 text-[#4285F4] text-[13px] font-medium hover:bg-[#4285F4]/25 disabled:opacity-30 transition-colors">
            {creating ? 'Creating...' : 'Create Document'}
          </button>
        </div>
      </div>
    </ModalShell>
  )
}

// ── Google Sheets Modal ──

export function GoogleSheetsModal({ onClose, integrationStatus }: ModalProps) {
  const [title, setTitle] = useState('')
  const [headers, setHeaders] = useState<string[]>([])
  const [rows, setRows] = useState<string[][]>([])
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [resultUrl, setResultUrl] = useState('')

  const icon = (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#0F9D58" />
      <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#87CEAC" />
      <rect x="6.5" y="11.5" width="11" height="8" rx="0.5" fill="#fff" fillOpacity="0.9" />
      <line x1="6.5" y1="15.5" x2="17.5" y2="15.5" stroke="#0F9D58" strokeWidth="0.8" />
      <line x1="11" y1="11.5" x2="11" y2="19.5" stroke="#0F9D58" strokeWidth="0.8" />
    </svg>
  )

  if (!integrationStatus?.google_connected) {
    return <ModalShell title="Create Spreadsheet" icon={icon} onClose={onClose}><NotConnected onClose={onClose} /></ModalShell>
  }

  if (resultUrl) {
    return <ModalShell title="Create Spreadsheet" icon={icon} onClose={onClose}><SuccessResult label="Spreadsheet created!" url={resultUrl} onClose={onClose} /></ModalShell>
  }

  const handleAI = async (prompt: string) => {
    setAiLoading(true)
    setAiResponse('')
    setError('')
    try {
      const result = await askToolAgent(`Create a Google Sheet for me: ${prompt}`)
      setAiResponse(result.answer)
      const action = result.actions.find(a => a.type === 'create_sheet')
      if (action) {
        if (action.title) setTitle(action.title as string)
        if (action.headers) setHeaders(action.headers as string[])
        if (action.rows) setRows(action.rows as string[][])
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setAiLoading(false)
    }
  }

  const handleCreate = async () => {
    const name = title.trim() || 'Untitled Spreadsheet'
    setCreating(true)
    setError('')
    try {
      const res = await executeAction('create_sheet', { title: name, headers, rows })
      if (!res.success) throw new Error(res.error || 'Failed')
      setResultUrl(res.result.url as string)
    } catch (e) {
      setError(String(e))
    } finally {
      setCreating(false)
    }
  }

  const hasData = headers.length > 0 || rows.length > 0
  const formEmpty = !title && !hasData

  return (
    <ModalShell title="Create Spreadsheet" icon={icon} onClose={onClose}>
      <AIPromptBar
        placeholder="Describe the data you want to export..."
        onSubmit={handleAI}
        loading={aiLoading}
        suggestions={[
          'Export my gradebook with all student grades',
          'Engagement metrics breakdown by student',
          'Concept mastery overview across the class',
        ]}
        showSuggestions={formEmpty && !aiResponse}
      />
      {aiResponse && <AIResponseMessage text={aiResponse} />}
      {!aiResponse && !aiLoading && formEmpty && <OrSeparator />}
      <div className="space-y-3 mt-3">
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Spreadsheet Title</label>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Gradebook Export" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors" />
        </div>

        {/* Data preview table */}
        {hasData && (
          <div>
            <label className="text-[11px] text-white/25 mb-1.5 block">Data Preview</label>
            <div className="overflow-x-auto rounded-lg border border-white/[0.06]">
              <table className="w-full text-[11px]">
                {headers.length > 0 && (
                  <thead>
                    <tr>
                      {headers.map((h, i) => (
                        <th key={i} className="px-2.5 py-2 text-left font-medium text-white/50 bg-white/[0.03] border-b border-white/[0.06] whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {rows.slice(0, 5).map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j} className="px-2.5 py-1.5 text-white/35 border-b border-white/[0.03] whitespace-nowrap">{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length > 5 && (
                <div className="px-2.5 py-1.5 text-[10px] text-white/20 bg-white/[0.02]">
                  +{rows.length - 5} more rows
                </div>
              )}
            </div>
          </div>
        )}

        {error && <p className="text-[11px] text-red-400/70">{error}</p>}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-[13px] text-white/30 hover:text-white/50 transition-colors">Cancel</button>
          <button onClick={handleCreate} disabled={creating} className="px-4 py-2 rounded-xl bg-[#0F9D58]/15 text-[#0F9D58] text-[13px] font-medium hover:bg-[#0F9D58]/25 disabled:opacity-30 transition-colors">
            {creating ? 'Creating...' : 'Create Spreadsheet'}
          </button>
        </div>
      </div>
    </ModalShell>
  )
}

// ── Excel Modal ──

export function ExcelModal({ onClose }: ModalProps) {
  const [title, setTitle] = useState('')
  const [headers, setHeaders] = useState<string[]>([])
  const [rows, setRows] = useState<string[][]>([])
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [downloadUrl, setDownloadUrl] = useState('')

  const icon = (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#217346" />
      <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#33C481" />
      <path d="M7.5 12l3 4m0-4l-3 4" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  )

  if (downloadUrl) {
    return (
      <ModalShell title="Download Excel" icon={icon} onClose={onClose}>
        <SuccessResult label="Spreadsheet ready!" url={downloadUrl} onClose={onClose} />
      </ModalShell>
    )
  }

  const handleAI = async (prompt: string) => {
    setAiLoading(true)
    setAiResponse('')
    setError('')
    try {
      const result = await askToolAgent(`Generate an Excel spreadsheet for me: ${prompt}`)
      setAiResponse(result.answer)
      const action = result.actions.find(a => a.type === 'create_excel' || a.type === 'create_sheet')
      if (action) {
        if (action.title) setTitle(action.title as string)
        if (action.headers) setHeaders(action.headers as string[])
        if (action.rows) setRows(action.rows as string[][])
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setAiLoading(false)
    }
  }

  const handleCreate = async () => {
    const name = title.trim() || 'Export'
    setCreating(true)
    setError('')
    try {
      const res = await executeAction('create_excel', { title: name, headers, rows })
      if (!res.success) throw new Error(res.error || 'Failed')
      setDownloadUrl(res.result.download_url as string)
    } catch (e) {
      setError(String(e))
    } finally {
      setCreating(false)
    }
  }

  const hasData = headers.length > 0 || rows.length > 0
  const formEmpty = !title && !hasData

  return (
    <ModalShell title="Download Excel" icon={icon} onClose={onClose}>
      <AIPromptBar
        placeholder="Describe the data you want to export..."
        onSubmit={handleAI}
        loading={aiLoading}
        suggestions={[
          'Export my gradebook with all student grades',
          'Engagement metrics breakdown by student',
          'Concept mastery overview across the class',
        ]}
        showSuggestions={formEmpty && !aiResponse}
      />
      {aiResponse && <AIResponseMessage text={aiResponse} />}
      {!aiResponse && !aiLoading && formEmpty && <OrSeparator />}
      <div className="space-y-3 mt-3">
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">File Name</label>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Gradebook Export" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors" />
        </div>

        {hasData && (
          <div>
            <label className="text-[11px] text-white/25 mb-1.5 block">Data Preview</label>
            <div className="overflow-x-auto rounded-lg border border-white/[0.06]">
              <table className="w-full text-[11px]">
                {headers.length > 0 && (
                  <thead>
                    <tr>
                      {headers.map((h, i) => (
                        <th key={i} className="px-2.5 py-2 text-left font-medium text-white/50 bg-white/[0.03] border-b border-white/[0.06] whitespace-nowrap">{h}</th>
                      ))}
                    </tr>
                  </thead>
                )}
                <tbody>
                  {rows.slice(0, 5).map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j} className="px-2.5 py-1.5 text-white/35 border-b border-white/[0.03] whitespace-nowrap">{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length > 5 && (
                <div className="px-2.5 py-1.5 text-[10px] text-white/20 bg-white/[0.02]">
                  +{rows.length - 5} more rows
                </div>
              )}
            </div>
          </div>
        )}

        {error && <p className="text-[11px] text-red-400/70">{error}</p>}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-[13px] text-white/30 hover:text-white/50 transition-colors">Cancel</button>
          <button onClick={handleCreate} disabled={creating} className="px-4 py-2 rounded-xl bg-[#217346]/15 text-[#33C481] text-[13px] font-medium hover:bg-[#217346]/25 disabled:opacity-30 transition-colors">
            {creating ? 'Generating...' : 'Download .xlsx'}
          </button>
        </div>
      </div>
    </ModalShell>
  )
}

// ── Calendar Event Modal ──

export function CalendarEventModal({ onClose, integrationStatus }: ModalProps) {
  const [summary, setSummary] = useState('')
  const [description, setDescription] = useState('')
  const [date, setDate] = useState('')
  const [startTime, setStartTime] = useState('14:00')
  const [endTime, setEndTime] = useState('15:00')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const icon = (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="3" width="20" height="19" rx="2" fill="#4285F4" />
      <rect x="2" y="3" width="20" height="6" rx="2" fill="#1967D2" />
      <rect x="7" y="1" width="2" height="4" rx="1" fill="#1967D2" />
      <rect x="15" y="1" width="2" height="4" rx="1" fill="#1967D2" />
    </svg>
  )

  if (!integrationStatus?.google_connected) {
    return <ModalShell title="Create Event" icon={icon} onClose={onClose}><NotConnected onClose={onClose} /></ModalShell>
  }

  if (success) {
    return <ModalShell title="Create Event" icon={icon} onClose={onClose}><SuccessResult label="Event created!" onClose={onClose} /></ModalShell>
  }

  const handleAI = async (prompt: string) => {
    setAiLoading(true)
    setAiResponse('')
    setError('')
    try {
      const result = await askToolAgent(`Create a calendar event for me: ${prompt}`)
      setAiResponse(result.answer)
      const action = result.actions.find(a => a.type === 'calendar_event')
      if (action) {
        if (action.summary) setSummary(action.summary as string)
        if (action.description) setDescription(action.description as string)
        if (action.start) {
          const start = new Date(action.start as string)
          setDate(start.toISOString().split('T')[0])
          setStartTime(start.toTimeString().slice(0, 5))
        }
        if (action.end) {
          const end = new Date(action.end as string)
          setEndTime(end.toTimeString().slice(0, 5))
        }
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setAiLoading(false)
    }
  }

  const handleCreate = async () => {
    if (!summary.trim() || !date) return
    setCreating(true)
    setError('')
    try {
      const res = await executeAction('calendar_event', {
        summary,
        description,
        start: `${date}T${startTime}:00`,
        end: `${date}T${endTime}:00`,
      })
      if (!res.success) throw new Error(res.error || 'Failed')
      setSuccess(true)
    } catch (e) {
      setError(String(e))
    } finally {
      setCreating(false)
    }
  }

  const formEmpty = !summary && !description && !date

  return (
    <ModalShell title="Create Event" icon={icon} onClose={onClose}>
      <AIPromptBar
        placeholder="Describe the event you want to create..."
        onSubmit={handleAI}
        loading={aiLoading}
        suggestions={[
          'Office hours block for next week',
          'Review session before the exam',
          'One-on-one with a struggling student',
        ]}
        showSuggestions={formEmpty && !aiResponse}
      />
      {aiResponse && <AIResponseMessage text={aiResponse} />}
      {!aiResponse && !aiLoading && formEmpty && <OrSeparator />}
      <div className="space-y-3 mt-3">
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Event Title</label>
          <input value={summary} onChange={e => setSummary(e.target.value)} placeholder="Office Hours — CS101" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors" />
        </div>
        <div className="grid grid-cols-3 gap-2">
          <div>
            <label className="text-[11px] text-white/25 mb-1 block">Date</label>
            <input type="date" value={date} onChange={e => setDate(e.target.value)} className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 outline-none focus:border-white/20 transition-colors [color-scheme:dark]" />
          </div>
          <div>
            <label className="text-[11px] text-white/25 mb-1 block">Start</label>
            <input type="time" value={startTime} onChange={e => setStartTime(e.target.value)} className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 outline-none focus:border-white/20 transition-colors [color-scheme:dark]" />
          </div>
          <div>
            <label className="text-[11px] text-white/25 mb-1 block">End</label>
            <input type="time" value={endTime} onChange={e => setEndTime(e.target.value)} className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 outline-none focus:border-white/20 transition-colors [color-scheme:dark]" />
          </div>
        </div>
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Description (optional)</label>
          <textarea value={description} onChange={e => setDescription(e.target.value)} placeholder="Event details..." rows={3} className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors resize-none" />
        </div>
        {error && <p className="text-[11px] text-red-400/70">{error}</p>}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-[13px] text-white/30 hover:text-white/50 transition-colors">Cancel</button>
          <button onClick={handleCreate} disabled={creating || !summary.trim() || !date} className="px-4 py-2 rounded-xl bg-[#4285F4]/15 text-[#4285F4] text-[13px] font-medium hover:bg-[#4285F4]/25 disabled:opacity-30 transition-colors">
            {creating ? 'Creating...' : 'Create Event'}
          </button>
        </div>
      </div>
    </ModalShell>
  )
}

// ── LMS Announcement Modal ──

export function LMSAnnouncementModal({ onClose, integrationStatus, courses }: ModalProps) {
  const [courseId, setCourseId] = useState(courses[0]?.id || '')
  const [title, setTitle] = useState('')
  const [message, setMessage] = useState('')
  const [aiLoading, setAiLoading] = useState(false)
  const [aiResponse, setAiResponse] = useState('')
  const [posting, setPosting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)

  const icon = (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 3L2 9l10 6 10-6-10-6z" fill="#F98012" />
      <path d="M2 9v6l10 6 10-6V9" fill="none" stroke="#F98012" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  )

  if (!integrationStatus?.lms_connected) {
    return (
      <ModalShell title="Post Announcement" icon={icon} onClose={onClose}>
        <div className="text-center py-6">
          <p className="text-[13px] text-white/40">No LMS configured. Contact your administrator.</p>
          <button onClick={onClose} className="mt-4 px-4 py-2 rounded-xl text-[13px] text-white/30 hover:text-white/50 transition-colors">Close</button>
        </div>
      </ModalShell>
    )
  }

  if (success) {
    return <ModalShell title="Post Announcement" icon={icon} onClose={onClose}><SuccessResult label="Announcement posted!" onClose={onClose} /></ModalShell>
  }

  const handleAI = async (prompt: string) => {
    setAiLoading(true)
    setAiResponse('')
    setError('')
    try {
      const result = await askToolAgent(`Draft an LMS announcement for me: ${prompt}`)
      setAiResponse(result.answer)
      const action = result.actions.find(a => a.type === 'lms_announcement')
      if (action) {
        if (action.title) setTitle(action.title as string)
        if (action.message) setMessage(action.message as string)
        if (action.course_id) {
          const match = courses.find(c => c.id === action.course_id)
          if (match) setCourseId(match.id)
        }
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setAiLoading(false)
    }
  }

  const handlePost = async () => {
    if (!title.trim() || !message.trim()) return
    setPosting(true)
    setError('')
    try {
      const res = await executeAction('lms_announcement', { course_id: courseId, title, message })
      if (!res.success) throw new Error(res.error || 'Failed')
      setSuccess(true)
    } catch (e) {
      setError(String(e))
    } finally {
      setPosting(false)
    }
  }

  const formEmpty = !title && !message

  return (
    <ModalShell title="Post Announcement" icon={icon} onClose={onClose}>
      <AIPromptBar
        placeholder="Describe the announcement you want to post..."
        onSubmit={handleAI}
        loading={aiLoading}
        suggestions={[
          'Exam reminder with study tips',
          'Share new course resources',
          'Schedule change notification',
        ]}
        showSuggestions={formEmpty && !aiResponse}
      />
      {aiResponse && <AIResponseMessage text={aiResponse} />}
      {!aiResponse && !aiLoading && formEmpty && <OrSeparator />}
      <div className="space-y-3 mt-3">
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Course</label>
          <select value={courseId} onChange={e => setCourseId(e.target.value)} className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 outline-none focus:border-white/20 transition-colors [color-scheme:dark]">
            {courses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Title</label>
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Upcoming exam reminder" className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors" />
        </div>
        <div>
          <label className="text-[11px] text-white/25 mb-1 block">Message</label>
          <textarea value={message} onChange={e => setMessage(e.target.value)} placeholder="Write your announcement..." rows={5} className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-[13px] text-white/80 placeholder-white/15 outline-none focus:border-white/20 transition-colors resize-none" />
        </div>
        {error && <p className="text-[11px] text-red-400/70">{error}</p>}
        <div className="flex items-center justify-end gap-2 pt-1">
          <button onClick={onClose} className="px-4 py-2 rounded-xl text-[13px] text-white/30 hover:text-white/50 transition-colors">Cancel</button>
          <button onClick={handlePost} disabled={posting || !title.trim() || !message.trim()} className="px-4 py-2 rounded-xl bg-[#F98012]/15 text-[#F98012] text-[13px] font-medium hover:bg-[#F98012]/25 disabled:opacity-30 transition-colors">
            {posting ? 'Posting...' : 'Post Announcement'}
          </button>
        </div>
      </div>
    </ModalShell>
  )
}
