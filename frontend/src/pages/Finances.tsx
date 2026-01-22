import { useState, useMemo } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Plus,
  Download,
  ChevronLeft,
  ChevronRight,
  Trash2,
  X,
  Calendar,
  Tag,
  FileText,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Pagination } from "@/components/ui/pagination"
import { financesApi, type Finance } from "@/lib/api"
import { formatCurrency, formatDate, formatShortDate } from "@/lib/utils"
import toast from "react-hot-toast"
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
  const queryClient = useQueryClient()
  const [period, setPeriod] = useState<Period>("month")
  const [page, setPage] = useState(1)
  const [selectedTransaction, setSelectedTransaction] = useState<Finance | null>(null)

  const deleteMutation = useMutation({
    mutationFn: (id: number) => financesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      queryClient.invalidateQueries({ queryKey: ["finance-summary"] })
      queryClient.invalidateQueries({ queryKey: ["finance-trend"] })
      toast.success("Transação removida!")
    },
    onError: () => {
      toast.error("Erro ao remover transação")
    },
  })

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
    staleTime: 30 * 1000, // 30 segundos
    refetchOnWindowFocus: false,
  })
  
  const totalPages = Math.ceil((transactions?.total || 0) / ITEMS_PER_PAGE)

  const { data: summary } = useQuery({
    queryKey: ["finance-summary", period],
    queryFn: () =>
      financesApi
        .getSummary(format(start, "yyyy-MM-dd"), format(end, "yyyy-MM-dd"))
        .then((r) => r.data),
    staleTime: 30 * 1000,
    refetchOnWindowFocus: false,
  })

  const { data: trend } = useQuery({
    queryKey: ["finance-trend-12"],
    queryFn: () => financesApi.getTrend(12).then((r) => r.data),
    staleTime: 60 * 1000, // 1 minuto
    refetchOnWindowFocus: false,
  })

  const { data: categories } = useQuery({
    queryKey: ["categories"],
    queryFn: () => financesApi.getCategories().then((r) => r.data),
    staleTime: 5 * 60 * 1000, // 5 minutos
    refetchOnWindowFocus: false,
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
          <CardTitle>Transações</CardTitle>
          {transactions?.total ? (
            <span className="text-sm text-muted-foreground">
              {transactions.total} transação(ões) • Página {page} de {totalPages || 1}
            </span>
          ) : null}
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {transactions?.items?.map((transaction) => (
              <div
                key={transaction.id}
                className="flex items-center justify-between p-4 rounded-xl bg-muted/50 hover:bg-muted/70 transition-colors group cursor-pointer"
                onClick={() => setSelectedTransaction(transaction)}
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  <div
                    className={`p-2.5 rounded-full shrink-0 ${
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
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="font-medium truncate">{transaction.description}</p>
                    </div>
                    <div className="flex items-center gap-2 text-sm text-muted-foreground mt-0.5">
                      <span className="truncate">{transaction.category?.name || "Sem categoria"}</span>
                      <span>•</span>
                      <span className="shrink-0">{formatShortDate(transaction.transaction_date)}</span>
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0 ml-4">
                  <div className="text-right">
                    <span
                      className={`font-semibold text-lg ${
                        transaction.type === "income" ? "text-success" : "text-destructive"
                      }`}
                    >
                      {transaction.type === "income" ? "+" : "-"}
                      {formatCurrency(transaction.amount)}
                    </span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="opacity-0 group-hover:opacity-100 transition-opacity h-8 w-8"
                    disabled={deleteMutation.isPending}
                    onClick={(e) => {
                      e.stopPropagation()
                      if (confirm(`Deletar "${transaction.description}"?`)) {
                        deleteMutation.mutate(transaction.id)
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
          
          {/* Paginação melhorada */}
          {totalPages > 1 && (
            <div className="flex justify-center mt-6 pt-4 border-t">
              <Pagination
                currentPage={page}
                totalPages={totalPages}
                onPageChange={setPage}
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Modal de Detalhes da Transação */}
      {selectedTransaction && (
        <div 
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedTransaction(null)}
        >
          <div 
            className="bg-background rounded-2xl shadow-2xl max-w-md w-full max-h-[90vh] overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between p-6 border-b">
              <div className="flex items-center gap-3">
                <div
                  className={`p-3 rounded-full ${
                    selectedTransaction.type === "income"
                      ? "bg-success/10 text-success"
                      : "bg-destructive/10 text-destructive"
                  }`}
                >
                  {selectedTransaction.type === "income" ? (
                    <TrendingUp className="h-6 w-6" />
                  ) : (
                    <TrendingDown className="h-6 w-6" />
                  )}
                </div>
                <div>
                  <h2 className="text-lg font-semibold">
                    {selectedTransaction.type === "income" ? "Receita" : "Despesa"}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    Detalhes da transação
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSelectedTransaction(null)}
              >
                <X className="h-5 w-5" />
              </Button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-6">
              {/* Valor */}
              <div className="text-center py-4">
                <span
                  className={`text-4xl font-bold ${
                    selectedTransaction.type === "income" ? "text-success" : "text-destructive"
                  }`}
                >
                  {selectedTransaction.type === "income" ? "+" : "-"}
                  {formatCurrency(selectedTransaction.amount)}
                </span>
              </div>

              {/* Descrição */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <FileText className="h-4 w-4" />
                  <span>Descrição</span>
                </div>
                <p className="text-base bg-muted/50 rounded-xl p-4">
                  {selectedTransaction.description || "Sem descrição"}
                </p>
              </div>

              {/* Categoria */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <Tag className="h-4 w-4" />
                  <span>Categoria</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="bg-primary/10 text-primary px-3 py-1.5 rounded-full text-sm font-medium">
                    {selectedTransaction.category?.name || "Sem categoria"}
                  </span>
                </div>
              </div>

              {/* Data */}
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  <span>Data</span>
                </div>
                <p className="text-base">
                  {formatDate(selectedTransaction.transaction_date, "long")}
                </p>
              </div>
            </div>

            {/* Footer */}
            <div className="p-6 border-t flex gap-3">
              <Button
                variant="outline"
                className="flex-1"
                onClick={() => setSelectedTransaction(null)}
              >
                Fechar
              </Button>
              <Button
                variant="destructive"
                className="flex-1"
                onClick={() => {
                  if (confirm(`Deletar "${selectedTransaction.description}"?`)) {
                    deleteMutation.mutate(selectedTransaction.id)
                    setSelectedTransaction(null)
                  }
                }}
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Excluir
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
