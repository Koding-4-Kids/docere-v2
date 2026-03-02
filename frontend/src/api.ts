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

export interface StudyArtifact {
  type: 'notes' | 'flashcards' | 'study_guide' | 'slides'
  title: string
  content: string
  source_concepts: string[]
}

export interface MeetingAction {
  type: 'meeting_suggestion'
  reason: string
  concepts: string[]
}

// ── Student Widget Types ──

export interface QuizQuestion {
  question: string
  choices: string[]
  correct_index: number | null
  correct_answer: string
  explanation: string
}

export interface PracticeQuizWidget {
  type: 'practice_quiz'
  title: string
  concept: string
  questions: QuizQuestion[]
}

export interface StepHint {
  text: string
}

export interface StepHintsWidget {
  type: 'step_hints'
  title: string
  problem_context: string
  hints: StepHint[]
}

// ── Instructor Widget Types ──

export interface StudentCardWidget {
  type: 'student_card'
  student_name: string
  student_id: string
  engagement_level: string
  confusion_label: string
  grade_label: string
  total_interactions: number
  top_concepts: { name: string; mastery_label: string }[]
  recent_activity: string
  profile_summary: string
}

export interface AtRiskRow {
  student_name: string
  student_id: string
  risk_reason: string
  confusion_label: string
  engagement_level: string
  grade_label: string
  recommended_action: string
}

export interface AtRiskTableWidget {
  type: 'at_risk_table'
  title: string
  students: AtRiskRow[]
}

export interface HeatmapCell {
  concept: string
  mastery_label: string
  mastery_value: number
  student_count: number
  times_struggled: number
}

export interface ConceptHeatmapWidget {
  type: 'concept_heatmap'
  title: string
  cells: HeatmapCell[]
}

export interface EngagementBucket {
  level: string
  count: number
  student_names: string[]
}

export interface EngagementChartWidget {
  type: 'engagement_chart'
  title: string
  total_students: number
  buckets: EngagementBucket[]
}

export type StudentWidget = PracticeQuizWidget | StepHintsWidget
export type InstructorWidget = StudentCardWidget | AtRiskTableWidget | ConceptHeatmapWidget | EngagementChartWidget
export type Widget = StudentWidget | InstructorWidget

// ── Source References ──

export interface SourceRef {
  type: string
  label: string
  student_name: string | null
  detail: string | null
}

