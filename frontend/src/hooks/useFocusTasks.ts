import { useState, useEffect } from 'react'

export type TaskStatus = 'planned' | 'in-progress' | 'done'
export type Priority = 'low' | 'medium' | 'high' | 'urgent'

export interface FocusTask {
  id: string
  title: string
  note: string
  status: TaskStatus
  priority: Priority
  createdAt: string
}

const STORAGE_KEY = 'docere-focus-tasks'

function loadTasks(): FocusTask[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

export function useFocusTasks() {
  const [tasks, setTasks] = useState<FocusTask[]>(loadTasks)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tasks))
  }, [tasks])

  const addTask = (data: Omit<FocusTask, 'id' | 'createdAt'>) => {
    const task: FocusTask = {
      ...data,
      id: crypto.randomUUID(),
      createdAt: new Date().toISOString(),
    }
    setTasks(prev => [task, ...prev])
  }

  const updateTask = (id: string, updates: Partial<Omit<FocusTask, 'id' | 'createdAt'>>) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, ...updates } : t))
  }

  const moveTask = (id: string, status: TaskStatus) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, status } : t))
  }

  const deleteTask = (id: string) => {
    setTasks(prev => prev.filter(t => t.id !== id))
  }

  return { tasks, addTask, updateTask, moveTask, deleteTask }
}
