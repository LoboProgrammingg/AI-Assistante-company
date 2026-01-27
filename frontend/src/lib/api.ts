import axios, { type AxiosInstance, type AxiosError } from "axios"

const API_URL = import.meta.env.VITE_API_URL || "/api/v1"

const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token")
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token")
      window.location.href = "/login"
    }
    return Promise.reject(error)
  }
)

export interface User {
  id: number
  phone_number: string
  name: string | null
  timezone: string
  language: string
  is_active: boolean
  created_at: string
}

export interface UserStats {
  total_reminders: number
  active_reminders: number
  completed_reminders: number
  total_transactions: number
  total_income: number
  total_expenses: number
  total_meetings: number
  total_messages: number
}

export interface Reminder {
  id: number
  user_id: number
  title: string
  description: string | null
  scheduled_time: string
  remind_before_minutes: number
  recurrence_type: "once" | "daily" | "weekdays" | "weekends" | "weekly" | "monthly"
  is_active: boolean
  is_completed: boolean
  notified: boolean
  created_at: string
  updated_at: string
}

export interface Finance {
  id: number
  user_id: number
  type: "income" | "expense"
  amount: number
  description: string
  category_id: number | null
  category?: FinanceCategory
  transaction_date: string
  is_recurring: boolean
  tags: string[]
  created_at: string
}

export interface FinanceCategory {
  id: number
  name: string
  type: "income" | "expense"
  icon: string | null
  color: string | null
}

export interface FinanceSummary {
  period: { start: string; end: string }
  summary: {
    total_income: number
    total_expenses: number
    balance: number
    transaction_count: number
  }
  by_category: Array<{
    category: string
    amount: number
    percentage: number
  }>
}

export type MeetingStatus = "not_recorded" | "recording" | "uploading" | "processing" | "ready" | "failed"

export interface Meeting {
  id: number
  user_id: number
  title: string
  date: string
  duration_minutes: number | null
  summary: string | null
  transcription?: string | null
  audio_url?: string | null
  key_topics: Array<{ topic: string; summary?: string }>
  action_items: Array<{ 
    task: string
    responsible?: string
    status: string
    priority?: string
    deadline?: string 
  }>
  participants: Array<{ name: string; role?: string }>
  decisions: Array<{ decision: string; context?: string }>
  sentiment: string | null
  keywords: string[]
  created_at: string
  updated_at?: string
  // Campos de listagem
  key_topics_count?: number
  action_items_count?: number
  participants_count?: number
  // Novos campos v2
  google_event_id?: string
  meet_url?: string
  start_time?: string
  end_time?: string
  record_enabled?: boolean
  status?: MeetingStatus
  has_transcript?: boolean
  short_summary?: string
  error_message?: string
}

export interface MeetingSession {
  id: number
  meeting_id: number
  source_type: "realtime" | "manual_upload"
  status: "recording" | "uploading" | "processing" | "ready" | "failed"
  started_at: string
  ended_at?: string
  duration_seconds?: number
  chunks_count: number
  error_message?: string
  created_at: string
}

export interface MeetingArtifact {
  id: number
  meeting_id: number
  transcript_text?: string
  transcript_language: string
  executive_summary?: string
  short_summary?: string
  topics: Array<{ topic: string; summary?: string }>
  action_items: Array<{ task: string; owner?: string; due_date?: string; confidence: number }>
  decisions: Array<{ decision: string; context?: string; made_by?: string }>
  risks_blockers: string[]
  participants_detected: string[]
  transcription_model?: string
  summarization_model?: string
  processing_time_seconds?: number
  created_at: string
}

export interface MeetingDetail extends Meeting {
  sessions: MeetingSession[]
  artifacts: MeetingArtifact[]
}

export interface SyncGoogleCalendarResponse {
  synced_count: number
  created_count: number
  updated_count: number
  meetings: Meeting[]
  message: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  limit: number
  pages: number
  has_next: boolean
  has_prev: boolean
}

export interface ChatMessage {
  role: "user" | "assistant"
  content: string
  timestamp: string
  intent?: string
  entities?: Record<string, unknown>
}

export interface AuthUser {
  id: number
  name: string | null
  email: string
  phone_number: string
  is_verified: boolean
  is_active: boolean
  created_at: string
}

export interface LoginResponse {
  access_token: string
  token_type: string
  user: AuthUser
}

export interface RegisterData {
  name: string
  email: string
  password: string
  password_confirm: string
  phone_number: string
}

