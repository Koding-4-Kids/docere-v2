import { Plus, MessageSquare } from 'lucide-react'
import { ThemeToggle } from './ThemeToggle'

interface Conversation {
  id: string
  title: string
  courseName: string
  lastMessageAt: string
}

interface SidebarProps {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  dark: boolean
  toggleTheme: () => void
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

export function Sidebar({ conversations, activeId, onSelect, onNew, dark, toggleTheme }: SidebarProps) {
  return (
    <div className="w-64 h-screen flex flex-col bg-bg-100 border-r border-bg-300">
      {/* Header */}
      <div className="p-4 flex items-center justify-between">
        <span className="text-lg font-semibold text-text-100 tracking-tight">Docere</span>
        <div className="flex items-center gap-1">
          <ThemeToggle dark={dark} toggle={toggleTheme} />
          <button
            onClick={onNew}
            className="p-2 rounded-lg text-text-400 hover:text-text-200 hover:bg-bg-200 transition-colors"
            aria-label="New conversation"
          >
            <Plus className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto custom-scrollbar px-2 pb-4">
        {conversations.length === 0 ? (
          <p className="text-sm text-text-400 px-3 py-8 text-center">No conversations yet</p>
        ) : (
          <div className="space-y-1">
            {conversations.map(conv => (
              <button
                key={conv.id}
                onClick={() => onSelect(conv.id)}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors group ${
                  activeId === conv.id
                    ? 'bg-bg-200 text-text-100'
                    : 'text-text-300 hover:bg-bg-200 hover:text-text-200'
                }`}
              >
                <div className="flex items-start gap-2">
                  <MessageSquare className="w-4 h-4 mt-0.5 shrink-0 opacity-50" />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium truncate">{conv.title || 'New conversation'}</p>
                    <div className="flex items-center gap-2 mt-0.5">
                      <span className="text-[11px] text-accent font-medium truncate">{conv.courseName}</span>
                      <span className="text-[11px] text-text-500">{timeAgo(conv.lastMessageAt)}</span>
                    </div>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
