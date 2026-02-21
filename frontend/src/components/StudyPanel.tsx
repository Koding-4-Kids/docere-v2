import { useState } from 'react'
import { X, ChevronLeft, ChevronRight, RotateCcw, BookOpen, Layers, FileText, Presentation, Eye } from 'lucide-react'
import { useTypewriter } from '../hooks/useTypewriter'
import type { StudyArtifact } from '../api'

interface StudyPanelProps {
  artifact: StudyArtifact | null
  isGenerating: boolean
  onClose: () => void
}

const TYPE_META: Record<string, { label: string; icon: typeof BookOpen; color: string }> = {
  notes: { label: 'Notes', icon: FileText, color: 'text-blue-500 bg-blue-500/10' },
  flashcards: { label: 'Flashcards', icon: Layers, color: 'text-purple-500 bg-purple-500/10' },
  study_guide: { label: 'Study Guide', icon: BookOpen, color: 'text-green-500 bg-green-500/10' },
  slides: { label: 'Slides', icon: Presentation, color: 'text-orange-500 bg-orange-500/10' },
}

export function StudyPanel({ artifact, isGenerating, onClose }: StudyPanelProps) {
  const meta = artifact ? TYPE_META[artifact.type] : null

  return (
    <div className="w-[480px] shrink-0 border-l border-bg-300 bg-bg-100 flex flex-col animate-slide-in-right">
      {/* Header */}
      <div className="px-4 py-3 border-b border-bg-300 flex items-center gap-3">
        {meta && (
          <span className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium ${meta.color}`}>
            <meta.icon className="w-3.5 h-3.5" />
            {meta.label}
          </span>
        )}
        <span className="text-sm font-medium text-text-200 truncate flex-1">
          {artifact?.title || 'Study Materials'}
        </span>
        <button
          onClick={onClose}
          className="p-1 rounded-md hover:bg-bg-200 text-text-400 hover:text-text-200 transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-5">
        {isGenerating && !artifact && (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="flex gap-1.5">
              <span className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 rounded-full bg-accent animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <p className="text-sm text-text-400">Generating study materials...</p>
          </div>
        )}

        {artifact && artifact.type === 'flashcards' && (
          <FlashcardViewer content={artifact.content} />
        )}

        {artifact && artifact.type === 'slides' && (
          <SlidesViewer content={artifact.content} />
        )}

        {artifact && (artifact.type === 'notes' || artifact.type === 'study_guide') && (
          <MarkdownContent content={artifact.content} />
        )}
      </div>
    </div>
  )
}

// ── Markdown renderer with typewriter ──

function MarkdownContent({ content }: { content: string }) {
  const { displayedText, isComplete, showAll } = useTypewriter({ text: content })

  return (
    <div className="relative">
      {!isComplete && (
        <button
          onClick={showAll}
          className="absolute top-0 right-0 flex items-center gap-1 px-2 py-1 rounded-md text-xs text-text-400 hover:text-text-200 hover:bg-bg-200 transition-colors"
        >
          <Eye className="w-3 h-3" />
          Show all
        </button>
      )}
      <div className="prose-sm">
        {displayedText.split('\n').map((line, i) => (
          <MarkdownLine key={i} line={line} />
        ))}
        {!isComplete && <span className="inline-block w-0.5 h-4 bg-accent animate-pulse ml-0.5" />}
      </div>
    </div>
  )
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

// ── Flashcard viewer ──

interface Flashcard {
  front: string
  back: string
}

function FlashcardViewer({ content }: { content: string }) {
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)

  let cards: Flashcard[] = []
  try {
    cards = JSON.parse(content)
  } catch {
    return <p className="text-sm text-text-400">Failed to load flashcards.</p>
  }

  if (!cards.length) return <p className="text-sm text-text-400">No flashcards generated.</p>

  const card = cards[index]

  return (
    <div className="flex flex-col items-center gap-4">
      <p className="text-xs text-text-500">{index + 1} / {cards.length}</p>

      {/* Card */}
      <div
        onClick={() => setFlipped(f => !f)}
        className="w-full cursor-pointer"
        style={{ perspective: '1000px' }}
      >
        <div
          className="relative w-full transition-transform duration-500"
          style={{
            transformStyle: 'preserve-3d',
            transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
          }}
        >
          {/* Front */}
          <div
            className="w-full min-h-[200px] flex flex-col items-center justify-center p-6 rounded-xl border border-bg-300 bg-bg-0"
            style={{ backfaceVisibility: 'hidden' }}
          >
            <p className="text-base text-text-100 text-center leading-relaxed">{card.front}</p>
            <p className="text-xs text-text-500 mt-4">Click to flip</p>
          </div>

          {/* Back */}
          <div
            className="absolute inset-0 w-full min-h-[200px] flex flex-col items-center justify-center p-6 rounded-xl border border-accent/30 bg-accent/5"
            style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
          >
            <p className="text-base text-text-100 text-center leading-relaxed">{card.back}</p>
            <p className="text-xs text-text-500 mt-4">Click to flip back</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => { setIndex(i => Math.max(0, i - 1)); setFlipped(false) }}
          disabled={index === 0}
          className="p-2 rounded-lg border border-bg-300 hover:bg-bg-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-4 h-4 text-text-300" />
        </button>
        <button
          onClick={() => { setFlipped(false); setIndex(0) }}
          className="p-2 rounded-lg border border-bg-300 hover:bg-bg-200 transition-colors"
          title="Restart"
        >
          <RotateCcw className="w-4 h-4 text-text-300" />
        </button>
        <button
          onClick={() => { setIndex(i => Math.min(cards.length - 1, i + 1)); setFlipped(false) }}
          disabled={index === cards.length - 1}
          className="p-2 rounded-lg border border-bg-300 hover:bg-bg-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-4 h-4 text-text-300" />
        </button>
      </div>
    </div>
  )
}

// ── Slides viewer ──

interface Slide {
  title: string
  bullets: string[]
}

function SlidesViewer({ content }: { content: string }) {
  const [index, setIndex] = useState(0)

  let slides: Slide[] = []
  try {
    slides = JSON.parse(content)
  } catch {
    return <p className="text-sm text-text-400">Failed to load slides.</p>
  }

  if (!slides.length) return <p className="text-sm text-text-400">No slides generated.</p>

  const slide = slides[index]

  return (
    <div className="flex flex-col gap-4">
      <p className="text-xs text-text-500 text-center">Slide {index + 1} / {slides.length}</p>

      {/* Slide card (16:10 aspect ratio) */}
      <div className="w-full rounded-xl border border-bg-300 bg-bg-0 overflow-hidden" style={{ aspectRatio: '16/10' }}>
        <div className="h-full flex flex-col p-6">
          <h2 className="text-lg font-semibold text-text-100 mb-4">{slide.title}</h2>
          <ul className="flex-1 space-y-2.5">
            {slide.bullets.map((bullet, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-text-200">
                <span className="w-1.5 h-1.5 rounded-full bg-accent mt-1.5 shrink-0" />
                {bullet}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex items-center justify-center gap-3">
        <button
          onClick={() => setIndex(i => Math.max(0, i - 1))}
          disabled={index === 0}
          className="p-2 rounded-lg border border-bg-300 hover:bg-bg-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft className="w-4 h-4 text-text-300" />
        </button>
        <div className="flex gap-1">
          {slides.map((_, i) => (
            <button
              key={i}
              onClick={() => setIndex(i)}
              className={`w-2 h-2 rounded-full transition-colors ${i === index ? 'bg-accent' : 'bg-bg-300'}`}
            />
          ))}
        </div>
        <button
          onClick={() => setIndex(i => Math.min(slides.length - 1, i + 1))}
          disabled={index === slides.length - 1}
          className="p-2 rounded-lg border border-bg-300 hover:bg-bg-200 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight className="w-4 h-4 text-text-300" />
        </button>
      </div>
    </div>
  )
}