export const authApi = {
  register: (data: RegisterData) =>
    api.post<{ message: string; email: string; requires_verification: boolean }>("/auth/register", data),
  
  verifyEmail: (data: { email: string; code: string }) =>
    api.post<{ message: string; verified: boolean }>("/auth/verify-email", data),
  
  resendCode: (data: { email: string }) =>
    api.post<{ message: string }>("/auth/resend-code", data),
  
  login: (data: { email: string; password: string }) =>
    api.post<LoginResponse>("/auth/login", data),
  
  forgotPassword: (data: { email: string }) =>
    api.post<{ message: string }>("/auth/forgot-password", data),
  
  resetPassword: (data: { email: string; code: string; new_password: string; new_password_confirm: string }) =>
    api.post<{ message: string }>("/auth/reset-password", data),
  
  changePassword: (data: { current_password: string; new_password: string; new_password_confirm: string }) =>
    api.post<{ message: string }>("/auth/change-password", data),
}

export const usersApi = {
  create: (data: { phone_number: string; name?: string }) =>
    api.post<User>("/users/", data),
  
  getMe: () => api.get<User>("/users/me"),
  
  updateMe: (data: Partial<User>) => api.put<User>("/users/me", data),
  
  getStats: () => api.get<UserStats>("/users/me/stats"),
  
  getToken: (phone_number: string) =>
    api.post<{ access_token: string; token_type: string }>("/users/token", { phone_number }),
}

export const remindersApi = {
  list: (params?: { status?: string; page?: number; limit?: number }) =>
    api.get<PaginatedResponse<Reminder>>("/reminders/", { params }),
  
  getUpcoming: (hours = 24) =>
    api.get<{ items: Reminder[]; count: number }>("/reminders/upcoming", { params: { hours } }),
  
  get: (id: number) => api.get<Reminder>(`/reminders/${id}`),
  
  create: (data: Partial<Reminder>) => api.post<Reminder>("/reminders/", data),
  
  update: (id: number, data: Partial<Reminder>) =>
    api.put<Reminder>(`/reminders/${id}`, data),
  
  delete: (id: number) => api.delete(`/reminders/${id}`),
  
  complete: (id: number) => api.post<Reminder>(`/reminders/${id}/complete`),
}

export const financesApi = {
  list: (params?: {
    type?: string
    start_date?: string
    end_date?: string
    page?: number
    limit?: number
  }) => api.get<PaginatedResponse<Finance>>("/finances/", { params }),
  
  get: (id: number) => api.get<Finance>(`/finances/${id}`),
  
  create: (data: Partial<Finance>) => api.post<Finance>("/finances/", data),
  
  update: (id: number, data: Partial<Finance>) =>
    api.put<Finance>(`/finances/${id}`, data),
  
  delete: (id: number) => api.delete(`/finances/${id}`),
  
  getSummary: (start_date: string, end_date: string) =>
    api.get<FinanceSummary>("/finances/summary", { params: { start_date, end_date } }),
  
  getMonthlySummary: (year: number, month: number) =>
    api.get<FinanceSummary>("/finances/summary/monthly", { params: { year, month } }),
  
  getTrend: (months = 6) =>
    api.get<{ data: Array<{ month: string; income: number; expenses: number; balance: number }> }>(
      "/finances/trend",
      { params: { months } }
    ),
  
  getCategories: () =>
    api.get<{ expense_categories: FinanceCategory[]; income_categories: FinanceCategory[] }>(
      "/finances/categories"
    ),
}

