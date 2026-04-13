import React from 'react'

/** Pluggable logger so it can be swapped for a reporting service in production. */
export function logError(error: Error, errorInfo: React.ErrorInfo): void {
  if (typeof console !== 'undefined' && console.error) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }
}

function ErrorFallback() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-bg-0 text-text-100 px-4">
      <h1 className="text-xl font-semibold text-text-200 mb-2">Something went wrong</h1>
      <p className="text-sm text-text-400 text-center mb-6 max-w-sm">
        An unexpected error occurred. Please reload the page.
      </p>
      <button
        type="button"
        onClick={() => window.location.reload()}
        className="px-4 py-2 rounded-lg bg-accent text-white text-sm font-medium hover:bg-accent-hover transition-colors"
      >
        Reload
      </button>
    </div>
  )
}

interface ErrorBoundaryProps {
  children: React.ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
}

export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo): void {
    logError(error, errorInfo)
  }

  render(): React.ReactNode {
    if (this.state.hasError) {
      return <ErrorFallback />
    }
    return this.props.children
  }
}
