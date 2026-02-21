import { useState } from 'react'
import type { EngagementChartWidget } from '../../api'

const LEVEL_COLORS: Record<string, { bar: string; text: string }> = {
  high: { bar: 'bg-green-400/50', text: 'text-green-400/70' },
  medium: { bar: 'bg-yellow-400/50', text: 'text-yellow-400/70' },
  low: { bar: 'bg-orange-400/50', text: 'text-orange-400/70' },
  inactive: { bar: 'bg-red-400/50', text: 'text-red-400/70' },
  unknown: { bar: 'bg-white/20', text: 'text-white/30' },
}

const LEVEL_ORDER = ['high', 'medium', 'low', 'inactive', 'unknown']

export function EngagementChart({ widget }: { widget: EngagementChartWidget }) {
  const [expandedLevel, setExpandedLevel] = useState<string | null>(null)

  const sorted = [...widget.buckets].sort(
    (a, b) => LEVEL_ORDER.indexOf(a.level) - LEVEL_ORDER.indexOf(b.level)
  )

  const maxCount = Math.max(...sorted.map(b => b.count), 1)

  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[12px] font-medium text-white/70">{widget.title}</p>
        <span className="text-[10px] text-white/25">{widget.total_students} students</span>
      </div>

      <div className="space-y-1.5">
        {sorted.map((bucket) => {
          const colors = LEVEL_COLORS[bucket.level] || LEVEL_COLORS.unknown
          const widthPct = (bucket.count / maxCount) * 100
          const isExpanded = expandedLevel === bucket.level

          return (
            <div key={bucket.level}>
              <button
                onClick={() => setExpandedLevel(isExpanded ? null : bucket.level)}
                className="w-full text-left"
              >
                <div className="flex items-center gap-2">
                  <span className={`text-[10px] capitalize font-medium w-14 ${colors.text}`}>
                    {bucket.level}
                  </span>
                  <div className="flex-1 h-2.5 rounded bg-white/[0.04] overflow-hidden">
                    <div
                      className={`h-full rounded ${colors.bar} transition-all`}
                      style={{ width: `${widthPct}%` }}
                    />
                  </div>
                  <span className="text-[10px] text-white/40 w-5 text-right">{bucket.count}</span>
                  {bucket.student_names.length > 0 && (
                    <svg
                      className={`w-3 h-3 text-white/20 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  )}
                </div>
              </button>
              {isExpanded && bucket.student_names.length > 0 && (
                <p className="ml-16 mt-0.5 mb-0.5 text-[9px] text-white/25 leading-relaxed">
                  {bucket.student_names.join(', ')}
                </p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