export const meetingsApi = {
  // Legacy endpoints
  list: (params?: { page?: number; limit?: number; upcoming_only?: boolean; status_filter?: string }) =>
    api.get<PaginatedResponse<Meeting>>("/meetings", { params }),
  
  get: (id: number) => api.get<MeetingDetail>(`/meetings/${id}`),
  
  create: (data: Partial<Meeting>) => api.post<Meeting>("/meetings/", data),
  
  update: (id: number, data: Partial<Meeting>) =>
    api.put<Meeting>(`/meetings/${id}`, data),
  
  delete: (id: number) => api.delete(`/meetings/${id}`),
  
  search: (q: string) =>
    api.get<{ results: Meeting[]; count: number }>("/meetings/search", { params: { q } }),
  
  getPendingActionItems: () =>
    api.get<{ items: Array<{ task: string; meeting_id: number; meeting_title: string }>; count: number }>(
      "/meetings/action-items/pending"
    ),
  
  updateActionItemStatus: (meetingId: number, itemIndex: number, status: string) =>
    api.patch<Meeting>(`/meetings/${meetingId}/action-items/${itemIndex}`, null, {
      params: { status },
    }),

  // V2 Recording/Transcription endpoints
  syncGoogleCalendar: (daysAhead = 30) =>
    api.post<SyncGoogleCalendarResponse>("/meetings/sync-google-calendar", null, {
      params: { days_ahead: daysAhead },
    }),

  enableRecording: (meetingId: number, enabled = true) =>
    api.post<{ meeting_id: number; record_enabled: boolean; message: string }>(
      `/meetings/${meetingId}/enable-recording`,
      { enabled }
    ),

  startSession: (meetingId: number) =>
    api.post<{ session_id: number; meeting_id: number; status: string; upload_endpoint: string }>(
      `/meetings/${meetingId}/sessions`
    ),

  uploadChunk: (meetingId: number, sessionId: number, chunk: Blob, chunkIndex: number, startMs?: number, endMs?: number) => {
    const formData = new FormData()
    formData.append("file", chunk, `chunk_${chunkIndex}.webm`)
    return api.post<{ chunk_id: number; chunk_index: number; received: boolean }>(
      `/meetings/${meetingId}/sessions/${sessionId}/chunks`,
      formData,
      {
        params: { chunk_index: chunkIndex, start_ms: startMs, end_ms: endMs },
        headers: { "Content-Type": "multipart/form-data" },
      }
    )
  },

  stopSession: (meetingId: number, sessionId: number) =>
    api.post<{ session_id: number; status: string; message: string }>(
      `/meetings/${meetingId}/sessions/${sessionId}/stop`
    ),

  uploadRecording: (meetingId: number, file: File) => {
    const formData = new FormData()
    formData.append("file", file)
    return api.post<{ session_id: number; meeting_id: number; file_size_bytes: number; status: string }>(
      `/meetings/${meetingId}/upload`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } }
    )
  },

  reprocess: (meetingId: number, transcribe = true, summarize = true) =>
    api.post<{ meeting_id: number; session_id: number; message: string }>(
      `/meetings/${meetingId}/reprocess`,
      { transcribe, summarize }
    ),
}

