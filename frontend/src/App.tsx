import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { Toaster } from "react-hot-toast"
import { useEffect } from "react"

import { Layout } from "@/components/layout/Layout"
import {
  Dashboard,
  Login,
  Register,
  VerifyEmail,
  ForgotPassword,
  ResetPassword,
  Finances,
  Reminders,
  Meetings,
  MeetingDetail,
  Chat,
  Settings,
  Contacts,
  Documents,
  Todoist,
} from "@/pages"
import { useAuthStore } from "@/stores/auth"
import { initializeTheme } from "@/stores/theme"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 1000 * 60 * 2, // 2 minutos
      gcTime: 1000 * 60 * 10, // 10 minutos de cache
      refetchOnMount: false,
      refetchOnReconnect: true,
    },
    mutations: {
      retry: 0,
    },
  },
})

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, token } = useAuthStore()

  useEffect(() => {
    if (token && !isAuthenticated) {
      useAuthStore.getState().fetchUser()
    }
  }, [token, isAuthenticated])

  if (!token) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}

function App() {
  useEffect(() => {
    initializeTheme()
  }, [])

  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/verify-email" element={<VerifyEmail />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="finances" element={<Finances />} />
            <Route path="reminders" element={<Reminders />} />
            <Route path="meetings" element={<Meetings />} />
            <Route path="meetings/:id" element={<MeetingDetail />} />
            <Route path="contacts" element={<Contacts />} />
            <Route path="documents" element={<Documents />} />
            <Route path="todoist" element={<Todoist />} />
            <Route path="chat" element={<Chat />} />
            <Route path="settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 4000,
          style: {
            background: "hsl(var(--card))",
            color: "hsl(var(--card-foreground))",
            border: "1px solid hsl(var(--border))",
          },
        }}
      />
    </QueryClientProvider>
  )
}

export default App