export interface SourceFilters {
  profiles: boolean
  mastery: boolean
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  model_used: string | null
  token_count: number | null
  created_at: string
  artifact: StudyArtifact | null
  action: MeetingAction | null
  widgets: Widget[] | null
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

// ── Assignments ──

export interface AssignmentSummary {
  id: string
  title: string | null
  material_type: string
}

export async function listAssignments(courseId: string): Promise<AssignmentSummary[]> {
  return apiFetch<AssignmentSummary[]>(`/api/v1/courses/${courseId}/assignments`)
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

export async function deleteConversation(conversationId: string): Promise<void> {
  const token = getStoredToken()
  const res = await fetch(`/api/v1/chat/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
  })
  if (!res.ok && res.status !== 204) {
    throw new Error('Failed to delete conversation')
  }
}

// ── Messages ──

export async function sendMessage(conversationId: string, content: string): Promise<AgentMessageResponse> {
  return apiFetch<AgentMessageResponse>(`/api/v1/chat/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  })
}

export async function sendMessageStream(conversationId: string, content: string, 
  onToken: (text: string) => void, 
  onError?: (message: string) => void,
): Promise<AgentMessageResponse> {
  const token = getStoredToken()
  const res = await fetch(`/api/v1/chat/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    headers: {
      'Accept': 'text/event-stream',
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content }),
  })

  if (res.status === 401) {
    clearAuth()
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error((body as { detail?: string }).detail || `API error ${res.status}`)
  }

  // Extract content type
  const contentType = res.headers.get('content-type') || ''

  // Fallback if the backend still returns JSON
  if (!contentType.includes('text/event-stream')) {
    const finalResponse = await res.json() as AgentMessageResponse
    return finalResponse
  }

  if (!res.body) {
    throw new Error('Streaming response body unavailable')
  }

  const decoder = new TextDecoder()
  const reader = res.body.getReader()
  let buffer = ''
  let finalResponse: AgentMessageResponse | null = null

  // Handle the events.
  const handleSseEvent = (rawEvent: string): void => {
    let eventType = 'message'
    const dataLines: string[] = []

    for (const line of rawEvent.split('\n')) {
      if (line.startsWith('event:')) {
        eventType = line.slice(6).trim()
      } else if (line.startsWith('data:')) {
        dataLines.push(line.slice(5).trim())
      }
    }
    if (!dataLines.length) return

    let payload: unknown
    try {
      payload = JSON.parse(dataLines.join('\n'))
    } catch {
      return
    }

    if (eventType === 'token') {
      const text = (payload as { text?: string }).text
      if (typeof text === 'string') onToken(text)
      return
    }

    if (eventType === 'final') {
      finalResponse = payload as AgentMessageResponse
      return
    }

    if (eventType === 'error') {
      const detail = (payload as { detail?: string }).detail || 'Streaming failed'
      onError?.(detail)
      throw new Error(detail)
    }
  }

  // Read the stream and handle the events
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')

    let boundary = buffer.indexOf('\n\n')
    while (boundary !== -1) {
      const rawEvent = buffer.slice(0, boundary)
      buffer = buffer.slice(boundary + 2)
      if (rawEvent.trim()) {
        handleSseEvent(rawEvent)
      }
      boundary = buffer.indexOf('\n\n')
    }
  }

  // Handle the final chunk
  buffer += decoder.decode().replace(/\r\n/g, '\n')

  if (buffer.trim()) {
    handleSseEvent(buffer)
  }

  if (!finalResponse) {
    throw new Error('Streaming ended before final response')
  }

  return finalResponse
}

// ── Calendar / Meetings ──

export interface TimeSlot {
  start: string
  end: string
  instructor_id: string
}

export interface MeetingRequest {
  id: string
  student_id: string
  instructor_id: string
  course_id: string
  conversation_id: string | null
  scheduled_start: string
  scheduled_end: string
  status: string
  context_summary: string | null
  struggle_concepts: string[] | null
  google_event_id: string | null
  created_at: string
}

export async function getAvailableSlots(courseId: string): Promise<TimeSlot[]> {
  return apiFetch<TimeSlot[]>(`/api/v1/calendar/available-slots/${courseId}`)
}

export async function bookMeeting(
  courseId: string,
  instructorId: string,
  slotStart: string,
  slotEnd: string,
  conversationId?: string,
): Promise<MeetingRequest> {
  return apiFetch<MeetingRequest>(`/api/v1/calendar/book/${courseId}`, {
    method: 'POST',
    body: JSON.stringify({
      instructor_id: instructorId,
      slot_start: slotStart,
      slot_end: slotEnd,
      conversation_id: conversationId || null,
    }),
  })
}

export async function listMeetings(courseId: string): Promise<MeetingRequest[]> {
  return apiFetch<MeetingRequest[]>(`/api/v1/calendar/meetings/${courseId}`)
}

export async function cancelMeeting(meetingId: string): Promise<void> {
  await apiFetch(`/api/v1/calendar/meetings/${meetingId}/cancel`, { method: 'POST' })
}

// ── Instructor Concepts ──

export interface AddConceptResponse {
  cell: HeatmapCell
  students_affected: number
  memories_matched: number
}

export async function addConcept(courseId: string, conceptName: string): Promise<AddConceptResponse> {
  return apiFetch<AddConceptResponse>(`/api/v1/instructor/dashboard/${courseId}/concepts`, {
    method: 'POST',
    body: JSON.stringify({ concept_name: conceptName }),
  })
}


// ── Integrations ──

export interface IntegrationStatus {
  google_connected: boolean
  google_scopes: string[]
  lms_type: string | null
  lms_connected: boolean
}

export interface ExecuteActionResponse {
  success: boolean
  result: Record<string, unknown>
  error: string | null
}

export interface MetaAction {
  type: 'draft_email' | 'create_doc' | 'create_sheet' | 'create_excel' | 'lms_announcement' | 'calendar_event'
  [key: string]: unknown
}

export async function getIntegrationStatus(): Promise<IntegrationStatus> {
  return apiFetch<IntegrationStatus>('/api/v1/integrations/status')
}

export async function executeAction(
  actionType: string,
  payload: Record<string, unknown>,
): Promise<ExecuteActionResponse> {
  return apiFetch<ExecuteActionResponse>('/api/v1/integrations/execute', {
    method: 'POST',
    body: JSON.stringify({ action_type: actionType, payload }),
  })
}

// ── Gradebook Sync ──

export interface SpreadsheetInfo {
  id: string
  title: string
  url: string
  modified_time: string
}

export interface SpreadsheetData {
  title: string
  headers: string[]
  rows: string[][]
}

export interface GradeItem {
  id: string
  name: string
  category: string
  grade_max: number
}

export interface ColumnMapping {
  student_name_col: number
  grade_columns: Record<string, number>
}

export interface ValidationIssue {
  row: number
  col: number
  type: string
  current: string
  expected: string
  suggestion: string
}

export interface ValidationResult {
  valid: boolean
  mappings: ColumnMapping | null
  issues: ValidationIssue[]
  preview: { student: string; student_lms_id: string; grades: { item: string; item_id: string; new: number }[] }[]
  student_count: number
}

export interface SyncResult {
  synced: number
  failed: number
  errors: { student: string; item_id: string; error: string }[]
}

export interface FixResult {
  fixed_data: SpreadsheetData
  changes: { row: number; col: number; old: string; new: string; reason: string }[]
}

export interface ExcelUploadResult extends SpreadsheetData {
  upload_id: string
  filename: string
  sheet_names: string[]
}

export async function listGoogleSpreadsheets(): Promise<SpreadsheetInfo[]> {
  return apiFetch<SpreadsheetInfo[]>('/api/v1/gradebook/sources/google')
}

export async function readGoogleSpreadsheet(spreadsheetId: string): Promise<SpreadsheetData> {
  return apiFetch<SpreadsheetData>('/api/v1/gradebook/sources/google/read', {
    method: 'POST',
    body: JSON.stringify({ spreadsheet_id: spreadsheetId }),
  })
}

export async function readGoogleSpreadsheetUrl(url: string): Promise<SpreadsheetData> {
  return apiFetch<SpreadsheetData>('/api/v1/gradebook/sources/google/read-url', {
    method: 'POST',
    body: JSON.stringify({ url }),
  })
}

export async function uploadExcel(file: File): Promise<ExcelUploadResult> {
  const token = getStoredToken()
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch('/api/v1/integrations/upload-excel', {
    method: 'POST',
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
    body: formData,
  })

  if (res.status === 401) {
    clearAuth()
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Upload failed: ${res.status}`)
  }
  return res.json()
}

