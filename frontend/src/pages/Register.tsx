import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { MessageSquare, User, Mail, Lock, Phone, Eye, EyeOff, MapPin } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { authApi } from "@/lib/api"
import toast from "react-hot-toast"

// Mapeamento de estados brasileiros para timezones
const ESTADOS_TIMEZONE: Record<string, { nome: string; timezone: string }> = {
  AC: { nome: "Acre", timezone: "America/Rio_Branco" },
  AL: { nome: "Alagoas", timezone: "America/Maceio" },
  AP: { nome: "Amapá", timezone: "America/Belem" },
  AM: { nome: "Amazonas", timezone: "America/Manaus" },
  BA: { nome: "Bahia", timezone: "America/Bahia" },
  CE: { nome: "Ceará", timezone: "America/Fortaleza" },
  DF: { nome: "Distrito Federal", timezone: "America/Sao_Paulo" },
  ES: { nome: "Espírito Santo", timezone: "America/Sao_Paulo" },
  GO: { nome: "Goiás", timezone: "America/Sao_Paulo" },
  MA: { nome: "Maranhão", timezone: "America/Fortaleza" },
  MT: { nome: "Mato Grosso", timezone: "America/Cuiaba" },
  MS: { nome: "Mato Grosso do Sul", timezone: "America/Campo_Grande" },
  MG: { nome: "Minas Gerais", timezone: "America/Sao_Paulo" },
  PA: { nome: "Pará", timezone: "America/Belem" },
  PB: { nome: "Paraíba", timezone: "America/Fortaleza" },
  PR: { nome: "Paraná", timezone: "America/Sao_Paulo" },
  PE: { nome: "Pernambuco", timezone: "America/Recife" },
  PI: { nome: "Piauí", timezone: "America/Fortaleza" },
  RJ: { nome: "Rio de Janeiro", timezone: "America/Sao_Paulo" },
  RN: { nome: "Rio Grande do Norte", timezone: "America/Fortaleza" },
  RS: { nome: "Rio Grande do Sul", timezone: "America/Sao_Paulo" },
  RO: { nome: "Rondônia", timezone: "America/Porto_Velho" },
  RR: { nome: "Roraima", timezone: "America/Boa_Vista" },
  SC: { nome: "Santa Catarina", timezone: "America/Sao_Paulo" },
  SP: { nome: "São Paulo", timezone: "America/Sao_Paulo" },
  SE: { nome: "Sergipe", timezone: "America/Maceio" },
  TO: { nome: "Tocantins", timezone: "America/Araguaina" },
}

