/**
 * API client for Docere v2 backend.
 * All calls go through Vite proxy: /api → http://localhost:8000
 */

// ── Types ──

export interface User {
  id: string
  name: string
  email: string | null
  role: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user_id: string
  name: string
  role: string
}

export interface Course {
  id: string
  name: string
  course_code: string | null
}

export interface ConversationSummary {
  id: string
  course_id: string
  assignment_id: string | null
  title: string | null
  status: string
  started_at: string
  last_message_at: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  model_used: string | null
  token_count: number | null
  created_at: string
}

export interface ConversationDetail extends ConversationSummary {
  messages: Message[]
}

export interface AgentMessageResponse {
  message: Message
  strategy_used: string | null
  memory_context_tokens: number
}

// ── Token management ──

const TOKEN_KEY = 'docere_token'
const USER_KEY = 'docere_user'

export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getStoredUser(): User | null {
  const raw = localStorage.getItem(USER_KEY)
  return raw ? JSON.parse(raw) : null
}

export function storeAuth(token: string, user: User): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

// ── Fetch wrapper ──

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getStoredToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(path, { ...options, headers })

  if (res.status === 401) {
    clearAuth()
    window.location.reload()
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `API error ${res.status}`)
  }

  return res.json()
}

// ── Auth ──

export async function devLogin(email: string): Promise<TokenResponse> {
  const data = await apiFetch<TokenResponse>('/api/v1/auth/dev/login', {
    method: 'POST',
    body: JSON.stringify({ email }),
  })
  storeAuth(data.access_token, {
    id: data.user_id,
    name: data.name,
    email,
    role: data.role,
  })
  return data
}

export async function getMe(): Promise<User> {
  return apiFetch<User>('/api/v1/auth/me')
}

// ── Courses ──

export async function listCourses(): Promise<Course[]> {
  return apiFetch<Course[]>('/api/v1/courses/')
}

// ── Conversations ──

export async function createConversation(courseId: string, title?: string): Promise<ConversationSummary> {
  return apiFetch<ConversationSummary>('/api/v1/chat/conversations', {
    method: 'POST',
    body: JSON.stringify({ course_id: courseId, title }),
  })
}

export async function listConversations(courseId?: string): Promise<ConversationSummary[]> {
  const params = courseId ? `?course_id=${courseId}` : ''
  return apiFetch<ConversationSummary[]>(`/api/v1/chat/conversations${params}`)
}

export async function getConversation(conversationId: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/v1/chat/conversations/${conversationId}`)
}

// ── Messages ──

export async function sendMessage(conversationId: string, content: string): Promise<AgentMessageResponse> {
  return apiFetch<AgentMessageResponse>(`/api/v1/chat/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}
