import { useState, useEffect } from "react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { User, Palette, Bell, Shield, Lock, MapPin, Calendar, Loader2, CheckCircle, XCircle, ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useAuthStore } from "@/stores/auth"
import { useThemeStore } from "@/stores/theme"
import { authApi, integrationsApi } from "@/lib/api"
import toast from "react-hot-toast"
import { useSearchParams } from "react-router-dom"

const BRAZILIAN_STATES = [
  { value: "AC", label: "Acre" },
  { value: "AL", label: "Alagoas" },
  { value: "AP", label: "Amapá" },
  { value: "AM", label: "Amazonas" },
  { value: "BA", label: "Bahia" },
  { value: "CE", label: "Ceará" },
  { value: "DF", label: "Distrito Federal" },
  { value: "ES", label: "Espírito Santo" },
  { value: "GO", label: "Goiás" },
  { value: "MA", label: "Maranhão" },
  { value: "MT", label: "Mato Grosso" },
  { value: "MS", label: "Mato Grosso do Sul" },
  { value: "MG", label: "Minas Gerais" },
  { value: "PA", label: "Pará" },
  { value: "PB", label: "Paraíba" },
  { value: "PR", label: "Paraná" },
  { value: "PE", label: "Pernambuco" },
  { value: "PI", label: "Piauí" },
  { value: "RJ", label: "Rio de Janeiro" },
  { value: "RN", label: "Rio Grande do Norte" },
  { value: "RS", label: "Rio Grande do Sul" },
  { value: "RO", label: "Rondônia" },
  { value: "RR", label: "Roraima" },
  { value: "SC", label: "Santa Catarina" },
  { value: "SP", label: "São Paulo" },
  { value: "SE", label: "Sergipe" },
  { value: "TO", label: "Tocantins" },
]

const TIMEZONES = [
  { value: "America/Sao_Paulo", label: "Brasília (GMT-3)" },
  { value: "America/Fortaleza", label: "Fortaleza (GMT-3)" },
  { value: "America/Recife", label: "Recife (GMT-3)" },
  { value: "America/Bahia", label: "Salvador (GMT-3)" },
  { value: "America/Belem", label: "Belém (GMT-3)" },
  { value: "America/Cuiaba", label: "Cuiabá (GMT-4)" },
  { value: "America/Manaus", label: "Manaus (GMT-4)" },
  { value: "America/Porto_Velho", label: "Porto Velho (GMT-4)" },
  { value: "America/Rio_Branco", label: "Rio Branco (GMT-5)" },
  { value: "America/Boa_Vista", label: "Boa Vista (GMT-4)" },
]

