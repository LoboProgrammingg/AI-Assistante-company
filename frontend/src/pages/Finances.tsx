import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Plus,
  Filter,
  Calendar,
  Download,
  ChevronLeft,
  ChevronRight,
  Trash2,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { financesApi, type Finance } from "@/lib/api"
import { formatCurrency, formatDate } from "@/lib/utils"
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
} from "recharts"
import {
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  startOfYear,
  endOfYear,
  format,
  subDays,
} from "date-fns"
import { ptBR } from "date-fns/locale"

type Period = "day" | "week" | "month" | "year"

const ITEMS_PER_PAGE = 20

export function Finances() {
  const [period, setPeriod] = useState<Period>("month")
  const [page, setPage] = useState(1)

  const getDateRange = () => {
    const now = new Date()
    switch (period) {
      case "day":
        return { start: now, end: now }
      case "week":
        return { start: startOfWeek(now, { locale: ptBR }), end: endOfWeek(now, { locale: ptBR }) }
      case "month":
        return { start: startOfMonth(now), end: endOfMonth(now) }
      case "year":
        return { start: startOfYear(now), end: endOfYear(now) }
    }
  }

  const { start, end } = getDateRange()

  const { data: transactions } = useQuery({
    queryKey: ["transactions", period, page],
    queryFn: () =>
      financesApi
        .list({
          start_date: format(start, "yyyy-MM-dd"),
          end_date: format(end, "yyyy-MM-dd"),
          limit: ITEMS_PER_PAGE,
          page: page,
        })
        .then((r) => r.data),
  })
  
  const totalPages = Math.ceil((transactions?.total || 0) / ITEMS_PER_PAGE)

  const { data: summary } = useQuery({
    queryKey: ["finance-summary", period],
    queryFn: () =>
      financesApi
        .getSummary(format(start, "yyyy-MM-dd"), format(end, "yyyy-MM-dd"))
        .then((r) => r.data),
  })

  const { data: trend } = useQuery({
    queryKey: ["finance-trend-12"],
    queryFn: () => financesApi.getTrend(12).then((r) => r.data),
  })

  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => financesApi.getCategories().then((r) => r.data),
  })

  const periodLabels: Record<Period, string> = {
    day: "Hoje",
    week: "Esta Semana",
    month: "Este Mês",
    year: "Este Ano",
  }

  const exportToCSV = () => {
    if (!transactions?.items?.length) return
    
    const headers = ["Data", "Descrição", "Categoria", "Tipo", "Valor"]
    const rows = transactions.items.map((t: Finance) => [
      formatDate(t.transaction_date),
      t.description,
      t.category?.name || "Sem categoria",
      t.type === "income" ? "Receita" : "Despesa",
      t.amount.toFixed(2).replace(".", ",")
    ])
    
    const csvContent = [
      headers.join(";"),
      ...rows.map(row => row.join(";"))
    ].join("\n")
    
    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" })
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = `financas_${format(start, "yyyy-MM-dd")}_${format(end, "yyyy-MM-dd")}.csv`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Finanças</h1>
          <p className="text-muted-foreground">
            Controle seus gastos e receitas.
          </p>
        </div>
        <div className="flex gap-2">
          <Button 
            variant="outline" 
            size="sm"
            onClick={() => exportToCSV()}
            disabled={!transactions?.items?.length}
          >
            <Download className="h-4 w-4 mr-2" />
            Exportar CSV
          </Button>
          <Button size="sm">
            <Plus className="h-4 w-4 mr-2" />
            Nova Transação
          </Button>
        </div>
      </div>

      {/* Period Selector */}
      <div className="flex gap-2 p-1 bg-muted rounded-lg w-fit">
        {(["day", "week", "month", "year"] as Period[]).map((p) => (
          <Button
            key={p}
            variant={period === p ? "default" : "ghost"}
            size="sm"
            onClick={() => {
              setPeriod(p)
              setPage(1) // Reset page when period changes
            }}
          >
            {periodLabels[p]}
          </Button>
        ))}
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Receitas</CardTitle>
            <TrendingUp className="h-4 w-4 text-success" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-success">
              {formatCurrency(summary?.summary?.total_income ?? 0)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Despesas</CardTitle>
            <TrendingDown className="h-4 w-4 text-destructive" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-destructive">
              {formatCurrency(summary?.summary?.total_expenses ?? 0)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Saldo</CardTitle>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div
              className={`text-2xl font-bold ${
                (summary?.summary?.balance ?? 0) >= 0 ? "text-success" : "text-destructive"
              }`}
            >
              {formatCurrency(summary?.summary?.balance ?? 0)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts */}
      <div className="grid gap-4 md:grid-cols-2">
        {/* Trend Chart */}
        <Card>
          <CardHeader>
            <CardTitle>Evolução Mensal</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={trend?.data ?? []}>
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
                  <Line
                    type="monotone"
                    dataKey="income"
                    stroke="#10b981"
                    strokeWidth={2}
                    name="Receitas"
                  />
                  <Line
                    type="monotone"
                    dataKey="expenses"
                    stroke="#ef4444"
                    strokeWidth={2}
                    name="Despesas"
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Categories Chart - Estilo com porcentagens */}
        <Card>
          <CardHeader>
            <CardTitle>Despesas por Categoria</CardTitle>
          </CardHeader>
          <CardContent>
            {summary?.by_category && summary.by_category.length > 0 ? (
              <div className="space-y-4">
                {summary.by_category.slice(0, 8).map((cat, index) => {
                  const totalExpenses = summary?.summary?.total_expenses || 1
                  const amount = (cat as any).total || cat.amount || 0
                  const percentage = cat.percentage ?? ((amount / totalExpenses) * 100)
                  const colors = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#14b8a6", "#f97316"]
                  return (
                    <div key={cat.category} className="space-y-2">
                      <div className="flex items-center justify-between text-sm">
                        <div className="flex items-center gap-2">
                          <div 
                            className="w-3 h-3 rounded-full" 
                            style={{ backgroundColor: colors[index % colors.length] }}
                          />
                          <span className="font-medium">{cat.category}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="text-muted-foreground">{percentage.toFixed(0)}%</span>
                          <span className="font-semibold min-w-[80px] text-right">{formatCurrency(amount)}</span>
                        </div>
                      </div>
                      <div className="w-full bg-muted rounded-full h-2">
                        <div
                          className="h-2 rounded-full transition-all"
                          style={{
                            width: `${Math.min(percentage, 100)}%`,
                            backgroundColor: colors[index % colors.length],
                          }}
                        />
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="h-[200px] flex items-center justify-center">
                <p className="text-muted-foreground">Nenhuma despesa neste período</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Transactions List */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Transações Recentes</CardTitle>
          {transactions?.total ? (
            <span className="text-sm text-muted-foreground">
              {transactions.total} transação(ões)
            </span>
          ) : null}
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {transactions?.items?.map((transaction) => (
              <div
                key={transaction.id}
                className="flex items-center justify-between p-4 rounded-lg bg-muted/50 group"
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`p-2 rounded-full ${
                      transaction.type === "income"
                        ? "bg-success/10 text-success"
                        : "bg-destructive/10 text-destructive"
                    }`}
                  >
                    {transaction.type === "income" ? (
                      <TrendingUp className="h-4 w-4" />
                    ) : (
                      <TrendingDown className="h-4 w-4" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium">{transaction.description}</p>
                    <p className="text-sm text-muted-foreground">
                      {transaction.category?.name} • {formatDate(transaction.transaction_date)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className={`font-semibold ${
                      transaction.type === "income" ? "text-success" : "text-destructive"
                    }`}
                  >
                    {transaction.type === "income" ? "+" : "-"}
                    {formatCurrency(transaction.amount)}
                  </span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
                    onClick={() => {
                      if (confirm(`Deletar "${transaction.description}"?`)) {
                        financesApi.delete(transaction.id).then(() => {
                          window.location.reload()
                        })
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            ))}
            {(!transactions?.items || transactions.items.length === 0) && (
              <p className="text-center text-muted-foreground py-8">
                Nenhuma transação encontrada
              </p>
            )}
          </div>
          
          {/* Paginação */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6 pt-4 border-t">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1}
              >
                <ChevronLeft className="h-4 w-4 mr-1" />
                Anterior
              </Button>
              <span className="text-sm text-muted-foreground">
                Página {page} de {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages}
              >
                Próxima
                <ChevronRight className="h-4 w-4 ml-1" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
