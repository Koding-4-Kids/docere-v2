import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { ToastList } from '../components/Toast'
import type { ToastType } from '../components/Toast'

export type { ToastType } from '../components/Toast'

const TOAST_AUTO_DISMISS_MS = 4000
const MAX_TOASTS = 5

export interface ToastItem {
  id: string
  message: string
  type: ToastType
  createdAt: number
}

interface ToastContextValue {
  addToast: (message: string, type: ToastType) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([])
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const removeToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
    const timer = timersRef.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timersRef.current.delete(id)
    }
  }, [])

  const addToast = useCallback((message: string, type: ToastType) => {
    const id = crypto.randomUUID()
    const createdAt = Date.now()
    const item: ToastItem = { id, message, type, createdAt }
    setToasts(prev => {
      const next = prev.length >= MAX_TOASTS ? prev.slice(-(MAX_TOASTS - 1)) : prev
      return [...next, item]
    })
  }, [])

  useEffect(() => {
    const now = Date.now()
    toasts.forEach(t => {
      if (timersRef.current.has(t.id)) return
      const delay = Math.max(0, t.createdAt + TOAST_AUTO_DISMISS_MS - now)
      const timer = setTimeout(() => removeToast(t.id), delay)
      timersRef.current.set(t.id, timer)
    })
    const currentIds = new Set(toasts.map(t => t.id))
    timersRef.current.forEach((timer, id) => {
      if (!currentIds.has(id)) {
        clearTimeout(timer)
        timersRef.current.delete(id)
      }
    })
  }, [toasts, removeToast])

  useEffect(() => {
    return () => {
      timersRef.current.forEach(timer => clearTimeout(timer))
      timersRef.current.clear()
    }
  }, [])

  const value: ToastContextValue = { addToast }

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastList
        toasts={toasts}
        onDismiss={removeToast}
      />
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (ctx === null) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return ctx
}
