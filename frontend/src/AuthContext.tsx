import { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { type User, getStoredToken, getStoredUser, devLogin, clearAuth, getMe } from './api'

interface AuthState {
  user: User | null
  loading: boolean
  login: (email: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(getStoredUser)
  const [loading, setLoading] = useState(true)

  // On mount, verify stored token or auto-login in dev mode
  useEffect(() => {
    const token = getStoredToken()
    if (token) {
      getMe()
        .then(setUser)
        .catch(() => {
          clearAuth()
          setUser(null)
        })
        .finally(() => setLoading(false))
    } else {
      // Auto dev login — skip the login page entirely
      devLogin('student@test.com')
        .then(data => {
          setUser({ id: data.user_id, name: data.name, email: 'student@test.com', role: data.role })
        })
        .catch(() => {})
        .finally(() => setLoading(false))
    }
  }, [])

  const login = useCallback(async (email: string) => {
    const data = await devLogin(email)
    setUser({ id: data.user_id, name: data.name, email, role: data.role })
  }, [])

  const logout = useCallback(() => {
    clearAuth()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
