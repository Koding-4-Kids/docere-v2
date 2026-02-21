import { Calendar } from 'lucide-react'
import type { MeetingAction } from '../api'

interface MeetingCardProps {
  action: MeetingAction
  onSchedule: () => void
}

export function MeetingCard({ action, onSchedule }: MeetingCardProps) {
  return (
    <div className="mt-3 rounded-xl border border-accent/20 bg-accent/5 p-4 animate-fade-in">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
          <Calendar className="w-4.5 h-4.5 text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-text-200 mb-1">
            Schedule a meeting with your instructor
          </p>
          <p className="text-xs text-text-400 mb-3 leading-relaxed">
            {action.reason}
          </p>
          {action.concepts.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-3">
              {action.concepts.map(concept => (
                <span
                  key={concept}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/15"
                >
                  {concept}
                </span>
              ))}
            </div>
          )}
          <button
            onClick={onSchedule}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-accent hover:bg-accent-hover text-white text-sm font-medium transition-colors"
          >
            <Calendar className="w-3.5 h-3.5" />
            Schedule Meeting
          </button>
        </div>
      </div>
    </div>
  )
}
