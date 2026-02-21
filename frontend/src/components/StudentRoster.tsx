import { useState, useMemo } from 'react'
import { studentColor } from './ConceptGraph3D'

interface TaggedStudent {
  id: string
  name: string
}

interface RosterStudent {
  id: string
  name: string
  engagement?: string | null
  total_interactions?: number | null
  avg_confusion?: number | null
}

interface Props {
  students: RosterStudent[]
  taggedStudents: TaggedStudent[]
  onToggleTag: (student: TaggedStudent) => void
  onZoomToStudent: (studentId: string) => void
  onViewClassroom: () => void
}

export function StudentRoster({ students, taggedStudents, onToggleTag, onZoomToStudent, onViewClassroom }: Props) {
  const [search, setSearch] = useState('')
  const [searchOpen, setSearchOpen] = useState(false)

  const filtered = useMemo(() => {
    if (!search) return students
    const q = search.toLowerCase()
    return students.filter(s => s.name.toLowerCase().includes(q))
  }, [students, search])

  const taggedIds = useMemo(
    () => new Set(taggedStudents.map(s => s.id)),
    [taggedStudents],
  )

  const handleClick = (student: RosterStudent) => {
    onToggleTag({ id: student.id, name: student.name })
    onZoomToStudent(student.id)
  }

  return (
    <div className="absolute right-4 top-4 bottom-4 w-[260px] z-10 flex flex-col bg-black/60 backdrop-blur-md rounded-2xl border border-white/10 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10">
        <span className="text-xs font-medium text-white/60">
          Students ({students.length})
        </span>
        <button
          onClick={() => { setSearchOpen(p => !p); setSearch('') }}
          className="text-white/30 hover:text-white/60 transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </button>
      </div>

      {/* Search input */}
      {searchOpen && (
        <div className="px-3 py-2 border-b border-white/5">
          <input
            autoFocus
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Filter by name..."
            className="w-full bg-white/5 text-white/80 text-[12px] placeholder-white/20 rounded-lg px-3 py-1.5 outline-none border border-white/10 focus:border-white/20"
          />
        </div>
      )}

      {/* Student list */}
      <div className="flex-1 overflow-y-auto py-1">
        {/* Entire Classroom — pan out */}
        <button
          onClick={onViewClassroom}
          className="w-full flex items-center gap-2.5 px-4 py-2 text-left transition-all hover:bg-white/5 border-b border-white/5"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeOpacity="0.5" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
            <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
            <circle cx="9" cy="7" r="4" />
            <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
            <path d="M16 3.13a4 4 0 0 1 0 7.75" />
          </svg>
          <div className="text-[13px] text-white/60 font-medium">Entire Classroom</div>
        </button>

        {filtered.length === 0 && (
          <div className="text-white/20 text-[11px] text-center py-6">
            {search ? 'No students match' : 'No students yet'}
          </div>
        )}
        {filtered.map(student => {
          const isTagged = taggedIds.has(student.id)
          return (
            <button
              key={student.id}
              onClick={() => handleClick(student)}
              className={`w-full flex items-center gap-2.5 px-4 py-2 text-left transition-all hover:bg-white/5 ${
                isTagged ? 'bg-white/[0.07] border-l-2 border-[#4488ff]' : 'border-l-2 border-transparent'
              }`}
            >
              {/* Engagement dot */}
              <span
                className="w-2 h-2 rounded-full shrink-0"
                style={{ backgroundColor: studentColor(student.engagement) }}
              />

              {/* Name + metadata */}
              <div className="flex-1 min-w-0">
                <div className="text-[13px] text-white/80 truncate">
                  {student.name}
                </div>
                <div className="text-[10px] text-white/30">
                  {student.total_interactions ?? 0} chats
                  {student.avg_confusion != null && (
                    <span className="ml-2">{Math.round(student.avg_confusion * 100)}% confusion</span>
                  )}
                </div>
              </div>

              {/* Tag indicator */}
              {isTagged && (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4488ff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}
