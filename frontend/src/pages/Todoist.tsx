import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  CheckSquare,
  Plus,
  Check,
  Clock,
  AlertTriangle,
  Calendar,
  Trash2,
  ExternalLink,
  RefreshCw,
  Filter,
  Tag,
  FolderKanban,
  Wifi,
  WifiOff,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { todoistApi, type TodoistTask, type TodoistTaskCreate } from "@/lib/api"
import { cn } from "@/lib/utils"
import { format, parseISO } from "date-fns"
import { ptBR } from "date-fns/locale"
import toast from "react-hot-toast"

type FilterType = "today" | "tomorrow" | "overdue" | "all"

const priorityConfig: Record<number, { color: string; bg: string; label: string; icon: string }> = {
  1: { 
    color: "text-slate-500", 
    bg: "bg-slate-100 dark:bg-slate-800 border-slate-200 dark:border-slate-700", 
    label: "Normal",
    icon: "○"
  },
  2: { 
    color: "text-blue-500", 
    bg: "bg-blue-50 dark:bg-blue-950 border-blue-200 dark:border-blue-800", 
    label: "Média",
    icon: "◐"
  },
  3: { 
    color: "text-amber-500", 
    bg: "bg-amber-50 dark:bg-amber-950 border-amber-200 dark:border-amber-800", 
    label: "Alta",
    icon: "◕"
  },
  4: { 
    color: "text-red-500", 
    bg: "bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800", 
    label: "Urgente",
    icon: "●"
  },
}

