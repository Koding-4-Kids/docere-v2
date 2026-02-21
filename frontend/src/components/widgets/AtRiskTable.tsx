import type { AtRiskTableWidget } from '../../api'

const ENGAGEMENT_COLOR: Record<string, string> = {
  high: 'text-green-400/70',
  medium: 'text-yellow-400/70',
  low: 'text-orange-400/70',
  inactive: 'text-red-400/70',
  unknown: 'text-white/30',
}

export function AtRiskTable({ widget }: { widget: AtRiskTableWidget }) {
  if (!widget.students.length) return null

  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">
      <div className="flex items-center gap-2 mb-2">
        <span className="w-1.5 h-1.5 rounded-full bg-red-400/60" />
        <p className="text-[12px] font-medium text-white/70">{widget.title}</p>
        <span className="text-[10px] text-white/25">{widget.students.length}</span>
      </div>

      <div className="space-y-1">
        {widget.students.map((s) => (
          <div
            key={s.student_id}
            className="flex items-start gap-2 rounded-lg bg-white/[0.02] border border-white/[0.04] px-2.5 py-1.5"
          >
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-medium text-white/80 truncate">{s.student_name}</span>
                <span className={`text-[9px] capitalize shrink-0 ${ENGAGEMENT_COLOR[s.engagement_level] || ENGAGEMENT_COLOR.unknown}`}>
                  {s.engagement_level}
                </span>
                <span className="text-[9px] text-white/25 shrink-0">{s.grade_label}</span>
              </div>
              <p className="text-[10px] text-white/40 mt-0.5 line-clamp-1">{s.risk_reason}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
