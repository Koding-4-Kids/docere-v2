import { useState, useEffect, useCallback, useRef } from 'react'

interface UseTypewriterOptions {
  text: string
  enabled?: boolean
  charsPerTick?: number
  intervalMs?: number
}

interface UseTypewriterResult {
  displayedText: string
  isComplete: boolean
  showAll: () => void
  progress: number
}

export function useTypewriter({
  text,
  enabled = true,
  charsPerTick = 3,
  intervalMs = 12,
}: UseTypewriterOptions): UseTypewriterResult {
  const [charIndex, setCharIndex] = useState(0)
  const [skipped, setSkipped] = useState(false)
  const rafRef = useRef<number>(0)
  const lastTickRef = useRef<number>(0)

  // Speed up for long content
  const speed = text.length > 3000 ? 5 : charsPerTick

  // Reset when text changes (adjusting state during render, per react.dev)
  const [prevText, setPrevText] = useState(text)
  if (text !== prevText) {
    setPrevText(text)
    setCharIndex(0)
    setSkipped(false)
  }

  useEffect(() => {
    lastTickRef.current = 0
  }, [text])

  const isComplete = !enabled || skipped || charIndex >= text.length

  useEffect(() => {
    if (!enabled || skipped || charIndex >= text.length) return

    const tick = (timestamp: number) => {
      if (!lastTickRef.current) lastTickRef.current = timestamp
      const elapsed = timestamp - lastTickRef.current

      if (elapsed >= intervalMs) {
        setCharIndex(prev => Math.min(prev + speed, text.length))
        lastTickRef.current = timestamp
      }

      if (charIndex < text.length) {
        rafRef.current = requestAnimationFrame(tick)
      }
    }

    rafRef.current = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(rafRef.current)
  }, [enabled, skipped, charIndex, text.length, speed, intervalMs])

  const showAll = useCallback(() => setSkipped(true), [])

  const displayedText = isComplete ? text : text.slice(0, charIndex)
  const progress = text.length > 0 ? (isComplete ? 1 : charIndex / text.length) : 1

  return { displayedText, isComplete, showAll, progress }
}
