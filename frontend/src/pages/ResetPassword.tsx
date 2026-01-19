import { useState } from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import { MessageSquare, Lock, KeyRound, Eye, EyeOff, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { authApi } from "@/lib/api"
import toast from "react-hot-toast"

export function ResetPassword() {
  const location = useLocation()
  const navigate = useNavigate()
  const emailFromState = location.state?.email || ""

  const [formData, setFormData] = useState({
    email: emailFromState,
    code: "",
    new_password: "",
    new_password_confirm: "",
  })
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})

  const validateForm = () => {
    const newErrors: Record<string, string> = {}

    if (!formData.email.trim()) {
      newErrors.email = "Email é obrigatório"
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = "Email inválido"
    }

    if (!formData.code.trim()) {
      newErrors.code = "Código é obrigatório"
    } else if (formData.code.length !== 6) {
      newErrors.code = "Código deve ter 6 dígitos"
    }

    if (!formData.new_password) {
      newErrors.new_password = "Senha é obrigatória"
    } else if (formData.new_password.length < 8) {
      newErrors.new_password = "Senha deve ter pelo menos 8 caracteres"
    } else if (!/[A-Z]/.test(formData.new_password)) {
      newErrors.new_password = "Senha deve conter letra maiúscula"
    } else if (!/[a-z]/.test(formData.new_password)) {
      newErrors.new_password = "Senha deve conter letra minúscula"
    } else if (!/\d/.test(formData.new_password)) {
      newErrors.new_password = "Senha deve conter número"
    }

    if (formData.new_password !== formData.new_password_confirm) {
      newErrors.new_password_confirm = "Senhas não conferem"
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
      await authApi.resetPassword(formData)
      toast.success("Senha alterada com sucesso!")
      navigate("/login")
    } catch (error: any) {
      const message = error.response?.data?.detail || "Erro ao redefinir senha. Tente novamente."
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
            <KeyRound className="w-8 h-8 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl">Redefinir Senha</CardTitle>
          <CardDescription>
            Digite o código recebido por email e sua nova senha
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="email">
                Email
              </label>
              <Input
                id="email"
                name="email"
                type="email"
                placeholder="seu@email.com"
                value={formData.email}
                onChange={handleChange}
                className={errors.email ? "border-destructive" : ""}
              />
              {errors.email && <p className="text-xs text-destructive">{errors.email}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="code">
                Código de Verificação
              </label>
              <Input
                id="code"
                name="code"
                type="text"
                placeholder="000000"
                maxLength={6}
                value={formData.code}
                onChange={handleChange}
                className={`text-center text-2xl tracking-widest ${errors.code ? "border-destructive" : ""}`}
              />
              {errors.code && <p className="text-xs text-destructive">{errors.code}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="new_password">
                Nova Senha
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="new_password"
                  name="new_password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Mínimo 8 caracteres"
                  value={formData.new_password}
                  onChange={handleChange}
                  className={`pl-10 pr-10 ${errors.new_password ? "border-destructive" : ""}`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.new_password && <p className="text-xs text-destructive">{errors.new_password}</p>}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="new_password_confirm">
                Confirmar Nova Senha
              </label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="new_password_confirm"
                  name="new_password_confirm"
                  type={showConfirmPassword ? "text" : "password"}
                  placeholder="Confirme sua nova senha"
                  value={formData.new_password_confirm}
                  onChange={handleChange}
                  className={`pl-10 pr-10 ${errors.new_password_confirm ? "border-destructive" : ""}`}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {errors.new_password_confirm && <p className="text-xs text-destructive">{errors.new_password_confirm}</p>}
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Redefinindo..." : "Redefinir Senha"}
            </Button>
          </form>
        </CardContent>
        <CardFooter className="flex justify-center">
          <Link to="/login" className="text-sm text-primary hover:underline flex items-center gap-1">
            <ArrowLeft className="h-4 w-4" />
            Voltar para login
          </Link>
        </CardFooter>
      </Card>
    </div>
  )
}
