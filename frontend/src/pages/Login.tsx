import { useState, useEffect } from "react"
import { useNavigate, Link, useLocation } from "react-router-dom"
import { Mail, Lock, Eye, EyeOff, ArrowRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { AuthBackground } from "@/components/AuthBackground"
import { useAuthStore } from "@/stores/auth"
import toast from "react-hot-toast"

export function Login() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const { login } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (location.state?.verified) {
      toast.success("Email verificado!")
    }
  }, [location.state])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || !password) {
      toast.error("Preencha todos os campos")
      return
    }

    setIsLoading(true)
    try {
      await login(email, password)
      navigate("/")
    } catch (error: any) {
      toast.error(error.response?.data?.detail || "Credenciais inválidas")
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
            className="w-96 h-96 object-contain mx-auto drop-shadow-[0_0_30px_rgba(139,92,246,0.3)]"
          />
        </div>

        {/* Form Card */}
        <div className="bg-white/[0.02] backdrop-blur-sm border border-white/[0.05] rounded-2xl p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30" />
              <Input
                type="email"
                placeholder="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-13 pl-12 bg-white/[0.03] border-white/[0.08] text-white placeholder:text-white/30 rounded-xl focus:border-purple-500/50 focus:ring-purple-500/20"
              />
            </div>

            <div className="relative">
              <Lock className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-white/30" />
              <Input
                type={showPassword ? "text" : "password"}
                placeholder="Senha"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-13 pl-12 pr-12 bg-white/[0.03] border-white/[0.08] text-white placeholder:text-white/30 rounded-xl focus:border-purple-500/50 focus:ring-purple-500/20"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
              >
                {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
              </button>
            </div>

            <div className="text-right">
              <Link to="/forgot-password" className="text-sm text-white/40 hover:text-purple-400 transition-colors">
                Esqueceu a senha?
              </Link>
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
                  Entrar
                  <ArrowRight className="w-4 h-4" />
                </span>
              )}
            </Button>
          </form>

          <div className="mt-6 pt-6 border-t border-white/[0.05] text-center">
            <span className="text-white/40 text-sm">Não tem conta? </span>
            <Link to="/register" className="text-purple-400 hover:text-purple-300 text-sm font-medium transition-colors">
              Criar conta
            </Link>
          </div>
        </div>

        <p className="mt-6 text-center text-white/20 text-xs">
          © 2026 IRIS
        </p>
      </div>
    </AuthBackground>
  )
}
