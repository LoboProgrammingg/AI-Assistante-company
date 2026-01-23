import { useState } from "react"
import { useNavigate, Link } from "react-router-dom"
import { User, Mail, Lock, Phone, Eye, EyeOff, MapPin, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { AuthBackground } from "@/components/AuthBackground"
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
    <AuthBackground>
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-0">
          <img 
            src="/images/iris-logo.png" 
            alt="IRIS" 
            className="w-80 h-80 object-contain mx-auto drop-shadow-[0_0_30px_rgba(139,92,246,0.3)]"
          />
        </div>

        {/* Form Card */}
        <div className="bg-white/[0.02] backdrop-blur-sm border border-white/[0.05] rounded-2xl p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Nome */}
            <div>
              <div className="relative">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30" />
                <Input
                  name="name"
                  type="text"
                  placeholder="Nome completo"
                  value={formData.name}
                  onChange={handleChange}
                  className={`h-12 pl-12 bg-white/[0.03] border-white/[0.08] text-white placeholder:text-white/30 rounded-xl focus:border-purple-500/50 ${errors.name ? "border-red-500/50" : ""}`}
                />
              </div>
              {errors.name && <p className="text-xs text-red-400 mt-1">{errors.name}</p>}
            </div>

            {/* Email */}
            <div>
              <div className="relative">
                <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30" />
                <Input
                  name="email"
                  type="email"
                  placeholder="Email"
                  value={formData.email}
                  onChange={handleChange}
                  className={`h-12 pl-12 bg-white/[0.03] border-white/[0.08] text-white placeholder:text-white/30 rounded-xl focus:border-purple-500/50 ${errors.email ? "border-red-500/50" : ""}`}
                />
              </div>
              {errors.email && <p className="text-xs text-red-400 mt-1">{errors.email}</p>}
            </div>

            {/* Telefone */}
            <div>
              <div className="relative">
                <Phone className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30" />
                <Input
                  name="phone_number"
                  type="tel"
                  placeholder="WhatsApp (5565992540370)"
                  value={formData.phone_number}
                  onChange={handleChange}
                  className={`h-12 pl-12 bg-white/[0.03] border-white/[0.08] text-white placeholder:text-white/30 rounded-xl focus:border-purple-500/50 ${errors.phone_number ? "border-red-500/50" : ""}`}
                />
              </div>
              {errors.phone_number && <p className="text-xs text-red-400 mt-1">{errors.phone_number}</p>}
            </div>

            {/* Estado */}
            <div>
              <div className="relative">
                <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30 z-10" />
                <Select
                  value={formData.state}
                  onValueChange={(value) => {
                    setFormData((prev) => ({ ...prev, state: value }))
                    if (errors.state) setErrors((prev) => ({ ...prev, state: "" }))
                  }}
                >
                  <SelectTrigger className={`h-12 pl-12 bg-white/[0.03] border-white/[0.08] text-white rounded-xl focus:border-purple-500/50 [&>span]:text-white/30 ${formData.state ? "[&>span]:text-white" : ""} ${errors.state ? "border-red-500/50" : ""}`}>
                    <SelectValue placeholder="Selecione seu estado" />
                  </SelectTrigger>
                  <SelectContent className="bg-[#0a0a12] border-white/10">
                    {Object.entries(ESTADOS_TIMEZONE)
                      .sort((a, b) => a[1].nome.localeCompare(b[1].nome))
                      .map(([sigla, { nome }]) => (
                        <SelectItem key={sigla} value={sigla} className="text-white hover:bg-white/10">
                          {nome} ({sigla})
                        </SelectItem>
                      ))}
                  </SelectContent>
                </Select>
              </div>
              {errors.state && <p className="text-xs text-red-400 mt-1">{errors.state}</p>}
            </div>

            {/* Senha */}
            <div>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30" />
                <Input
                  name="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Senha (mín. 8 caracteres)"
                  value={formData.password}
                  onChange={handleChange}
                  className={`h-12 pl-12 pr-12 bg-white/[0.03] border-white/[0.08] text-white placeholder:text-white/30 rounded-xl focus:border-purple-500/50 ${errors.password ? "border-red-500/50" : ""}`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                >
                  {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              {errors.password && <p className="text-xs text-red-400 mt-1">{errors.password}</p>}
            </div>

            {/* Confirmar Senha */}
            <div>
              <div className="relative">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30" />
                <Input
                  name="password_confirm"
                  type={showConfirmPassword ? "text" : "password"}
                  placeholder="Confirmar senha"
                  value={formData.password_confirm}
                  onChange={handleChange}
                  className={`h-12 pl-12 pr-12 bg-white/[0.03] border-white/[0.08] text-white placeholder:text-white/30 rounded-xl focus:border-purple-500/50 ${errors.password_confirm ? "border-red-500/50" : ""}`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                >
                  {showConfirmPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              {errors.password_confirm && <p className="text-xs text-red-400 mt-1">{errors.password_confirm}</p>}
            </div>

            <Button 
              type="submit" 
              disabled={isLoading}
              className="w-full h-12 text-base font-medium bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 border-0 rounded-xl transition-all duration-300 mt-2"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <span className="flex items-center gap-2">
                  Criar Conta
                  <ArrowRight className="w-4 h-4" />
                </span>
              )}
            </Button>
          </form>

          <div className="mt-5 pt-5 border-t border-white/[0.05] text-center">
            <span className="text-white/40 text-sm">Já tem conta? </span>
            <Link to="/login" className="text-purple-400 hover:text-purple-300 text-sm font-medium transition-colors">
              Fazer login
            </Link>
          </div>
        </div>

        <p className="mt-5 text-center text-white/20 text-xs">
          © 2026 IRIS
        </p>
      </div>
    </AuthBackground>
  )
}
