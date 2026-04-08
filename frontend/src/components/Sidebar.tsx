import { useEffect, useRef, useState } from 'react'
import { Sun, Moon, LogOut, Plus, Trash2, Timer, MessageSquare, ChevronRight } from 'lucide-react'
import { Icons } from './ClaudeChatInput'

interface Conversation {
  id: string
  title: string
  courseName: string
  courseId: string
  lastMessageAt: string
}

interface CourseInfo {
  id: string
  name: string
}

interface SidebarProps {
  conversations: Conversation[]
  courses: CourseInfo[]
  activeId: string | null
  activeCourseId: string | null
  onSelect: (id: string) => void
  onNew: () => void
  onNewForCourse: (courseId: string) => void
  onToggleCourse: (courseId: string | null) => void
  onDelete: (id: string) => void
  onLogout: () => void
  userEmail: string
  dark: boolean
  toggleTheme: () => void
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

export function Sidebar({
  conversations, courses, activeId, activeCourseId,
  onSelect, onNew, onNewForCourse, onToggleCourse, onDelete,
  onLogout, userEmail, dark, toggleTheme, onOpenFocus,
}: SidebarProps) {
  const profileRef = useRef<HTMLDivElement | null>(null)
  const [isProfileActive, setIsProfileActive] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const handleProfile = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setIsProfileActive(false)
      }
    }
    document.addEventListener('click', handleProfile)
    return () => document.removeEventListener('click', handleProfile)
  }, [])

  const toggleSection = (key: string) => {
    setCollapsedSections(prev => ({ ...prev, [key]: !prev[key] }))
  }

  // Group conversations by courseId
  const courseConvs = conversations.reduce<Record<string, Conversation[]>>((acc, conv) => {
    if (!acc[conv.courseId]) acc[conv.courseId] = []
    acc[conv.courseId].push(conv)
    return acc
  }, {})

  // "General" gets conversations that don't match any known course
  const knownCourseIds = new Set(courses.map(c => c.id))
  const generalConvs = conversations.filter(c => !knownCourseIds.has(c.courseId))

  const isGeneralActive = activeCourseId === null

  return (
    <nav className={`h-screen flex-shrink-0 border-r border-bg-300/60 bg-bg-100 flex flex-col transition-all duration-200 ${sidebarCollapsed ? 'w-[52px]' : 'w-[260px]'}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-4 border-b border-bg-300/60">
        {!sidebarCollapsed && (
          <div className="flex items-center gap-2">
            <Icons.Logo className="w-5 h-5" />
            <span className="text-[12px] font-medium text-text-300">Docere</span>
          </div>
        )}
        <button
          onClick={() => setSidebarCollapsed(c => !c)}
          className={`text-text-400 hover:text-text-200 transition-colors p-1 rounded-md hover:bg-bg-200 ${sidebarCollapsed ? 'mx-auto' : ''}`}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            {sidebarCollapsed ? (
              <>
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </>
            ) : (
              <>
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
              </>
            )}
          </svg>
        </button>
      </div>

      {/* New Chat */}
      <div className="px-2 pt-3 pb-1">
        <button
          onClick={onNew}
          className={`flex items-center gap-2 rounded-xl border border-bg-300/70 hover:bg-bg-200 active:bg-bg-300 transition-all text-[13px] font-medium text-text-200 ${
            sidebarCollapsed ? 'w-9 h-9 justify-center mx-auto' : 'w-full px-3 py-2.5'
          }`}
        >
          <Plus className="w-4 h-4 text-accent shrink-0" />
          {!sidebarCollapsed && 'New chat'}
        </button>
      </div>

      {/* Sections */}
      <div className="flex-1 overflow-y-auto custom-scrollbar py-2">
        {sidebarCollapsed ? (
          /* Collapsed: show icons */
          <div className="space-y-1 px-1.5">
            <button
              onClick={() => onToggleCourse(null)}
              className={`w-9 h-9 rounded-lg flex items-center justify-center mx-auto transition-all ${
                isGeneralActive ? 'bg-accent/10 text-accent' : 'bg-bg-200 text-text-400 hover:bg-bg-300'
              }`}
              title="General"
            >
              <MessageSquare className="w-4 h-4" />
            </button>
            {courses.map(c => {
              const isActive = activeCourseId === c.id
              return (
                <button
                  key={c.id}
                  onClick={() => onToggleCourse(c.id)}
                  className={`w-9 h-9 rounded-lg flex items-center justify-center mx-auto text-[11px] font-bold transition-all ${
                    isActive ? 'bg-accent/10 text-accent' : 'bg-bg-200 text-text-400 hover:bg-bg-300'
                  }`}
                  title={c.name}
                >
                  {c.name.charAt(0).toUpperCase()}
                </button>
              )
            })}
          </div>
        ) : (
          <>
            {/* General section */}
            <SidebarSection
              label="General"
              isContextActive={isGeneralActive}
              isCollapsed={!!collapsedSections['general']}
              onToggleCollapse={() => toggleSection('general')}
              onActivateContext={() => onToggleCourse(null)}
              onNewChat={onNew}
              conversations={generalConvs}
              activeConvId={activeId}
              onSelectConv={onSelect}
              onDeleteConv={onDelete}
            />

            {/* Course sections */}
            {courses.map(course => (
              <SidebarSection
                key={course.id}
                label={course.name}
                isContextActive={activeCourseId === course.id}
                isCollapsed={!!collapsedSections[course.id]}
                onToggleCollapse={() => toggleSection(course.id)}
                onActivateContext={() => onToggleCourse(course.id)}
                onNewChat={() => onNewForCourse(course.id)}
                conversations={courseConvs[course.id] || []}
                activeConvId={activeId}
                onSelectConv={onSelect}
                onDeleteConv={onDelete}
              />
            ))}

            {conversations.length === 0 && courses.length === 0 && (
              <div className="text-[12px] text-text-400 text-center py-8 px-3">
                No conversations yet
              </div>
            )}
          </>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-bg-300/60 px-2 py-3 space-y-0.5">
        {onOpenFocus && (
          <button
            onClick={onOpenFocus}
            className={`flex items-center gap-2 rounded-lg hover:bg-bg-200 active:bg-bg-300 transition-all text-[13px] text-text-300 ${
              sidebarCollapsed ? 'w-9 h-9 justify-center mx-auto' : 'w-full px-3 py-2'
            }`}
          >
            <Timer className="w-4 h-4 text-amber-500 shrink-0" />
            {!sidebarCollapsed && 'Focus Mode'}
          </button>
        )}

        {/* Profile */}
        <div ref={profileRef} className="relative">
          <button
            onClick={() => setIsProfileActive(v => !v)}
            className={`flex items-center gap-2 rounded-lg hover:bg-bg-200 transition-all ${
              sidebarCollapsed ? 'w-9 h-9 justify-center mx-auto' : 'w-full px-3 py-2'
            }`}
          >
            <div className="w-6 h-6 rounded-full bg-accent/15 flex items-center justify-center text-[10px] font-bold text-accent shrink-0">
              {(userEmail || '?').charAt(0).toUpperCase()}
            </div>
            {!sidebarCollapsed && (
              <span className="text-[12px] text-text-400 truncate flex-1 text-left">{userEmail}</span>
            )}
          </button>

          {isProfileActive && (
            <div
              role="menu"
              className={`absolute z-10 bottom-full mb-1 w-52 rounded-xl bg-bg-0 shadow-lg border border-bg-300 text-sm text-text-300 ${
                sidebarCollapsed ? 'left-[52px]' : 'left-0'
              }`}
            >
              <div className="p-1.5">
                <span className="block text-[11px] text-text-500 px-3 py-1.5 truncate">{userEmail}</span>
                <button
                  onClick={toggleTheme}
                  className="flex items-center gap-2 w-full px-3 py-2 text-left rounded-lg hover:bg-bg-200 transition-colors text-[13px]"
                  role="menuitem"
                >
                  {dark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                  {dark ? 'Light mode' : 'Dark mode'}
                </button>
                <button
                  onClick={onLogout}
                  className="flex items-center gap-2 w-full px-3 py-2 text-left rounded-lg hover:bg-bg-200 transition-colors text-[13px]"
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
    </nav>
  )
}

/* ── Collapsible sidebar section ── */

interface SidebarSectionProps {
  label: string
  isContextActive: boolean
  isCollapsed: boolean
  onToggleCollapse: () => void
  onActivateContext: () => void
  onNewChat: () => void
  conversations: Conversation[]
  activeConvId: string | null
  onSelectConv: (id: string) => void
  onDeleteConv: (id: string) => void
}

function SidebarSection({
  label, isContextActive, isCollapsed, onToggleCollapse,
  onActivateContext, onNewChat, conversations, activeConvId,
  onSelectConv, onDeleteConv,
}: SidebarSectionProps) {
  return (
    <div className="mb-1">
      {/* Section header — looks like a button row */}
      <div className="group mx-2 flex items-center gap-1">
        {/* Main toggle button — activates context */}
        <button
          onClick={onActivateContext}
          className={`flex-1 flex items-center gap-2 px-2.5 py-2 rounded-lg text-left transition-all ${
            isContextActive
              ? 'bg-accent/10 border border-accent/20'
              : 'hover:bg-bg-200 border border-transparent'
          }`}
        >
          {/* On/off dot */}
          <span className={`w-2 h-2 rounded-full shrink-0 transition-colors ${
            isContextActive ? 'bg-accent' : 'bg-text-500/40'
          }`} />
          <span className={`text-[13px] font-medium truncate transition-colors ${
            isContextActive ? 'text-accent' : 'text-text-300'
          }`}>
            {label}
          </span>
          {isContextActive && (
            <span className="ml-auto text-[9px] text-accent/60 font-medium uppercase tracking-wider shrink-0">On</span>
          )}
        </button>

        {/* Collapse chevron */}
        {conversations.length > 0 && (
          <button
            onClick={onToggleCollapse}
            className="p-1.5 text-text-500 hover:text-text-300 transition-colors shrink-0 rounded-md hover:bg-bg-200"
          >
            <ChevronRight className={`w-3.5 h-3.5 transition-transform duration-150 ${isCollapsed ? '' : 'rotate-90'}`} />
          </button>
        )}

        {/* New chat for this section */}
        <button
          onClick={onNewChat}
          className="p-1.5 text-text-500 hover:text-accent shrink-0 rounded-md hover:bg-bg-200 opacity-0 group-hover:opacity-100 transition-all"
          title={`New chat in ${label}`}
        >
          <Plus className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Conversations */}
      {!isCollapsed && conversations.length > 0 && (
        <div className="mt-0.5">
          {conversations.map(conv => {
            const isActive = activeConvId === conv.id
            return (
              <div
                key={conv.id}
                className={`group relative transition-all ${
                  isActive
                    ? 'bg-bg-200/80 border-l-2 border-accent'
                    : 'border-l-2 border-transparent hover:bg-bg-200/50'
                }`}
              >
                <button
                  onClick={() => onSelectConv(conv.id)}
                  className="flex items-center gap-2.5 w-full text-left pl-7 pr-8 py-2"
                >
                  <MessageSquare className={`w-3 h-3 shrink-0 ${isActive ? 'text-accent' : 'text-text-400'}`} />
                  <div className="min-w-0 flex-1">
                    <p className={`text-[12px] truncate ${isActive ? 'text-text-100' : 'text-text-300'}`}>
                      {conv.title || 'New conversation'}
                    </p>
                    <span className="text-[10px] text-text-500">{timeAgo(conv.lastMessageAt)}</span>
                  </div>
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onDeleteConv(conv.id) }}
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 z-10 opacity-0 group-hover:opacity-100 p-1.5 rounded-md hover:bg-bg-300 text-text-500 hover:text-red-500 transition-all"
                  title="Delete"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
