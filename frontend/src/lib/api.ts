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

export interface Contact {
  id: number
  user_id: number
  name: string
  phone_number: string
  group_name: string
  notes: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface ContactCreate {
  name: string
  phone_number: string
  group_name?: string
  notes?: string
}

export interface ContactGroupSummary {
  group_name: string
  count: number
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
  list: (params?: { page?: number; limit?: number }) =>
    api.get<PaginatedResponse<Meeting>>("/meetings/", { params }),
  
  get: (id: number) => api.get<Meeting>(`/meetings/${id}`),
  
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

export const contactsApi = {
  list: (params?: { group?: string; search?: string; page?: number; limit?: number }) =>
    api.get<PaginatedResponse<Contact>>("/contacts/", { params }),

  get: (id: number) => api.get<Contact>(`/contacts/${id}`),

  create: (data: ContactCreate) => api.post<Contact>("/contacts/", data),

  createBulk: (contacts: ContactCreate[]) =>
    api.post<Contact[]>("/contacts/bulk", { contacts }),

  update: (id: number, data: Partial<ContactCreate>) =>
    api.put<Contact>(`/contacts/${id}`, data),

  delete: (id: number) => api.delete(`/contacts/${id}`),

  getByGroup: (groupName: string) =>
    api.get<{ group_name: string; count: number; contacts: Contact[] }>(`/contacts/group/${groupName}`),

  getGroupsSummary: () =>
    api.get<ContactGroupSummary[]>("/contacts/groups"),
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
