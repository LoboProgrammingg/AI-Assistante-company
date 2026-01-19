import { useState } from "react"
import { Link } from "react-router-dom"
import { MessageSquare, Mail, ArrowLeft } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { authApi } from "@/lib/api"
import toast from "react-hot-toast"

export function ForgotPassword() {
  const [email, setEmail] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [emailSent, setEmailSent] = useState(false)
  const [error, setError] = useState("")

  const validateEmail = (email: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (!email.trim()) {
      setError("Email é obrigatório")
      return
    }

    if (!validateEmail(email)) {
      setError("Email inválido")
      return
    }

    setIsLoading(true)
    try {
      await authApi.forgotPassword({ email })
      setEmailSent(true)
      toast.success("Código enviado para seu email!")
    } catch (error: any) {
      const message = error.response?.data?.detail || "Erro ao enviar código. Tente novamente."
      toast.error(message)
    } finally {
      setIsLoading(false)
    }
  }

  if (emailSent) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
        <Card className="w-full max-w-md">
          <CardHeader className="text-center">
            <div className="mx-auto w-16 h-16 rounded-2xl bg-green-500 flex items-center justify-center mb-4">
              <Mail className="w-8 h-8 text-white" />
            </div>
            <CardTitle className="text-2xl">Email Enviado!</CardTitle>
            <CardDescription>
              Enviamos um código de recuperação para <strong>{email}</strong>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground text-center">
              Verifique sua caixa de entrada e spam. O código expira em 15 minutos.
            </p>
            <Link to="/reset-password" state={{ email }}>
              <Button className="w-full">
                Inserir Código
              </Button>
            </Link>
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

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-primary flex items-center justify-center mb-4">
            <MessageSquare className="w-8 h-8 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl">Esqueceu a Senha?</CardTitle>
          <CardDescription>
            Digite seu email para receber um código de recuperação
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="email">
                Email
              </label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  id="email"
                  type="email"
                  placeholder="seu@email.com"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    setError("")
                  }}
                  className={`pl-10 ${error ? "border-destructive" : ""}`}
                />
              </div>
              {error && <p className="text-xs text-destructive">{error}</p>}
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Enviando..." : "Enviar Código"}
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
