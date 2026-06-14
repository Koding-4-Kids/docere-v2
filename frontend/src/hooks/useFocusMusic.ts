import { useState, useEffect, useRef, useCallback } from 'react'

export interface MusicTrack {
  id: string
  title: string
  artist: string
  videoId: string
  thumbnail: string
}

export type MusicCategory = 'lofi' | 'classical' | 'jazz' | 'ambient' | 'energetic' | 'chill'

const PLAYLISTS: Record<MusicCategory, MusicTrack[]> = {
  lofi: [
    { id: '1', title: 'Lofi Hip Hop Radio', artist: 'Lofi Girl', videoId: 'jfKfPfyJRdk', thumbnail: 'https://img.youtube.com/vi/jfKfPfyJRdk/mqdefault.jpg' },
    { id: '2', title: 'Deep Focus', artist: 'Chill Beats', videoId: '5qap5aO4i9A', thumbnail: 'https://img.youtube.com/vi/5qap5aO4i9A/mqdefault.jpg' },
    { id: '3', title: 'Coffee Shop Vibes', artist: 'Lofi Girl', videoId: 'lTRiuFIWV54', thumbnail: 'https://img.youtube.com/vi/lTRiuFIWV54/mqdefault.jpg' },
    { id: '4', title: 'Chillhop Essentials', artist: 'Chillhop Music', videoId: '7NOSDKb0HlU', thumbnail: 'https://img.youtube.com/vi/7NOSDKb0HlU/mqdefault.jpg' },
    { id: '5', title: 'Late Night Lofi', artist: 'The Jazz Hop Cafe', videoId: 'kgx4WGK0oNU', thumbnail: 'https://img.youtube.com/vi/kgx4WGK0oNU/mqdefault.jpg' },
  ],
  classical: [
    { id: '6', title: 'Classical Music for Studying', artist: 'Various', videoId: 'mIYzp5rcTvU', thumbnail: 'https://img.youtube.com/vi/mIYzp5rcTvU/mqdefault.jpg' },
    { id: '7', title: 'Moonlight Sonata', artist: 'Beethoven', videoId: '4Tr0otuiQuU', thumbnail: 'https://img.youtube.com/vi/4Tr0otuiQuU/mqdefault.jpg' },
    { id: '8', title: 'Clair de Lune', artist: 'Debussy', videoId: 'CvFH_6DNRCY', thumbnail: 'https://img.youtube.com/vi/CvFH_6DNRCY/mqdefault.jpg' },
    { id: '9', title: 'Gymnopédie No.1', artist: 'Erik Satie', videoId: 'S-Xm7s9eGxU', thumbnail: 'https://img.youtube.com/vi/S-Xm7s9eGxU/mqdefault.jpg' },
    { id: '10', title: 'The Four Seasons', artist: 'Vivaldi', videoId: 'GRxofEmo3HA', thumbnail: 'https://img.youtube.com/vi/GRxofEmo3HA/mqdefault.jpg' },
  ],
  jazz: [
    { id: '11', title: 'Jazz for Study', artist: 'Various', videoId: 'neV3EPgvZ3g', thumbnail: 'https://img.youtube.com/vi/neV3EPgvZ3g/mqdefault.jpg' },
    { id: '12', title: 'Autumn Leaves', artist: 'Jazz Standards', videoId: 'xXBNlApwh0c', thumbnail: 'https://img.youtube.com/vi/xXBNlApwh0c/mqdefault.jpg' },
    { id: '13', title: 'Smooth Jazz', artist: 'Cafe Music BGM', videoId: 'fEvM-OUbaKs', thumbnail: 'https://img.youtube.com/vi/fEvM-OUbaKs/mqdefault.jpg' },
    { id: '14', title: 'Late Night Jazz', artist: 'Jazz Lounge', videoId: 'RelGGvSaqvg', thumbnail: 'https://img.youtube.com/vi/RelGGvSaqvg/mqdefault.jpg' },
    { id: '15', title: 'Jazz Piano Bar', artist: 'Cafe Music BGM', videoId: 'Dx5qFachd3A', thumbnail: 'https://img.youtube.com/vi/Dx5qFachd3A/mqdefault.jpg' },
  ],
  ambient: [
    { id: '16', title: 'Weightless', artist: 'Marconi Union', videoId: 'UfcAVejslrU', thumbnail: 'https://img.youtube.com/vi/UfcAVejslrU/mqdefault.jpg' },
    { id: '17', title: 'Ambient Study Music', artist: 'Yellow Brick Cinema', videoId: 'sjkrrmBnpGE', thumbnail: 'https://img.youtube.com/vi/sjkrrmBnpGE/mqdefault.jpg' },
    { id: '18', title: 'Rain Sounds', artist: 'Nature Sounds', videoId: 'mPZkdNFkNps', thumbnail: 'https://img.youtube.com/vi/mPZkdNFkNps/mqdefault.jpg' },
    { id: '19', title: 'Space Ambient', artist: 'Stellardrone', videoId: 'gpvznAiKblU', thumbnail: 'https://img.youtube.com/vi/gpvznAiKblU/mqdefault.jpg' },
    { id: '20', title: 'Forest Sounds', artist: 'Nature Ambience', videoId: 'xNN7iTA57jM', thumbnail: 'https://img.youtube.com/vi/xNN7iTA57jM/mqdefault.jpg' },
  ],
  energetic: [
    { id: '21', title: 'Eye of the Tiger', artist: 'Survivor', videoId: 'btPJPFnesV4', thumbnail: 'https://img.youtube.com/vi/btPJPFnesV4/mqdefault.jpg' },
    { id: '22', title: 'Stronger', artist: 'Kanye West', videoId: 'PsO6ZnUZ0Ts', thumbnail: 'https://img.youtube.com/vi/PsO6ZnUZ0Ts/mqdefault.jpg' },
    { id: '23', title: "Don't Stop Me Now", artist: 'Queen', videoId: 'HgzGwKwLmgM', thumbnail: 'https://img.youtube.com/vi/HgzGwKwLmgM/mqdefault.jpg' },
    { id: '24', title: 'Blinding Lights', artist: 'The Weeknd', videoId: 'fHI8X4OXluQ', thumbnail: 'https://img.youtube.com/vi/fHI8X4OXluQ/mqdefault.jpg' },
    { id: '25', title: 'Uptown Funk', artist: 'Bruno Mars', videoId: 'OPf0YbXqDm0', thumbnail: 'https://img.youtube.com/vi/OPf0YbXqDm0/mqdefault.jpg' },
  ],
  chill: [
    { id: '26', title: 'Best Part', artist: 'Daniel Caesar ft. H.E.R.', videoId: 'evilNOD_fSo', thumbnail: 'https://img.youtube.com/vi/evilNOD_fSo/mqdefault.jpg' },
    { id: '27', title: 'Location', artist: 'Khalid', videoId: 'SfOYAqCEPNg', thumbnail: 'https://img.youtube.com/vi/SfOYAqCEPNg/mqdefault.jpg' },
    { id: '28', title: 'Breathe', artist: 'Télépopmusik', videoId: 'vyut3GyQtn0', thumbnail: 'https://img.youtube.com/vi/vyut3GyQtn0/mqdefault.jpg' },
    { id: '29', title: 'Electric Feel', artist: 'MGMT', videoId: 'MmZexg8sxyk', thumbnail: 'https://img.youtube.com/vi/MmZexg8sxyk/mqdefault.jpg' },
    { id: '30', title: 'Redbone', artist: 'Childish Gambino', videoId: 'Kp7eSUU9oy8', thumbnail: 'https://img.youtube.com/vi/Kp7eSUU9oy8/mqdefault.jpg' },
  ],
}

