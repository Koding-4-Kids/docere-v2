import { useState, useEffect } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'

function getSystemDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function useTheme() {
  const [themeMode, setThemeModeState] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem('docere-theme')
    if (stored === 'dark' || stored === 'light' || stored === 'system') return stored
    return 'system'
  })

  const [dark, setDark] = useState(() => {
    const stored = localStorage.getItem('docere-theme')
    if (stored === 'system') return getSystemDark()
    if (stored === 'dark') return true
    if (stored === 'light') return false
    return getSystemDark()
  })

  useEffect(() => {
    if (themeMode === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      const apply = () => setDark(getSystemDark())
      apply()
      mq.addEventListener('change', apply)
      return () => mq.removeEventListener('change', apply)
    }
    setDark(themeMode === 'dark')
  }, [themeMode])

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark)
    localStorage.setItem('docere-theme', themeMode)
  }, [dark, themeMode])

  const setThemeMode = (mode: ThemeMode) => {
    setThemeModeState(mode)
  }

  return {
    dark,
    themeMode,
    setThemeMode,
    toggle: () =>
      setThemeModeState(prevMode => {
        const isCurrentlyDark = prevMode === 'system' ? dark : prevMode === 'dark'
        return isCurrentlyDark ? 'light' : 'dark'
      }),
  }
}
