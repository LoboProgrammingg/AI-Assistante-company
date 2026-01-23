import { useState, useEffect, useRef } from "react"
import { useNavigate, useLocation, Link } from "react-router-dom"
import { RefreshCw, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AuthBackground } from "@/components/AuthBackground"
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
      toast.error("Digite o código completo")
      return
    }

    setIsLoading(true)
    try {
      await authApi.verifyEmail({ email, code: fullCode })
      toast.success("Email verificado!")
      navigate("/login", { state: { verified: true } })
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Código inválido")
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
      toast.success("Código reenviado!")
      setCountdown(60)
      setCode(["", "", "", "", "", ""])
      inputRefs.current[0]?.focus()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Erro ao reenviar")
    } finally {
      setIsResending(false)
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
        <div className="bg-white/[0.02] backdrop-blur-sm border border-white/[0.05] rounded-2xl p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Code Inputs */}
            <div className="flex justify-center gap-3">
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
                  className="w-12 h-14 text-center text-2xl font-bold bg-white/[0.03] border-white/[0.08] text-white rounded-xl focus:border-purple-500/50 focus:ring-purple-500/20"
                  autoFocus={index === 0}
                />
              ))}
            </div>

            <Button 
              type="submit" 
              disabled={isLoading}
              className="w-full h-13 text-base font-medium bg-gradient-to-r from-purple-600 to-cyan-600 hover:from-purple-500 hover:to-cyan-500 border-0 rounded-xl transition-all duration-300"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <span className="flex items-center gap-2">
                  Verificar
                  <ArrowRight className="w-4 h-4" />
                </span>
              )}
            </Button>
          </form>

          {/* Resend */}
          <div className="mt-6 pt-6 border-t border-white/[0.05] text-center">
            <p className="text-white/40 text-sm mb-3">Não recebeu?</p>
            <Button
              variant="ghost"
              onClick={handleResend}
              disabled={isResending || countdown > 0}
              className="text-purple-400 hover:text-purple-300 hover:bg-white/5"
            >
              <RefreshCw className={`h-4 w-4 mr-2 ${isResending ? "animate-spin" : ""}`} />
              {countdown > 0 ? `Aguarde ${countdown}s` : "Reenviar código"}
            </Button>
          </div>
        </div>

        {/* Back Link */}
        <div className="mt-6 text-center">
          <Link to="/register" className="text-white/40 hover:text-purple-400 text-sm transition-colors">
            ← Voltar ao cadastro
          </Link>
        </div>

        <p className="mt-6 text-center text-white/20 text-xs">
          © 2026 IRIS
        </p>
      </div>
    </AuthBackground>
  )
}
