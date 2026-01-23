import type { ReactNode } from "react"

interface AuthBackgroundProps {
  children: ReactNode
}

export function AuthBackground({ children }: AuthBackgroundProps) {
  return (
    <div className="min-h-screen relative overflow-hidden bg-[#050508]">
      {/* Gradient Mesh */}
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-to-b from-purple-600/20 via-cyan-600/10 to-transparent rounded-full blur-[100px]" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-blue-600/10 rounded-full blur-[80px]" />
        <div className="absolute bottom-0 right-0 w-[400px] h-[400px] bg-purple-600/10 rounded-full blur-[80px]" />
      </div>

      {/* Tech Grid */}
      <div 
        className="absolute inset-0"
        style={{
          backgroundImage: `
            linear-gradient(rgba(99, 102, 241, 0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(99, 102, 241, 0.03) 1px, transparent 1px)
          `,
          backgroundSize: '50px 50px'
        }}
      />

      {/* Horizontal Lines */}
      <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-cyan-500/30 to-transparent" />
      <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-purple-500/30 to-transparent" />

      {/* Corner Accents */}
      <div className="absolute top-0 left-0 w-32 h-32">
        <div className="absolute top-8 left-0 w-24 h-[1px] bg-gradient-to-r from-cyan-500/50 to-transparent" />
        <div className="absolute top-0 left-8 w-[1px] h-24 bg-gradient-to-b from-cyan-500/50 to-transparent" />
      </div>
      <div className="absolute top-0 right-0 w-32 h-32">
        <div className="absolute top-8 right-0 w-24 h-[1px] bg-gradient-to-l from-purple-500/50 to-transparent" />
        <div className="absolute top-0 right-8 w-[1px] h-24 bg-gradient-to-b from-purple-500/50 to-transparent" />
      </div>
      <div className="absolute bottom-0 left-0 w-32 h-32">
        <div className="absolute bottom-8 left-0 w-24 h-[1px] bg-gradient-to-r from-purple-500/50 to-transparent" />
        <div className="absolute bottom-0 left-8 w-[1px] h-24 bg-gradient-to-t from-purple-500/50 to-transparent" />
      </div>
      <div className="absolute bottom-0 right-0 w-32 h-32">
        <div className="absolute bottom-8 right-0 w-24 h-[1px] bg-gradient-to-l from-cyan-500/50 to-transparent" />
        <div className="absolute bottom-0 right-8 w-[1px] h-24 bg-gradient-to-t from-cyan-500/50 to-transparent" />
      </div>

      {/* Content */}
      <div className="relative z-10 min-h-screen flex items-center justify-center p-6">
        {children}
      </div>
    </div>
  )
}
