import { useState, useEffect } from 'react'
import { Calendar, Plus, Trash2, Check, Loader2 } from 'lucide-react'
import { getStoredToken } from '../api'

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

interface OfficeHoursBlock {
  id: string
  day_of_week: number
  start_time: string
  end_time: string
  timezone: string
  slot_duration_minutes: number
  is_active: boolean
}

interface CalendarSetupProps {
  courseId: string
}

export function CalendarSetup({ courseId }: CalendarSetupProps) {
  const [connected, setConnected] = useState(false)
  const [checkingStatus, setCheckingStatus] = useState(true)
  const [officeHours, setOfficeHours] = useState<OfficeHoursBlock[]>([])
  const [adding, setAdding] = useState(false)

  // New office hours form
  const [newDay, setNewDay] = useState(0)
  const [newStart, setNewStart] = useState('09:00')
  const [newEnd, setNewEnd] = useState('11:00')

  const token = getStoredToken()
  const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {}
  const jsonHeaders = { ...headers, 'Content-Type': 'application/json' }

  useEffect(() => {
    // Check calendar status
    fetch('/api/v1/calendar/status', { headers })
      .then(r => r.ok ? r.json() : { connected: false })
      .then(data => {
        setConnected(data.connected)
        setCheckingStatus(false)
      })
      .catch(() => setCheckingStatus(false))

    // Load office hours
    fetch(`/api/v1/calendar/office-hours/${courseId}`, { headers })
      .then(r => r.ok ? r.json() : [])
      .then(setOfficeHours)
      .catch(() => {})

    // Listen for OAuth popup result
    const handleMessage = (e: MessageEvent) => {
      if (e.data?.type === 'google-oauth-callback') {
        setConnected(e.data.status === 'success')
      }
    }
    window.addEventListener('message', handleMessage)
    return () => window.removeEventListener('message', handleMessage)
  }, [courseId])

  const handleConnectCalendar = () => {
    fetch('/api/v1/calendar/oauth/authorize', { headers })
      .then(r => r.json())
      .then(data => {
        window.open(data.url, '_blank', 'width=600,height=700')
      })
      .catch(() => {})
  }

  const handleDisconnect = () => {
    fetch('/api/v1/calendar/disconnect', { method: 'DELETE', headers })
      .then(() => setConnected(false))
      .catch(() => {})
  }

  const handleAddOfficeHours = () => {
    setAdding(true)
    fetch(`/api/v1/calendar/office-hours/${courseId}`, {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({
        day_of_week: newDay,
        start_time: newStart,
        end_time: newEnd,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      }),
    })
      .then(r => r.json())
      .then(oh => {
        setOfficeHours(prev => [...prev, oh])
        setAdding(false)
      })
      .catch(() => setAdding(false))
  }

  const handleDeleteOfficeHours = (id: string) => {
    fetch(`/api/v1/calendar/office-hours/${id}`, { method: 'DELETE', headers })
      .then(() => setOfficeHours(prev => prev.filter(oh => oh.id !== id)))
      .catch(() => {})
  }

  if (checkingStatus) {
    return (
      <div className="flex items-center gap-2 text-white/40 text-sm py-3">
        <Loader2 className="w-4 h-4 animate-spin" />
        Checking calendar...
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Calendar Connection */}
      <div className="flex items-center justify-between bg-white/[0.03] rounded-xl border border-white/10 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${connected ? 'bg-green-500/10' : 'bg-white/5'}`}>
            {connected ? <Check className="w-4 h-4 text-green-400" /> : <Calendar className="w-4 h-4 text-white/40" />}
          </div>
          <div>
            <p className="text-sm text-white/80">
              {connected ? 'Google Calendar connected' : 'Connect Google Calendar'}
            </p>
            <p className="text-[11px] text-white/30">
              {connected ? 'Students can book during your office hours' : 'Required to enable meeting scheduling'}
            </p>
          </div>
        </div>
        {connected ? (
          <button
            onClick={handleDisconnect}
            className="text-xs text-white/30 hover:text-red-400 transition-colors"
          >
            Disconnect
          </button>
        ) : (
          <button
            onClick={handleConnectCalendar}
            className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/10 hover:bg-white/15 text-sm text-white/70 transition-colors"
          >
            <svg width="16" height="16" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
            </svg>
            Connect
          </button>
        )}
      </div>

      {/* Office Hours */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <p className="text-xs uppercase tracking-wider text-white/30">Office Hours</p>
        </div>

        {/* Existing blocks */}
        <div className="space-y-2 mb-3">
          {officeHours.map(oh => (
            <div key={oh.id} className="flex items-center justify-between bg-white/[0.03] rounded-lg border border-white/10 px-3 py-2">
              <div className="flex items-center gap-3">
                <span className="text-sm text-white/70 font-medium w-24">{DAYS[oh.day_of_week]}</span>
                <span className="text-sm text-white/50">
                  {oh.start_time} - {oh.end_time}
                </span>
                <span className="text-[10px] text-white/25">{oh.slot_duration_minutes}min slots</span>
              </div>
              <button
                onClick={() => handleDeleteOfficeHours(oh.id)}
                className="text-white/20 hover:text-red-400 transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          ))}
        </div>

        {/* Add new */}
        <div className="flex items-end gap-2">
          <select
            value={newDay}
            onChange={e => setNewDay(parseInt(e.target.value))}
            className="bg-white/[0.04] border border-white/10 rounded-lg px-2 py-1.5 text-sm text-white/70 outline-none"
          >
            {DAYS.map((d, i) => <option key={i} value={i}>{d}</option>)}
          </select>
          <input
            type="time"
            value={newStart}
            onChange={e => setNewStart(e.target.value)}
            className="bg-white/[0.04] border border-white/10 rounded-lg px-2 py-1.5 text-sm text-white/70 outline-none"
          />
          <span className="text-white/30 text-sm pb-1.5">to</span>
          <input
            type="time"
            value={newEnd}
            onChange={e => setNewEnd(e.target.value)}
            className="bg-white/[0.04] border border-white/10 rounded-lg px-2 py-1.5 text-sm text-white/70 outline-none"
          />
          <button
            onClick={handleAddOfficeHours}
            disabled={adding}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#4488ff]/15 hover:bg-[#4488ff]/25 text-[#88bbff] text-sm transition-colors disabled:opacity-50"
          >
            {adding ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
            Add
          </button>
        </div>
      </div>
    </div>
  )
}
