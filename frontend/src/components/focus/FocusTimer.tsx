import { useState, useEffect, useRef } from 'react'
import { Play, Pause, Square, RotateCcw, Settings, X, Maximize, Minimize } from 'lucide-react'
import type { useFocusTimer } from '../../hooks/useFocusTimer'

type TimerState = ReturnType<typeof useFocusTimer>

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export function FocusTimerView({ timer }: { timer: TimerState }) {
  const [showSettings, setShowSettings] = useState(false)
  const [isFullScreen, setIsFullScreen] = useState(false)
  const [showControls, setShowControls] = useState(true)
  const containerRef = useRef<HTMLDivElement>(null)

  const toggleFullScreen = () => {
    if (!document.fullscreenElement) {
      containerRef.current?.requestFullscreen().catch(() => {})
    } else {
      document.exitFullscreen()
    }
  }

  useEffect(() => {
    const handler = () => setIsFullScreen(!!document.fullscreenElement)
    document.addEventListener('fullscreenchange', handler)
    return () => document.removeEventListener('fullscreenchange', handler)
  }, [])

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (!isFullScreen) { setShowControls(true); return }
      setShowControls(e.clientY > window.innerHeight * 0.8)
    }
    window.addEventListener('mousemove', handler)
    return () => window.removeEventListener('mousemove', handler)
  }, [isFullScreen])

  const pomoTabs: { id: 'focus' | 'shortBreak' | 'longBreak'; label: string }[] = [
    { id: 'focus', label: 'Focus' },
    { id: 'shortBreak', label: 'Short Break' },
    { id: 'longBreak', label: 'Long Break' },
  ]

  // Neobrutalist button base style
  const btnBase =
    'group relative font-black uppercase tracking-wider border-4 border-black dark:border-white rounded-xl transition-all active:translate-x-1 active:translate-y-1 active:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] hover:translate-y-[-2px] hover:translate-x-[-2px] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:hover:shadow-[6px_6px_0px_0px_rgba(255,255,255,1)]'

  return (
    <div ref={containerRef} className="flex flex-col items-center h-full w-full relative bg-white dark:bg-black transition-all duration-1000">
      {/* Pomodoro Tabs */}
      {timer.timerMode === 'pomodoro' && (
        <div className={`mt-4 md:mt-8 flex gap-2 md:gap-4 z-10 flex-wrap justify-center md:justify-start md:pl-8 transition-all duration-500 ${isFullScreen && !showControls ? 'opacity-0 -translate-y-10' : 'opacity-100'}`}>
          {pomoTabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => timer.switchPomoMode(tab.id)}
              className={`px-4 py-1.5 md:px-6 md:py-2 font-black uppercase tracking-tight border-4 border-black dark:border-white rounded-xl transition-all text-xs md:text-base whitespace-nowrap ${
                timer.pomoMode === tab.id
                  ? 'bg-accent text-white translate-x-[-1px] translate-y-[-1px] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]'
                  : 'bg-white dark:bg-black text-black dark:text-white hover:translate-y-[-1px] hover:translate-x-[-1px] hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:hover:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:shadow-[2px_2px_0px_0px_rgba(255,255,255,1)]'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* Timer Display */}
      <div className={`flex-1 flex flex-col items-center z-10 w-full px-4 ${isFullScreen ? 'justify-center pt-0' : 'justify-start pt-24'} md:justify-center`}>
        <span className={`font-sans font-bold tracking-tight leading-none text-black dark:text-white select-none transition-all duration-500 tabular-nums ${isFullScreen ? 'text-[24vw]' : 'text-[22vw] md:text-[16rem]'}`}>
          {formatTime(timer.displayTime)}
        </span>

        {timer.timerMode === 'pomodoro' && (
          <div className={`mt-4 text-2xl font-black uppercase tracking-widest text-black/40 dark:text-white/40 transition-all duration-500 ${isFullScreen && !showControls ? 'opacity-0 scale-95' : 'opacity-100'}`}>
            Session #{timer.sessionCount}
          </div>
        )}
        {timer.timerMode === 'flow' && timer.isRunning && (
          <div className={`mt-4 text-2xl font-black uppercase tracking-widest text-black/40 dark:text-white/40 transition-all duration-500 ${isFullScreen && !showControls ? 'opacity-0 scale-95' : 'opacity-100'}`}>
            Flow Mode
          </div>
        )}
      </div>

      {/* Controls */}
      <div className={`${isFullScreen ? 'absolute bottom-12 md:bottom-32 left-0 right-0 max-w-[240px] md:max-w-none mx-auto' : 'absolute bottom-0 md:bottom-auto md:static md:pb-32 left-0 right-0 max-w-[240px] md:max-w-none mx-auto'} flex flex-col md:flex-row flex-wrap justify-center gap-3 md:gap-6 items-center z-10 px-4 w-full md:w-auto transition-all duration-500 ${showControls ? 'opacity-100' : 'opacity-0 translate-y-20 pointer-events-none'}`}>
        {!timer.isRunning && !timer.isPaused ? (
          <>
            <button
              onClick={timer.startTimer}
              className={`w-full md:w-auto px-8 py-2 md:px-5 md:py-3 bg-white dark:bg-black text-black dark:text-white text-lg md:text-xl flex items-center justify-center gap-3 ${btnBase}`}
            >
              <Play className="w-5 h-5 md:w-6 md:h-6 fill-current" />
              <span>Start</span>
            </button>
            <button
              onClick={() => setShowSettings(true)}
              className={`w-full md:w-auto px-8 py-2 md:px-5 md:py-3 bg-white dark:bg-black text-black dark:text-white text-lg md:text-xl flex items-center justify-center gap-3 ${btnBase}`}
            >
              <Settings className="w-5 h-5 md:w-6 md:h-6" />
              <span>Settings</span>
            </button>
            <button
              onClick={toggleFullScreen}
              className={`w-full md:w-auto md:aspect-square px-8 py-2 md:p-3 bg-white dark:bg-black text-black dark:text-white flex items-center justify-center gap-3 ${btnBase}`}
              title={isFullScreen ? 'Exit Fullscreen' : 'Fullscreen'}
            >
              {isFullScreen ? <Minimize className="w-5 h-5 md:w-6 md:h-6" /> : <Maximize className="w-5 h-5 md:w-6 md:h-6" />}
              <span className="md:hidden font-black uppercase text-lg tracking-wider whitespace-nowrap">
                {isFullScreen ? 'Exit Full Screen' : 'Full Screen'}
              </span>
            </button>
          </>
        ) : (
          <>
            {timer.isPaused ? (
              <button
                onClick={timer.resumeTimer}
                className={`w-full md:w-auto px-8 py-2 md:px-5 md:py-3 bg-white dark:bg-black text-black dark:text-white text-lg md:text-xl flex items-center justify-center gap-3 ${btnBase}`}
              >
                <Play className="w-5 h-5 md:w-6 md:h-6 fill-current" />
                <span>Resume</span>
              </button>
            ) : (
              <button
                onClick={timer.pauseTimer}
                className={`w-full md:w-auto px-8 py-2 md:px-5 md:py-3 bg-white dark:bg-black text-black dark:text-white text-lg md:text-xl flex items-center justify-center gap-3 ${btnBase}`}
              >
                <Pause className="w-5 h-5 md:w-6 md:h-6 fill-current" />
                <span>Pause</span>
              </button>
            )}
            <button
              onClick={timer.stopTimer}
              className={`w-full md:w-auto px-8 py-2 md:px-5 md:py-3 bg-red-500 text-white text-lg md:text-xl flex items-center justify-center gap-3 ${btnBase}`}
            >
              <Square className="w-5 h-5 md:w-6 md:h-6 fill-current" />
              <span>Stop</span>
            </button>
            <button
              onClick={timer.resetTimer}
              className={`w-full md:w-auto px-8 py-2 md:px-5 md:py-3 bg-white dark:bg-black text-black dark:text-white text-lg md:text-xl flex items-center justify-center gap-3 ${btnBase}`}
            >
              <RotateCcw className="w-5 h-5 md:w-6 md:h-6" />
              <span>Reset</span>
            </button>
            <button
              onClick={() => setShowSettings(true)}
              className={`w-full md:w-auto px-8 py-2 md:px-5 md:py-3 bg-white dark:bg-black text-black dark:text-white text-lg md:text-xl flex items-center justify-center gap-3 ${btnBase}`}
            >
              <Settings className="w-5 h-5 md:w-6 md:h-6" />
              <span>Settings</span>
            </button>
            <button
              onClick={toggleFullScreen}
              className={`w-full md:w-auto md:aspect-square px-8 py-2 md:p-3 bg-white dark:bg-black text-black dark:text-white flex items-center justify-center gap-3 ${btnBase}`}
              title={isFullScreen ? 'Exit Fullscreen' : 'Fullscreen'}
            >
              {isFullScreen ? <Minimize className="w-5 h-5 md:w-6 md:h-6" /> : <Maximize className="w-5 h-5 md:w-6 md:h-6" />}
              <span className="md:hidden font-black uppercase text-lg tracking-wider whitespace-nowrap">
                {isFullScreen ? 'Exit Full Screen' : 'Full Screen'}
              </span>
            </button>
          </>
        )}
      </div>

      {/* Settings Modal */}
      {showSettings && (
        <div
          className="fixed inset-0 bg-black/60 dark:bg-white/10 backdrop-blur-sm flex items-center justify-center z-[6000]"
          onClick={() => setShowSettings(false)}
        >
          <div
            className="bg-white dark:bg-black border-4 border-black dark:border-white rounded-xl p-6 max-w-md w-full mx-4 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] dark:shadow-[8px_8px_0px_0px_rgba(255,255,255,1)]"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-3xl font-black text-black dark:text-white uppercase tracking-tight">Settings</h2>
              <button
                onClick={() => setShowSettings(false)}
                className="p-1.5 text-black dark:text-white hover:rotate-90 transition-transform"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            {/* Timer Mode */}
            <div className="mb-4 space-y-3">
              <label className="block text-base font-black uppercase tracking-wide text-black dark:text-white text-center">
                Timer Mode
              </label>
              <div className="flex gap-4 p-1.5 border-4 border-black dark:border-white rounded-xl bg-zinc-50 dark:bg-zinc-900">
                {(['flow', 'pomodoro'] as const).map(mode => (
                  <button
                    key={mode}
                    onClick={() => { timer.setTimerMode(mode); timer.setIsRunning(false) }}
                    className={`flex-1 py-3 font-black uppercase tracking-tight rounded-lg transition-all ${
                      timer.timerMode === mode
                        ? 'bg-accent text-white shadow-[4px_4px_0px_0px_rgba(0,0,0,0.2)]'
                        : 'text-black dark:text-white hover:bg-black/5 dark:hover:bg-white/5'
                    }`}
                  >
                    {mode === 'flow' ? 'Flow' : 'Pomodoro'}
                  </button>
                ))}
              </div>
            </div>

            <div className="mb-4 p-3 border-4 border-black dark:border-white rounded-xl bg-zinc-50 dark:bg-zinc-900">
              <p className="text-[10px] font-bold text-center text-zinc-600 dark:text-zinc-400 uppercase tracking-widest leading-relaxed">
                {timer.timerMode === 'flow'
                  ? 'Focus timer is currently set to run indefinitely.'
                  : 'Structured sessions with focus and break intervals.'}
              </p>
            </div>

            {/* Durations */}
            {timer.timerMode === 'pomodoro' && (
              <div className="mb-4 p-4 border-4 border-black dark:border-white rounded-xl bg-zinc-50 dark:bg-zinc-900">
                <label className="block text-sm font-black uppercase tracking-wide mb-4 text-black dark:text-white text-center">
                  Durations (Mins)
                </label>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: 'Focus', value: timer.focusDuration, set: timer.setFocusDuration, mode: 'focus' as const },
                    { label: 'Short', value: timer.shortBreakDuration, set: timer.setShortBreakDuration, mode: 'shortBreak' as const },
                    { label: 'Long', value: timer.longBreakDuration, set: timer.setLongBreakDuration, mode: 'longBreak' as const },
                  ].map(d => (
                    <div key={d.label} className="flex flex-col gap-1.5">
                      <span className="text-[9px] font-black uppercase text-zinc-500 dark:text-zinc-400 text-center">{d.label}</span>
                      <input
                        type="number"
                        min={1}
                        max={99}
                        value={d.value}
                        onChange={e => {
                          const val = Math.min(99, Math.max(1, parseInt(e.target.value) || 1))
                          d.set(val)
                          if (!timer.isRunning && timer.pomoMode === d.mode) {
                            timer.setPomoTime(val * 60)
                          }
                        }}
                        className="w-full bg-white dark:bg-black border-2 border-black dark:border-white text-black dark:text-white font-black text-center py-1.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-accent text-sm"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={() => setShowSettings(false)}
              className={`w-full px-8 py-3 bg-accent text-white text-2xl ${btnBase}`}
            >
              Save & Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
