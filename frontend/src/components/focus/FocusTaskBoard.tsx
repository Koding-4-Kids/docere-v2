import { useState } from 'react'
import { Plus, X, ChevronLeft, ChevronRight, ClipboardList, Loader, CheckCircle } from 'lucide-react'
import type { FocusTask, TaskStatus, Priority } from '../../hooks/useFocusTasks'

interface FocusTaskBoardProps {
  tasks: FocusTask[]
  addTask: (data: Omit<FocusTask, 'id' | 'createdAt'>) => void
  updateTask: (id: string, updates: Partial<Omit<FocusTask, 'id' | 'createdAt'>>) => void
  moveTask: (id: string, status: TaskStatus) => void
  deleteTask: (id: string) => void
}

const ITEMS_PER_PAGE = 4

const columns: { id: TaskStatus; title: string; icon: typeof ClipboardList; bg: string }[] = [
  { id: 'planned', title: 'Todo', icon: ClipboardList, bg: 'bg-blue-200 dark:bg-blue-900' },
  { id: 'in-progress', title: 'In Progress', icon: Loader, bg: 'bg-orange-200 dark:bg-orange-900' },
  { id: 'done', title: 'Done', icon: CheckCircle, bg: 'bg-green-200 dark:bg-green-900' },
]

const priorityEmoji: Record<Priority, string> = { low: '🟢', medium: '🟡', high: '🟠', urgent: '🔴' }
const priorityColor: Record<Priority, string> = {
  low: 'text-green-600 dark:text-green-400 border-green-600 dark:border-green-400',
  medium: 'text-yellow-600 dark:text-yellow-400 border-yellow-600 dark:border-yellow-400',
  high: 'text-orange-600 dark:text-orange-400 border-orange-600 dark:border-orange-400',
  urgent: 'text-red-600 dark:text-red-400 border-red-600 dark:border-red-400',
}