export const chatApi = {
  sendMessage: (message: string) =>
    api.post<{
      response: string
      intent: string
      entities: Record<string, unknown>
      next_action: string
    }>("/chat/message", { message }),
  
  sendAudio: (audioFile: File) => {
    const formData = new FormData()
    formData.append("audio", audioFile)
    return api.post<{
      response: string
      intent: string
      entities: Record<string, unknown>
      next_action: string
      transcription: string
      is_meeting: boolean
      meeting_id?: number
    }>("/chat/audio", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  },
}

// ==================== Tarefas ====================

export interface Task {
  id: number
  title: string
  description: string | null
  status: "backlog" | "todo" | "in_progress" | "done" | "cancelled"
  priority: "low" | "medium" | "high" | "urgent"
  due_date: string | null
  project_id: number | null
  parent_id: number | null
  labels: number[]
  remind_before_minutes: number
  recurrence_type: string
  estimated_minutes: number | null
  actual_minutes: number | null
  is_active: boolean
  notified: boolean
  completed_at: string | null
  created_at: string
  updated_at: string
  subtask_count: number
  is_overdue: boolean
}

export interface TaskCreate {
  title: string
  description?: string
  priority?: string
  status?: string
  due_date?: string
  project_id?: number
  parent_id?: number
  labels?: number[]
  remind_before_minutes?: number
  recurrence_type?: string
  estimated_minutes?: number
}

export interface TaskUpdate {
  title?: string
  description?: string
  priority?: string
  status?: string
  due_date?: string
  project_id?: number
  labels?: number[]
  remind_before_minutes?: number
  estimated_minutes?: number
}

export interface TaskSummary {
  total: number
  by_status: Record<string, number>
  by_priority: Record<string, number>
  overdue: number
  due_today: number
}

export interface KanbanBoard {
  backlog: Task[]
  todo: Task[]
  in_progress: Task[]
  done: Task[]
}

export interface Project {
  id: number
  name: string
  description: string | null
  color: string
  icon: string | null
  is_active: boolean
  is_favorite: boolean
  created_at: string
}

export interface TaskLabel {
  id: number
  name: string
  color: string
  created_at: string
}

export const tasksApi = {
  list: (params?: { status?: string; priority?: string; project_id?: number; limit?: number }) =>
    api.get<Task[]>("/tasks/", { params }),

  get: (id: number) => api.get<Task>(`/tasks/${id}`),

  create: (data: TaskCreate) => api.post<Task>("/tasks/", data),

  update: (id: number, data: TaskUpdate) => api.put<Task>(`/tasks/${id}`, data),

  delete: (id: number) => api.delete(`/tasks/${id}`),

  complete: (id: number) => api.post<Task>(`/tasks/${id}/complete`),

  getKanban: (project_id?: number) =>
    api.get<KanbanBoard>("/tasks/kanban", { params: { project_id } }),

  getSummary: () => api.get<TaskSummary>("/tasks/summary"),

  getOverdue: () => api.get<Task[]>("/tasks/overdue"),

  getUpcoming: (hours?: number) =>
    api.get<Task[]>("/tasks/upcoming", { params: { hours } }),

  getSubtasks: (id: number) => api.get<Task[]>(`/tasks/${id}/subtasks`),

  // Projects
  listProjects: () => api.get<Project[]>("/tasks/projects/"),

  createProject: (data: { name: string; description?: string; color?: string }) =>
    api.post<Project>("/tasks/projects/", data),

  deleteProject: (id: number) => api.delete(`/tasks/projects/${id}`),

  // Labels
  listLabels: () => api.get<TaskLabel[]>("/tasks/labels/"),

  createLabel: (data: { name: string; color?: string }) =>
    api.post<TaskLabel>("/tasks/labels/", data),

  deleteLabel: (id: number) => api.delete(`/tasks/labels/${id}`),
}

export interface Document {
  id: number
  user_id: number
  filename: string
  original_filename: string
  file_size: number
  mime_type: string | null
  title: string | null
  description: string | null
  category: "work" | "personal" | "study" | "finance" | "health" | "legal" | "other"
  tags: string[]
  content_text: string | null
  embedding_status: string
  send_to_ai: boolean
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface DocumentListResponse {
  items: Document[]
  total: number
  page: number
  pages: number
  has_next: boolean
  has_prev: boolean
  ai_count: number
  ai_limit: number
}

export interface DocumentStats {
  total_documents: number
  ai_documents: number
  ai_limit: number
  by_category: Record<string, number>
  total_size_bytes: number
}

// ==================== Integrações (Google Calendar, etc) ====================

export interface IntegrationStatus {
  provider: string
  connected: boolean
  account_email?: string
  account_name?: string
}

export interface ConnectResponse {
  authorization_url: string
}

export interface AvailableIntegration {
  provider: string
  name: string
  description: string
  configured: boolean
  icon: string
}

export const integrationsApi = {
  // Google Calendar
  getGoogleCalendarStatus: () =>
    api.get<IntegrationStatus>("/integrations/google-calendar/status"),

  connectGoogleCalendar: () =>
    api.get<ConnectResponse>("/integrations/google-calendar/connect"),

  disconnectGoogleCalendar: () =>
    api.delete<{ success: boolean; message: string }>("/integrations/google-calendar/disconnect"),

  // Listar integrações disponíveis
  getAvailable: () =>
    api.get<{ integrations: AvailableIntegration[] }>("/integrations/available"),
}

export const documentsApi = {
  list: (params?: { category?: string; send_to_ai?: boolean; search?: string; page?: number; limit?: number }) =>
    api.get<DocumentListResponse>("/documents/", { params }),

  get: (id: number) => api.get<Document>(`/documents/${id}`),

  upload: (file: File, data: { title?: string; description?: string; category?: string; tags?: string; send_to_ai?: boolean }) => {
    const formData = new FormData()
    formData.append("file", file)
    if (data.title) formData.append("title", data.title)
    if (data.description) formData.append("description", data.description)
    if (data.category) formData.append("category", data.category)
    if (data.tags) formData.append("tags", data.tags)
    formData.append("send_to_ai", String(data.send_to_ai || false))
    return api.post<Document>("/documents/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    })
  },

  update: (id: number, data: Partial<{ title: string; description: string; category: string; tags: string[]; send_to_ai: boolean }>) =>
    api.put<Document>(`/documents/${id}`, data),

  toggleAi: (id: number) => api.post<Document>(`/documents/${id}/toggle-ai`),

  delete: (id: number, permanent?: boolean) =>
    api.delete(`/documents/${id}`, { params: { permanent } }),

  getStats: () => api.get<DocumentStats>("/documents/stats"),

  download: (id: number) => {
    const token = localStorage.getItem("token")
    const baseUrl = import.meta.env.VITE_API_URL || "/api/v1"
    window.open(`${baseUrl}/documents/${id}/download?token=${token}`, "_blank")
  },
}

export default api
