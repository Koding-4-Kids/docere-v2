import { useEffect, useRef, useState } from 'react'
import { MessageSquare, Sun, Moon, HelpCircle, Settings, LogOut, Plus } from 'lucide-react'

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
  onLogout: () => void
  userEmail: string
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

export function Sidebar({ conversations, activeId, onSelect, onNew, onLogout, userEmail, dark, toggleTheme }: SidebarProps) {
  const profileRef = useRef<HTMLButtonElement | null>(null)
  const [isProfileActive, setIsProfileActive] = useState(false)

  useEffect(() => {
    const handleProfile = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setIsProfileActive(false)
      }
    }
    document.addEventListener('click', handleProfile)
    return () => document.removeEventListener('click', handleProfile)
  }, [])

  // Group conversations by course
  const courseGroups = conversations.reduce<Record<string, Conversation[]>>((acc, conv) => {
    if (!acc[conv.courseName]) acc[conv.courseName] = []
    acc[conv.courseName].push(conv)
    return acc
  }, {})

  return (
    <nav className="w-80 h-screen flex-shrink-0 border-r border-bg-300 bg-bg-100 flex flex-col">
      <div className="flex flex-col h-full px-4">
        {/* Header: Logo + Profile */}
        <div className="h-20 flex items-center pl-2">
          <div className="w-full flex items-center gap-x-4">
            <img src="/docere-logo.png" alt="Docere" className="h-8 object-contain" />

            <div className="relative flex-1 text-right">
              <button
                ref={profileRef}
                className="p-1.5 rounded-md text-text-400 hover:bg-bg-200 active:bg-bg-300"
                onClick={() => setIsProfileActive(v => !v)}
                aria-haspopup="menu"
                aria-expanded={isProfileActive}
              >
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-5 h-5">
                  <path
                    fillRule="evenodd"
                    d="M10 3a.75.75 0 01.55.24l3.25 3.5a.75.75 0 11-1.1 1.02L10 4.852 7.3 7.76a.75.75 0 01-1.1-1.02l3.25-3.5A.75.75 0 0110 3zm-3.76 9.2a.75.75 0 011.06.04l2.7 2.908 2.7-2.908a.75.75 0 111.1 1.02l-3.25 3.5a.75.75 0 01-1.1 0l-3.25-3.5a.75.75 0 01.04-1.06z"
                    clipRule="evenodd"
                  />
                </svg>
              </button>

              {isProfileActive && (
                <div
                  role="menu"
                  className="absolute z-10 top-12 right-0 w-64 rounded-lg bg-bg-0 shadow-md border border-bg-300 text-sm text-text-300"
                >
                  <div className="p-2 text-left">
                    <span className="block text-text-400 p-2">{userEmail}</span>
                    <button
                      onClick={toggleTheme}
                      className="flex items-center gap-2 w-full p-2 text-left rounded-md hover:bg-bg-200 active:bg-bg-300 duration-150"
                      role="menuitem"
                    >
                      {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                      {dark ? 'Light mode' : 'Dark mode'}
                    </button>
                    <button
                      onClick={onLogout}
                      className="flex items-center gap-2 w-full p-2 text-left rounded-md hover:bg-bg-200 active:bg-bg-300 duration-150"
                      role="menuitem"
                    >
                      <LogOut className="w-4 h-4" />
                      Logout
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
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
                    <button
                      key={conv.id}
                      onClick={() => onSelect(conv.id)}
                      className={`w-full text-left flex items-center gap-x-2 p-2 rounded-lg duration-150 ${
                        activeId === conv.id
                          ? 'bg-bg-200 text-text-100'
                          : 'text-text-300 hover:bg-bg-200 hover:text-text-200'
                      }`}
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
                  ))}
                </div>
              </li>
            )}
          </ul>
        </div>

        {/* Footer nav */}
        <div className="pt-2 mt-2 border-t border-bg-300 pb-4">
          <ul className="text-sm font-medium space-y-0.5">
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
  )
}
