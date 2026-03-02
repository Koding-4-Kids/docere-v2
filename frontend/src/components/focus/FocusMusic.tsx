import { useState } from 'react'
import { Play, Pause, SkipBack, SkipForward, Music, Volume2, VolumeX } from 'lucide-react'
import type { useFocusMusic, MusicCategory } from '../../hooks/useFocusMusic'

type MusicState = ReturnType<typeof useFocusMusic>

const CATEGORY_META: Record<MusicCategory, { label: string; emoji: string }> = {
  lofi: { label: 'Lo-fi Study', emoji: '🎧' },
  classical: { label: 'Classical', emoji: '🎻' },
  jazz: { label: 'Jazz', emoji: '🎷' },
  ambient: { label: 'Ambient', emoji: '🌊' },
  energetic: { label: 'Energetic', emoji: '⚡' },
  chill: { label: 'Chill', emoji: '😌' },
}

function formatTime(seconds: number): string {
  if (isNaN(seconds)) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function FocusMusicView({ music }: { music: MusicState }) {
  const [showVolume, setShowVolume] = useState(false)
  const currentTrack = music.playlist[music.currentTrackIndex]

  return (
    <div className="flex flex-col md:flex-row h-full gap-4 md:gap-8 max-w-6xl mx-auto py-4 md:py-8 px-4">
      {/* Left: Category Selector */}
      <div className="w-full md:w-80 shrink-0">
        <div className="bg-white dark:bg-black border-4 border-black dark:border-white rounded-2xl shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] dark:shadow-[8px_8px_0px_0px_rgba(255,255,255,1)] overflow-hidden">
          {/* Header */}
          <div className="bg-white dark:bg-black px-4 py-4 border-b-4 border-black dark:border-white flex items-center gap-3">
            <div className="w-10 h-10 flex items-center justify-center bg-accent/20 border-2 border-black dark:border-white rounded-xl shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] dark:shadow-[3px_3px_0px_0px_rgba(255,255,255,1)]">
              <Music className="w-5 h-5 text-black dark:text-white" />
            </div>
            <h3 className="font-black text-lg text-black dark:text-white uppercase tracking-tight">
              Playlists
            </h3>
          </div>

          {/* Categories */}
          <div className="p-4 space-y-3">
            {music.categories.map(cat => {
              const meta = CATEGORY_META[cat]
              return (
                <button
                  key={cat}
                  onClick={() => music.selectCategory(cat)}
                  className={`w-full p-3 border-2 border-black dark:border-white rounded-xl cursor-pointer transition-all flex items-center gap-3 ${
                    music.activeCategory === cat
                      ? 'bg-accent/20 translate-x-[-2px] translate-y-[-2px] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]'
                      : 'bg-white dark:bg-zinc-900 hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:hover:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]'
                  }`}
                >
                  <span className="text-2xl">{meta.emoji}</span>
                  <span className="font-black uppercase tracking-tight text-sm text-black dark:text-white">
                    {meta.label}
                  </span>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Right: Player */}
      <div className="flex-1 min-w-0">
        <div className="flex flex-col h-full bg-white dark:bg-black border-4 border-black dark:border-white rounded-2xl shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] dark:shadow-[12px_12px_0px_0px_rgba(255,255,255,1)] overflow-hidden">
          {/* Header */}
          <div className="bg-white dark:bg-black px-4 py-4 border-b-4 border-black dark:border-white flex items-center justify-between shrink-0">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 flex items-center justify-center bg-accent/20 border-2 border-black dark:border-white rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]">
                <Music className="w-7 h-7 text-black dark:text-white" />
              </div>
              <h3 className="font-black text-xl text-black dark:text-white uppercase tracking-tight">
                Music Player
              </h3>
            </div>
            <span className="w-10 h-10 flex items-center justify-center bg-black dark:bg-white text-white dark:text-black rounded-lg border-2 border-black dark:border-white font-bold text-base shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:shadow-[2px_2px_0px_0px_rgba(255,255,255,1)]">
              {music.playlist.length}
            </span>
          </div>

          {/* Playlist */}
          <div className="flex-1 overflow-y-auto p-6 scrollbar-hide">
            {music.playlist.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-8 space-y-4">
                <div className="w-20 h-20 bg-zinc-100 dark:bg-zinc-900 border-4 border-black dark:border-white rounded-2xl flex items-center justify-center shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]">
                  <Music className="w-10 h-10 text-zinc-400" />
                </div>
                <div>
                  <p className="text-xl font-black uppercase text-black dark:text-white">No tracks loaded</p>
                  <p className="text-sm font-medium text-zinc-500 mt-2">Pick a playlist category to start listening</p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                {music.playlist.map((track, idx) => (
                  <div
                    key={track.id}
                    onClick={() => music.playTrack(idx)}
                    className={`group relative p-3 border-2 border-black dark:border-white rounded-xl cursor-pointer transition-all ${
                      idx === music.currentTrackIndex
                        ? 'bg-accent/20 translate-x-[-2px] translate-y-[-2px] shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]'
                        : 'bg-white dark:bg-zinc-900 hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:hover:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="relative w-12 h-12 flex-shrink-0">
                        {track.thumbnail ? (
                          <img src={track.thumbnail} alt={track.title} className="w-full h-full object-cover rounded-lg border-2 border-black dark:border-white" />
                        ) : (
                          <div className="w-full h-full flex items-center justify-center border-2 border-black dark:border-white rounded-lg bg-zinc-200 dark:bg-zinc-800">
                            <Music className="w-5 h-5 text-zinc-500" />
                          </div>
                        )}
                        {idx === music.currentTrackIndex && music.isPlaying && (
                          <div className="absolute inset-0 flex items-center justify-center bg-black/60 rounded-lg">
                            <div className="flex items-end gap-0.5 h-4">
                              <div className="w-1 bg-white animate-pulse" style={{ height: '60%', animationDelay: '0ms' }} />
                              <div className="w-1 bg-white animate-pulse" style={{ height: '100%', animationDelay: '150ms' }} />
                              <div className="w-1 bg-white animate-pulse" style={{ height: '40%', animationDelay: '300ms' }} />
                            </div>
                          </div>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-black truncate text-sm tracking-tight text-black dark:text-white">{track.title}</div>
                        <div className="text-xs font-bold text-zinc-500 dark:text-zinc-400">{track.artist}</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Player Controls */}
          <div className="border-t-4 border-black dark:border-white p-6 bg-zinc-50 dark:bg-zinc-950">
            <div className="flex flex-col gap-6">
              {/* Track info + progress */}
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-4 min-w-0 max-w-[40%]">
                  {currentTrack ? (
                    <>
                      <div className="w-14 h-14 bg-accent/20 border-2 border-black dark:border-white rounded-2xl flex items-center justify-center shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] flex-shrink-0 overflow-hidden">
                        {currentTrack.thumbnail ? (
                          <img src={currentTrack.thumbnail} alt={currentTrack.title} className="w-full h-full object-cover" />
                        ) : (
                          <Music className="w-7 h-7 text-black dark:text-white" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="font-black truncate uppercase tracking-tighter text-black dark:text-white text-base">{currentTrack.title}</div>
                        <div className="text-xs font-black text-zinc-500 dark:text-zinc-400 uppercase tracking-widest truncate">{currentTrack.artist}</div>
                      </div>
                    </>
                  ) : (
                    <div className="flex items-center gap-4 opacity-30">
                      <div className="w-14 h-14 bg-zinc-200 dark:bg-zinc-800 border-2 border-black dark:border-white rounded-2xl" />
                      <div className="flex-1 space-y-2">
                        <div className="h-5 w-32 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
                        <div className="h-3 w-20 bg-zinc-200 dark:bg-zinc-800 rounded-lg" />
                      </div>
                    </div>
                  )}
                </div>

                <div className="flex-1 flex flex-col gap-1">
                  <input
                    type="range"
                    min="0"
                    max={music.duration || 100}
                    value={music.currentTime}
                    onChange={e => music.seekTo(parseFloat(e.target.value))}
                    disabled={music.playlist.length === 0}
                    className="w-full h-3 appearance-none bg-zinc-200 dark:bg-zinc-800 border-2 border-black dark:border-white rounded-lg cursor-pointer accent-accent overflow-hidden shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:shadow-[2px_2px_0px_0px_rgba(255,255,255,1)]"
                  />
                  <div className="flex justify-between text-[11px] font-black uppercase tracking-tighter text-zinc-500">
                    <span>{formatTime(music.currentTime)}</span>
                    <span>{formatTime(music.duration)}</span>
                  </div>
                </div>
              </div>

              {/* Transport */}
              <div className="relative flex items-center justify-between">
                <div className="w-1/3">
                  <button
                    onClick={music.toggleMute}
                    disabled={music.playlist.length === 0}
                    className="group relative w-12 h-12 bg-white dark:bg-zinc-800 border-2 border-black dark:border-white rounded-xl flex items-center justify-center transition-all active:translate-x-0 active:translate-y-0 active:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] hover:enabled:translate-y-[-2px] hover:enabled:translate-x-[-2px] hover:enabled:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:hover:enabled:shadow-[6px_6px_0px_0px_rgba(255,255,255,1)] disabled:opacity-30 disabled:cursor-not-allowed"
                  >
                    {music.isMuted ? <VolumeX className="w-6 h-6 text-red-500" /> : <Volume2 className="w-6 h-6 text-black dark:text-white" />}
                  </button>
                </div>

                <div className="flex items-center justify-center gap-4 sm:gap-6 absolute left-1/2 -translate-x-1/2">
                  <button
                    onClick={music.prevTrack}
                    disabled={music.playlist.length === 0}
                    className="group relative w-12 h-12 bg-accent/10 border-2 border-black dark:border-white rounded-xl flex items-center justify-center transition-all active:translate-x-0 active:translate-y-0 active:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] hover:enabled:translate-y-[-2px] hover:enabled:translate-x-[-2px] hover:enabled:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:hover:enabled:shadow-[6px_6px_0px_0px_rgba(255,255,255,1)] disabled:opacity-30"
                  >
                    <SkipBack className="w-6 h-6 text-black dark:text-white fill-current" />
                  </button>
                  <button
                    onClick={music.togglePlay}
                    disabled={music.playlist.length === 0}
                    className="group relative w-16 h-16 bg-accent text-white border-2 border-black dark:border-white rounded-2xl flex items-center justify-center transition-all active:translate-x-0 active:translate-y-0 active:shadow-none shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:shadow-[6px_6px_0px_0px_rgba(255,255,255,1)] hover:enabled:translate-y-[-2px] hover:enabled:translate-x-[-2px] hover:enabled:shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] dark:hover:enabled:shadow-[8px_8px_0px_0px_rgba(255,255,255,1)] disabled:opacity-30"
                  >
                    {music.isPlaying ? <Pause className="w-8 h-8 fill-current" /> : <Play className="w-8 h-8 fill-current ml-1" />}
                  </button>
                  <button
                    onClick={music.nextTrack}
                    disabled={music.playlist.length === 0}
                    className="group relative w-12 h-12 bg-accent/10 border-2 border-black dark:border-white rounded-xl flex items-center justify-center transition-all active:translate-x-0 active:translate-y-0 active:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] hover:enabled:translate-y-[-2px] hover:enabled:translate-x-[-2px] hover:enabled:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:hover:enabled:shadow-[6px_6px_0px_0px_rgba(255,255,255,1)] disabled:opacity-30"
                  >
                    <SkipForward className="w-6 h-6 text-black dark:text-white fill-current" />
                  </button>
                </div>

                {/* Volume slider */}
                <div className="flex items-center w-1/3 justify-end">
                  <div className="relative flex items-center">
                    <button
                      onClick={() => setShowVolume(!showVolume)}
                      disabled={music.playlist.length === 0}
                      className="group relative w-12 h-12 bg-white dark:bg-zinc-800 border-2 border-black dark:border-white rounded-xl flex items-center justify-center transition-all active:translate-x-0 active:translate-y-0 active:shadow-none shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] hover:enabled:translate-y-[-2px] hover:enabled:translate-x-[-2px] hover:enabled:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:hover:enabled:shadow-[6px_6px_0px_0px_rgba(255,255,255,1)] disabled:opacity-30"
                    >
                      <Volume2 className="w-6 h-6 text-black dark:text-white" />
                    </button>
                    {showVolume && music.playlist.length > 0 && (
                      <div className="absolute bottom-full right-0 mb-4 bg-white dark:bg-black border-4 border-black dark:border-white p-3 rounded-xl shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] dark:shadow-[8px_8px_0px_0px_rgba(255,255,255,1)] w-32 z-20">
                        <input
                          type="range"
                          min="0"
                          max="100"
                          value={music.volume}
                          onChange={e => music.setVolume(parseInt(e.target.value))}
                          className="w-full h-8 appearance-none bg-accent/20 border-2 border-black dark:border-white rounded-lg cursor-pointer accent-accent"
                        />
                        <div className="text-center mt-2 font-black text-xs uppercase tracking-tighter text-black dark:text-white">
                          Volume: {music.volume}%
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
