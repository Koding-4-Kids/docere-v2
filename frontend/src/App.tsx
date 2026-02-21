import { useState } from 'react'
import { AuthProvider, useAuth } from './AuthContext'
import { ChatPage } from './pages/ChatPage'
import { LTICallbackPage } from './pages/LTICallbackPage'
import { InstructorDashboardPage } from './pages/InstructorDashboardPage'
import { Icons } from './components/ClaudeChatInput'
import './index.css'

function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim()) return
    setLoading(true)
    setError('')
    try {
      await login(email.trim())
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-bg-0 text-text-100">
      <div className="w-full max-w-sm p-8 animate-fade-in">
        <div className="flex justify-center mb-6">
          <Icons.Logo className="w-16 h-16" />
        </div>
        <h1 className="text-2xl font-serif text-center text-text-200 mb-1">Docere</h1>
        <p className="text-sm text-text-400 text-center mb-8">Sign in to your AI tutor</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="you@college.edu"
            className="w-full px-4 py-3 rounded-xl border border-bg-300 bg-bg-100 text-text-100 placeholder:text-text-500 focus:outline-none focus:border-accent/50 text-sm"
            autoFocus
          />
          {error && <p className="text-sm text-red-500">{error}</p>}
          <button
            type="submit"
            disabled={loading || !email.trim()}
            className="w-full py-3 rounded-xl bg-accent text-white font-medium text-sm hover:bg-accent-hover transition-colors disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <p className="text-xs text-text-500 text-center mt-6">
          Development login — enter any email to get started
        </p>
      </div>
    </div>
  )
}

function AppContent() {
  const { user, loading } = useAuth()

  // Handle LTI callback route before auth check
  if (window.location.pathname === '/lti/callback') {
    return <LTICallbackPage />
  }

  // Handle instructor dashboard route (self-contained auth from hash fragment)
  if (window.location.pathname.startsWith('/instructor/dashboard/')) {
    return <InstructorDashboardPage />
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-bg-0">
        <Icons.Logo className="w-12 h-12 animate-pulse" />
      </div>
    )
  }

  if (!user) return <LoginPage />
  return <ChatPage />
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}
