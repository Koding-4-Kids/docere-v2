import { useState, useEffect } from 'react'
import { X, Calendar, Clock, Check, Loader2 } from 'lucide-react'
import * as api from '../api'
import type { TimeSlot, MeetingAction } from '../api'

interface MeetingSchedulerProps {
  courseId: string
  conversationId: string | null
  action: MeetingAction | null
  onClose: () => void
  onBooked: () => void
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
}

function formatTime(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

export function MeetingScheduler({ courseId, conversationId, action, onClose, onBooked }: MeetingSchedulerProps) {
  const [slots, setSlots] = useState<TimeSlot[]>([])
  const [loading, setLoading] = useState(true)
  const [booking, setBooking] = useState(false)
  const [booked, setBooked] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedSlot, setSelectedSlot] = useState<TimeSlot | null>(null)

  useEffect(() => {
    api.getAvailableSlots(courseId)
      .then(data => {
        setSlots(data)
        setLoading(false)
      })
      .catch(() => {
        setError('Failed to load available times')
        setLoading(false)
      })
  }, [courseId])

  const handleBook = async () => {
    if (!selectedSlot) return
    setBooking(true)
    setError(null)
    try {
      await api.bookMeeting(
        courseId,
        selectedSlot.instructor_id,
        selectedSlot.start,
        selectedSlot.end,
        conversationId || undefined,
      )
      setBooked(true)
      setTimeout(() => {
        onBooked()
        onClose()
      }, 2000)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to book meeting')
      setBooking(false)
    }
  }

  // Group slots by date
  const slotsByDate: Record<string, TimeSlot[]> = {}
  for (const slot of slots) {
    const dateKey = formatDate(slot.start)
    if (!slotsByDate[dateKey]) slotsByDate[dateKey] = []
    slotsByDate[dateKey].push(slot)
  }

  return (
    <div className="w-[400px] border-l border-bg-300 bg-bg-100 flex flex-col animate-slide-in-right">
      {/* Header */}
      <div className="px-5 py-4 border-b border-bg-300 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <Calendar className="w-4 h-4 text-accent" />
          </div>
          <div>
            <h2 className="text-sm font-medium text-text-100">Schedule Meeting</h2>
            <p className="text-[10px] text-text-400">Pick a time that works for you</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="w-7 h-7 rounded-lg flex items-center justify-center text-text-400 hover:text-text-200 hover:bg-bg-200 transition-all"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Context */}
      {action && action.concepts.length > 0 && (
        <div className="px-5 py-3 border-b border-bg-300 bg-accent/5">
          <p className="text-[10px] uppercase tracking-wider text-text-500 mb-1.5">Topics to discuss</p>
          <div className="flex flex-wrap gap-1.5">
            {action.concepts.map(c => (
              <span key={c} className="text-[11px] px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/15">
                {c}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-5 py-4">
        {loading && (
          <div className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-text-400 animate-spin mb-3" />
            <p className="text-sm text-text-400">Loading available times...</p>
          </div>
        )}

        {error && (
          <div className="text-center py-12">
            <p className="text-sm text-red-500 mb-2">{error}</p>
            <button
              onClick={() => { setError(null); setLoading(true); api.getAvailableSlots(courseId).then(setSlots).finally(() => setLoading(false)) }}
              className="text-xs text-accent hover:underline"
            >
              Try again
            </button>
          </div>
        )}

        {booked && (
          <div className="flex flex-col items-center justify-center py-12 animate-fade-in">
            <div className="w-12 h-12 rounded-full bg-green-500/10 flex items-center justify-center mb-4">
              <Check className="w-6 h-6 text-green-500" />
            </div>
            <p className="text-sm font-medium text-text-200 mb-1">Meeting Booked!</p>
            <p className="text-xs text-text-400">You'll receive a calendar invite</p>
          </div>
        )}

        {!loading && !error && !booked && slots.length === 0 && (
          <div className="text-center py-12">
            <Calendar className="w-8 h-8 text-text-400 mx-auto mb-3" />
            <p className="text-sm text-text-300 mb-1">No available slots</p>
            <p className="text-xs text-text-400">Your instructor hasn't set up office hours yet</p>
          </div>
        )}

        {!loading && !error && !booked && Object.entries(slotsByDate).map(([date, dateSlots]) => (
          <div key={date} className="mb-5">
            <p className="text-[11px] font-medium text-text-300 mb-2 uppercase tracking-wider">{date}</p>
            <div className="grid grid-cols-2 gap-2">
              {dateSlots.map((slot, i) => {
                const isSelected = selectedSlot?.start === slot.start
                return (
                  <button
                    key={i}
                    onClick={() => setSelectedSlot(isSelected ? null : slot)}
                    className={`flex items-center gap-2 px-3 py-2.5 rounded-xl border text-sm transition-all ${
                      isSelected
                        ? 'border-accent bg-accent/10 text-accent'
                        : 'border-bg-300 bg-bg-0 text-text-300 hover:bg-bg-200 hover:border-accent/30'
                    }`}
                  >
                    <Clock className="w-3.5 h-3.5 shrink-0" />
                    <span>{formatTime(slot.start)}</span>
                  </button>
                )
              })}
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      {!booked && selectedSlot && (
        <div className="px-5 py-4 border-t border-bg-300">
          <div className="text-xs text-text-400 mb-3">
            {formatDate(selectedSlot.start)} at {formatTime(selectedSlot.start)} - {formatTime(selectedSlot.end)}
          </div>
          <button
            onClick={handleBook}
            disabled={booking}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-accent hover:bg-accent-hover disabled:opacity-50 text-white text-sm font-medium transition-colors"
          >
            {booking ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Booking...
              </>
            ) : (
              <>
                <Calendar className="w-4 h-4" />
                Confirm Booking
              </>
            )}
          </button>
        </div>
      )}
    </div>
  )
}
