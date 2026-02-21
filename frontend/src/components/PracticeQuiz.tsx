import { useState } from 'react'
import type { PracticeQuizWidget } from '../api'

export function PracticeQuiz({ widget }: { widget: PracticeQuizWidget }) {
  const [currentQ, setCurrentQ] = useState(0)
  const [selectedChoice, setSelectedChoice] = useState<number | null>(null)
  const [textAnswer, setTextAnswer] = useState('')
  const [revealed, setRevealed] = useState(false)
  const [score, setScore] = useState(0)
  const [finished, setFinished] = useState(false)

  const q = widget.questions[currentQ]
  if (!q) return null

  const isMultipleChoice = q.choices && q.choices.length > 0

  const handleCheck = () => {
    if (revealed) return
    setRevealed(true)
    if (isMultipleChoice && selectedChoice === q.correct_index) {
      setScore(s => s + 1)
    }
  }

  const handleNext = () => {
    if (currentQ + 1 >= widget.questions.length) {
      setFinished(true)
      return
    }
    setCurrentQ(i => i + 1)
    setSelectedChoice(null)
    setTextAnswer('')
    setRevealed(false)
  }

  const handleReset = () => {
    setCurrentQ(0)
    setSelectedChoice(null)
    setTextAnswer('')
    setRevealed(false)
    setScore(0)
    setFinished(false)
  }

  if (finished) {
    return (
      <div className="mt-2.5 rounded-xl border border-bg-300 bg-bg-0 p-3.5 animate-fade-in">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[13px] font-medium text-text-200">{widget.title}</p>
            <p className="text-[11px] text-text-400 mt-0.5">
              {score} / {widget.questions.length} correct
            </p>
          </div>
          <button
            onClick={handleReset}
            className="px-3 py-1.5 rounded-lg bg-bg-200 hover:bg-bg-300 text-text-300 text-[11px] font-medium transition-colors"
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-2.5 rounded-xl border border-bg-300 bg-bg-0 p-3.5 animate-fade-in">
      {/* Header row */}
      <div className="flex items-center justify-between mb-2.5">
        <p className="text-[13px] font-medium text-text-200">{widget.title}</p>
        <span className="text-[10px] text-text-500">{currentQ + 1}/{widget.questions.length}</span>
      </div>

      {/* Progress bar */}
      <div className="w-full h-0.5 rounded-full bg-bg-300 mb-2.5">
        <div
          className="h-0.5 rounded-full bg-accent transition-all"
          style={{ width: `${((currentQ + 1) / widget.questions.length) * 100}%` }}
        />
      </div>

      <p className="text-[12px] text-text-200 mb-2">{q.question}</p>

      {isMultipleChoice ? (
        <div className="space-y-1.5 mb-2.5">
          {q.choices.map((choice, i) => {
            let style = 'border-bg-300 bg-bg-100'
            if (revealed && i === q.correct_index) style = 'border-green-500/40 bg-green-500/5'
            else if (revealed && i === selectedChoice) style = 'border-red-500/40 bg-red-500/5'
            else if (i === selectedChoice) style = 'border-accent/40 bg-accent/5'

            return (
              <button
                key={i}
                onClick={() => !revealed && setSelectedChoice(i)}
                className={`w-full text-left px-3 py-1.5 rounded-lg border text-[12px] text-text-200 transition-all ${style} ${!revealed ? 'hover:border-accent/30 cursor-pointer' : 'cursor-default'}`}
              >
                {choice}
              </button>
            )
          })}
        </div>
      ) : (
        <div className="mb-2.5">
          <input
            type="text"
            value={textAnswer}
            onChange={e => setTextAnswer(e.target.value)}
            placeholder="Type your answer..."
            disabled={revealed}
            className="w-full px-3 py-1.5 rounded-lg border border-bg-300 bg-bg-100 text-[12px] text-text-200 placeholder:text-text-500 focus:outline-none focus:border-accent/40"
          />
          {revealed && (
            <p className="mt-1.5 text-[11px] text-green-600 dark:text-green-400">Answer: {q.correct_answer}</p>
          )}
        </div>
      )}

      {revealed && q.explanation && (
        <p className="text-[11px] text-text-400 mb-2.5 italic">{q.explanation}</p>
      )}

      <div className="flex gap-2">
        {!revealed ? (
          <button
            onClick={handleCheck}
            disabled={isMultipleChoice ? selectedChoice === null : !textAnswer.trim()}
            className="px-3 py-1.5 rounded-lg bg-accent hover:bg-accent-hover disabled:opacity-30 disabled:cursor-not-allowed text-white text-[11px] font-medium transition-colors"
          >
            Check
          </button>
        ) : (
          <button
            onClick={handleNext}
            className="px-3 py-1.5 rounded-lg bg-accent hover:bg-accent-hover text-white text-[11px] font-medium transition-colors"
          >
            {currentQ + 1 >= widget.questions.length ? 'Results' : 'Next'}
          </button>
        )}
      </div>
    </div>
  )
}
