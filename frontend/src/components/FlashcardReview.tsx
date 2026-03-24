import { useState, useEffect, useRef, useCallback } from 'react'
import { X, RotateCcw, Check, Undo2 } from 'lucide-react'
import { Icons } from './ClaudeChatInput'
import * as api from '../api'
import type { ReviewSession } from '../api'

interface FlashcardReviewProps {
  courseId: string
  onClose: () => void
}

const SWIPE_THRESHOLD = 100
const VELOCITY_THRESHOLD = 0.4
const EXIT_DURATION = 280

export function FlashcardReview({ courseId, onClose }: FlashcardReviewProps) {
  const [session, setSession] = useState<ReviewSession | null>(null)
  const [loading, setLoading] = useState(true)
  const [currentIndex, setCurrentIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [gotItCount, setGotItCount] = useState(0)
  const [againCount, setAgainCount] = useState(0)
  const [undoStack, setUndoStack] = useState<{ cardId: string; rating: number; index: number }[]>([])
  const [showUndo, setShowUndo] = useState(false)

  // Swipe state
  const [dragX, setDragX] = useState(0)
  const [dragY, setDragY] = useState(0)
  const [isDragging, setIsDragging] = useState(false)
  const [exitDir, setExitDir] = useState<'left' | 'right' | null>(null)
  const startRef = useRef({ x: 0, y: 0, time: 0 })
  const cardStartTime = useRef(Date.now())

  // Load review session
  useEffect(() => {
    setLoading(true)
    api.getReviewSession(courseId)
      .then(s => {
        setSession(s)
        setLoading(false)
        cardStartTime.current = Date.now()
      })
      .catch(() => setLoading(false))
  }, [courseId])

  const cards = session?.cards || []
  const totalCards = cards.length
  const isComplete = currentIndex >= totalCards
  const currentCard = !isComplete ? cards[currentIndex] : null
  const nextCard = currentIndex + 1 < totalCards ? cards[currentIndex + 1] : null

  // ── Swipe handlers (pointer events — works for mouse + touch) ──

  const onPointerDown = useCallback((e: React.PointerEvent) => {
    (e.target as HTMLElement).setPointerCapture(e.pointerId)
    startRef.current = { x: e.clientX, y: e.clientY, time: Date.now() }
    setIsDragging(true)
    setDragX(0)
    setDragY(0)
  }, [])

  const onPointerMove = useCallback((e: React.PointerEvent) => {
    if (!isDragging) return
    setDragX(e.clientX - startRef.current.x)
    setDragY(e.clientY - startRef.current.y)
  }, [isDragging])

  const handleSwipeAction = useCallback(async (direction: 'left' | 'right') => {
    if (!currentCard) return

    setExitDir(direction)
    const rating = direction === 'right' ? 3 : 1 // Good or Again
    const durationMs = Date.now() - cardStartTime.current

    // Fire API call (don't block animation)
    api.reviewCard(currentCard.id, rating, durationMs).catch(() => {})

    if (direction === 'right') setGotItCount(c => c + 1)
    else setAgainCount(c => c + 1)

    setUndoStack(prev => [...prev, { cardId: currentCard.id, rating, index: currentIndex }])
    setShowUndo(true)

    // Wait for exit animation, then advance
    setTimeout(() => {
      setExitDir(null)
      setFlipped(false)
      setDragX(0)
      setDragY(0)
      setCurrentIndex(i => i + 1)
      cardStartTime.current = Date.now()
    }, EXIT_DURATION)
  }, [currentCard, currentIndex])

  const onPointerUp = useCallback((e: React.PointerEvent) => {
    if (!isDragging) return
    setIsDragging(false)

    const elapsed = Date.now() - startRef.current.time
    const velocity = Math.abs(dragX) / Math.max(elapsed, 1)
    const totalMove = Math.abs(e.clientX - startRef.current.x) + Math.abs(e.clientY - startRef.current.y)

    // Tap detection — flip the card
    if (totalMove < 10 && elapsed < 300) {
      setFlipped(f => !f)
      setDragX(0)
      setDragY(0)
      return
    }

    const isQuickFlick = velocity > VELOCITY_THRESHOLD && Math.abs(dragX) > 40
    const isPastThreshold = Math.abs(dragX) > SWIPE_THRESHOLD

    if (isPastThreshold || isQuickFlick) {
      const direction = dragX > 0 ? 'right' : 'left'
      handleSwipeAction(direction)
    } else {
      // Snap back
      setDragX(0)
      setDragY(0)
    }
  }, [isDragging, dragX, handleSwipeAction])

  // ── Undo ──

  const handleUndo = useCallback(async () => {
    const last = undoStack[undoStack.length - 1]
    if (!last) return

    api.undoCardReview(last.cardId).catch(() => {})

    if (last.rating === 3) setGotItCount(c => Math.max(0, c - 1))
    else setAgainCount(c => Math.max(0, c - 1))

    setUndoStack(prev => prev.slice(0, -1))
    setShowUndo(false)
    setExitDir(null)
    setFlipped(false)
    setDragX(0)
    setDragY(0)
    setCurrentIndex(last.index)
    cardStartTime.current = Date.now()
  }, [undoStack])

  // Auto-hide undo after 5s
  useEffect(() => {
    if (!showUndo) return
    const timer = setTimeout(() => setShowUndo(false), 5000)
    return () => clearTimeout(timer)
  }, [showUndo, currentIndex])

  // ── Computed styles ──

  const progress = Math.min(Math.abs(dragX) / SWIPE_THRESHOLD, 1)
  const rightOpacity = dragX > 0 ? Math.min(dragX / SWIPE_THRESHOLD, 1) : 0
  const leftOpacity = dragX < 0 ? Math.min(-dragX / SWIPE_THRESHOLD, 1) : 0

  // ── Loading state ──

  if (loading) {
    return (
      <div className="absolute inset-0 z-50 bg-bg-0/95 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 animate-fade-in">
          <Icons.Logo className="w-10 h-10 animate-pulse" />
          <p className="text-sm text-text-400">Loading flashcards...</p>
        </div>
      </div>
    )
  }

  // ── Empty state ──

  if (!session || totalCards === 0) {
    return (
      <div className="absolute inset-0 z-50 bg-bg-0/95 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4 animate-fade-in max-w-sm text-center">
          <div className="w-14 h-14 rounded-full bg-bg-200 flex items-center justify-center">
            <Check className="w-7 h-7 text-green-500" />
          </div>
          <h2 className="text-lg font-serif text-text-100">No cards to review</h2>
          <p className="text-sm text-text-400">
            Chat with Docere and ask for flashcards to start building your deck.
          </p>
          <button
            onClick={onClose}
            className="px-5 py-2 rounded-xl bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            Back to chat
          </button>
        </div>
      </div>
    )
  }

  // ── Completion state ──

  if (isComplete) {
    return (
      <div className="absolute inset-0 z-50 bg-bg-0/95 flex items-center justify-center">
        <div className="flex flex-col items-center gap-6 animate-fade-in max-w-sm text-center">
          <div className="w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center">
            <Check className="w-8 h-8 text-green-500" />
          </div>
          <div>
            <h2 className="text-xl font-serif text-text-100 mb-1">All caught up!</h2>
            <p className="text-sm text-text-400">{totalCards} card{totalCards !== 1 ? 's' : ''} reviewed</p>
          </div>
          <div className="flex gap-10">
            <div className="text-center">
              <p className="text-2xl font-semibold text-green-500">{gotItCount}</p>
              <p className="text-xs text-text-400">Got it</p>
            </div>
            <div className="text-center">
              <p className="text-2xl font-semibold text-red-400">{againCount}</p>
              <p className="text-xs text-text-400">Review again</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="px-6 py-2.5 rounded-xl bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            Done
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="absolute inset-0 z-50 bg-bg-0/95 flex flex-col animate-fade-in overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-bg-300">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-purple-500/10 flex items-center justify-center">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="rgb(168,85,247)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="2" width="20" height="20" rx="2" />
              <path d="M7 7h10M7 12h10M7 17h6" />
            </svg>
          </div>
          <div>
            <h1 className="text-sm font-medium text-text-100">Review Flashcards</h1>
            <p className="text-xs text-text-400">
              {currentIndex + 1} of {totalCards}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-2 rounded-lg text-text-400 hover:text-text-200 hover:bg-bg-200 transition-all"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Progress bar */}
      <div className="h-1 bg-bg-200">
        <div
          className="h-full bg-accent transition-all duration-300 ease-out"
          style={{ width: `${(currentIndex / totalCards) * 100}%` }}
        />
      </div>

      {/* Card stack area */}
      <div className="flex-1 flex items-center justify-center px-6 py-8">
        <div className="relative w-full max-w-md" style={{ height: '340px' }}>

          {/* Peek card (underneath) */}
          {nextCard && !exitDir && (
            <div
              className="absolute inset-0 rounded-2xl border border-bg-300 bg-bg-100 p-6 flex items-center justify-center"
              style={{
                transform: `scale(${0.95 + progress * 0.05}) translateY(${8 - progress * 8}px)`,
                transition: isDragging ? 'none' : 'transform 300ms cubic-bezier(0.16, 1, 0.3, 1)',
              }}
            >
              <p className="text-base text-text-300 text-center line-clamp-4 select-none">
                {nextCard.front}
              </p>
            </div>
          )}

          {/* Top card (swipeable) */}
          {currentCard && (
            <div
              className={`absolute inset-0 touch-none select-none ${exitDir === 'right' ? 'animate-exit-right' : exitDir === 'left' ? 'animate-exit-left' : ''}`}
              style={!exitDir ? {
                transform: `translateX(${dragX}px) translateY(${dragY * 0.3}px) rotate(${dragX * 0.04}deg)`,
                transition: isDragging ? 'none' : 'transform 300ms cubic-bezier(0.16, 1, 0.3, 1)',
                cursor: isDragging ? 'grabbing' : 'grab',
                zIndex: 10,
              } : { zIndex: 10 }}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
            >
              {/* Card with 3D flip */}
              <div
                className="w-full h-full relative"
                style={{ perspective: '1000px' }}
              >
                <div
                  className="w-full h-full transition-transform duration-500"
                  style={{
                    transformStyle: 'preserve-3d',
                    transform: flipped ? 'rotateY(180deg)' : 'rotateY(0deg)',
                  }}
                >
                  {/* Front */}
                  <div
                    className="absolute inset-0 rounded-2xl border border-bg-300 bg-bg-0 shadow-lg p-6 flex flex-col items-center justify-center"
                    style={{ backfaceVisibility: 'hidden' }}
                  >
                    <p className="text-lg text-text-100 text-center leading-relaxed font-medium">
                      {currentCard.front}
                    </p>
                    <p className="text-xs text-text-500 mt-4">tap to reveal</p>
                  </div>

                  {/* Back */}
                  <div
                    className="absolute inset-0 rounded-2xl border border-bg-300 bg-bg-100 shadow-lg p-6 flex flex-col items-center justify-center"
                    style={{ backfaceVisibility: 'hidden', transform: 'rotateY(180deg)' }}
                  >
                    <p className="text-base text-text-200 text-center leading-relaxed">
                      {currentCard.back}
                    </p>
                  </div>
                </div>
              </div>

              {/* Swipe overlays */}
              {!exitDir && (
                <>
                  {/* Got it — right */}
                  <div
                    className="absolute inset-0 rounded-2xl border-2 border-green-500 bg-green-500/5 flex items-center justify-center pointer-events-none"
                    style={{ opacity: rightOpacity }}
                  >
                    <span className="text-green-500 font-semibold text-lg -rotate-12">Got it</span>
                  </div>

                  {/* Review again — left */}
                  <div
                    className="absolute inset-0 rounded-2xl border-2 border-red-400 bg-red-400/5 flex items-center justify-center pointer-events-none"
                    style={{ opacity: leftOpacity }}
                  >
                    <span className="text-red-400 font-semibold text-lg rotate-12">Again</span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Action buttons + undo */}
      <div className="px-6 pb-6 pt-2">
        <div className="max-w-md mx-auto">
          {/* Swipe button fallbacks */}
          <div className="flex items-center justify-center gap-6 mb-3">
            <button
              onClick={() => handleSwipeAction('left')}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-red-400/30 text-red-400 hover:bg-red-400/10 transition-all text-sm font-medium"
            >
              <RotateCcw className="w-4 h-4" />
              Again
            </button>
            <button
              onClick={() => handleSwipeAction('right')}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-green-500/30 text-green-500 hover:bg-green-500/10 transition-all text-sm font-medium"
            >
              <Check className="w-4 h-4" />
              Got it
            </button>
          </div>

          {/* Undo */}
          {showUndo && undoStack.length > 0 && (
            <div className="flex justify-center animate-fade-in">
              <button
                onClick={handleUndo}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-text-400 hover:text-text-200 hover:bg-bg-200 transition-all"
              >
                <Undo2 className="w-3.5 h-3.5" />
                Undo
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
