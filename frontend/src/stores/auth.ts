import { create } from "zustand"
import { persist } from "zustand/middleware"
import { type User, type AuthUser, usersApi, authApi } from "@/lib/api"

interface AuthState {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  fetchUser: () => Promise<void>
  updateUser: (data: Partial<User>) => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email: string, password: string) => {
        set({ isLoading: true })
        try {
          const { data } = await authApi.login({ email, password })
          localStorage.setItem("token", data.access_token)
          set({ 
            token: data.access_token, 
            isAuthenticated: true 
          })
          await get().fetchUser()
        } finally {
          set({ isLoading: false })
        }
      },

      logout: () => {
        localStorage.removeItem("token")
        set({ user: null, token: null, isAuthenticated: false })
      },

      fetchUser: async () => {
        try {
          const { data } = await usersApi.getMe()
          set({ user: data, isAuthenticated: true })
        } catch {
          localStorage.removeItem("token")
          set({ user: null, token: null, isAuthenticated: false })
        }
      },

      updateUser: async (data: Partial<User>) => {
        const { data: updated } = await usersApi.updateMe(data)
        set({ user: updated })
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({ token: state.token }),
    }
  )
)
