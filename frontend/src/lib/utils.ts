import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { format, formatDistanceToNow, isToday, isTomorrow, isYesterday } from "date-fns"
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

export function formatDate(date: string | Date, style?: "short" | "long"): string {
  const d = typeof date === "string" ? new Date(date) : date
  const formatStr = style === "long" ? "dd 'de' MMMM 'de' yyyy" : "dd/MM/yyyy"
  return format(d, formatStr, { locale: ptBR })
}

export function formatRelativeDate(date: string | Date | null | undefined): string {
  // Validação de entrada
  if (!date) {
    return "Data não definida"
  }
  
  // Converte string para Date, garantindo que interprete como UTC se terminar com Z
  let d: Date
  if (typeof date === "string") {
    // Se a string não termina com Z, adicionar para garantir interpretação UTC
    const dateStr = date.endsWith("Z") ? date : date + "Z"
    d = new Date(dateStr)
  } else {
    d = date
  }
  
  // Verificar se a data é válida
  if (isNaN(d.getTime())) {
    return "Data inválida"
  }
  
  // Agora d está no timezone local do navegador (convertido de UTC)
  if (isToday(d)) {
    return `Hoje às ${format(d, "HH:mm", { locale: ptBR })}`
  }
  if (isTomorrow(d)) {
    return `Amanhã às ${format(d, "HH:mm", { locale: ptBR })}`
  }
  if (isYesterday(d)) {
    return `Ontem às ${format(d, "HH:mm", { locale: ptBR })}`
  }
  
  return format(d, "dd/MM 'às' HH:mm", { locale: ptBR })
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