export function FocusTaskBoard({ tasks, addTask, updateTask, moveTask, deleteTask }: FocusTaskBoardProps) {
  const [draggedId, setDraggedId] = useState<string | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [targetColumn, setTargetColumn] = useState<TaskStatus>('planned')
  const [pages, setPages] = useState<Record<TaskStatus, number>>({ 'planned': 1, 'in-progress': 1, 'done': 1 })
  const [form, setForm] = useState({ title: '', note: '', priority: 'medium' as Priority })

  const openAdd = (col: TaskStatus) => {
    setEditingId(null)
    setTargetColumn(col)
    setForm({ title: '', note: '', priority: 'medium' })
    setShowModal(true)
  }

  const openEdit = (task: FocusTask) => {
    setEditingId(task.id)
    setTargetColumn(task.status)
    setForm({ title: task.title, note: task.note, priority: task.priority })
    setShowModal(true)
  }

  const handleSave = () => {
    if (!form.title.trim()) return
    if (editingId) {
      updateTask(editingId, { ...form, status: targetColumn })
    } else {
      addTask({ ...form, status: targetColumn })
    }
    setShowModal(false)
  }

  const handleDragStart = (e: React.DragEvent, id: string) => {
    setDraggedId(id)
    e.dataTransfer.effectAllowed = 'move'
  }

  const handleDrop = (e: React.DragEvent, status: TaskStatus) => {
    e.preventDefault()
    if (draggedId) { moveTask(draggedId, status); setDraggedId(null) }
  }

  return (
    <div className="flex flex-col items-center w-full max-w-7xl mx-auto py-4 md:py-8 px-4 pb-24">
      <div className="w-full">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
          {columns.map(col => {
            const colTasks = tasks.filter(t => t.status === col.id)
            const totalPages = Math.ceil(colTasks.length / ITEMS_PER_PAGE)
            const page = Math.min(pages[col.id], totalPages || 1)
            const visible = colTasks.slice((page - 1) * ITEMS_PER_PAGE, page * ITEMS_PER_PAGE)

            return (
              <div
                key={col.id}
                className="flex flex-col bg-white dark:bg-black border-4 border-black dark:border-white rounded-xl shadow-[8px_8px_0px_0px_rgba(0,0,0,1)] dark:shadow-[8px_8px_0px_0px_rgba(255,255,255,1)] overflow-visible h-fit"
                onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move' }}
                onDrop={e => handleDrop(e, col.id)}
              >
                {/* Column header */}
                <div className="bg-white dark:bg-black rounded-t-lg px-4 py-4 border-b-4 border-black dark:border-white flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 flex items-center justify-center rounded-lg border-2 border-black dark:border-white shadow-[2px_2px_0px_0px_rgba(0,0,0,1)] dark:shadow-[2px_2px_0px_0px_rgba(255,255,255,1)] ${col.bg}`}>
                      <col.icon className="w-5 h-5 text-black dark:text-white" />
                    </div>
                    <h3 className="font-black text-lg text-black dark:text-white font-sans uppercase tracking-wide">
                      {col.title}
                    </h3>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => openAdd(col.id)}
                      className="w-8 h-8 flex items-center justify-center bg-white dark:bg-black text-black dark:text-white hover:bg-neutral-100 dark:hover:bg-neutral-900 rounded-lg border-2 border-black dark:border-white transition-transform hover:scale-105 active:scale-95"
                    >
                      <Plus className="w-5 h-5 stroke-[3]" />
                    </button>
                    <span className="w-8 h-8 flex items-center justify-center bg-black dark:bg-white text-white dark:text-black rounded-lg border-2 border-black dark:border-white font-bold text-sm">
                      {colTasks.length}
                    </span>
                  </div>
                </div>

                {/* Cards */}
                <div
                  className="bg-neutral-50 dark:bg-neutral-900/50 p-4 min-h-[300px] md:min-h-[600px] flex flex-col"
                  onDragOver={e => { e.preventDefault(); e.dataTransfer.dropEffect = 'move' }}
                  onDrop={e => handleDrop(e, col.id)}
                >
                  <div className="flex-1">
                    {visible.length === 0 ? (
                      <div className="h-full flex flex-col items-center justify-center text-neutral-400 dark:text-neutral-500 space-y-4 opacity-60">
                        <p className="text-sm font-bold uppercase tracking-widest border-2 border-dashed border-neutral-300 dark:border-neutral-700 px-4 py-2 rounded-lg">
                          Empty
                        </p>
                        <button
                          onClick={() => openAdd(col.id)}
                          className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider hover:text-black dark:hover:text-white transition-colors"
                        >
                          <Plus className="w-4 h-4" />
                          Add Task
                        </button>
                      </div>
                    ) : (
                      visible.map(task => (
                        <div
                          key={task.id}
                          draggable
                          onDragStart={e => handleDragStart(e, task.id)}
                          onClick={() => openEdit(task)}
                          className="bg-white dark:bg-neutral-900 rounded-lg p-3 md:p-4 mb-3 md:mb-4 cursor-pointer transition-all border-2 border-black dark:border-white shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] hover:translate-x-[-2px] hover:translate-y-[-2px] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:hover:shadow-[6px_6px_0px_0px_rgba(255,255,255,1)] group relative min-h-[80px]"
                        >
                          {/* Delete */}
                          <button
                            onClick={e => { e.stopPropagation(); deleteTask(task.id) }}
                            className="absolute -top-2 -right-2 bg-white dark:bg-black border-2 border-black dark:border-white rounded-full p-1 text-black dark:text-white hover:bg-red-500 hover:text-white dark:hover:bg-red-500 transition-all opacity-100 md:opacity-0 md:group-hover:opacity-100 z-10 shadow-sm"
                          >
                            <X className="h-3 w-3 md:h-4 md:w-4 stroke-[3]" />
                          </button>

                          <div className="flex flex-col gap-1">
                            <h3 className="font-bold text-black dark:text-white text-sm md:text-base leading-tight break-words pr-2">
                              {task.title}
                            </h3>
                            {task.note && (
                              <p className="text-xs md:text-sm text-neutral-600 dark:text-neutral-400 font-medium line-clamp-2 leading-relaxed">
                                {task.note}
                              </p>
                            )}
                            {task.priority && (
                              <div className={`inline-flex items-center gap-1 px-1.5 py-0.5 border rounded-md bg-neutral-100 dark:bg-neutral-800 w-fit mt-2 ${priorityColor[task.priority]}`}>
                                <span className="text-xs leading-none">{priorityEmoji[task.priority]}</span>
                                <span className="text-[9px] md:text-xs font-black uppercase">{task.priority}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      ))
                    )}
                  </div>

                  {/* Pagination */}
                  {totalPages > 1 && (
                    <div className="flex items-center justify-between mt-4 border-t-2 border-dashed border-neutral-300 dark:border-neutral-700 pt-4">
                      <button
                        onClick={() => setPages(p => ({ ...p, [col.id]: Math.max(1, page - 1) }))}
                        disabled={page === 1}
                        className="p-1 rounded-md hover:bg-black hover:text-white dark:hover:bg-white dark:hover:text-black disabled:opacity-30 transition-colors"
                      >
                        <ChevronLeft className="w-5 h-5 stroke-[3]" />
                      </button>
                      <span className="text-xs font-black text-neutral-500 dark:text-neutral-400">
                        PAGE {page} / {totalPages}
                      </span>
                      <button
                        onClick={() => setPages(p => ({ ...p, [col.id]: Math.min(totalPages, page + 1) }))}
                        disabled={page === totalPages}
                        className="p-1 rounded-md hover:bg-black hover:text-white dark:hover:bg-white dark:hover:text-black disabled:opacity-30 transition-colors"
                      >
                        <ChevronRight className="w-5 h-5 stroke-[3]" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>

        {/* Add/Edit Modal */}
        {showModal && (
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[6000]"
            onClick={() => setShowModal(false)}
          >
            <div
              className="bg-white dark:bg-black rounded-xl p-8 max-w-md w-full mx-4 border-4 border-black dark:border-white shadow-[12px_12px_0px_0px_rgba(0,0,0,1)] dark:shadow-[12px_12px_0px_0px_rgba(255,255,255,1)]"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex justify-between items-center mb-6">
                <h3 className="text-2xl font-black text-black dark:text-white uppercase">
                  {editingId ? 'Edit Task' : 'Add New Task'}
                </h3>
                <button
                  onClick={() => setShowModal(false)}
                  className="text-black dark:text-white hover:rotate-90 transition-transform"
                >
                  <X className="w-8 h-8 stroke-[3]" />
                </button>
              </div>

              {/* Title */}
              <div className="mb-4">
                <label className="block text-sm font-bold mb-2 text-black dark:text-white uppercase tracking-wider">Title</label>
                <input
                  type="text"
                  value={form.title}
                  onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
                  className="w-full bg-neutral-100 dark:bg-neutral-900 border-2 border-black dark:border-white rounded-lg px-4 py-3 text-black dark:text-white font-bold focus:outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:focus:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] transition-all"
                  placeholder="What needs to be done?"
                  autoFocus
                />
              </div>

              {/* Note */}
              <div className="mb-4">
                <label className="block text-sm font-bold mb-2 text-black dark:text-white uppercase tracking-wider">Note</label>
                <textarea
                  value={form.note}
                  onChange={e => setForm(f => ({ ...f, note: e.target.value }))}
                  rows={3}
                  className="w-full bg-neutral-100 dark:bg-neutral-900 border-2 border-black dark:border-white rounded-lg px-4 py-3 text-black dark:text-white font-medium focus:outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:focus:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] transition-all"
                  placeholder="Enter details..."
                />
              </div>

              {/* Priority */}
              <div className="mb-6">
                <label className="block text-sm font-bold mb-2 text-black dark:text-white uppercase tracking-wider">Priority</label>
                <div className="relative">
                  <select
                    value={form.priority}
                    onChange={e => setForm(f => ({ ...f, priority: e.target.value as Priority }))}
                    className="w-full bg-neutral-100 dark:bg-neutral-900 border-2 border-black dark:border-white rounded-lg px-3 py-2 text-black dark:text-white font-bold appearance-none focus:outline-none focus:shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:focus:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)]"
                  >
                    <option value="low">🟢 Low</option>
                    <option value="medium">🟡 Medium</option>
                    <option value="high">🟠 High</option>
                    <option value="urgent">🔴 Urgent</option>
                  </select>
                  <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-black dark:text-white">
                    <svg className="fill-current h-4 w-4" viewBox="0 0 20 20"><path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" /></svg>
                  </div>
                </div>
              </div>

              {/* Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={() => setShowModal(false)}
                  className="flex-1 bg-white dark:bg-black text-black dark:text-white border-2 border-black dark:border-white hover:bg-neutral-100 dark:hover:bg-neutral-900 px-4 py-3 rounded-xl font-black text-lg uppercase tracking-wider transition-all shadow-[4px_4px_0px_0px_rgba(0,0,0,1)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,1)] hover:translate-y-[-2px] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,1)] dark:hover:shadow-[6px_6px_0px_0px_rgba(255,255,255,1)]"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="flex-1 bg-accent text-white border-2 border-black dark:border-white px-4 py-3 rounded-xl font-black text-lg uppercase tracking-wider transition-all shadow-[4px_4px_0px_0px_rgba(0,0,0,0.5)] dark:shadow-[4px_4px_0px_0px_rgba(255,255,255,0.5)] hover:translate-y-[-2px] hover:shadow-[6px_6px_0px_0px_rgba(0,0,0,0.5)] dark:hover:shadow-[6px_6px_0px_0px_rgba(255,255,255,0.5)]"
                >
                  {editingId ? 'Save Changes' : 'Create Task'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
