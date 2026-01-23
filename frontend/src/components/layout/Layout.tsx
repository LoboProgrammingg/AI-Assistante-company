import { Outlet } from "react-router-dom"
import { Sidebar } from "./Sidebar"
import { FloatingChat } from "@/components/FloatingChat"
import { useUIStore } from "@/stores/ui"
import { cn } from "@/lib/utils"

export function Layout() {
  const { sidebarCollapsed } = useUIStore()

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className={cn(
        "transition-all duration-300",
        sidebarCollapsed ? "md:pl-[72px]" : "md:pl-64"
      )}>
        <div className="p-6 md:p-8">
          <Outlet />
        </div>
      </main>
      <FloatingChat />
    </div>
  )
}