export function Todoist() {
  const [filter, setFilter] = useState<FilterType>("today")
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [newTask, setNewTask] = useState<TodoistTaskCreate>({
    content: "",
    due_string: "",
    priority: 1,
  })
  const queryClient = useQueryClient()

  // Status da conexão
  const { data: status } = useQuery({
    queryKey: ["todoist-status"],
    queryFn: () => todoistApi.getStatus().then((r) => r.data),
    staleTime: 1000 * 60 * 5,
  })

  // Resumo do dia
  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["todoist-summary"],
    queryFn: () => todoistApi.getTodaySummary().then((r) => r.data),
    enabled: status?.connected,
    refetchInterval: 1000 * 60 * 5, // Refetch a cada 5 minutos
  })

  // Lista de tarefas
  const { data: tasks, isLoading: tasksLoading } = useQuery({
    queryKey: ["todoist-tasks", filter],
    queryFn: () =>
      todoistApi
        .listTasks({ 
          filter: filter === "all" ? undefined : filter
        })
        .then((r) => r.data),
    enabled: status?.connected,
  })

  // Alertas
  const { data: alerts } = useQuery({
    queryKey: ["todoist-alerts"],
    queryFn: () => todoistApi.getAlerts().then((r) => r.data),
    enabled: status?.connected,
    refetchInterval: 1000 * 60, // Refetch a cada minuto
  })

  // Projetos
  const { data: projects } = useQuery({
    queryKey: ["todoist-projects"],
    queryFn: () => todoistApi.getProjects().then((r) => r.data),
    enabled: status?.connected,
  })

  // Mutations
  const createMutation = useMutation({
    mutationFn: (data: TodoistTaskCreate) => todoistApi.createTask(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todoist-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["todoist-summary"] })
      setIsCreateOpen(false)
      setNewTask({ content: "", due_string: "", priority: 1 })
      toast.success("Tarefa criada no Todoist!")
    },
    onError: () => {
      toast.error("Erro ao criar tarefa")
    },
  })

  const completeMutation = useMutation({
    mutationFn: (id: string) => todoistApi.completeTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todoist-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["todoist-summary"] })
      toast.success("Tarefa concluída!")
    },
    onError: () => {
      toast.error("Erro ao concluir tarefa")
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => todoistApi.deleteTask(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["todoist-tasks"] })
      queryClient.invalidateQueries({ queryKey: ["todoist-summary"] })
      toast.success("Tarefa removida!")
    },
    onError: () => {
      toast.error("Erro ao remover tarefa")
    },
  })

  const handleCreateTask = () => {
    if (!newTask.content.trim()) {
      toast.error("Digite o título da tarefa")
      return
    }
    createMutation.mutate(newTask)
  }

  const formatDueDate = (due: TodoistTask["due"]) => {
    if (!due) return null
    try {
      if (due.datetime) {
        return format(parseISO(due.datetime), "dd/MM HH:mm", { locale: ptBR })
      }
      return format(parseISO(due.date), "dd/MM", { locale: ptBR })
    } catch {
      return due.string || due.date
    }
  }

  const filterLabels: Record<FilterType, string> = {
    today: "Hoje",
    tomorrow: "Amanhã",
    overdue: "Atrasadas",
    all: "Todas",
  }

  // Se não está configurado
  if (status && !status.configured) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4">
        <WifiOff className="h-16 w-16 text-muted-foreground" />
        <h2 className="text-2xl font-bold">Todoist não configurado</h2>
        <p className="text-muted-foreground text-center max-w-md">
          Para usar a integração com o Todoist, configure a variável{" "}
          <code className="bg-muted px-1 rounded">TODOIST_API_KEY</code> no servidor.
        </p>
      </div>
    )
  }

  // Se não está conectado
  if (status && !status.connected) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh] space-y-4">
        <AlertTriangle className="h-16 w-16 text-warning" />
        <h2 className="text-2xl font-bold">Erro de conexão</h2>
        <p className="text-muted-foreground text-center max-w-md">
          {status.message}
        </p>
        <Button
          onClick={() => queryClient.invalidateQueries({ queryKey: ["todoist-status"] })}
        >
          <RefreshCw className="h-4 w-4 mr-2" />
          Tentar novamente
        </Button>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-3xl font-bold tracking-tight">Todoist</h1>
            {status?.connected && (
              <span className="flex items-center gap-1 text-sm text-success">
                <Wifi className="h-4 w-4" />
                Conectado
              </span>
            )}
          </div>
          <p className="text-muted-foreground">
            Gerencie suas tarefas do Todoist integradas com a IA.
          </p>
        </div>

        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              queryClient.invalidateQueries({ queryKey: ["todoist-tasks"] })
              queryClient.invalidateQueries({ queryKey: ["todoist-summary"] })
            }}
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Atualizar
          </Button>

          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4 mr-2" />
                Nova Tarefa
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Nova Tarefa no Todoist</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-4">
                <div className="space-y-2">
                  <Label htmlFor="content">Título</Label>
                  <Input
                    id="content"
                    placeholder="Ex: Estudar Python"
                    value={newTask.content}
                    onChange={(e) =>
                      setNewTask({ ...newTask, content: e.target.value })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="due_string">Prazo</Label>
                  <Input
                    id="due_string"
                    placeholder="Ex: amanhã às 10h, sexta-feira"
                    value={newTask.due_string}
                    onChange={(e) =>
                      setNewTask({ ...newTask, due_string: e.target.value })
                    }
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="priority">Prioridade</Label>
                  <Select
                    value={String(newTask.priority)}
                    onValueChange={(v) =>
                      setNewTask({ ...newTask, priority: Number(v) })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1">Normal</SelectItem>
                      <SelectItem value="2">Média</SelectItem>
                      <SelectItem value="3">Alta</SelectItem>
                      <SelectItem value="4">Urgente</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">Descrição (opcional)</Label>
                  <Input
                    id="description"
                    placeholder="Detalhes adicionais..."
                    value={newTask.description || ""}
                    onChange={(e) =>
                      setNewTask({ ...newTask, description: e.target.value })
                    }
                  />
                </div>

                <Button
                  className="w-full"
                  onClick={handleCreateTask}
                  disabled={createMutation.isPending}
                >
                  {createMutation.isPending ? "Criando..." : "Criar Tarefa"}
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {/* Alertas */}
      {alerts && alerts.length > 0 && (
        <Card className="border-warning bg-warning/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-warning flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Tarefas Próximas do Prazo
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {alerts.map((alert) => (
                <div
                  key={alert.task_id}
                  className="flex items-center justify-between p-3 rounded-lg bg-warning/10"
                >
                  <div>
                    <p className="font-medium">{alert.task_title}</p>
                    <p className="text-sm text-muted-foreground">
                      {alert.message}
                    </p>
                  </div>
                  <span className="text-sm font-medium text-warning">
                    {alert.minutes_remaining} min
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Hoje</CardTitle>
            <CheckSquare className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {summaryLoading ? "..." : summary?.today_count ?? 0}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Atrasadas</CardTitle>
            <Clock className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">
              {summaryLoading ? "..." : summary?.overdue_count ?? 0}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Alertas</CardTitle>
            <AlertTriangle className="h-4 w-4 text-warning" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-warning">
              {summaryLoading ? "..." : summary?.alerts_count ?? 0}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Projetos</CardTitle>
            <FolderKanban className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{projects?.length ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        <div className="flex gap-2 p-1 bg-muted rounded-lg">
          {(["today", "tomorrow", "overdue", "all"] as FilterType[]).map((f) => (
            <Button
              key={f}
              variant={filter === f ? "default" : "ghost"}
              size="sm"
              onClick={() => setFilter(f)}
            >
              <Filter className="h-3 w-3 mr-1" />
              {filterLabels[f]}
            </Button>
          ))}
        </div>
      </div>

      {/* Tasks List */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CheckSquare className="h-5 w-5" />
            Tarefas
          </CardTitle>
        </CardHeader>
        <CardContent>
          {tasksLoading ? (
            <div className="flex justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <div className="space-y-3">
              {tasks?.map((task) => (
                <div
                  key={task.id}
                  className={cn(
                    "flex items-center justify-between p-4 rounded-lg border transition-colors",
                    task.is_completed
                      ? "bg-muted/30 border-muted"
                      : "bg-card hover:bg-muted/50"
                  )}
                >
                  <div className="flex items-center gap-4 flex-1">
                    <button
                      onClick={() => completeMutation.mutate(task.id)}
                      className={cn(
                        "p-2 rounded-full border-2 transition-colors",
                        task.is_completed
                          ? "bg-success border-success text-white"
                          : "border-muted-foreground hover:border-success hover:bg-success/10"
                      )}
                    >
                      <Check className="h-3 w-3" />
                    </button>

                    <div className="flex-1 min-w-0">
                      <p
                        className={cn(
                          "font-medium truncate",
                          task.is_completed && "line-through text-muted-foreground"
                        )}
                      >
                        {task.content}
                      </p>
                      <div className="flex items-center gap-3 text-sm text-muted-foreground">
                        {task.due && (
                          <span className="flex items-center gap-1">
                            <Calendar className="h-3 w-3" />
                            {formatDueDate(task.due)}
                          </span>
                        )}
                        {task.labels?.length > 0 && (
                          <span className="flex items-center gap-1">
                            <Tag className="h-3 w-3" />
                            {task.labels.join(", ")}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        "px-2 py-1 rounded text-xs font-medium border",
                        priorityConfig[task.priority]?.bg
                      )}
                    >
                      <span className={priorityConfig[task.priority]?.color}>
                        {priorityConfig[task.priority]?.label}
                      </span>
                    </span>

                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => window.open(task.url, "_blank")}
                      title="Abrir no Todoist"
                    >
                      <ExternalLink className="h-4 w-4" />
                    </Button>

                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => deleteMutation.mutate(task.id)}
                      className="text-destructive hover:text-destructive"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}

              {(!tasks || tasks.length === 0) && (
                <p className="text-center text-muted-foreground py-8">
                  Nenhuma tarefa encontrada
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Projects */}
      {projects && projects.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FolderKanban className="h-5 w-5" />
              Projetos
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 md:grid-cols-3">
              {projects.map((project) => (
                <div
                  key={project.id}
                  className="flex items-center gap-3 p-3 rounded-lg border hover:bg-muted/50 cursor-pointer transition-colors"
                  onClick={() => window.open(project.url, "_blank")}
                >
                  <div
                    className="w-3 h-3 rounded-full"
                    style={{ backgroundColor: project.color }}
                  />
                  <span className="font-medium">{project.name}</span>
                  {project.is_favorite && (
                    <span className="text-yellow-500">★</span>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