export function Register() {
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    password_confirm: "",
    phone_number: "",
    state: "",
  })
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const navigate = useNavigate()

  // Formata o telefone para o padrão WhatsApp (apenas dígitos, ex: 5565992540370)
  const formatPhoneForWhatsApp = (phone: string): string => {
    return phone.replace(/\D/g, "")
  }

  // Valida o formato do telefone WhatsApp
  const validateWhatsAppPhone = (phone: string): boolean => {
    const digits = phone.replace(/\D/g, "")
    // Formato: código país (2 dígitos) + DDD (2 dígitos) + número (8-9 dígitos)
    // Ex: 5565992540370 (BR + MT + número)
    return digits.length >= 12 && digits.length <= 13 && digits.startsWith("55")
  }

  const validateForm = () => {
    const newErrors: Record<string, string> = {}

    if (!formData.name.trim()) {
      newErrors.name = "Nome é obrigatório"
    } else if (formData.name.length < 2) {
      newErrors.name = "Nome deve ter pelo menos 2 caracteres"
    }

    if (!formData.email.trim()) {
      newErrors.email = "Email é obrigatório"
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = "Email inválido"
    }

    if (!formData.password) {
      newErrors.password = "Senha é obrigatória"
    } else if (formData.password.length < 8) {
      newErrors.password = "Senha deve ter pelo menos 8 caracteres"
    } else if (!/[A-Z]/.test(formData.password)) {
      newErrors.password = "Senha deve conter letra maiúscula"
    } else if (!/[a-z]/.test(formData.password)) {
      newErrors.password = "Senha deve conter letra minúscula"
    } else if (!/\d/.test(formData.password)) {
      newErrors.password = "Senha deve conter número"
    }

    if (formData.password !== formData.password_confirm) {
      newErrors.password_confirm = "Senhas não conferem"
    }

    if (!formData.phone_number.trim()) {
      newErrors.phone_number = "Telefone é obrigatório"
    } else if (!validateWhatsAppPhone(formData.phone_number)) {
      newErrors.phone_number = "Formato: 5565992540370 (código país + DDD + número)"
    }

    if (!formData.state) {
      newErrors.state = "Selecione seu estado"
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    setFormData((prev) => ({ ...prev, [name]: value }))
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: "" }))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    setIsLoading(true)
    try {
      // Formatar telefone e obter timezone do estado selecionado
      const timezone = ESTADOS_TIMEZONE[formData.state]?.timezone || "America/Sao_Paulo"
      const dataToSend = {
        name: formData.name,
        email: formData.email,
        password: formData.password,
        password_confirm: formData.password_confirm,
        phone_number: formatPhoneForWhatsApp(formData.phone_number),
        timezone: timezone,
      }
      await authApi.register(dataToSend)
      toast.success("Cadastro realizado! Verifique seu email.")
      navigate("/verify-email", { state: { email: formData.email } })
    } catch (error: any) {
      const message = error.response?.data?.detail || "Erro ao cadastrar. Tente novamente."
      toast.error(message)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-primary flex items-center justify-center mb-4">
            <MessageSquare className="w-8 h-8 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl">Criar Conta</CardTitle>
          <CardDescription>
            Cadastre-se para acessar o WhatsApp AI Assistant
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="name">
                Nome Completo
              </label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="name"
                  name="name"
                  type="text"
                  placeholder="Seu nome completo"
                  value={formData.name}
                  onChange={handleChange}
                  className={`pl-10 ${errors.name ? "border-destructive" : ""}`}
                />
              </div>
              {errors.name && <p className="text-xs text-destructive">{errors.name}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="email">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="email"
                  name="email"
                  type="email"
                  placeholder="seu@email.com"
                  value={formData.email}
                  onChange={handleChange}
                  className={`pl-10 ${errors.email ? "border-destructive" : ""}`}
                />
              </div>
              {errors.email && <p className="text-xs text-destructive">{errors.email}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="phone_number">
                Telefone (WhatsApp)
              </label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="phone_number"
                  name="phone_number"
                  type="tel"
                  placeholder="5565992540370"
                  value={formData.phone_number}
                  onChange={handleChange}
                  className={`pl-10 ${errors.phone_number ? "border-destructive" : ""}`}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                Formato: código país + DDD + número (ex: 5565992540370)
              </p>
              {errors.phone_number && <p className="text-xs text-destructive">{errors.phone_number}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="state">
                Estado
              </label>
              <div className="relative">
                <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground z-10" />
                <Select
                  value={formData.state}
                  onValueChange={(value) => {
                    setFormData((prev) => ({ ...prev, state: value }))
                    if (errors.state) {
                      setErrors((prev) => ({ ...prev, state: "" }))
                    }
                  }}
                >
                  <SelectTrigger className={`pl-10 ${errors.state ? "border-destructive" : ""}`}>
                    <SelectValue placeholder="Selecione seu estado" />
                  </SelectTrigger>
                  <SelectContent>
                    {Object.entries(ESTADOS_TIMEZONE)
                      .sort((a, b) => a[1].nome.localeCompare(b[1].nome))
                      .map(([sigla, { nome }]) => (
                        <SelectItem key={sigla} value={sigla}>
                          {nome} ({sigla})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="text-xs text-muted-foreground">
                Usado para ajustar o horário da IA ao seu fuso
              </p>
              {errors.state && <p className="text-xs text-destructive">{errors.state}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="password">
                Senha
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Mínimo 8 caracteres"
                  value={formData.password}
                  onChange={handleChange}
                  className={`pl-10 pr-10 ${errors.password ? "border-destructive" : ""}`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-destructive">{errors.password}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="password_confirm">
                Confirmar Senha
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="password_confirm"
                  name="password_confirm"
                  type={showConfirmPassword ? "text" : "password"}
                  placeholder="Confirme sua senha"
                  value={formData.password_confirm}
                  onChange={handleChange}
                  className={`pl-10 pr-10 ${errors.password_confirm ? "border-destructive" : ""}`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.password_confirm && <p className="text-xs text-destructive">{errors.password_confirm}</p>}
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Cadastrando..." : "Criar Conta"}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center">
          <p className="text-sm text-muted-foreground">
            Já tem uma conta?{" "}
            <Link to="/login" className="text-primary hover:underline">
              Faça login
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  )
}
