import type { InstructorWidget, StudentCardWidget, AtRiskTableWidget, ConceptHeatmapWidget, EngagementChartWidget } from '../api'
import { StudentCard } from './widgets/StudentCard'
import { AtRiskTable } from './widgets/AtRiskTable'
import { ConceptHeatmap } from './widgets/ConceptHeatmap'
import { EngagementChart } from './widgets/EngagementChart'

function SingleWidget({ widget, courseId }: { widget: InstructorWidget; courseId?: string }) {
  switch (widget.type) {
    case 'student_card':
      return <StudentCard widget={widget as StudentCardWidget} />
    case 'at_risk_table':
      return <AtRiskTable widget={widget as AtRiskTableWidget} />
    case 'concept_heatmap':
      return <ConceptHeatmap widget={widget as ConceptHeatmapWidget} courseId={courseId} />
    case 'engagement_chart':
      return <EngagementChart widget={widget as EngagementChartWidget} />
    default:
      return null
  }
}

/** Lays out widgets: full-width ones stacked, half-width ones in a 2-col grid. */
export function InstructorWidgets({ widgets, courseId }: { widgets: InstructorWidget[]; courseId?: string }) {
  if (!widgets.length) return null

  const full = widgets.filter(w => w.type === 'student_card' || w.type === 'at_risk_table')
  const half = widgets.filter(w => w.type === 'concept_heatmap' || w.type === 'engagement_chart')

  return (
    <div className="mt-2 space-y-2">
      {full.map((w, i) => (
        <SingleWidget key={i} widget={w} courseId={courseId} />
      ))}
      {half.length > 0 && (
        <div className={half.length >= 2 ? 'grid grid-cols-2 gap-2' : ''}>
          {half.map((w, i) => (
            <SingleWidget key={`h${i}`} widget={w} courseId={courseId} />
          ))}
        </div>
      )}
    </div>
  )
}

// Keep single-widget export for backward compat
export { SingleWidget as InstructorWidgetRenderer }
