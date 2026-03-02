import { useState } from 'react'
import { Play, Pause, SkipBack, SkipForward, Music, Volume2, VolumeX } from 'lucide-react'
import type { useFocusMusic } from '../../hooks/useFocusMusic'

type MusicState = ReturnType<typeof useFocusMusic>

export function FocusMiniPlayer({ music }: { music: MusicState }) {
  const [showVolume, setShowVolume] = useState(false)
  const currentTrack = music.playlist[music.currentTrackIndex]

  if (!currentTrack) return null

  return (
    <div className="flex items-center gap-4 bg-white dark:bg-zinc-900 border-4 border-black dark:border-white rounded-2xl p-2 px-4 shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] dark:shadow-[8px_8px_0px_0px_rgba(255,255,255,1)] pointer-events-auto">
      {/* Thumbnail */}
      <div className="w-12 h-12 bg-accent/20 border-2 border-black dark:border-white rounded-xl overflow-hidden flex-shrink-0 shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:shadow-[2px_2px_0px_0px_rgba(255,255,255,1)]">
        {currentTrack.thumbnail ? (
          <img src={currentTrack.thumbnail} alt={currentTrack.title} className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <Music className="w-5 h-5 text-black dark:text-white" />
          </div>
        )}
      </div>

      {/* Info */}
      <div className="flex flex-col min-w-0 max-w-[100px]">
        <div className="font-black truncate uppercase tracking-tighter text-black dark:text-white text-[10px] leading-tight">
          {currentTrack.title}
        </div>
        <div className="text-[9px] font-black text-zinc-500 dark:text-zinc-400 uppercase tracking-widest truncate">
          {currentTrack.artist}
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center gap-1.5 border-l-2 border-black dark:border-white pl-3">
        <button
          onClick={music.prevTrack}
          className="w-8 h-8 bg-accent/10 border-2 border-black dark:border-white rounded-lg flex items-center justify-center transition-all hover:translate-x-[-1px] hover:translate-y-[-1px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-x-0 active:translate-y-0 active:shadow-none"
        >
          <SkipBack className="w-4 h-4 text-black dark:text-white fill-current" />
        </button>
        <button
          onClick={music.togglePlay}
          className="w-10 h-10 bg-accent text-white border-2 border-black dark:border-white rounded-xl flex items-center justify-center transition-all hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-0 active:translate-y-0 active:shadow-none"
        >
          {music.isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
        </button>
        <button
          onClick={music.nextTrack}
          className="w-8 h-8 bg-accent/10 border-2 border-black dark:border-white rounded-lg flex items-center justify-center transition-all hover:translate-x-[-1px] hover:translate-y-[-1px] hover:shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] active:translate-x-0 active:translate-y-0 active:shadow-none"
        >
          <SkipForward className="w-4 h-4 text-black dark:text-white fill-current" />
        </button>

        {/* Volume */}
        <div className="relative flex items-center ml-1">
          <button
            onClick={() => setShowVolume(!showVolume)}
            onContextMenu={e => { e.preventDefault(); music.toggleMute() }}
            className="w-8 h-8 bg-white dark:bg-black border-2 border-black dark:border-white rounded-lg flex items-center justify-center transition-all hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-[3px_3px_0px_0px_rgba(0,0,0,1)] active:translate-x-0 active:translate-y-0 active:shadow-none"
            title="Left click to toggle slider, Right click to mute"
          >
            {music.isMuted ? <VolumeX className="w-4 h-4 text-red-500" /> : <Volume2 className="w-4 h-4 text-black dark:text-white" />}
          </button>
          {showVolume && (
            <div className="absolute bottom-full right-0 mb-4 bg-white dark:bg-black border-4 border-black dark:border-white p-2 rounded-xl shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] w-24">
              <input
                type="range"
                min="0"
                max="100"
                value={music.isMuted ? 0 : music.volume}
                onChange={e => music.setVolume(parseInt(e.target.value))}
                className="w-full h-4 appearance-none bg-accent/20 border-2 border-black dark:border-white rounded-lg cursor-pointer accent-accent"
              />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
