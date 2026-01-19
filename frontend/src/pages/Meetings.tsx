import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import {
  Users,
  Plus,
  Search,
  Calendar,
  Clock,
  Circle,
  ChevronRight,
  Target,
  Lightbulb,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { meetingsApi } from "@/lib/api"
import { formatDate } from "@/lib/utils"

export function Meetings() {
  const [searchQuery, setSearchQuery] = useState("")
  const navigate = useNavigate()

  const { data: meetings } = useQuery({
    queryKey: ["meetings"],
    queryFn: () => meetingsApi.list({ limit: 100 }).then((r) => r.data),
  })

  const { data: searchResults } = useQuery({
    queryKey: ["meetings-search", searchQuery],
    queryFn: () => meetingsApi.search(searchQuery).then((r) => r.data),
    enabled: searchQuery.length >= 2,
  })

  const { data: pendingActions } = useQuery({
    queryKey: ["pending-actions"],
    queryFn: () => meetingsApi.getPendingActionItems().then((r) => r.data),
  })

  const displayedMeetings = searchQuery.length >= 2 
    ? searchResults?.results 
    : meetings?.items

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Reuniões</h1>
          <p className="text-muted-foreground">
            Visualize resumos e ações das suas reuniões.
          </p>
        </div>
        <Button size="sm">
          <Plus className="h-4 w-4 mr-2" />
          Nova Reunião
        </Button>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Buscar reuniões..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Stats */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total de Reuniões</CardTitle>
            <Users className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{meetings?.total ?? 0}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Ações Pendentes</CardTitle>
            <Circle className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-500">
              {pendingActions?.count ?? 0}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Este Mês</CardTitle>
            <Calendar className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {meetings?.items?.filter((m) => {
                const date = new Date(m.date)
                const now = new Date()
                return date.getMonth() === now.getMonth() && date.getFullYear() === now.getFullYear()
              }).length ?? 0}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Meetings List */}
      <div className="space-y-4">
        {displayedMeetings?.map((meeting) => (
          <Card 
            key={meeting.id} 
            className="overflow-hidden cursor-pointer hover:shadow-lg hover:border-primary/50 transition-all"
            onClick={() => navigate(`/meetings/${meeting.id}`)}
          >
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4 flex-1">
                  <div className="p-3 rounded-full bg-primary/10 text-primary">
                    <Users className="h-6 w-6" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <CardTitle className="text-lg truncate">
                      {meeting.title || "Reunião"}
                    </CardTitle>
                    <div className="flex items-center gap-4 text-sm text-muted-foreground mt-1">
                      <span className="flex items-center gap-1">
                        <Calendar className="h-3 w-3" />
                        {formatDate(meeting.date)}
                      </span>
                      {meeting.duration_minutes && meeting.duration_minutes > 0 && (
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3" />
                          {meeting.duration_minutes} min
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-6">
                  {(meeting.action_items_count ?? 0) > 0 && (
                    <div className="text-center">
                      <div className="flex items-center gap-1 text-blue-600 dark:text-blue-400">
                        <Target className="h-4 w-4" />
                        <span className="text-lg font-bold">{meeting.action_items_count}</span>
                      </div>
                      <div className="text-xs text-muted-foreground">tarefas</div>
                    </div>
                  )}
                  {(meeting.key_topics_count ?? 0) > 0 && (
                    <div className="text-center">
                      <div className="flex items-center gap-1 text-yellow-600 dark:text-yellow-400">
                        <Lightbulb className="h-4 w-4" />
                        <span className="text-lg font-bold">{meeting.key_topics_count}</span>
                      </div>
                      <div className="text-xs text-muted-foreground">tópicos</div>
                    </div>
                  )}
                  <ChevronRight className="h-5 w-5 text-muted-foreground" />
                </div>
              </div>
            </CardHeader>
            {meeting.summary && (
              <CardContent className="pt-0">
                <p className="text-sm text-muted-foreground line-clamp-2">
                  {meeting.summary}
                </p>
              </CardContent>
            )}
          </Card>
        ))}

        {(!displayedMeetings || displayedMeetings.length === 0) && (
          <Card>
            <CardContent className="py-12">
              <div className="text-center">
                <Users className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <p className="text-lg font-medium text-muted-foreground">
                  {searchQuery.length >= 2
                    ? "Nenhuma reunião encontrada para a busca"
                    : "Nenhuma reunião registrada"}
                </p>
                <p className="text-sm text-muted-foreground mt-2">
                  Envie um áudio de reunião no Chat para começar.
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  )
}
