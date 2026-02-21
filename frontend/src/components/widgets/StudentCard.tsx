import type { StudentCardWidget } from '../../api'

const ENGAGEMENT_DOT: Record<string, string> = {
  high: 'bg-green-400',
  medium: 'bg-yellow-400',
  low: 'bg-orange-400',
  inactive: 'bg-red-400',
  unknown: 'bg-white/20',
}

export function StudentCard({ widget }: { widget: StudentCardWidget }) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">
      {/* Header + stats in one row */}
      <div className="flex items-center gap-3">
        <div className="w-7 h-7 rounded-full bg-white/[0.06] flex items-center justify-center text-[11px] font-medium text-white/50 shrink-0">
          {widget.student_name.charAt(0)}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="text-[12px] font-medium text-white/90 truncate">{widget.student_name}</p>
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${ENGAGEMENT_DOT[widget.engagement_level] || ENGAGEMENT_DOT.unknown}`} />
            <span className="text-[9px] text-white/30 capitalize shrink-0">{widget.engagement_level}</span>
          </div>
          <div className="flex items-center gap-3 mt-0.5 text-[10px] text-white/45">
            <span>{widget.confusion_label}</span>
            <span className="text-white/15">|</span>
            <span>{widget.grade_label}</span>
            <span className="text-white/15">|</span>
            <span>{widget.total_interactions} interactions</span>
          </div>
        </div>
      </div>

      {/* Concepts inline */}
      {widget.top_concepts.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-2">
          {widget.top_concepts.map((c) => (
            <span
              key={c.name}
              className="text-[9px] px-1.5 py-0.5 rounded-full bg-white/[0.05] text-white/45 border border-white/[0.06]"
            >
              {c.name} — {c.mastery_label}
            </span>
          ))}
        </div>
      )}

      {/* Summary */}
      {widget.profile_summary && (
        <p className="text-[10px] text-white/35 leading-relaxed mt-2">{widget.profile_summary}</p>
      )}
    </div>
  )
}