declare global {
  interface Window {
    YT: any
    onYouTubeIframeAPIReady: () => void
  }
}

export function useFocusMusic() {
  const [playlist, setPlaylist] = useState<MusicTrack[]>([])
  const [currentTrackIndex, setCurrentTrackIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(false)
  const [volume, setVolumeState] = useState(50)
  const [isMuted, setIsMuted] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [playerReady, setPlayerReady] = useState(() => !!(window.YT && window.YT.Player))
  const [activeCategory, setActiveCategory] = useState<MusicCategory | null>(null)

  const playerRef = useRef<any>(null)
  const playlistRef = useRef<MusicTrack[]>([])
  const indexRef = useRef(0)

  useEffect(() => { playlistRef.current = playlist }, [playlist])
  useEffect(() => { indexRef.current = currentTrackIndex }, [currentTrackIndex])

  // Load YouTube IFrame API
  useEffect(() => {
    if (window.YT && window.YT.Player) return
    if (!document.querySelector('script[src*="youtube.com/iframe_api"]')) {
      const tag = document.createElement('script')
      tag.src = 'https://www.youtube.com/iframe_api'
      document.head.appendChild(tag)
    }
    const prev = window.onYouTubeIframeAPIReady
    window.onYouTubeIframeAPIReady = () => {
      prev?.()
      setPlayerReady(true)
    }
  }, [])

  // Create player instance
  useEffect(() => {
    if (!playerReady || playerRef.current) return
    if (!document.getElementById('docere-yt-player')) {
      const div = document.createElement('div')
      div.id = 'docere-yt-player'
      div.style.display = 'none'
      document.body.appendChild(div)
    }
    playerRef.current = new window.YT.Player('docere-yt-player', {
      height: '0',
      width: '0',
      playerVars: { autoplay: 0, controls: 0, disablekb: 1, enablejsapi: 1, fs: 0, modestbranding: 1, playsinline: 1, rel: 0 },
      events: {
        onReady: () => { playerRef.current?.setVolume(volume) },
        onStateChange: (e: any) => {
          if (e.data === 0 && playlistRef.current.length > 0) {
            const next = (indexRef.current + 1) % playlistRef.current.length
            setCurrentTrackIndex(next)
            setIsPlaying(false)
            setTimeout(() => {
              const track = playlistRef.current[next]
              if (playerRef.current && track) {
                playerRef.current.loadVideoById(track.videoId)
                playerRef.current.playVideo()
                setIsPlaying(true)
              }
            }, 100)
          }
        },
      },
    })
  }, [playerReady])

  // Progress tracking
  useEffect(() => {
    if (!isPlaying || !playerRef.current) return
    const interval = setInterval(() => {
      if (playerRef.current?.getCurrentTime) {
        setCurrentTime(playerRef.current.getCurrentTime())
        setDuration(playerRef.current.getDuration())
      }
    }, 1000)
    return () => clearInterval(interval)
  }, [isPlaying])

  // Sync volume
  useEffect(() => {
    playerRef.current?.setVolume?.(isMuted ? 0 : volume)
  }, [volume, isMuted])

  const selectCategory = useCallback((cat: MusicCategory) => {
    setActiveCategory(cat)
    setPlaylist(PLAYLISTS[cat])
    setCurrentTrackIndex(0)
    setIsPlaying(false)
  }, [])

  const playTrack = useCallback((index?: number) => {
    const idx = index ?? currentTrackIndex
    const track = playlistRef.current[idx]
    if (playerRef.current && track) {
      if (index !== undefined) setCurrentTrackIndex(index)
      playerRef.current.loadVideoById(track.videoId)
      playerRef.current.playVideo()
      setIsPlaying(true)
    }
  }, [currentTrackIndex])

  const togglePlay = useCallback(() => {
    if (!playerRef.current) return
    if (isPlaying) {
      playerRef.current.pauseVideo()
      setIsPlaying(false)
    } else {
      if (playerRef.current.getPlayerState() === 2) {
        playerRef.current.playVideo()
        setIsPlaying(true)
      } else {
        playTrack()
      }
    }
  }, [isPlaying, playTrack])

  const nextTrack = useCallback(() => {
    if (playlist.length === 0) return
    const next = (currentTrackIndex + 1) % playlist.length
    setCurrentTrackIndex(next)
    setIsPlaying(false)
    setTimeout(() => {
      if (playerRef.current && playlist[next]) {
        playerRef.current.loadVideoById(playlist[next].videoId)
        playerRef.current.playVideo()
        setIsPlaying(true)
      }
    }, 100)
  }, [playlist, currentTrackIndex])

  const prevTrack = useCallback(() => {
    if (playlist.length === 0) return
    const prev = (currentTrackIndex - 1 + playlist.length) % playlist.length
    setCurrentTrackIndex(prev)
    setIsPlaying(false)
    setTimeout(() => {
      if (playerRef.current && playlist[prev]) {
        playerRef.current.loadVideoById(playlist[prev].videoId)
        playerRef.current.playVideo()
        setIsPlaying(true)
      }
    }, 100)
  }, [playlist, currentTrackIndex])

  const toggleMute = useCallback(() => {
    if (!playerRef.current) return
    if (isMuted) {
      playerRef.current.setVolume(volume || 50)
      setIsMuted(false)
    } else {
      playerRef.current.setVolume(0)
      setIsMuted(true)
    }
  }, [isMuted, volume])

  const setVolume = useCallback((v: number) => {
    setVolumeState(v)
    if (isMuted) setIsMuted(false)
  }, [isMuted])

  const seekTo = useCallback((time: number) => {
    setCurrentTime(time)
    playerRef.current?.seekTo?.(time, true)
  }, [])

  return {
    playlist,
    currentTrackIndex,
    isPlaying,
    volume,
    isMuted,
    currentTime,
    duration,
    activeCategory,
    selectCategory,
    playTrack,
    togglePlay,
    nextTrack,
    prevTrack,
    toggleMute,
    setVolume,
    seekTo,
    categories: Object.keys(PLAYLISTS) as MusicCategory[],
  }
}
