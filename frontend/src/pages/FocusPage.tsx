import { useState } from 'react'
import { X, Clock, CheckSquare, Music } from 'lucide-react'
import { useFocusTimer } from '../hooks/useFocusTimer'
import { useFocusTasks } from '../hooks/useFocusTasks'
import { useFocusMusic } from '../hooks/useFocusMusic'
import { FocusTimerView } from '../components/focus/FocusTimer'
import { FocusTaskBoard } from '../components/focus/FocusTaskBoard'
import { FocusMusicView } from '../components/focus/FocusMusic'
import { FocusMiniPlayer } from '../components/focus/FocusMiniPlayer'

interface FocusPageProps {
  onClose: () => void
}

type Tab = 'focus' | 'tasks' | 'music'

function formatCompact(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export function FocusPage({ onClose }: FocusPageProps) {
  const [activeTab, setActiveTab] = useState<Tab>('focus')
  const timer = useFocusTimer()
  const { tasks, addTask, updateTask, moveTask, deleteTask } = useFocusTasks()
  const music = useFocusMusic()

  const navItems: { id: Tab; label: string; icon: typeof Clock }[] = [
    { id: 'focus', label: 'Focus', icon: Clock },
    { id: 'tasks', label: 'Task', icon: CheckSquare },
    { id: 'music', label: 'Music', icon: Music },
  ]

  return (
    <div className="absolute inset-0 z-50 bg-white dark:bg-black text-black dark:text-white flex flex-col overflow-hidden transition-colors font-sans">
      {/* ====================== DESKTOP LAYOUT ====================== */}
      <div className="hidden md:block w-full h-full relative">
        {/* Floating Nav */}
        <div className="fixed top-8 inset-x-0 mx-auto z-[5000] flex max-w-fit bg-white dark:bg-black border-4 border-black dark:border-white shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] dark:shadow-[8px_8px_0px_0px_rgba(255,255,255,1)] rounded-2xl p-2 items-center justify-center space-x-2">
          {navItems.map(item => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`relative flex items-center space-x-2 px-6 py-2 rounded-xl transition-all duration-200 border-2 border-transparent hover:translate-y-[-1px] hover:translate-x-[-1px] ${
                activeTab === item.id
                  ? 'bg-accent text-white border-black dark:border-white shadow-[4px_4px_0px_0px_rgba(100,100,100,0.5)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,0.5)]'
                  : 'text-neutral-500 dark:text-neutral-400 hover:bg-gray-100 dark:hover:bg-neutral-900'
              }`}
            >
              <item.icon className="w-5 h-5 stroke-[2.5]" />
              <span className="text-sm font-black uppercase tracking-wider">{item.label}</span>
            </button>
          ))}
        </div>

        {/* Header Controls — top right */}
        <div className="fixed top-8 right-8 z-[5001] flex items-center gap-4 pointer-events-auto">
          {/* Connect Music Services */}
          <div className="flex items-center gap-2 bg-white dark:bg-black border-4 border-black dark:border-white rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] p-1.5">
            <button
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#1DB954]/10 hover:bg-[#1DB954]/20 transition-all group"
              title="Connect Spotify"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#1DB954">
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
              </svg>
              <span className="text-[10px] font-black uppercase tracking-wider text-[#1DB954] hidden lg:block">Spotify</span>
            </button>
            <div className="w-px h-6 bg-black/10 dark:bg-white/10" />
            <button
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#FC3C44]/10 hover:bg-[#FC3C44]/20 transition-all group"
              title="Connect Apple Music"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="#FC3C44">
                <path d="M23.994 6.124a9.23 9.23 0 00-.24-2.19c-.317-1.31-1.062-2.31-2.18-3.043a5.022 5.022 0 00-1.877-.726 10.496 10.496 0 00-1.564-.15c-.04-.003-.083-.01-.124-.013H5.986c-.152.01-.303.017-.455.026-.747.043-1.49.123-2.193.4-1.336.53-2.3 1.452-2.865 2.78-.192.448-.292.925-.363 1.408-.056.392-.088.785-.1 1.18 0 .032-.007.062-.01.093v12.223c.01.14.017.283.027.424.05.815.154 1.624.497 2.373.65 1.42 1.738 2.353 3.234 2.802.42.127.856.187 1.293.228.555.053 1.11.063 1.667.063h11.334c.024 0 .048-.003.073-.004.727-.013 1.45-.06 2.157-.24 1.643-.418 2.828-1.373 3.482-2.954.2-.48.322-.98.392-1.49.057-.415.084-.833.097-1.25.004-.083.01-.166.01-.25V6.22l-.007-.096zM17.13 12.96l-.002.015c0 .91-.003 1.822-.003 2.733 0 .5-.057.993-.212 1.47-.163.5-.432.89-.864 1.16-.346.218-.73.32-1.13.358-.378.037-.752.02-1.117-.106-.58-.2-.96-.57-1.143-1.16a1.89 1.89 0 01-.074-.63c.023-.59.252-1.08.718-1.45.33-.264.718-.4 1.13-.468.396-.065.797-.088 1.193-.145.227-.033.447-.09.6-.293.09-.118.12-.26.12-.41V8.97c0-.2-.04-.38-.21-.51-.1-.08-.23-.12-.35-.13h-.07c-.7.14-1.39.27-2.08.41l-3.27.65c-.03.01-.06.01-.08.02-.23.05-.33.17-.35.4v.03c0 .06-.01.11-.01.17v5.65c0 .17 0 .34-.01.51-.02.53-.07 1.06-.25 1.56-.18.51-.46.92-.92 1.19-.35.21-.73.32-1.13.36-.39.04-.77.02-1.14-.11-.58-.2-.95-.58-1.13-1.17a1.86 1.86 0 01-.07-.6c.02-.57.24-1.05.69-1.42.33-.28.72-.41 1.13-.48.4-.07.8-.09 1.2-.15.22-.03.42-.09.57-.27.1-.13.14-.28.14-.44V6.88c0-.3.07-.56.33-.73.17-.12.37-.18.57-.22.46-.09.93-.18 1.39-.27l3.08-.62c.78-.15 1.56-.31 2.34-.46.1-.02.2-.04.3-.04.38-.02.62.2.63.59v6.82l.01.01z"/>
              </svg>
              <span className="text-[10px] font-black uppercase tracking-wider text-[#FC3C44] hidden lg:block">Apple</span>
            </button>
          </div>

          {/* Mini Timer */}
          {timer.isRunning && activeTab !== 'focus' && (
            <div className="flex items-center bg-white dark:bg-black px-4 h-14 rounded-xl gap-3 border-4 border-black dark:border-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]">
              <Clock className="w-6 h-6 text-black dark:text-white" strokeWidth={2.5} />
              <span className="font-black text-xl tabular-nums text-black dark:text-white leading-none">
                {formatCompact(timer.displayTime)}
              </span>
            </div>
          )}

          {/* Close */}
          <button
            onClick={onClose}
            className="w-14 h-14 bg-white dark:bg-black border-4 border-black dark:border-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] rounded-xl flex items-center justify-center hover:translate-y-[-2px] hover:translate-x-[-2px] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:hover:shadow-[6px_6px_0px_0px_rgba(255,255,255,1)] transition-all active:translate-x-1 active:translate-y-1 active:shadow-none"
          >
            <X className="w-6 h-6 stroke-[3] text-black dark:text-white" />
          </button>
        </div>

        {/* Mini Player — bottom right (when not on music tab) */}
        {activeTab !== 'music' && music.playlist.length > 0 && (
          <div className="fixed bottom-10 right-8 z-[5001] pointer-events-none">
            <FocusMiniPlayer music={music} />
          </div>
        )}

        {/* Content */}
        <div className="p-6 pt-28 h-full overflow-auto">
          {activeTab === 'focus' && <FocusTimerView timer={timer} />}
          {activeTab === 'tasks' && (
            <FocusTaskBoard tasks={tasks} addTask={addTask} updateTask={updateTask} moveTask={moveTask} deleteTask={deleteTask} />
          )}
          {activeTab === 'music' && <FocusMusicView music={music} />}
        </div>
      </div>

      {/* ====================== MOBILE LAYOUT ====================== */}
      <div className="md:hidden flex flex-col h-[100dvh] overflow-hidden bg-white dark:bg-black">
        {/* Mobile Header */}
        <div className="flex-none flex items-center justify-between px-4 py-3 z-50 bg-white dark:bg-black shadow-sm">
          {/* Connect Music — mobile */}
          <div className="flex items-center gap-1 bg-white dark:bg-black border-2 border-black dark:border-white rounded-lg shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:shadow-[2px_2px_0px_0px_rgba(255,255,255,1)] p-1">
            <button className="p-1.5 rounded-md bg-[#1DB954]/10 hover:bg-[#1DB954]/20 transition-all" title="Connect Spotify">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="#1DB954">
                <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
              </svg>
            </button>
            <div className="w-px h-5 bg-black/10 dark:bg-white/10" />
            <button className="p-1.5 rounded-md bg-[#FC3C44]/10 hover:bg-[#FC3C44]/20 transition-all" title="Connect Apple Music">
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="#FC3C44">
                <path d="M23.994 6.124a9.23 9.23 0 00-.24-2.19c-.317-1.31-1.062-2.31-2.18-3.043a5.022 5.022 0 00-1.877-.726 10.496 10.496 0 00-1.564-.15c-.04-.003-.083-.01-.124-.013H5.986c-.152.01-.303.017-.455.026-.747.043-1.49.123-2.193.4-1.336.53-2.3 1.452-2.865 2.78-.192.448-.292.925-.363 1.408-.056.392-.088.785-.1 1.18 0 .032-.007.062-.01.093v12.223c.01.14.017.283.027.424.05.815.154 1.624.497 2.373.65 1.42 1.738 2.353 3.234 2.802.42.127.856.187 1.293.228.555.053 1.11.063 1.667.063h11.334c.024 0 .048-.003.073-.004.727-.013 1.45-.06 2.157-.24 1.643-.418 2.828-1.373 3.482-2.954.2-.48.322-.98.392-1.49.057-.415.084-.833.097-1.25.004-.083.01-.166.01-.25V6.22l-.007-.096zM17.13 12.96l-.002.015c0 .91-.003 1.822-.003 2.733 0 .5-.057.993-.212 1.47-.163.5-.432.89-.864 1.16-.346.218-.73.32-1.13.358-.378.037-.752.02-1.117-.106-.58-.2-.96-.57-1.143-1.16a1.89 1.89 0 01-.074-.63c.023-.59.252-1.08.718-1.45.33-.264.718-.4 1.13-.468.396-.065.797-.088 1.193-.145.227-.033.447-.09.6-.293.09-.118.12-.26.12-.41V8.97c0-.2-.04-.38-.21-.51-.1-.08-.23-.12-.35-.13h-.07c-.7.14-1.39.27-2.08.41l-3.27.65c-.03.01-.06.01-.08.02-.23.05-.33.17-.35.4v.03c0 .06-.01.11-.01.17v5.65c0 .17 0 .34-.01.51-.02.53-.07 1.06-.25 1.56-.18.51-.46.92-.92 1.19-.35.21-.73.32-1.13.36-.39.04-.77.02-1.14-.11-.58-.2-.95-.58-1.13-1.17a1.86 1.86 0 01-.07-.6c.02-.57.24-1.05.69-1.42.33-.28.72-.41 1.13-.48.4-.07.8-.09 1.2-.15.22-.03.42-.09.57-.27.1-.13.14-.28.14-.44V6.88c0-.3.07-.56.33-.73.17-.12.37-.18.57-.22.46-.09.93-.18 1.39-.27l3.08-.62c.78-.15 1.56-.31 2.34-.46.1-.02.2-.04.3-.04.38-.02.62.2.63.59v6.82l.01.01z"/>
              </svg>
            </button>
          </div>

          <div className="flex items-center gap-3">
            {/* Mini Timer on mobile */}
            {timer.isRunning && activeTab !== 'focus' && (
              <div className="flex items-center bg-white dark:bg-black px-3 h-10 rounded-lg gap-2 border-2 border-black dark:border-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:shadow-[2px_2px_0px_0px_rgba(255,255,255,1)]">
                <Clock className="w-4 h-4 text-black dark:text-white" strokeWidth={2.5} />
                <span className="font-black text-sm tabular-nums text-black dark:text-white">
                  {formatCompact(timer.displayTime)}
                </span>
              </div>
            )}
            <button
              onClick={onClose}
              className="w-10 h-10 border-2 border-black dark:border-white rounded-lg flex items-center justify-center bg-white dark:bg-black shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:shadow-[2px_2px_0px_0px_rgba(255,255,255,1)]"
            >
              <X className="w-5 h-5 stroke-[3] text-black dark:text-white" />
            </button>
          </div>
        </div>

        {/* Mobile Content */}
        <div className={`flex-1 overflow-y-auto overflow-x-hidden scrollbar-hide pb-48 ${activeTab === 'focus' ? 'p-0' : 'p-4'}`}>
          {activeTab === 'focus' && <FocusTimerView timer={timer} />}
          {activeTab === 'tasks' && (
            <FocusTaskBoard tasks={tasks} addTask={addTask} updateTask={updateTask} moveTask={moveTask} deleteTask={deleteTask} />
          )}
          {activeTab === 'music' && <FocusMusicView music={music} />}
        </div>

        {/* Fixed Bottom: MiniPlayer + Nav Pill */}
        <div className="fixed bottom-6 inset-x-0 z-[60] flex flex-col items-center gap-4 pointer-events-none px-6">
          {/* Mini Player */}
          {activeTab !== 'music' && music.playlist.length > 0 && (
            <div className="pointer-events-auto w-full max-w-[320px] flex justify-center transform scale-95 shadow-xl">
              <FocusMiniPlayer music={music} />
            </div>
          )}

          {/* Navigation Pill */}
          <div className="pointer-events-auto w-full max-w-[320px]">
            <div className="flex justify-between items-center bg-white dark:bg-zinc-900 border-4 border-black dark:border-white rounded-2xl p-2 shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]">
              {navItems.map(item => (
                <button
                  key={item.id}
                  onClick={() => setActiveTab(item.id)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-xl transition-all duration-300 ${
                    activeTab === item.id
                      ? 'bg-accent text-white font-black shadow-[2px_2px_0px_0px_rgba(0,0,0,0.2)]'
                      : 'text-gray-500 dark:text-gray-400 font-bold hover:text-black dark:hover:text-white'
                  }`}
                >
                  <item.icon className="w-5 h-5" strokeWidth={activeTab === item.id ? 2.5 : 2} />
                  <span className="text-xs uppercase tracking-wider">{item.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
