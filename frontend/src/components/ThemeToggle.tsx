import { Moon, Sun } from 'lucide-react'

interface ThemeToggleProps {
  dark: boolean
  toggle: () => void
}

export function ThemeToggle({ dark, toggle }: ThemeToggleProps) {
  return (
    <button
      onClick={toggle}
      className="p-2 rounded-lg text-text-400 hover:text-text-200 hover:bg-bg-200 transition-colors"
      aria-label="Toggle theme"
    >
      {dark ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
    </button>
  )
}
