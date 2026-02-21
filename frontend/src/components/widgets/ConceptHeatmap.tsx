import { useState } from 'react'
import type { ConceptHeatmapWidget, HeatmapCell } from '../../api'
import { addConcept } from '../../api'

function masteryStyle(value: number): string {
  if (value >= 0.75) return 'bg-green-400/10 border-green-400/15 text-green-400/80'
  if (value >= 0.55) return 'bg-emerald-400/8 border-emerald-400/12 text-emerald-400/70'
  if (value >= 0.35) return 'bg-yellow-400/8 border-yellow-400/12 text-yellow-400/70'
  if (value >= 0.2) return 'bg-orange-400/8 border-orange-400/12 text-orange-400/70'
  return 'bg-red-400/8 border-red-400/12 text-red-400/70'
}

interface Props {
  widget: ConceptHeatmapWidget
  courseId?: string
}

type Mode = 'idle' | 'input' | 'confirm' | 'loading'

export function ConceptHeatmap({ widget, courseId }: Props) {
  const [extraCells, setExtraCells] = useState<HeatmapCell[]>([])
  const [mode, setMode] = useState<Mode>('idle')
  const [inputValue, setInputValue] = useState('')
  const [error, setError] = useState<string | null>(null)

  const allCells = [...widget.cells, ...extraCells]

  if (!allCells.length && mode === 'idle' && !courseId) return null

  const handleAdd = async () => {
    if (!courseId || !inputValue.trim()) return
    setMode('loading')
    setError(null)
    try {
      const result = await addConcept(courseId, inputValue.trim())
      setExtraCells(prev => [...prev, result.cell])
      setInputValue('')
      setMode('idle')
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to add concept'
      setError(msg)
      setMode('input')
    }
  }

  return (
    <div className="rounded-xl border border-white/[0.08] bg-white/[0.03] p-3">
      <p className="text-[12px] font-medium text-white/70 mb-2">{widget.title}</p>

      {allCells.length > 0 && (
        <div className="grid grid-cols-3 gap-1">
          {allCells.map((cell) => (
            <div
              key={cell.concept}
              className={`rounded-lg border px-2 py-1 ${masteryStyle(cell.mastery_value)}`}
            >
              <p className="text-[10px] font-medium truncate">{cell.concept}</p>
              <div className="flex items-center justify-between mt-0.5">
                <span className="text-[9px] opacity-60">{cell.mastery_label}</span>
                <span className="text-[8px] opacity-35">{cell.student_count}s</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {courseId && (
        <div className={allCells.length > 0 ? 'mt-2 pt-2 border-t border-white/[0.06]' : ''}>
          {mode === 'idle' && (
            <button
              onClick={() => { setMode('input'); setError(null) }}
              className="text-[10px] text-white/30 hover:text-white/60 transition-colors"
            >
              + Add concept
            </button>
          )}

          {mode === 'input' && (
            <div className="flex items-center gap-1.5">
              <input
                autoFocus
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && inputValue.trim()) setMode('confirm')
                  if (e.key === 'Escape') { setMode('idle'); setInputValue(''); setError(null) }
                }}
                placeholder="e.g. recursion"
                className="flex-1 bg-white/[0.05] rounded-md px-2 py-1 text-[10px] text-white/80 placeholder-white/20 outline-none border border-white/10 focus:border-white/20"
              />
              <button
                onClick={() => inputValue.trim() && setMode('confirm')}
                disabled={!inputValue.trim()}
                className="text-[10px] text-[#4488ff]/70 hover:text-[#4488ff] disabled:text-white/15 transition-colors"
              >
                Add
              </button>
              <button
                onClick={() => { setMode('idle'); setInputValue(''); setError(null) }}
                className="text-[10px] text-white/25 hover:text-white/50 transition-colors"
              >
                Cancel
              </button>
            </div>
          )}

          {mode === 'confirm' && (
            <div className="text-[10px]">
              <p className="text-white/50 mb-1.5">
                Are you sure you want to add "<span className="text-white/80">{inputValue.trim()}</span>"?
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleAdd}
                  className="text-[#4488ff] hover:text-[#66aaff] transition-colors"
                >
                  Yes, add it
                </button>
                <button
                  onClick={() => setMode('input')}
                  className="text-white/25 hover:text-white/50 transition-colors"
                >
                  Go back
                </button>
              </div>
            </div>
          )}

          {mode === 'loading' && (
            <p className="text-[10px] text-white/30 animate-pulse">Scanning past interactions...</p>
          )}

          {error && (
            <p className="text-[10px] text-red-400/70 mt-1">{error}</p>
          )}
        </div>
      )}
    </div>
  )
}
