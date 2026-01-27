import { Link, useLocation } from "react-router-dom"
import {
  LayoutDashboard,
  DollarSign,
  Bell,
  Users,
  Settings,
  LogOut,
  Menu,
  X,
  FileText,
  ChevronLeft,
  ChevronRight,
  CheckSquare,
} from "lucide-react"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { useAuthStore } from "@/stores/auth"
import { getInitials } from "@/lib/utils"
import { useState } from "react"
import { useUIStore } from "@/stores/ui"

const navigation = [
  { name: "Dashboard", href: "/", icon: LayoutDashboard },
  { name: "Finanças", href: "/finances", icon: DollarSign },
  { name: "Lembretes", href: "/reminders", icon: Bell },
  { name: "Tarefas", href: "/tasks", icon: CheckSquare },
  { name: "Reuniões", href: "/meetings", icon: Users },
  { name: "Documentos", href: "/documents", icon: FileText },
  { name: "Configurações", href: "/settings", icon: Settings },
]

export function Sidebar() {
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const [isMobileOpen, setIsMobileOpen] = useState(false)
  const { sidebarCollapsed, toggleSidebar } = useUIStore()

  return (
    <>
      {/* Mobile menu button */}
      <Button
        variant="ghost"
        size="icon"
        className="fixed top-4 left-4 z-50 md:hidden"
        onClick={() => setIsMobileOpen(!isMobileOpen)}
      >
        {isMobileOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
      </Button>

      {/* Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 bg-sidebar border-r border-sidebar-border transform transition-all duration-300 ease-in-out md:translate-x-0",
          sidebarCollapsed ? "w-[72px]" : "w-64",
          isMobileOpen ? "translate-x-0 w-64" : "-translate-x-full md:translate-x-0"
        )}
      >
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className={cn(
            "flex items-center border-b border-sidebar-border transition-all duration-300",
            sidebarCollapsed ? "justify-center px-3 py-5" : "gap-3 px-5 py-5"
          )}>
            <img 
              src="/images/iris-logo.png" 
              alt="IRIS Logo" 
              className={cn(
                "object-contain transition-all duration-300",
                sidebarCollapsed ? "w-10 h-10" : "w-32 h-32"
              )}
            />
          </div>

          {/* Navigation */}
          <nav className={cn(
            "flex-1 py-4 space-y-1 overflow-y-auto overflow-x-hidden",
            sidebarCollapsed ? "px-2" : "px-3"
          )}>
            {navigation.map((item) => {
              const isActive = location.pathname === item.href
              return (
                <Link
                  key={item.name}
                  to={item.href}
                  onClick={() => setIsMobileOpen(false)}
                  title={sidebarCollapsed ? item.name : undefined}
                  className={cn(
                    "flex items-center rounded-lg text-sm font-medium transition-colors",
                    sidebarCollapsed ? "justify-center p-2.5" : "gap-3 px-3 py-2.5",
                    isActive
                      ? "bg-sidebar-accent text-sidebar-primary"
                      : "text-sidebar-foreground hover:bg-sidebar-accent/50"
                  )}
                >
                  <item.icon className="w-5 h-5 shrink-0" />
                  {!sidebarCollapsed && <span>{item.name}</span>}
                </Link>
              )
            })}
          </nav>

          {/* Collapse button - Desktop only */}
          <div className="hidden md:flex justify-center py-2 border-t border-sidebar-border">
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleSidebar}
              className="w-full mx-2 text-muted-foreground hover:text-foreground"
            >
              {sidebarCollapsed ? (
                <ChevronRight className="h-4 w-4" />
              ) : (
                <>
                  <ChevronLeft className="h-4 w-4 mr-2" />
                  <span>Minimizar</span>
                </>
              )}
            </Button>
          </div>

          {/* User section */}
          <div className={cn(
            "border-t border-sidebar-border transition-all duration-300",
            sidebarCollapsed ? "p-2" : "p-4"
          )}>
            <div className={cn(
              "flex items-center",
              sidebarCollapsed ? "justify-center" : "gap-3"
            )}>
              <Avatar className={sidebarCollapsed ? "h-9 w-9" : ""}>
                <AvatarFallback className="bg-primary text-primary-foreground">
                  {user?.name ? getInitials(user.name) : "U"}
                </AvatarFallback>
              </Avatar>
              {!sidebarCollapsed && (
                <>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-sidebar-foreground truncate">
                      {user?.name || "Usuário"}
                    </p>
                    <p className="text-xs text-muted-foreground truncate">
                      {user?.phone_number}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={logout}
                    className="text-muted-foreground hover:text-destructive shrink-0"
                  >
                    <LogOut className="w-4 h-4" />
                  </Button>
                </>
              )}
            </div>
            {sidebarCollapsed && (
              <Button
                variant="ghost"
                size="icon"
                onClick={logout}
                className="w-full mt-2 text-muted-foreground hover:text-destructive"
                title="Sair"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            )}
          </div>
        </div>
      </aside>
    </>
  )
}
