import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { Plus, CheckCircle2, Circle, Clock, AlertTriangle, MoreHorizontal, Trash2, Calendar } from "lucide-react"
import { format } from "date-fns"
import { ptBR } from "date-fns/locale"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Badge } from "@/components/ui/badge"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { tasksApi, type Task, type TaskCreate } from "@/lib/api"
import toast from "react-hot-toast"

const priorityColors = {
  low: "bg-green-500/20 text-green-400 border-green-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  high: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  urgent: "bg-red-500/20 text-red-400 border-red-500/30",
}

const priorityLabels = {
  low: "Baixa",
  medium: "Média",
  high: "Alta",
  urgent: "Urgente",
}

const statusLabels = {
  backlog: "Backlog",
  todo: "A Fazer",
  in_progress: "Em Progresso",
  done: "Concluído",
}

const statusIcons = {
  backlog: Circle,
  todo: Circle,
  in_progress: Clock,
  done: CheckCircle2,
}

interface TaskCardProps {
  task: Task
  onComplete: (id: number) => void
  onDelete: (id: number) => void
  onStatusChange: (id: number, status: string) => void
}

function TaskCard({ task, onComplete, onDelete, onStatusChange }: TaskCardProps) {
  const Icon = statusIcons[task.status as keyof typeof statusIcons] || Circle
  
  return (
    <Card className="mb-2 hover:border-primary/50 transition-colors cursor-pointer group">
      <CardContent className="p-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-start gap-2 flex-1 min-w-0">
            <button 
              onClick={() => task.status !== "done" && onComplete(task.id)}
              className="mt-0.5 shrink-0"
            >
              <Icon className={`w-4 h-4 ${task.status === "done" ? "text-green-500" : "text-muted-foreground hover:text-primary"}`} />
            </button>
            <div className="flex-1 min-w-0">
              <p className={`text-sm font-medium truncate ${task.status === "done" ? "line-through text-muted-foreground" : ""}`}>
                {task.title}
              </p>
              {task.description && (
                <p className="text-xs text-muted-foreground truncate mt-0.5">
                  {task.description}
                </p>
              )}
              <div className="flex items-center gap-2 mt-2 flex-wrap">
                <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${priorityColors[task.priority as keyof typeof priorityColors]}`}>
                  {priorityLabels[task.priority as keyof typeof priorityLabels]}
                </Badge>
                {task.due_date && (
                  <span className={`text-[10px] flex items-center gap-1 ${task.is_overdue ? "text-red-400" : "text-muted-foreground"}`}>
                    <Calendar className="w-3 h-3" />
                    {format(new Date(task.due_date), "dd/MM", { locale: ptBR })}
                    {task.is_overdue && <AlertTriangle className="w-3 h-3" />}
                  </span>
                )}
              </div>
            </div>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-6 w-6 opacity-0 group-hover:opacity-100">
                <MoreHorizontal className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => onStatusChange(task.id, "backlog")}>
                Mover para Backlog
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onStatusChange(task.id, "todo")}>
                Mover para A Fazer
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onStatusChange(task.id, "in_progress")}>
                Mover para Em Progresso
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onComplete(task.id)}>
                Marcar como Concluído
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onDelete(task.id)} className="text-red-400">
                <Trash2 className="w-4 h-4 mr-2" />
                Excluir
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  )
}

interface KanbanColumnProps {
  title: string
  status: string
  tasks: Task[]
  count: number
  onComplete: (id: number) => void
  onDelete: (id: number) => void
  onStatusChange: (id: number, status: string) => void
}

function KanbanColumn({ title, status, tasks, count, onComplete, onDelete, onStatusChange }: KanbanColumnProps) {
  const Icon = statusIcons[status as keyof typeof statusIcons] || Circle
  
  return (
    <div className="flex-1 min-w-[280px] max-w-[350px]">
      <div className="flex items-center gap-2 mb-3 px-1">
        <Icon className="w-4 h-4 text-muted-foreground" />
        <h3 className="font-medium text-sm">{title}</h3>
        <Badge variant="secondary" className="ml-auto text-xs">{count}</Badge>
      </div>
      <div className="bg-muted/30 rounded-lg p-2 min-h-[400px]">
        {tasks.map((task) => (
          <TaskCard 
            key={task.id} 
            task={task} 
            onComplete={onComplete}
            onDelete={onDelete}
            onStatusChange={onStatusChange}
          />
        ))}
        {tasks.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-8">
            Nenhuma tarefa
          </p>
        )}
      </div>
    </div>
  )
}

export function Tasks() {
  const queryClient = useQueryClient()
  const [isDialogOpen, setIsDialogOpen] = useState(false)
  const [newTask, setNewTask] = useState<TaskCreate>({
    title: "",
    description: "",
    priority: "medium",
    status: "todo",
  })

  const { data: kanban, isLoading } = useQuery({
    queryKey: ["tasks", "kanban"],
    queryFn: () => tasksApi.getKanban(),
  })

  const { data: summary } = useQuery({
    queryKey: ["tasks", "summary"],
    queryFn: () => tasksApi.getSummary(),
  })

  const createMutation = useMutation({
    mutationFn: (data: TaskCreate) => tasksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      setIsDialogOpen(false)
      setNewTask({ title: "", description: "", priority: "medium", status: "todo" })
      toast.success("Tarefa criada!")
    },
    onError: () => toast.error("Erro ao criar tarefa"),
  })

  const completeMutation = useMutation({
    mutationFn: (id: number) => tasksApi.complete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      toast.success("Tarefa concluída!")
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => tasksApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
      toast.success("Tarefa removida")
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: { status: string } }) => 
      tasksApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] })
    },
  })

  const handleCreate = () => {
    if (!newTask.title.trim()) {
      toast.error("Título é obrigatório")
      return
    }
    createMutation.mutate(newTask)
  }

  const handleStatusChange = (id: number, status: string) => {
    updateMutation.mutate({ id, data: { status } })
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    )
  }

  const board = kanban?.data || { backlog: [], todo: [], in_progress: [], done: [] }
  const stats = summary?.data || { total: 0, overdue: 0, due_today: 0 }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Tarefas</h1>
          <p className="text-muted-foreground text-sm mt-1">
            {stats.total} tarefas • {stats.overdue > 0 && <span className="text-red-400">{stats.overdue} atrasadas</span>}
            {stats.due_today > 0 && <span className="text-yellow-400 ml-2">{stats.due_today} para hoje</span>}
          </p>
        </div>
        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="w-4 h-4 mr-2" />
              Nova Tarefa
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Nova Tarefa</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 mt-4">
              <div>
                <Input
                  placeholder="Título da tarefa"
                  value={newTask.title}
                  onChange={(e) => setNewTask({ ...newTask, title: e.target.value })}
                />
              </div>
              <div>
                <Textarea
                  placeholder="Descrição (opcional)"
                  value={newTask.description}
                  onChange={(e) => setNewTask({ ...newTask, description: e.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-muted-foreground mb-1 block">Prioridade</label>
                  <Select
                    value={newTask.priority}
                    onValueChange={(value) => setNewTask({ ...newTask, priority: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">🟢 Baixa</SelectItem>
                      <SelectItem value="medium">🟡 Média</SelectItem>
                      <SelectItem value="high">🟠 Alta</SelectItem>
                      <SelectItem value="urgent">🔴 Urgente</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <label className="text-sm text-muted-foreground mb-1 block">Status</label>
                  <Select
                    value={newTask.status}
                    onValueChange={(value) => setNewTask({ ...newTask, status: value })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="backlog">Backlog</SelectItem>
                      <SelectItem value="todo">A Fazer</SelectItem>
                      <SelectItem value="in_progress">Em Progresso</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                  Cancelar
                </Button>
                <Button onClick={handleCreate} disabled={createMutation.isPending}>
                  {createMutation.isPending ? "Criando..." : "Criar Tarefa"}
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      <div className="flex gap-4 overflow-x-auto pb-4">
        <KanbanColumn
          title="Backlog"
          status="backlog"
          tasks={board.backlog}
          count={board.backlog.length}
          onComplete={(id) => completeMutation.mutate(id)}
          onDelete={(id) => deleteMutation.mutate(id)}
          onStatusChange={handleStatusChange}
        />
        <KanbanColumn
          title="A Fazer"
          status="todo"
          tasks={board.todo}
          count={board.todo.length}
          onComplete={(id) => completeMutation.mutate(id)}
          onDelete={(id) => deleteMutation.mutate(id)}
          onStatusChange={handleStatusChange}
        />
        <KanbanColumn
          title="Em Progresso"
          status="in_progress"
          tasks={board.in_progress}
          count={board.in_progress.length}
          onComplete={(id) => completeMutation.mutate(id)}
          onDelete={(id) => deleteMutation.mutate(id)}
          onStatusChange={handleStatusChange}
        />
        <KanbanColumn
          title="Concluído"
          status="done"
          tasks={board.done}
          count={board.done.length}
          onComplete={(id) => completeMutation.mutate(id)}
          onDelete={(id) => deleteMutation.mutate(id)}
          onStatusChange={handleStatusChange}
        />
      </div>
    </div>
  )
}
