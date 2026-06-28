import { useState, useEffect } from 'react'
import type { MetaAction, ExecuteActionResponse } from '../api'
import { executeAction, getStoredToken } from '../api'

interface Props {
  action: MetaAction
  onDismiss?: () => void
}

// ── Brand icons (inline SVGs matching InstructorDashboardPage) ──

const ICONS: Record<string, React.ReactNode> = {
  draft_email: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="4" width="20" height="16" rx="2" fill="#fff" fillOpacity="0.1" stroke="#EA4335" strokeWidth="1.5" />
      <path d="M2 6l10 7 10-7" stroke="#EA4335" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  create_doc: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#4285F4" />
      <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#A1C2FA" />
      <rect x="7" y="12" width="10" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.9" />
      <rect x="7" y="15" width="7" height="1.2" rx="0.6" fill="#fff" fillOpacity="0.9" />
    </svg>
  ),
  create_sheet: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#0F9D58" />
      <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#87CEAC" />
      <rect x="6.5" y="11.5" width="11" height="8" rx="0.5" fill="#fff" fillOpacity="0.9" />
      <line x1="6.5" y1="15.5" x2="17.5" y2="15.5" stroke="#0F9D58" strokeWidth="0.8" />
      <line x1="11" y1="11.5" x2="11" y2="19.5" stroke="#0F9D58" strokeWidth="0.8" />
    </svg>
  ),
  lms_announcement: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M12 3L2 9l10 6 10-6-10-6z" fill="#F98012" />
      <path d="M2 9v6l10 6 10-6V9" fill="none" stroke="#F98012" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  ),
  create_excel: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M6 2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z" fill="#217346" />
      <path d="M14 2l6 6h-4a2 2 0 0 1-2-2V2z" fill="#33C481" />
      <path d="M7.5 12l3 4m0-4l-3 4" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  calendar_event: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
      <rect x="2" y="3" width="20" height="19" rx="2" fill="#4285F4" />
      <rect x="2" y="3" width="20" height="6" rx="2" fill="#1967D2" />
      <rect x="7" y="1" width="2" height="4" rx="1" fill="#1967D2" />
      <rect x="15" y="1" width="2" height="4" rx="1" fill="#1967D2" />
      <rect x="6" y="12" width="4" height="3" rx="0.5" fill="#fff" fillOpacity="0.9" />
    </svg>
  ),
}

const ACTION_LABELS: Record<string, { title: string; execute: string }> = {
  draft_email: { title: 'Email Draft', execute: 'Send Email' },
  create_doc: { title: 'Google Doc', execute: 'Create Document' },
  create_sheet: { title: 'Google Sheet', execute: 'Create Spreadsheet' },
  create_excel: { title: 'Excel File', execute: 'Download .xlsx' },
  lms_announcement: { title: 'LMS Announcement', execute: 'Post Announcement' },
  calendar_event: { title: 'Calendar Event', execute: 'Create Event' },
}

function EmailRecipientLabel({ to, courseId }: { to: string | string[]; courseId?: string }) {
  // Already a list of emails, or no group to resolve: show directly, no fetch needed
  const staticLabel = Array.isArray(to) ? to.join(', ') : (!courseId ? to : null)
  const [label, setLabel] = useState<string | null>(staticLabel)

  useEffect(() => {
    if (staticLabel !== null) return
    const token = getStoredToken()
    fetch('/api/v1/integrations/resolve-recipients', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ to, course_id: courseId }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setLabel(data.target_label) })
      .catch(() => setLabel(to as string))
  }, [to, courseId, staticLabel])

  return <span className="text-white/60">{label ?? 'Resolving...'}</span>
}

function ExpandableEmailBody({ body }: { body: string }) {
  const [expanded, setExpanded] = useState(false)
  const plainText = body.replace(/<[^>]*>/g, '')
  const isLong = plainText.length > 150

  return (
    <div className="mt-1">
      {expanded ? (
        <div
          className="text-white/40 text-[11px] leading-relaxed prose-sm"
          dangerouslySetInnerHTML={{ __html: body }}
        />
      ) : (
        <div className="text-white/40 text-[11px] leading-relaxed">
          {plainText.slice(0, 150)}{isLong ? '...' : ''}
        </div>
      )}
      {isLong && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[10px] text-[#4488ff]/60 hover:text-[#4488ff] mt-1 transition-colors"
        >
          {expanded ? 'Show less' : 'Show full email'}
        </button>
      )}
    </div>
  )
}

