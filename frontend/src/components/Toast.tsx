export type ToastType = 'success' | 'error' | 'info'

export interface ToastListItem {
  id: string
  message: string
  type: ToastType
}

interface ToastProps {
  id: string
  message: string
  type: ToastType
  onDismiss: (id: string) => void
}

const typeStyles: Record<ToastType, string> = {
  success: 'bg-green-600 text-white border-green-700 dark:bg-green-700 dark:border-green-800',
  error: 'bg-red-600 text-white border-red-700 dark:bg-red-700 dark:border-red-800',
  info: 'bg-blue-600 text-white border-blue-700 dark:bg-blue-700 dark:border-blue-800',
}

export function Toast({ id, message, type, onDismiss }: ToastProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg animate-fade-in ${typeStyles[type]}`}
    >
      <span className="flex-1 text-sm min-w-0">{message}</span>
      <button
        type="button"
        onClick={() => onDismiss(id)}
        className="shrink-0 p-1 rounded hover:opacity-80 focus:outline-none focus:ring-2 focus:ring-white/50"
        aria-label="Dismiss"
      >
        <span aria-hidden="true">×</span>
      </button>
    </div>
  )
}

interface ToastListProps {
  toasts: ToastListItem[]
  onDismiss: (id: string) => void
}

export function ToastList({ toasts, onDismiss }: ToastListProps) {
  if (toasts.length === 0) return null
  return (
    <div
      className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm w-full"
      role="status"
      aria-live="polite"
    >
      {toasts.map(t => (
        <Toast
          key={t.id}
          id={t.id}
          message={t.message}
          type={t.type}
          onDismiss={onDismiss}
        />
      ))}
    </div>
  )
}
