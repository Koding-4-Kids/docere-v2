import { useState, useEffect, useCallback } from 'react'

export type TimerMode = 'flow' | 'pomodoro'
export type PomoMode = 'focus' | 'shortBreak' | 'longBreak'

function loadNum(key: string, fallback: number): number {
  const v = localStorage.getItem(key)
  return v ? parseInt(v, 10) || fallback : fallback
}

export function useFocusTimer() {
  const [elapsedTime, setElapsedTime] = useState(0)
  const [isRunning, setIsRunning] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [timerMode, setTimerMode] = useState<TimerMode>('flow')
  const [pomoMode, setPomoMode] = useState<PomoMode>('focus')
  const [sessionCount, setSessionCount] = useState(1)
  const [focusDuration, setFocusDuration] = useState(() => loadNum('docere-focus-dur', 25))
  const [shortBreakDuration, setShortBreakDuration] = useState(() => loadNum('docere-short-dur', 5))
  const [longBreakDuration, setLongBreakDuration] = useState(() => loadNum('docere-long-dur', 15))
  const [pomoTime, setPomoTime] = useState(() => loadNum('docere-focus-dur', 25) * 60)

  // Persist durations
  useEffect(() => { localStorage.setItem('docere-focus-dur', String(focusDuration)) }, [focusDuration])
  useEffect(() => { localStorage.setItem('docere-short-dur', String(shortBreakDuration)) }, [shortBreakDuration])
  useEffect(() => { localStorage.setItem('docere-long-dur', String(longBreakDuration)) }, [longBreakDuration])

  // Update pomoTime when durations change (if not running)
  useEffect(() => {
    if (!isRunning) {
      if (pomoMode === 'focus') setPomoTime(focusDuration * 60)
      else if (pomoMode === 'shortBreak') setPomoTime(shortBreakDuration * 60)
      else if (pomoMode === 'longBreak') setPomoTime(longBreakDuration * 60)
    }
  }, [focusDuration, shortBreakDuration, longBreakDuration, pomoMode, isRunning])

  const switchPomoMode = useCallback((mode: PomoMode) => {
    setPomoMode(mode)
    setIsRunning(false)
    setIsPaused(false)
    if (mode === 'focus') setPomoTime(focusDuration * 60)
    else if (mode === 'shortBreak') setPomoTime(shortBreakDuration * 60)
    else if (mode === 'longBreak') setPomoTime(longBreakDuration * 60)
  }, [focusDuration, shortBreakDuration, longBreakDuration])

  const handlePhaseComplete = useCallback(() => {
    if (pomoMode === 'focus') {
      if (sessionCount % 4 === 0) {
        switchPomoMode('longBreak')
      } else {
        switchPomoMode('shortBreak')
      }
      setSessionCount(prev => prev + 1)
    } else {
      switchPomoMode('focus')
    }
  }, [pomoMode, sessionCount, switchPomoMode])

  // Tick
  useEffect(() => {
    if (!isRunning || isPaused) return
    const interval = setInterval(() => {
      if (timerMode === 'flow') {
        setElapsedTime(prev => prev + 1)
      } else {
        setPomoTime(prev => {
          if (prev <= 1) {
            handlePhaseComplete()
            return 0
          }
          return prev - 1
        })
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [isRunning, isPaused, timerMode, handlePhaseComplete])

  const startTimer = () => { setIsRunning(true); setIsPaused(false) }
  const pauseTimer = () => { setIsPaused(true) }
  const resumeTimer = () => { setIsPaused(false) }

  const stopTimer = () => {
    setIsRunning(false)
    setIsPaused(false)
    if (timerMode === 'flow') {
      setElapsedTime(0)
    } else {
      if (pomoMode === 'focus') setPomoTime(focusDuration * 60)
      else if (pomoMode === 'shortBreak') setPomoTime(shortBreakDuration * 60)
      else if (pomoMode === 'longBreak') setPomoTime(longBreakDuration * 60)
    }
  }

  const resetTimer = () => {
    setIsRunning(false)
    setIsPaused(false)
    if (timerMode === 'flow') {
      setElapsedTime(0)
    } else {
      if (pomoMode === 'focus') setPomoTime(focusDuration * 60)
      else if (pomoMode === 'shortBreak') setPomoTime(shortBreakDuration * 60)
      else if (pomoMode === 'longBreak') setPomoTime(longBreakDuration * 60)
    }
  }

  const displayTime = timerMode === 'flow' ? elapsedTime : pomoTime

  return {
    displayTime,
    elapsedTime,
    pomoTime,
    isRunning,
    isPaused,
    timerMode,
    pomoMode,
    sessionCount,
    focusDuration,
    shortBreakDuration,
    longBreakDuration,
    setTimerMode,
    setIsRunning,
    setPomoTime,
    setFocusDuration,
    setShortBreakDuration,
    setLongBreakDuration,
    startTimer,
    pauseTimer,
    resumeTimer,
    stopTimer,
    resetTimer,
    switchPomoMode,
  }
}
