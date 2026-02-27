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

function MarkdownLine({ line }: { line: string }) {
  const trimmed = line.trim()
  if (!trimmed) return <div className="h-3" />

  if (trimmed.startsWith('### '))
    return <h3 className="text-sm font-semibold text-text-100 mt-4 mb-1.5">{renderInline(trimmed.slice(4))}</h3>
  if (trimmed.startsWith('## '))
    return <h2 className="text-base font-semibold text-text-100 mt-5 mb-2">{renderInline(trimmed.slice(3))}</h2>
  if (trimmed.startsWith('# '))
    return <h1 className="text-lg font-bold text-text-100 mt-5 mb-2">{renderInline(trimmed.slice(2))}</h1>
  if (trimmed.startsWith('- ') || trimmed.startsWith('* '))
    return <li className="text-sm text-text-200 ml-4 mb-1 list-disc">{renderInline(trimmed.slice(2))}</li>
  if (/^\d+\.\s/.test(trimmed)) {
    const text = trimmed.replace(/^\d+\.\s/, '')
    return <li className="text-sm text-text-200 ml-4 mb-1 list-decimal">{renderInline(text)}</li>
  }
  if (trimmed.startsWith('```'))
    return <div className="font-mono text-xs bg-bg-200 px-3 py-1 rounded text-text-300">{trimmed.slice(3)}</div>

  return <p className="text-sm text-text-200 mb-2 leading-relaxed">{renderInline(trimmed)}</p>
}

function renderInline(text: string): (string | JSX.Element)[] {
  const parts: (string | JSX.Element)[] = []
  let remaining = text
  let key = 0
  while (remaining) {
    const boldMatch = remaining.match(/\*\*(.+?)\*\*/)
    const codeMatch = remaining.match(/`(.+?)`/)

    // Pick whichever comes first
    const boldIdx = boldMatch?.index ?? Infinity
    const codeIdx = codeMatch?.index ?? Infinity

    if (boldIdx === Infinity && codeIdx === Infinity) {
      parts.push(remaining)
      break
    }

    if (boldIdx <= codeIdx && boldMatch) {
      parts.push(remaining.slice(0, boldIdx))
      parts.push(<strong key={key++} className="font-semibold text-text-100">{boldMatch[1]}</strong>)
      remaining = remaining.slice(boldIdx + boldMatch[0].length)
    } else if (codeMatch) {
      parts.push(remaining.slice(0, codeIdx))
      parts.push(
        <code key={key++} className="px-1 py-0.5 rounded bg-bg-200 text-xs font-mono text-accent">{codeMatch[1]}</code>
      )
      remaining = remaining.slice(codeIdx + codeMatch[0].length)
    }
  }
  return parts
}

export function MessageBubble({ role, content, artifact, action, widgets, onOpenArtifact, onOpenMeetingScheduler }: MessageBubbleProps) {
  if (role === 'user') {
    return (
      <div className="flex justify-end mb-5 animate-fade-in">
        <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-br-md bg-accent/15 text-text-100 text-[14px] leading-relaxed">
          <div className="whitespace-pre-wrap">{content}</div>
        </div>
      </div>
    )
  }

  const Icon = artifact ? ARTIFACT_ICONS[artifact.type] || FileText : null

  return (
    <div className="flex justify-start gap-3 mb-5 animate-fade-in">
      <div className="w-7 h-7 shrink-0 mt-1">
        <Icons.Logo className="w-7 h-7 opacity-70" />
      </div>
      <div className="max-w-[80%]">
        <div className="px-4 py-3 rounded-2xl rounded-bl-md bg-bg-200/70 text-text-100 text-[14px] leading-relaxed">
          {content.split('\n').map((line, i) => (
            <MarkdownLine key={i} line={line} />
          ))}
        </div>
        {artifact && onOpenArtifact && Icon && (
          <button
            onClick={() => onOpenArtifact(artifact)}
            className="mt-2 flex items-center gap-2 px-3 py-2 rounded-xl border border-bg-300/70 bg-bg-0 hover:bg-bg-200 hover:border-accent/40 transition-all text-xs text-text-300 hover:text-text-200 group"
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
