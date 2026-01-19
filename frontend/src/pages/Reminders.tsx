import { useState } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  Bell,
  Plus,
  Check,
  Clock,
  Calendar,
  Repeat,
  Trash2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { remindersApi, type Reminder } from "@/lib/api"
import { formatRelativeDate, cn } from "@/lib/utils"
import {
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  isWithinInterval,
} from "date-fns"
import { ptBR } from "date-fns/locale"
import toast from "react-hot-toast"

type Period = "day" | "week" | "month" | "all"

const recurrenceLabels: Record<string, string> = {
  once: "Única vez",
  daily: "Diário",
  weekdays: "Dias úteis",
  weekends: "Fins de semana",
  weekly: "Semanal",
  monthly: "Mensal",
}

export function Reminders() {
  const [period, setPeriod] = useState<Period>("all")
  const [status, setStatus] = useState<"active" | "completed" | "all">("active")
  const queryClient = useQueryClient()

  const { data: reminders, isLoading } = useQuery({
    queryKey: ["reminders", status],
    queryFn: () => remindersApi.list({ status, limit: 100 }).then((r) => r.data),
  })

  const completeMutation = useMutation({
    mutationFn: (id: number) => remindersApi.complete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reminders"] })
      toast.success("Lembrete concluído!")
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => remindersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["reminders"] })
      toast.success("Lembrete removido!")
    },
  })

  const filterByPeriod = (items: Reminder[] = []) => {
    if (period === "all") return items

    const now = new Date()
    let start: Date, end: Date

    switch (period) {
      case "day":
        start = startOfDay(now)
        end = endOfDay(now)
        break
      case "week":
        start = startOfWeek(now, { locale: ptBR })
        end = endOfWeek(now, { locale: ptBR })
        break
      case "month":
        start = startOfMonth(now)
        end = endOfMonth(now)
        break
      default:
        return items
    }

    return items.filter((r) =>
      isWithinInterval(new Date(r.scheduled_time), { start, end })
    )
  }

  const filteredReminders = filterByPeriod(reminders?.items)

  const periodLabels: Record<Period, string> = {
    day: "Hoje",
    week: "Esta Semana",
    month: "Este Mês",
    all: "Todos",
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Lembretes</h1>
          <p className="text-muted-foreground">
            Gerencie seus lembretes e compromissos.
          </p>
        </div>
        <Button size="sm">
          <Plus className="h-4 w-4 mr-2" />
          Novo Lembrete
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-4">
        {/* Period Filter */}
        <div className="flex gap-2 p-1 bg-muted rounded-lg">
          {(["day", "week", "month", "all"] as Period[]).map((p) => (
            <Button
              key={p}
              variant={period === p ? "default" : "ghost"}
              size="sm"
              onClick={() => setPeriod(p)}
            >
              {periodLabels[p]}
            </Button>
          ))}
        </div>

        {/* Status Filter */}
        <div className="flex gap-2 p-1 bg-muted rounded-lg">
          <Button
            variant={status === "active" ? "default" : "ghost"}
            size="sm"
            onClick={() => setStatus("active")}
          >
            Ativos
          </Button>
          <Button
            variant={status === "completed" ? "default" : "ghost"}
            size="sm"
            onClick={() => setStatus("completed")}
          >
            Concluídos
          </Button>
          <Button
            variant={status === "all" ? "default" : "ghost"}
            size="sm"
            onClick={() => setStatus("all")}
          >
            Todos
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total</CardTitle>
            <Bell className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{reminders?.total ?? 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ativos</CardTitle>
            <Clock className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary">
              {reminders?.items?.filter((r) => r.is_active).length ?? 0}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Concluídos</CardTitle>
            <Check className="h-4 w-4 text-success" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-success">
              {reminders?.items?.filter((r) => r.is_completed).length ?? 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Reminders List */}
      <Card>
        <CardHeader>
          <CardTitle>Lembretes</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {filteredReminders?.map((reminder) => (
              <div
                key={reminder.id}
                className={cn(
                  "flex items-center justify-between p-4 rounded-lg border transition-colors",
                  reminder.is_completed
                    ? "bg-muted/30 border-muted"
                    : "bg-card hover:bg-muted/50"
                )}
              >
                <div className="flex items-center gap-4">
                  <div
                    className={cn(
                      "p-2 rounded-full",
                      reminder.is_completed
                        ? "bg-success/10 text-success"
                        : "bg-primary/10 text-primary"
                    )}
                  >
                    {reminder.is_completed ? (
                      <Check className="h-4 w-4" />
                    ) : (
                      <Bell className="h-4 w-4" />
                    )}
                  </div>
                  <div>
                    <p
                      className={cn(
                        "font-medium",
                        reminder.is_completed && "line-through text-muted-foreground"
                      )}
                    >
                      {reminder.title}
                    </p>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Calendar className="h-3 w-3" />
                      <span>{formatRelativeDate(reminder.scheduled_time)}</span>
                      {reminder.recurrence_type !== "once" && (
                        <>
                          <Repeat className="h-3 w-3 ml-2" />
                          <span>{recurrenceLabels[reminder.recurrence_type]}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  {!reminder.is_completed && (
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => completeMutation.mutate(reminder.id)}
                      className="text-success hover:text-success"
                    >
                      <Check className="h-4 w-4" />
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => deleteMutation.mutate(reminder.id)}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}

            {(!filteredReminders || filteredReminders.length === 0) && (
              <p className="text-center text-muted-foreground py-8">
                Nenhum lembrete encontrado
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
