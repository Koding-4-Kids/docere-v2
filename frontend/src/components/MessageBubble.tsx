import { Icons } from './ClaudeChatInput'
import { FileText, Layers, BookOpen, Presentation } from 'lucide-react'
import { MeetingCard } from './MeetingCard'
import { PracticeQuiz } from './PracticeQuiz'
import { StepHints } from './StepHints'
import type { StudyArtifact, MeetingAction, Widget, PracticeQuizWidget, StepHintsWidget } from '../api'

interface MessageBubbleProps {
  role: 'user' | 'assistant'
  content: string
  artifact?: StudyArtifact | null
  action?: MeetingAction | null
  widgets?: Widget[] | null
  onOpenArtifact?: (artifact: StudyArtifact) => void
  onOpenMeetingScheduler?: () => void
}

const ARTIFACT_ICONS: Record<string, typeof FileText> = {
  notes: FileText,
  flashcards: Layers,
  study_guide: BookOpen,
  slides: Presentation,
}

const ARTIFACT_LABELS: Record<string, string> = {
  notes: 'Notes',
  flashcards: 'Flashcards',
  study_guide: 'Study Guide',
  slides: 'Slides',
}

function WidgetRenderer({ widget }: { widget: Widget }) {
  switch (widget.type) {
    case 'practice_quiz':
      return <PracticeQuiz widget={widget as PracticeQuizWidget} />
    case 'step_hints':
      return <StepHints widget={widget as StepHintsWidget} />
    default:
      return null
  }
}

export function MessageBubble({ role, content, artifact, action, widgets, onOpenArtifact, onOpenMeetingScheduler }: MessageBubbleProps) {
  if (role === 'user') {
    return (
      <div className="flex justify-end mb-4 animate-fade-in">
        <div className="max-w-[75%] px-4 py-3 rounded-2xl rounded-br-md bg-accent text-white text-sm leading-relaxed">
          {content}
        </div>
      </div>
    )
  }

  const Icon = artifact ? ARTIFACT_ICONS[artifact.type] || FileText : null

  return (
    <div className="flex justify-start gap-2 mb-4 animate-fade-in">
      <div className="w-6 h-6 shrink-0 mt-1">
        <Icons.Logo className="w-6 h-6" />
      </div>
      <div className="max-w-[75%]">
        <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-bg-200 text-text-100 text-sm leading-relaxed">
          {content}
        </div>
        {artifact && onOpenArtifact && Icon && (
          <button
            onClick={() => onOpenArtifact(artifact)}
            className="mt-2 flex items-center gap-2 px-3 py-2 rounded-xl border border-bg-300 bg-bg-0 hover:bg-bg-200 hover:border-accent/40 transition-all text-xs text-text-300 hover:text-text-200 group"
          >
            <Icon className="w-3.5 h-3.5 text-text-400 group-hover:text-accent transition-colors" />
            <span className="font-medium">{artifact.title}</span>
            <span className="text-text-500">{ARTIFACT_LABELS[artifact.type]}</span>
          </button>
        )}
        {action && onOpenMeetingScheduler && (
          <MeetingCard action={action} onSchedule={onOpenMeetingScheduler} />
        )}
        {widgets && widgets.map((w, i) => (
          <WidgetRenderer key={i} widget={w} />
        ))}
      </div>
    </div>
  )
}
