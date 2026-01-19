import { useState, useEffect, useRef } from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import { MessageSquare, Mail, RefreshCw } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { authApi } from "@/lib/api"
import toast from "react-hot-toast"

export function VerifyEmail() {
  const [code, setCode] = useState(["", "", "", "", "", ""])
  const [isLoading, setIsLoading] = useState(false)
  const [isResending, setIsResending] = useState(false)
  const [countdown, setCountdown] = useState(0)
  const inputRefs = useRef<(HTMLInputElement | null)[]>([])
  const navigate = useNavigate()
  const location = useLocation()
  const email = location.state?.email || ""

  useEffect(() => {
    if (!email) {
      navigate("/register")
    }
  }, [email, navigate])

  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000)
      return () => clearTimeout(timer)
    }
  }, [countdown])

  const handleChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return

    const newCode = [...code]
    newCode[index] = value.slice(-1)
    setCode(newCode)

    if (value && index < 5) {
      inputRefs.current[index + 1]?.focus()
    }
  }

  const handleKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === "Backspace" && !code[index] && index > 0) {
      inputRefs.current[index - 1]?.focus()
    }
  }

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault()
    const pastedData = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6)
    if (pastedData.length === 6) {
      setCode(pastedData.split(""))
      inputRefs.current[5]?.focus()
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    const fullCode = code.join("")
    if (fullCode.length !== 6) {
      toast.error("Digite o código completo de 6 dígitos")
      return
    }

    setIsLoading(true)
    try {
      await authApi.verifyEmail({ email, code: fullCode })
      toast.success("Email verificado com sucesso!")
      navigate("/login", { state: { verified: true } })
    } catch (error: any) {
      const message = error.response?.data?.detail || "Código inválido ou expirado"
      toast.error(message)
      setCode(["", "", "", "", "", ""])
      inputRefs.current[0]?.focus()
    } finally {
      setIsLoading(false)
    }
  }

  const handleResend = async () => {
    if (countdown > 0) return

    setIsResending(true)
    try {
      await authApi.resendCode({ email })
      toast.success("Código reenviado! Verifique seu email.")
      setCountdown(60)
      setCode(["", "", "", "", "", ""])
      inputRefs.current[0]?.focus()
    } catch (error: any) {
      const message = error.response?.data?.detail || "Erro ao reenviar código"
      toast.error(message)
    } finally {
      setIsResending(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-background to-muted p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="mx-auto w-16 h-16 rounded-2xl bg-primary flex items-center justify-center mb-4">
            <Mail className="w-8 h-8 text-primary-foreground" />
          </div>
          <CardTitle className="text-2xl">Verificar Email</CardTitle>
          <CardDescription>
            Digite o código de 6 dígitos enviado para{" "}
            <span className="font-medium text-foreground">{email}</span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="flex justify-center gap-2">
              {code.map((digit, index) => (
                <Input
                  key={index}
                  ref={(el) => { inputRefs.current[index] = el }}
                  type="text"
                  inputMode="numeric"
                  maxLength={1}
                  value={digit}
                  onChange={(e) => handleChange(index, e.target.value)}
                  onKeyDown={(e) => handleKeyDown(index, e)}
                  onPaste={index === 0 ? handlePaste : undefined}
                  className="w-12 h-14 text-center text-2xl font-bold"
                  autoFocus={index === 0}
                />
              ))}
            </div>

            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? "Verificando..." : "Verificar Email"}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-sm text-muted-foreground mb-2">
              Não recebeu o código?
            </p>
            <Button
              variant="outline"
              onClick={handleResend}
              disabled={isResending || countdown > 0}
              className="gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${isResending ? "animate-spin" : ""}`} />
              {countdown > 0 ? `Reenviar em ${countdown}s` : "Reenviar código"}
            </Button>
          </div>
        </CardContent>
        <CardFooter className="flex justify-center">
          <p className="text-sm text-muted-foreground">
            Email errado?{" "}
            <Link to="/register" className="text-primary hover:underline">
              Voltar ao cadastro
            </Link>
          </p>
        </CardFooter>
      </Card>
    </div>
  )
}