export async function getGradeItems(courseId: string): Promise<GradeItem[]> {
  return apiFetch<GradeItem[]>(`/api/v1/gradebook/destinations/${courseId}/grade-items`)
}

export async function validateGradebook(
  sourceData: SpreadsheetData,
  courseId: string,
  gradeItemIds: string[],
): Promise<ValidationResult> {
  return apiFetch<ValidationResult>('/api/v1/gradebook/validate', {
    method: 'POST',
    body: JSON.stringify({ source_data: sourceData, course_id: courseId, grade_item_ids: gradeItemIds }),
  })
}

export async function syncGradebook(
  courseId: string,
  mappings: ColumnMapping,
  sourceData: SpreadsheetData,
  skipRows: number[] = [],
): Promise<SyncResult> {
  return apiFetch<SyncResult>('/api/v1/gradebook/sync', {
    method: 'POST',
    body: JSON.stringify({ course_id: courseId, mappings, source_data: sourceData, skip_rows: skipRows }),
  })
}

export async function fixGradebook(
  sourceData: SpreadsheetData,
  issues: ValidationIssue[],
): Promise<FixResult> {
  return apiFetch<FixResult>('/api/v1/gradebook/fix', {
    method: 'POST',
    body: JSON.stringify({ source_data: sourceData, issues }),
  })
}

// ── Flashcard Spaced Repetition ──

export interface FlashcardCard {
  id: string
  front: string
  back: string
  concepts: string[] | null
  state: string
  due_at: string
  reps: number
  lapses: number
}

export interface ReviewSession {
  cards: FlashcardCard[]
  total_due: number
  deck_id: string
}

export interface ReviewResult {
  card_id: string
  new_state: string
  new_due_at: string
  scheduled_days: number
}

export interface DueCount {
  course_id: string
  due_count: number
}

export async function getReviewSession(courseId: string, limit = 20): Promise<ReviewSession> {
  return apiFetch<ReviewSession>(`/api/v1/flashcards/courses/${courseId}/review?limit=${limit}`)
}

export async function reviewCard(
  cardId: string,
  rating: number,
  reviewDurationMs?: number,
): Promise<ReviewResult> {
  return apiFetch<ReviewResult>(`/api/v1/flashcards/cards/${cardId}/review`, {
    method: 'POST',
    body: JSON.stringify({ rating, review_duration_ms: reviewDurationMs }),
  })
}

export async function undoCardReview(cardId: string): Promise<ReviewResult> {
  return apiFetch<ReviewResult>(`/api/v1/flashcards/cards/${cardId}/undo`, {
    method: 'POST',
  })
}

export async function getDueCounts(): Promise<DueCount[]> {
  return apiFetch<DueCount[]>('/api/v1/flashcards/due-counts')
}
