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

async function apiFetch<T>(path: string, options: RequestInit = {}, retries = 2): Promise<T> {
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

  // Retry on rate limit with exponential backoff
  if (res.status === 429 && retries > 0) {
    const retryAfter = Number(res.headers.get('X-RateLimit-Reset') || '2')
    const delay = Math.min(retryAfter * 1000, 5000)
    await new Promise(r => setTimeout(r, delay))
    return apiFetch<T>(path, options, retries - 1)
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

export async function sendMessage(conversationId: string, content: string, notesContent?: string): Promise<AgentMessageResponse> {
  return apiFetch<AgentMessageResponse>(`/api/v1/chat/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content, notes_content: notesContent || null }),
  })
}

export interface StreamDoneMeta {
  message_id: string
  chat_text: string
  artifact: StudyArtifact | null
  action: MeetingAction | null
  widgets: Widget[]
  strategy_used: string | null
}

/**
 * Stream a message response via SSE (POST with auth headers).
 * Uses fetch + ReadableStream instead of EventSource (which only supports GET).
 */
export async function streamMessage(
  conversationId: string,
  content: string,
  onToken: (text: string) => void,
  onDone: (meta: StreamDoneMeta) => void,
  onError: (err: string) => void,
  notesContent?: string,
): Promise<void> {
  const token = getStoredToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const res = await fetch(`/api/v1/chat/conversations/${conversationId}/messages/stream`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ content, notes_content: notesContent || null }),
  })

  if (res.status === 401) {
    clearAuth()
    window.location.reload()
    throw new Error('Unauthorized')
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    onError(body.detail || `API error ${res.status}`)
    return
  }

  const reader = res.body?.getReader()
  if (!reader) {
    onError('No response body')
    return
  }

  const decoder = new TextDecoder()
  let buffer = ''
  let receivedDone = false

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      // Keep the last (possibly incomplete) line in the buffer
      buffer = lines.pop() || ''

      let currentEvent = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) {
          currentEvent = line.slice(7).trim()
        } else if (line.startsWith('data: ')) {
          const data = line.slice(6)
          try {
            const parsed = JSON.parse(data)
            if (currentEvent === 'token') {
              onToken(parsed.text)
            } else if (currentEvent === 'done') {
              receivedDone = true
              onDone(parsed as StreamDoneMeta)
            } else if (currentEvent === 'error') {
              onError(parsed.detail || 'Stream error')
              return
            }
          } catch {
            // Ignore malformed JSON lines
          }
          currentEvent = ''
        }
      }
    }
  } catch (err) {
    // Network error or connection drop mid-stream
    if (!receivedDone) {
      onError('Connection lost — please try again.')
    }
    return
  }

  // Stream ended without a done event — connection dropped after some tokens
  if (!receivedDone) {
    onError('Response interrupted — please try again.')
  }
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

export async function downloadFixedExcel(sourceData: SpreadsheetData): Promise<void> {
  const token = getStoredToken()
  const res = await fetch('/api/v1/gradebook/download-excel', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(sourceData),
  })
  if (!res.ok) throw new Error('Download failed')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${(sourceData.title || 'Gradebook').replace(/ /g, '_')}.xlsx`
  a.click()
  URL.revokeObjectURL(url)
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

// ── Student Documents ──

export interface StudentDocument {
  id: string
  filename: string
  status: 'uploaded' | 'processing' | 'completed' | 'failed'
  chunk_count: number
  page_count: number | null
  file_size_bytes: number
  created_at: string
  error_message: string | null
  doc_type: string | null
}

export interface StudentDocumentDetail extends StudentDocument {
  extracted_text: string | null
  has_file: boolean
}

export async function fetchDocumentFileBlob(docId: string): Promise<Blob> {
  const token = getStoredToken()
  const res = await fetch(`/api/v1/documents/${docId}/file`, {
    headers: token ? { 'Authorization': `Bearer ${token}` } : {},
  })
  if (res.status === 401) {
    clearAuth()
    window.location.reload()
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`Failed to fetch file: ${res.status}`)
  return res.blob()
}

export interface DocumentUploadResponse {
  doc_id: string
  filename: string
  status: string
  extracted_text: string
  page_count: number | null
}

export async function uploadDocument(courseId: string, file: File): Promise<DocumentUploadResponse> {
  const token = getStoredToken()
  const formData = new FormData()
  formData.append('file', file)
  formData.append('course_id', courseId)

  const res = await fetch('/api/v1/documents/upload', {
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

export async function uploadDocumentFromUrl(courseId: string, url: string): Promise<DocumentUploadResponse> {
  return apiFetch<DocumentUploadResponse>('/api/v1/documents/upload-url', {
    method: 'POST',
    body: JSON.stringify({ course_id: courseId, url }),
  })
}

export async function listDocuments(courseId?: string): Promise<StudentDocument[]> {
  const params = courseId ? `?course_id=${courseId}` : ''
  return apiFetch<StudentDocument[]>(`/api/v1/documents${params}`)
}

export async function getDocument(docId: string): Promise<StudentDocumentDetail> {
  return apiFetch<StudentDocumentDetail>(`/api/v1/documents/${docId}`)
}

export async function confirmDocument(docId: string): Promise<void> {
  await apiFetch<unknown>(`/api/v1/documents/${docId}/confirm`, { method: 'POST' })
}

export async function getDocumentStatus(docId: string): Promise<StudentDocument> {
  return apiFetch<StudentDocument>(`/api/v1/documents/${docId}/status`)
}

export async function deleteDocument(docId: string): Promise<void> {
  await apiFetch<void>(`/api/v1/documents/${docId}`, { method: 'DELETE' })
}

// ── Student Memory Graph ──

export interface MemoryGraphNode {
  id: string
  name: string
  type: 'memory' | 'concept' | 'document'
  // Memory fields
  memory_type?: string | null
  content?: string | null
  concepts?: string[] | null
  confusion_score?: number | null
  sentiment?: string | null
  // Concept fields
  mastery_level?: number | null
  mastery_label?: string | null
  times_practiced?: number | null
  times_struggled?: number | null
  // Document fields
  doc_type?: string | null
  filename?: string | null
  status?: string | null
  page_count?: number | null
  chunk_count?: number | null
}

export interface MemoryGraphEdge {
  source: string
  target: string
  type: 'memory_concept' | 'doc_concept' | 'concept_concept' | 'memory_memory'
  weight?: number | null
}

export interface MemoryGraphData {
  nodes: MemoryGraphNode[]
  edges: MemoryGraphEdge[]
}

export async function getMyMemoryGraph(courseId: string): Promise<MemoryGraphData> {
  return apiFetch<MemoryGraphData>(`/api/v1/memory/me/${courseId}/graph`)
}