export function Settings() {
  const { user, updateUser } = useAuthStore()
  const { theme, setTheme } = useThemeStore()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()

  const [name, setName] = useState(user?.name || "")
  const [timezone, setTimezone] = useState(user?.timezone || "America/Sao_Paulo")
  const [state, setState] = useState((user as any)?.preferences?.state || "")
  
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isChangingPassword, setIsChangingPassword] = useState(false)

  // Google Calendar Integration
  const { data: calendarStatus, isLoading: isLoadingCalendar, refetch: refetchCalendar } = useQuery({
    queryKey: ["google-calendar-status"],
    queryFn: async () => {
      const res = await integrationsApi.getGoogleCalendarStatus()
      return res.data
    },
  })

  const connectCalendarMutation = useMutation({
    mutationFn: async () => {
      const res = await integrationsApi.connectGoogleCalendar()
      return res.data
    },
    onSuccess: (data) => {
      // Redirecionar para página de autorização do Google
      window.location.href = data.authorization_url
    },
    onError: () => {
      toast.error("Erro ao conectar Google Calendar")
    },
  })

  const disconnectCalendarMutation = useMutation({
    mutationFn: async () => {
      const res = await integrationsApi.disconnectGoogleCalendar()
      return res.data
    },
    onSuccess: () => {
      toast.success("Google Calendar desconectado")
      refetchCalendar()
    },
    onError: () => {
      toast.error("Erro ao desconectar")
    },
  })

  // Processar callback do OAuth
  useEffect(() => {
    const integration = searchParams.get("integration")
    const status = searchParams.get("status")
    const email = searchParams.get("email")
    const message = searchParams.get("message")

    if (integration === "google_calendar") {
      if (status === "success") {
        toast.success(`Google Calendar conectado: ${email}`)
        refetchCalendar()
      } else if (status === "error") {
        toast.error(`Erro: ${message || "Falha na conexão"}`)
      }
      // Limpar params da URL
      setSearchParams({})
    }
  }, [searchParams, setSearchParams, refetchCalendar])

  const handleSaveProfile = async () => {
    try {
      const preferences = { ...(user as any)?.preferences, state }
      await updateUser({ name, timezone, preferences } as any)
      toast.success("Perfil atualizado!")
    } catch {
      toast.error("Erro ao atualizar perfil")
    }
  }

  const handleChangePassword = async () => {
    if (newPassword !== confirmPassword) {
      toast.error("As senhas não conferem")
      return
    }
    
    if (newPassword.length < 8) {
      toast.error("A nova senha deve ter no mínimo 8 caracteres")
      return
    }
    
    setIsChangingPassword(true)
    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
        new_password_confirm: confirmPassword,
      })
      toast.success("Senha alterada com sucesso!")
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (error: any) {
      const message = error.response?.data?.detail || "Erro ao alterar senha"
      toast.error(message)
    } finally {
      setIsChangingPassword(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Configurações</h1>
        <p className="text-muted-foreground">
          Gerencie suas preferências e configurações.
        </p>
      </div>

      {/* Profile Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5" />
            Perfil
          </CardTitle>
          <CardDescription>
            Atualize suas informações pessoais.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Nome</label>
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Seu nome"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Telefone</label>
              <Input value={user?.phone_number || ""} disabled />
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Estado</label>
              <select
                value={state}
                onChange={(e) => setState(e.target.value)}
                className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm"
              >
                <option value="">Selecione seu estado</option>
                {BRAZILIAN_STATES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Fuso Horário</label>
              <select
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm"
              >
                {TIMEZONES.map((tz) => (
                  <option key={tz.value} value={tz.value}>
                    {tz.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <Button onClick={handleSaveProfile}>Salvar Alterações</Button>
        </CardContent>
      </Card>

      {/* Appearance Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            Aparência
          </CardTitle>
          <CardDescription>
            Personalize a aparência do dashboard.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            <label className="text-sm font-medium">Tema</label>
            <div className="flex gap-2">
              {(["light", "dark", "system"] as const).map((t) => (
                <Button
                  key={t}
                  variant={theme === t ? "default" : "outline"}
                  onClick={() => setTheme(t)}
                  className="flex-1"
                >
                  {t === "light" && "Claro"}
                  {t === "dark" && "Escuro"}
                  {t === "system" && "Sistema"}
                </Button>
              ))}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Notification Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            Notificações
          </CardTitle>
          <CardDescription>
            Configure como você recebe notificações.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Lembretes por WhatsApp</p>
                <p className="text-sm text-muted-foreground">
                  Receba lembretes diretamente no WhatsApp
                </p>
              </div>
              <Button variant="outline" size="sm">
                Ativado
              </Button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Resumo Diário</p>
                <p className="text-sm text-muted-foreground">
                  Receba um resumo diário das suas atividades
                </p>
              </div>
              <Button variant="outline" size="sm">
                Desativado
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Password Change */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Lock className="h-5 w-5" />
            Alterar Senha
          </CardTitle>
          <CardDescription>
            Atualize sua senha de acesso.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium">Senha Atual</label>
            <Input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              placeholder="Digite sua senha atual"
            />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Nova Senha</label>
              <Input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Mínimo 8 caracteres"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Confirmar Nova Senha</label>
              <Input
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirme a nova senha"
              />
            </div>
          </div>
          <p className="text-xs text-muted-foreground">
            A senha deve ter no mínimo 8 caracteres, incluindo letra maiúscula, minúscula e número.
          </p>
          <Button 
            onClick={handleChangePassword} 
            disabled={isChangingPassword || !currentPassword || !newPassword || !confirmPassword}
          >
            {isChangingPassword ? "Alterando..." : "Alterar Senha"}
          </Button>
        </CardContent>
      </Card>

      {/* Security Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            Segurança
          </CardTitle>
          <CardDescription>
            Gerencie a segurança da sua conta.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Sessões Ativas</p>
                <p className="text-sm text-muted-foreground">
                  Gerencie os dispositivos conectados
                </p>
              </div>
              <Button variant="outline" size="sm">
                Gerenciar
              </Button>
            </div>
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium">Exportar Dados</p>
                <p className="text-sm text-muted-foreground">
                  Baixe uma cópia dos seus dados
                </p>
              </div>
              <Button variant="outline" size="sm">
                Exportar
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Integrações */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calendar className="h-5 w-5" />
            Integrações
          </CardTitle>
          <CardDescription>
            Conecte suas contas para sincronizar eventos e criar reuniões automaticamente.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Google Calendar */}
            <div className="flex items-center justify-between p-4 border rounded-lg">
              <div className="flex items-center gap-4">
                <div className="w-10 h-10 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center">
                  <Calendar className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <p className="font-medium flex items-center gap-2">
                    Google Calendar
                    {calendarStatus?.connected && (
                      <CheckCircle className="h-4 w-4 text-green-500" />
                    )}
                  </p>
                  {calendarStatus?.connected ? (
                    <p className="text-sm text-muted-foreground">
                      Conectado: {calendarStatus.account_email}
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground">
                      Sincronize eventos e crie reuniões com Google Meet
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {isLoadingCalendar ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : calendarStatus?.connected ? (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => disconnectCalendarMutation.mutate()}
                    disabled={disconnectCalendarMutation.isPending}
                  >
                    {disconnectCalendarMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <XCircle className="h-4 w-4 mr-2" />
                    )}
                    Desconectar
                  </Button>
                ) : (
                  <Button
                    size="sm"
                    onClick={() => connectCalendarMutation.mutate()}
                    disabled={connectCalendarMutation.isPending}
                  >
                    {connectCalendarMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    ) : (
                      <ExternalLink className="h-4 w-4 mr-2" />
                    )}
                    Conectar
                  </Button>
                )}
              </div>
            </div>

            {/* Info sobre integrações */}
            <div className="bg-muted/50 p-4 rounded-lg">
              <p className="text-sm text-muted-foreground">
                <strong>Dica:</strong> Ao conectar o Google Calendar, a IRIS poderá:
              </p>
              <ul className="text-sm text-muted-foreground mt-2 space-y-1 list-disc list-inside">
                <li>Criar eventos e reuniões automaticamente</li>
                <li>Enviar convites para participantes via e-mail</li>
                <li>Gerar links do Google Meet</li>
                <li>Verificar sua disponibilidade</li>
              </ul>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
