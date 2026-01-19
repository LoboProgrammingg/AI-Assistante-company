import { useParams, useNavigate } from "react-router-dom"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import {
  ArrowLeft,
  Calendar,
  Clock,
  Users,
  FileText,
  Target,
  Lightbulb,
  MessageSquare,
  CheckCircle,
  Circle,
  UserCheck,
  AlertCircle,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { meetingsApi } from "@/lib/api"
import { formatDate, cn } from "@/lib/utils"
import toast from "react-hot-toast"

export function MeetingDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: meeting, isLoading, error } = useQuery({
    queryKey: ["meeting", id],
    queryFn: () => meetingsApi.get(Number(id)).then((r) => r.data),
    enabled: !!id,
  })

  const updateActionMutation = useMutation({
    mutationFn: ({ itemIndex, status }: { itemIndex: number; status: string }) =>
      meetingsApi.updateActionItemStatus(Number(id), itemIndex, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["meeting", id] })
      queryClient.invalidateQueries({ queryKey: ["meetings"] })
      toast.success("Status atualizado!")
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <div className="animate-spin h-12 w-12 border-4 border-primary border-t-transparent rounded-full mx-auto" />
          <p className="mt-4 text-muted-foreground">Carregando reunião...</p>
        </div>
      </div>
    )
  }

  if (error || !meeting) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto" />
          <p className="mt-4 text-muted-foreground">Erro ao carregar reunião</p>
          <Button onClick={() => navigate("/meetings")} className="mt-4">
            Voltar para Reuniões
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex items-start gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate("/meetings")}>
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold">{meeting.title || "Reunião"}</h1>
          <div className="flex flex-wrap items-center gap-4 text-sm text-muted-foreground mt-1">
            <span className="flex items-center gap-1">
              <Calendar className="h-4 w-4" />
              {formatDate(meeting.date, "long")}
            </span>
            {meeting.duration_minutes && meeting.duration_minutes > 0 && (
              <span className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                {meeting.duration_minutes} min
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Coluna Principal */}
        <div className="lg:col-span-2 space-y-6">
          {/* Resumo */}
          {meeting.summary && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <FileText className="h-4 w-4 text-primary" />
                  Resumo
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-foreground leading-relaxed whitespace-pre-wrap">
                  {meeting.summary}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Tópicos */}
          {meeting.key_topics && meeting.key_topics.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Lightbulb className="h-4 w-4 text-yellow-500" />
                  Tópicos Principais ({meeting.key_topics.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {meeting.key_topics.map((topic, idx) => (
                    <li key={idx} className="border-l-2 border-yellow-500 pl-3">
                      <p className="font-medium">{topic.topic}</p>
                      {topic.summary && (
                        <p className="text-sm text-muted-foreground mt-1">{topic.summary}</p>
                      )}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Tarefas */}
          {meeting.action_items && meeting.action_items.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Target className="h-4 w-4 text-blue-500" />
                  Tarefas ({meeting.action_items.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="divide-y">
                  {meeting.action_items.map((item, idx) => (
                    <li key={idx} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                      <button
                        onClick={() =>
                          updateActionMutation.mutate({
                            itemIndex: idx,
                            status: item.status === "completed" ? "pending" : "completed",
                          })
                        }
                        className="mt-0.5"
                      >
                        {item.status === "completed" ? (
                          <CheckCircle className="h-5 w-5 text-green-500" />
                        ) : (
                          <Circle className="h-5 w-5 text-muted-foreground hover:text-blue-500" />
                        )}
                      </button>
                      <div className="flex-1">
                        <p className={cn(item.status === "completed" && "line-through text-muted-foreground")}>
                          {item.task}
                        </p>
                        <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
                          {item.responsible && (
                            <span className="flex items-center gap-1">
                              <UserCheck className="h-3 w-3" />
                              {item.responsible}
                            </span>
                          )}
                          {item.priority === "high" && <span className="text-red-500">Alta</span>}
                          {item.priority === "medium" && <span className="text-yellow-600">Média</span>}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Transcrição */}
          {meeting.transcription && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <MessageSquare className="h-4 w-4 text-gray-500" />
                  Transcrição
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="bg-muted rounded-lg p-4 max-h-80 overflow-y-auto">
                  <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                    {meeting.transcription}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Coluna Lateral */}
        <div className="space-y-6">
          {/* Decisões */}
          {meeting.decisions && meeting.decisions.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <AlertCircle className="h-4 w-4 text-purple-500" />
                  Decisões ({meeting.decisions.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-3">
                  {meeting.decisions.map((decision, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <CheckCircle className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="text-sm">{decision.decision}</p>
                        {decision.context && (
                          <p className="text-xs text-muted-foreground mt-1">{decision.context}</p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Participantes */}
          {meeting.participants && meeting.participants.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Users className="h-4 w-4 text-green-500" />
                  Participantes ({meeting.participants.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {meeting.participants.map((p, idx) => (
                    <span key={idx} className="text-sm bg-muted px-2 py-1 rounded">
                      {p.name}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Palavras-chave */}
          {meeting.keywords && meeting.keywords.length > 0 && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Palavras-chave</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-2">
                  {meeting.keywords.map((keyword, idx) => (
                    <span key={idx} className="text-xs bg-primary/10 text-primary px-2 py-1 rounded">
                      {keyword}
                    </span>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )
}
