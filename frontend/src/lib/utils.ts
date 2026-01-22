import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { format, isToday, isTomorrow, isYesterday, differenceInDays, parseISO } from "date-fns"
import { ptBR } from "date-fns/locale"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCurrency(value: number): string {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(value)
}

/**
 * Converte string de data do backend para Date local
 * O backend envia datas no timezone do usuário sem sufixo Z
 * Então interpretamos como hora local, não UTC
 * 
 * IMPORTANTE: Para datas sem hora (yyyy-MM-dd), criamos Date com hora 12:00
 * para evitar problemas de timezone que fazem a data aparecer 1 dia antes
 */
function parseLocalDate(dateStr: string): Date {
  let normalized = dateStr.trim()
  
  // Se já tem Z ou offset, é UTC - parse normal
  if (normalized.endsWith("Z") || /[+-]\d{2}:\d{2}$/.test(normalized)) {
    return new Date(normalized)
  }
  
  // CORREÇÃO: Data apenas (yyyy-MM-dd) - adiciona hora 12:00 para evitar shift de timezone
  if (/^\d{4}-\d{2}-\d{2}$/.test(normalized)) {
    const [year, month, day] = normalized.split("-").map(Number)
    return new Date(year, month - 1, day, 12, 0, 0)
  }
  
  // Substitui espaço por T para formato ISO
  if (normalized.includes(" ") && !normalized.includes("T")) {
    normalized = normalized.replace(" ", "T")
  }
  
  // Adiciona segundos se não tiver
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(normalized)) {
    normalized = normalized + ":00"
  }
  
  // Parse como hora local (sem converter de UTC)
  const parts = normalized.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/)
  if (parts) {
    const [, year, month, day, hour, minute, second] = parts
    return new Date(
      parseInt(year),
      parseInt(month) - 1,
      parseInt(day),
      parseInt(hour),
      parseInt(minute),
      parseInt(second)
    )
  }
  
  // Fallback para Date constructor
  return new Date(normalized)
}

export function formatDate(date: string | Date | null | undefined, style?: "short" | "long"): string {
  if (!date) return "—"
  
  const d = typeof date === "string" ? parseLocalDate(date) : date
  
  if (isNaN(d.getTime())) return "Data inválida"
  
  const formatStr = style === "long" ? "dd 'de' MMMM 'de' yyyy" : "dd/MM/yyyy"
  return format(d, formatStr, { locale: ptBR })
}

export function formatDateTime(date: string | Date | null | undefined): string {
  if (!date) return "—"
  
  const d = typeof date === "string" ? parseLocalDate(date) : date
  
  if (isNaN(d.getTime())) return "Data inválida"
  
  return format(d, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })
}

export function formatRelativeDate(date: string | Date | null | undefined): string {
  if (!date) {
    return "Data não definida"
  }
  
  const d = typeof date === "string" ? parseLocalDate(date) : date
  
  if (isNaN(d.getTime())) {
    return "Data inválida"
  }
  
  const now = new Date()
  const diffDays = differenceInDays(d, now)
  
  if (isToday(d)) {
    return `Hoje às ${format(d, "HH:mm", { locale: ptBR })}`
  }
  if (isTomorrow(d)) {
    return `Amanhã às ${format(d, "HH:mm", { locale: ptBR })}`
  }
  if (isYesterday(d)) {
    return `Ontem às ${format(d, "HH:mm", { locale: ptBR })}`
  }
  
  // Para datas próximas (até 7 dias)
  if (diffDays > 0 && diffDays <= 7) {
    return format(d, "EEEE 'às' HH:mm", { locale: ptBR })
  }
  
  // Para datas do mesmo ano
  if (d.getFullYear() === now.getFullYear()) {
    return format(d, "dd/MM 'às' HH:mm", { locale: ptBR })
  }
  
  // Para outros anos
  return format(d, "dd/MM/yyyy 'às' HH:mm", { locale: ptBR })
}

export function formatShortDate(date: string | Date | null | undefined): string {
  if (!date) return "—"
  
  const d = typeof date === "string" ? parseLocalDate(date) : date
  
  if (isNaN(d.getTime())) return "—"
  
  if (isToday(d)) return "Hoje"
  if (isYesterday(d)) return "Ontem"
  if (isTomorrow(d)) return "Amanhã"
  
  return format(d, "dd/MM", { locale: ptBR })
}

export function getInitials(name: string): string {
  if (!name) return ""
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2)
}
