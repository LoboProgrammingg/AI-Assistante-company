import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Bell,
  Users,
  ArrowUpRight,
  ArrowDownRight,
  Trash2,
} from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { usersApi, remindersApi, financesApi, meetingsApi } from "@/lib/api"
import { formatCurrency, formatRelativeDate } from "@/lib/utils"
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts"

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"]

export function Dashboard() {
  const queryClient = useQueryClient()

  const deleteReminderMutation = useMutation({
    mutationFn: (id: number) => remindersApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["upcoming-reminders"] })
      queryClient.invalidateQueries({ queryKey: ["user-stats"] })
    },
  })

  const deleteFinanceMutation = useMutation({
    mutationFn: (id: number) => financesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recent-finances"] })
      queryClient.invalidateQueries({ queryKey: ["user-stats"] })
      queryClient.invalidateQueries({ queryKey: ["monthly-summary"] })
      queryClient.invalidateQueries({ queryKey: ["finance-trend"] })
    },
  })

  const { data: stats } = useQuery({
    queryKey: ["user-stats"],
    queryFn: () => usersApi.getStats().then((r) => r.data),
  })

  const { data: upcomingReminders } = useQuery({
    queryKey: ["upcoming-reminders"],
    queryFn: () => remindersApi.getUpcoming(48).then((r) => r.data),
  })

  const { data: trend } = useQuery({
    queryKey: ["finance-trend"],
    queryFn: () => financesApi.getTrend(6).then((r) => r.data),
  })

  const { data: pendingActions } = useQuery({
    queryKey: ["pending-actions"],
    queryFn: () => meetingsApi.getPendingActionItems().then((r) => r.data),
  })

  const { data: recentFinances } = useQuery({
    queryKey: ["recent-finances"],
    queryFn: () => financesApi.list({ limit: 5 }).then((r) => r.data),
  })

  const currentMonth = new Date()
  const { data: monthlySummary } = useQuery({
    queryKey: ["monthly-summary", currentMonth.getFullYear(), currentMonth.getMonth() + 1],
    queryFn: () =>
      financesApi
        .getMonthlySummary(currentMonth.getFullYear(), currentMonth.getMonth() + 1)
        .then((r) => r.data),
  })

  const balance = (stats?.total_income ?? 0) - (stats?.total_expenses ?? 0)
  const isPositive = balance >= 0

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
        <p className="text-muted-foreground">
          Visão geral das suas atividades e finanças.
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Saldo Total</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className={`text-2xl font-bold ${isPositive ? "text-success" : "text-destructive"}`}>
              {formatCurrency(balance)}
            </div>
            <p className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
              {isPositive ? (
                <ArrowUpRight className="h-3 w-3 text-success" />
              ) : (
                <ArrowDownRight className="h-3 w-3 text-destructive" />
              )}
              <span>Este mês</span>
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Receitas</CardTitle>
            <TrendingUp className="h-4 w-4 text-success" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-success">
              {formatCurrency(stats?.total_income ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {stats?.total_transactions ?? 0} transações
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Despesas</CardTitle>
            <TrendingDown className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">
              {formatCurrency(stats?.total_expenses ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {stats?.total_transactions ?? 0} transações
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Lembretes Ativos</CardTitle>
            <Bell className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.active_reminders ?? 0}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {upcomingReminders?.count ?? 0} nas próximas 48h
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid gap-4 md:grid-cols-7">
        {/* Trend Chart */}
        <Card className="md:col-span-4">
          <CardHeader>
            <CardTitle>Evolução Financeira</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend?.data ?? []}>
                  <defs>
                    <linearGradient id="income" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="expenses" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="month" className="text-xs" />
                  <YAxis className="text-xs" tickFormatter={(v) => `R$${v}`} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                    }}
                    formatter={(value) => formatCurrency(Number(value))}
                  />
                  <Area
                    type="monotone"
                    dataKey="income"
                    stroke="#10b981"
                    fill="url(#income)"
                    name="Receitas"
                  />
                  <Area
                    type="monotone"
                    dataKey="expenses"
                    stroke="#ef4444"
                    fill="url(#expenses)"
                    name="Despesas"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Category Summary */}
        <Card className="md:col-span-3">
          <CardHeader>
            <CardTitle>Despesas por Categoria</CardTitle>
          </CardHeader>
          <CardContent>
            {monthlySummary?.by_category && monthlySummary.by_category.length > 0 ? (
              <div className="space-y-4">
                {monthlySummary.by_category.slice(0, 8).map((cat, index) => (
                  <div key={cat.category} className="space-y-2">
                    <div className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <div 
                          className="w-3 h-3 rounded-full" 
                          style={{ backgroundColor: COLORS[index % COLORS.length] }}
                        />
                        <span className="font-medium">{cat.category}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-muted-foreground">{cat.percentage.toFixed(0)}%</span>
                        <span className="font-semibold">{formatCurrency((cat as any).total ?? cat.amount)}</span>
                      </div>
                    </div>
                    <div className="w-full bg-muted rounded-full h-2">
                      <div
                        className="h-2 rounded-full transition-all"
                        style={{
                          width: `${Math.min(cat.percentage, 100)}%`,
                          backgroundColor: COLORS[index % COLORS.length],
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="h-[200px] flex items-center justify-center">
                <p className="text-muted-foreground">Nenhuma despesa este mês</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Lists Row */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Upcoming Reminders */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Próximos Lembretes</CardTitle>
            <Bell className="h-5 w-5 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {upcomingReminders?.items?.slice(0, 5).map((reminder) => (
                <div
                  key={reminder.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-muted/50 group"
                >
                  <div>
                    <p className="font-medium">{reminder.title}</p>
                    <p className="text-sm text-muted-foreground">
                      {formatRelativeDate(reminder.scheduled_time)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      if (confirm(`Deletar lembrete "${reminder.title}"?`)) {
                        deleteReminderMutation.mutate(reminder.id)
                      }
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-destructive/10 rounded transition-opacity"
                    title="Deletar lembrete"
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </button>
                </div>
              ))}
              {(!upcomingReminders?.items || upcomingReminders.items.length === 0) && (
                <p className="text-center text-muted-foreground py-4">
                  Nenhum lembrete próximo
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Recent Transactions */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Transações Recentes</CardTitle>
            <DollarSign className="h-5 w-5 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recentFinances?.items?.slice(0, 5).map((finance) => (
                <div
                  key={finance.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-muted/50 group"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-2 h-2 rounded-full ${finance.type === "income" ? "bg-green-500" : "bg-red-500"}`} />
                    <div>
                      <p className="font-medium">{finance.description}</p>
                      <p className="text-sm text-muted-foreground">
                        {finance.category?.name || "Sem categoria"}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`font-semibold ${finance.type === "income" ? "text-green-600" : "text-red-600"}`}>
                      {finance.type === "income" ? "+" : "-"}{formatCurrency(finance.amount)}
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        if (confirm(`Deletar transação "${finance.description}"?`)) {
                          deleteFinanceMutation.mutate(finance.id)
                        }
                      }}
                      className="opacity-0 group-hover:opacity-100 p-1.5 hover:bg-destructive/10 rounded transition-opacity"
                      title="Deletar transação"
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </button>
                  </div>
                </div>
              ))}
              {(!recentFinances?.items || recentFinances.items.length === 0) && (
                <p className="text-center text-muted-foreground py-4">
                  Nenhuma transação registrada
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Third Row - Pending Actions */}
      <div className="grid gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Ações Pendentes de Reuniões</CardTitle>
            <Users className="h-5 w-5 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {pendingActions?.items?.slice(0, 6).map((item, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg bg-muted/50"
                >
                  <p className="font-medium text-sm">{item.task}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {item.meeting_title}
                  </p>
                </div>
              ))}
              {(!pendingActions?.items || pendingActions.items.length === 0) && (
                <p className="text-center text-muted-foreground py-4 col-span-full">
                  Nenhuma ação pendente
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