function ActionPreview({ action }: { action: MetaAction }) {
  switch (action.type) {
    case 'draft_email':
      return (
        <div className="space-y-1.5 text-[12px]">
          {Boolean(action.to) && (
            <div className="flex gap-2">
              <span className="text-white/25 shrink-0">To:</span>
              <EmailRecipientLabel to={action.to as string | string[]} courseId={action.course_id as string} />
            </div>
          )}
          {Boolean(action.subject) && (
            <div className="flex gap-2">
              <span className="text-white/25 shrink-0">Subject:</span>
              <span className="text-white/60">{action.subject as string}</span>
            </div>
          )}
          {Boolean(action.body) && (
            <ExpandableEmailBody body={action.body as string} />
          )}
        </div>
      )

    case 'create_doc':
      return (
        <div className="space-y-1.5 text-[12px]">
          <div className="text-white/60 font-medium">{action.title as string}</div>
          {Boolean(action.content) && (
            <div className="text-white/35 text-[11px] line-clamp-3 leading-relaxed">
              {(action.content as string).slice(0, 200)}...
            </div>
          )}
        </div>
      )

    case 'create_sheet':
      return (
        <div className="space-y-1.5 text-[12px]">
          <div className="text-white/60 font-medium">{action.title as string}</div>
          {Boolean(action.headers) && (
            <div className="overflow-x-auto">
              <table className="text-[10px] text-white/40 border-collapse">
                <thead>
                  <tr>
                    {(action.headers as string[]).map((h, i) => (
                      <th key={i} className="px-2 py-1 border border-white/[0.06] text-left font-medium text-white/50">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(action.rows as string[][])?.slice(0, 3).map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j} className="px-2 py-1 border border-white/[0.06]">{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {(action.rows as string[][])?.length > 3 && (
                <div className="text-[10px] text-white/20 mt-1">
                  +{(action.rows as string[][]).length - 3} more rows
                </div>
              )}
            </div>
          )}
        </div>
      )

    case 'create_excel':
      return (
        <div className="space-y-1.5 text-[12px]">
          <div className="text-white/60 font-medium">{action.title as string}</div>
          {Boolean(action.headers) && (
            <div className="overflow-x-auto">
              <table className="text-[10px] text-white/40 border-collapse">
                <thead>
                  <tr>
                    {(action.headers as string[]).map((h, i) => (
                      <th key={i} className="px-2 py-1 border border-white/[0.06] text-left font-medium text-white/50">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {(action.rows as string[][])?.slice(0, 3).map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j} className="px-2 py-1 border border-white/[0.06]">{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {(action.rows as string[][])?.length > 3 && (
                <div className="text-[10px] text-white/20 mt-1">
                  +{(action.rows as string[][]).length - 3} more rows
                </div>
              )}
            </div>
          )}
        </div>
      )

    case 'lms_announcement':
      return (
        <div className="space-y-1.5 text-[12px]">
          <div className="text-white/60 font-medium">{action.title as string}</div>
          {Boolean(action.message) && (
            <div className="text-white/35 text-[11px] line-clamp-3 leading-relaxed">
              {(action.message as string).replace(/<[^>]*>/g, '').slice(0, 200)}
            </div>
          )}
        </div>
      )

    case 'calendar_event':
      return (
        <div className="space-y-1.5 text-[12px]">
          <div className="text-white/60 font-medium">{action.summary as string}</div>
          {Boolean(action.start) && (
            <div className="text-white/35 text-[11px]">
              {new Date(action.start as string).toLocaleString()} — {new Date(action.end as string).toLocaleTimeString()}
            </div>
          )}
          {Boolean(action.attendee_email) && (
            <div className="text-white/30 text-[11px]">With: {action.attendee_email as string}</div>
          )}
        </div>
      )

    default:
      return <div className="text-[11px] text-white/30">Unknown action type</div>
  }
}

export function ActionCard({ action, onDismiss }: Props) {
  const [state, setState] = useState<'preview' | 'executing' | 'done' | 'error'>('preview')
  const [result, setResult] = useState<ExecuteActionResponse | null>(null)

  const labels = ACTION_LABELS[action.type] || { title: action.type, execute: 'Execute' }

  const handleExecute = async () => {
    setState('executing')
    try {
      const { type, ...payload } = action
      const res = await executeAction(type, payload)
      setResult(res)
      setState(res.success ? 'done' : 'error')
    } catch (e) {
      setResult({ success: false, result: {}, error: String(e) })
      setState('error')
    }
  }

  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.02] overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2.5 px-3.5 py-2.5 border-b border-white/[0.06]">
        <div className="w-7 h-7 rounded-lg bg-white/[0.05] flex items-center justify-center shrink-0">
          {ICONS[action.type]}
        </div>
        <span className="text-[12px] font-medium text-white/50">{labels.title}</span>
        {state === 'done' && (
          <span className="ml-auto text-[10px] text-emerald-400/70 flex items-center gap-1">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12" /></svg>
            Done
          </span>
        )}
      </div>

      {/* Preview */}
      <div className="px-3.5 py-3">
        <ActionPreview action={action} />
      </div>

      {/* Actions */}
      {state === 'preview' && (
        <div className="flex items-center gap-2 px-3.5 pb-3">
          <button
            onClick={handleExecute}
            className="px-3 py-1.5 rounded-lg bg-[#4488ff]/15 text-[#4488ff] text-[11px] font-medium hover:bg-[#4488ff]/25 transition-colors"
          >
            {labels.execute}
          </button>
          {onDismiss && (
            <button
              onClick={onDismiss}
              className="px-3 py-1.5 rounded-lg text-[11px] text-white/25 hover:text-white/50 transition-colors"
            >
              Dismiss
            </button>
          )}
        </div>
      )}

      {state === 'executing' && (
        <div className="flex items-center gap-2 px-3.5 pb-3">
          <div className="flex gap-1">
            <span className="w-1 h-1 bg-[#4488ff]/50 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
            <span className="w-1 h-1 bg-[#4488ff]/50 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
            <span className="w-1 h-1 bg-[#4488ff]/50 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
          </div>
          <span className="text-[11px] text-white/25">Executing...</span>
        </div>
      )}

      {state === 'done' && result?.result && (
        <div className="px-3.5 pb-3">
          {(result.result.url as string) && (
            <a
              href={result.result.url as string}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-[#4488ff]/80 hover:text-[#4488ff] transition-colors underline underline-offset-2"
            >
              Open {labels.title} →
            </a>
          )}
        </div>
      )}

      {state === 'error' && (
        <div className="px-3.5 pb-3 space-y-2">
          <div className="text-[11px] text-red-400/70">{result?.error || 'Something went wrong'}</div>
          <button
            onClick={() => setState('preview')}
            className="text-[11px] text-white/30 hover:text-white/50 transition-colors"
          >
            Try again
          </button>
        </div>
      )}
    </div>
  )
}
