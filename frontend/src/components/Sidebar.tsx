import { useState } from 'react'
import { MessageSquare, HelpCircle, Settings, Plus, Trash2, Layers, Timer, X } from 'lucide-react'

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
  onDelete: (id: string) => void
  onLogout: () => void
  userName: string
  userEmail: string
  dark: boolean
  toggleTheme: () => void
  isOpen?: boolean
  onClose?: () => void
  onOpenFlashcards?: () => void
  flashcardDueCount?: number
  onOpenFocus?: () => void
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

// Collapsible submenu
function Menu({ children, items }: { children: React.ReactNode; items: { name: string; onClick?: () => void; icon?: React.ReactNode }[] }) {
  const [isOpened, setIsOpened] = useState(false)

  return (
    <div>
      <button
        className="w-full flex items-center justify-between text-text-300 p-2 rounded-lg hover:bg-bg-200 active:bg-bg-300 duration-150"
        onClick={() => setIsOpened(v => !v)}
        aria-expanded={isOpened}
      >
        <div className="flex items-center gap-x-2">{children}</div>
        <svg
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 20 20"
          fill="currentColor"
          className={`w-5 h-5 duration-150 ${isOpened ? 'rotate-180' : ''}`}
        >
          <path
            fillRule="evenodd"
            d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"
            clipRule="evenodd"
          />
        </svg>
      </button>

      {isOpened && (
        <ul className="mx-4 px-2 border-l border-bg-300 text-sm font-medium">
          {items.map((item, idx) => (
            <li key={idx}>
              <button
                onClick={item.onClick}
                className="flex items-center gap-x-2 text-text-300 p-2 rounded-lg hover:bg-bg-200 active:bg-bg-300 duration-150 w-full text-left"
              >
                {item.icon && <div className="text-text-400">{item.icon}</div>}
                {item.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function Sidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
  onDelete,
  isOpen = false,
  onClose,
  onOpenFlashcards,
  flashcardDueCount,
  onOpenFocus,
}: SidebarProps) {
  // Group conversations by course
  const courseGroups = conversations.reduce<Record<string, Conversation[]>>((acc, conv) => {
    if (!acc[conv.courseName]) acc[conv.courseName] = []
    acc[conv.courseName].push(conv)
    return acc
  }, {})

  return (
    <>
      {/* Backdrop: mobile only, when sidebar is open (click to close) */}
      <div
        aria-hidden
        className={`fixed inset-0 bg-black/40 z-40 transition-opacity duration-200 md:hidden ${isOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'}`}
        onClick={() => onClose?.()}
      />

      {/* Sidebar: mobile = overlay drawer; desktop (md+) = in flow, always visible */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-80 max-w-[85vw] transition-transform duration-200 ease-out md:relative md:inset-auto md:z-auto md:max-w-none md:translate-x-0 ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        <nav className="w-full h-screen md:h-full flex-shrink-0 border-r border-bg-300 bg-bg-100 flex flex-col">
      <div className="flex flex-col h-full px-4">
        {/* Header: Logo + X to close (mobile only) */}
        <div className="h-14 flex items-center justify-between shrink-0">
          <img src="/docere-logo.png" alt="Docere" className="h-7 object-contain" />
          <button
            type="button"
            onClick={() => onClose?.()}
            className="min-w-[44px] min-h-[44px] flex items-center justify-center rounded-lg text-text-400 hover:text-text-200 hover:bg-bg-200 transition-colors md:hidden"
            aria-label="Close menu"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* New Chat Button */}
        <button
          onClick={onNew}
          className="flex items-center gap-x-2 text-text-200 p-2.5 mb-2 rounded-lg border border-bg-300 hover:bg-bg-200 active:bg-bg-300 duration-150 text-sm font-medium"
        >
          <Plus className="w-5 h-5 text-accent" />
          New conversation
        </button>

        {/* Scrollable area */}
        <div className="flex-1 overflow-auto custom-scrollbar">
          <ul className="text-sm font-medium flex-1 space-y-1">
            {/* Conversations grouped by course */}
            {Object.keys(courseGroups).length > 0 ? (
              Object.entries(courseGroups).map(([courseName, convs]) => (
                <li key={courseName}>
                  <Menu
                    items={convs.map(conv => ({
                      name: conv.title || 'New conversation',
                      onClick: () => onSelect(conv.id),
                      icon: <MessageSquare className="w-4 h-4" />,
                    }))}
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={1.5}
                      stroke="currentColor"
                      className="w-5 h-5 text-text-400"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4.26 10.147a60.438 60.438 0 00-.491 6.347A48.62 48.62 0 0112 20.904a48.62 48.62 0 018.232-4.41 60.46 60.46 0 00-.491-6.347m-15.482 0a50.636 50.636 0 00-2.658-.813A59.906 59.906 0 0112 3.493a59.903 59.903 0 0110.399 5.84c-.896.248-1.783.52-2.658.814m-15.482 0A50.717 50.717 0 0112 13.489a50.702 50.702 0 017.74-3.342"
                      />
                    </svg>
                    <span className="text-sm">{courseName}</span>
                    <span className="ml-1 text-xs text-accent font-medium">({convs.length})</span>
                  </Menu>
                </li>
              ))
            ) : (
              /* Ungrouped flat list when no conversations */
              <li>
                <div className="text-text-400 text-sm text-center py-8">No conversations yet</div>
              </li>
            )}

            {/* Also show flat recent list when conversations exist */}
            {conversations.length > 0 && (
              <li className="pt-2 mt-2 border-t border-bg-300">
                <p className="text-[11px] uppercase tracking-wider text-text-500 px-2 mb-1">Recent</p>
                <div className="space-y-0.5">
                  {conversations.slice(0, 8).map(conv => (
                    <div
                      key={conv.id}
                      className={`group relative flex items-center gap-x-2 p-2 rounded-lg duration-150 ${
                        activeId === conv.id
                          ? 'bg-bg-200 text-text-100'
                          : 'text-text-300 hover:bg-bg-200 hover:text-text-200'
                      }`}
                    >
                      <button
                        onClick={() => onSelect(conv.id)}
                        className="flex items-center gap-x-2 min-w-0 flex-1 text-left"
                      >
                        <MessageSquare className="w-4 h-4 shrink-0 text-text-400" />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm truncate">{conv.title || 'New conversation'}</p>
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] text-accent font-medium">{conv.courseName}</span>
                            <span className="text-[11px] text-text-500">{timeAgo(conv.lastMessageAt)}</span>
                          </div>
                        </div>
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); onDelete(conv.id) }}
                        className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-bg-300 text-text-500 hover:text-red-500 transition-all shrink-0"
                        title="Delete conversation"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
              </li>
            )}
          </ul>
        </div>

        {/* Footer nav */}
        <div className="pt-2 mt-2 border-t border-bg-300 pb-4">
          <ul className="text-sm font-medium space-y-0.5">
            {onOpenFlashcards && (
              <li>
                <button
                  onClick={onOpenFlashcards}
                  className="flex items-center gap-x-2 text-text-300 p-2 rounded-lg hover:bg-bg-200 active:bg-bg-300 duration-150 w-full"
                >
                  <Layers className="w-5 h-5 text-purple-500" />
                  Flashcards
                  {(flashcardDueCount ?? 0) > 0 && (
                    <span className="ml-auto px-1.5 py-0.5 rounded-full bg-accent text-white text-[10px] font-bold min-w-[20px] text-center">
                      {flashcardDueCount}
                    </span>
                  )}
                </button>
              </li>
            )}
            {onOpenFocus && (
              <li>
                <button
                  onClick={onOpenFocus}
                  className="flex items-center gap-x-2 text-text-300 p-2 rounded-lg hover:bg-bg-200 active:bg-bg-300 duration-150 w-full"
                >
                  <Timer className="w-5 h-5 text-amber-500" />
                  Focus Mode
                </button>
              </li>
            )}
            <li>
              <a
                href="#"
                className="flex items-center gap-x-2 text-text-300 p-2 rounded-lg hover:bg-bg-200 active:bg-bg-300 duration-150"
              >
                <HelpCircle className="w-5 h-5 text-text-400" />
                Help
              </a>
            </li>
            <li>
              <a
                href="#"
                className="flex items-center gap-x-2 text-text-300 p-2 rounded-lg hover:bg-bg-200 active:bg-bg-300 duration-150"
              >
                <Settings className="w-5 h-5 text-text-400" />
                Settings
              </a>
            </li>
          </ul>
        </div>
      </div>
        </nav>
      </div>
    </>
  )
}
