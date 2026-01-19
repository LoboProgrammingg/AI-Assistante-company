import { create } from "zustand"
import { persist } from "zustand/middleware"

type Theme = "light" | "dark" | "system"

interface ThemeState {
  theme: Theme
  setTheme: (theme: Theme) => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "system",
      setTheme: (theme: Theme) => {
        set({ theme })
        
        const root = window.document.documentElement
        root.classList.remove("light", "dark")
        
        if (theme === "system") {
          const systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
            ? "dark"
            : "light"
          root.classList.add(systemTheme)
        } else {
          root.classList.add(theme)
        }
      },
    }),
    {
      name: "theme-storage",
    }
  )
)

export function initializeTheme() {
  const stored = localStorage.getItem("theme-storage")
  const theme = stored ? JSON.parse(stored).state.theme : "system"
  
  const root = window.document.documentElement
  root.classList.remove("light", "dark")
  
  if (theme === "system") {
    const systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light"
    root.classList.add(systemTheme)
  } else {
    root.classList.add(theme)
  }
}
