import { useState } from 'react'
import type { StepHintsWidget } from '../api'

export function StepHints({ widget }: { widget: StepHintsWidget }) {
  const [revealedCount, setRevealedCount] = useState(1)

  const allRevealed = revealedCount >= widget.hints.length

  return (
    <div className="mt-2.5 rounded-xl border border-bg-300 bg-bg-0 p-3.5 animate-fade-in">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[13px] font-medium text-text-200">{widget.title}</p>
        <span className="text-[10px] text-text-500">{revealedCount}/{widget.hints.length}</span>
      </div>

      {widget.problem_context && (
        <p className="text-[11px] text-text-400 mb-2">{widget.problem_context}</p>
      )}

      <div className="space-y-1.5">
        {widget.hints.map((hint, i) => {
          const isRevealed = i < revealedCount
          return (
            <div key={i} className="flex items-start gap-2">
              <span className={`w-4 h-4 rounded-full flex items-center justify-center shrink-0 text-[9px] font-bold mt-0.5 ${isRevealed ? 'bg-accent/15 text-accent' : 'bg-bg-300 text-text-500'}`}>
                {i + 1}
              </span>
              <p className={`text-[12px] leading-relaxed ${isRevealed ? 'text-text-200' : 'text-text-500 italic'}`}>
                {isRevealed ? hint.text : 'Reveal to see this hint'}
              </p>
            </div>
          )
        })}
      </div>

      {!allRevealed && (
        <button
          onClick={() => setRevealedCount(c => c + 1)}
          className="mt-2 px-3 py-1.5 rounded-lg bg-bg-200 hover:bg-bg-300 text-text-300 text-[11px] font-medium transition-colors"
        >
          Show next hint
        </button>
      )}
    </div>
  )
}
