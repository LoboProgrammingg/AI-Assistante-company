"""
Context Compressor - Reduz tokens enviados ao LLM.

Estratégias:
1. Filtra dados por relevância à intenção
2. Limita quantidade de transações/itens
3. Remove campos redundantes
4. Prioriza dados recentes
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CompressionConfig:
    """Configuração de compressão por intenção."""
    
    include_finance: bool = False
    include_reminders: bool = False
    include_meetings: bool = False
    include_goals: bool = False
    include_contacts: bool = False
    
    max_transactions: int = 10
    max_reminders: int = 5
    max_meetings: int = 3
    max_goals: int = 5
    
    include_summary: bool = True
    include_categories: bool = False
    include_previous_month: bool = False


INTENT_CONFIGS: Dict[str, CompressionConfig] = {
    "finance": CompressionConfig(
        include_finance=True,
        include_goals=True,
        max_transactions=20,
        include_summary=True,
        include_categories=True,
        include_previous_month=True,
    ),
    "goals": CompressionConfig(
        include_finance=True,
        include_goals=True,
        max_transactions=10,
        include_summary=True,
        include_categories=False,
        include_previous_month=True,
    ),
    "advisor": CompressionConfig(
        include_finance=True,
        include_goals=True,
        max_transactions=15,
        include_summary=True,
        include_categories=True,
        include_previous_month=True,
    ),
    "patterns": CompressionConfig(
        include_finance=True,
        max_transactions=30,
        include_summary=True,
        include_categories=True,
        include_previous_month=True,
    ),
    "reminder": CompressionConfig(
        include_reminders=True,
        max_reminders=10,
    ),
    "calendar": CompressionConfig(
        include_meetings=True,
        include_reminders=True,
        max_meetings=5,
        max_reminders=5,
    ),
    "general": CompressionConfig(
        include_finance=True,
        include_reminders=True,
        max_transactions=5,
        max_reminders=3,
        include_summary=True,
    ),
}


class ContextCompressor:
    """
    Comprime contexto do usuário baseado na intenção.
    
    Reduz significativamente o número de tokens enviados ao LLM
    mantendo apenas informações relevantes.
    """
    
    def __init__(self, intent: str = "general"):
        self.intent = intent
        self.config = INTENT_CONFIGS.get(intent, INTENT_CONFIGS["general"])
    
    def compress(self, full_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprime contexto completo.
        
        Args:
            full_context: Contexto completo do UserDataLoader
            
        Returns:
            Contexto comprimido com apenas dados relevantes
        """
        compressed = {}
        
        if self.config.include_finance:
            compressed["finance"] = self._compress_finance(
                full_context.get("finance", {})
            )
        
        if self.config.include_reminders:
            compressed["reminders"] = self._compress_reminders(
                full_context.get("reminders", {})
            )
        
        if self.config.include_meetings:
            compressed["meetings"] = self._compress_meetings(
                full_context.get("meetings", {})
            )
        
        if self.config.include_goals:
            compressed["goals"] = self._compress_goals(
                full_context.get("goals", {})
            )
        
        if self.config.include_contacts:
            compressed["contacts"] = full_context.get("contacts", {})
        
        return compressed
    
    def _compress_finance(self, finance: Dict[str, Any]) -> Dict[str, Any]:
        """Comprime dados financeiros."""
        result = {}
        
        current = finance.get("current_month", {})
        
        if self.config.include_summary:
            result["summary"] = current.get("summary", {})
            result["period"] = current.get("period", "")
        
        transactions = current.get("transactions", [])
        result["transactions"] = transactions[:self.config.max_transactions]
        result["transactions_total"] = len(transactions)
        
        if self.config.include_categories:
            result["by_category"] = current.get("by_category", [])[:5]
        
        top_expenses = finance.get("top_expenses", [])
        result["top_expenses"] = top_expenses[:5]
        
        if self.config.include_previous_month:
            previous = finance.get("previous_month", {})
            if previous:
                result["previous_month"] = {
                    "period": previous.get("period", ""),
                    "summary": previous.get("summary", {}),
                }
        
        return result
    
    def _compress_reminders(self, reminders: Dict[str, Any]) -> Dict[str, Any]:
        """Comprime lembretes."""
        active = reminders.get("active", [])
        
        return {
            "total_active": reminders.get("total_active", len(active)),
            "upcoming_count": reminders.get("upcoming_count", 0),
            "active": active[:self.config.max_reminders],
        }
    
    def _compress_meetings(self, meetings: Dict[str, Any]) -> Dict[str, Any]:
        """Comprime reuniões."""
        recent = meetings.get("recent", [])
        
        return {
            "recent": recent[:self.config.max_meetings],
        }
    
    def _compress_goals(self, goals: Dict[str, Any]) -> Dict[str, Any]:
        """Comprime metas."""
        active = goals.get("active", [])
        
        return {
            "active": active[:self.config.max_goals],
        }
    
    def format_for_prompt(self, compressed: Dict[str, Any]) -> str:
        """
        Formata contexto comprimido como string para prompt.
        
        Args:
            compressed: Contexto comprimido
            
        Returns:
            String formatada para incluir no prompt
        """
        parts = []
        
        if "finance" in compressed:
            parts.append(self._format_finance(compressed["finance"]))
        
        if "reminders" in compressed:
            parts.append(self._format_reminders(compressed["reminders"]))
        
        if "meetings" in compressed:
            parts.append(self._format_meetings(compressed["meetings"]))
        
        if "goals" in compressed:
            parts.append(self._format_goals(compressed["goals"]))
        
        return "\n\n".join(filter(None, parts))
    
    def _format_finance(self, finance: Dict[str, Any]) -> str:
        """Formata finanças para prompt."""
        lines = []
        
        summary = finance.get("summary", {})
        if summary:
            balance = summary.get("balance", 0)
            emoji = "🟢" if balance >= 0 else "🔴"
            lines.extend([
                f"💰 FINANÇAS ({finance.get('period', 'Período atual')})",
                f"  Receitas: R$ {summary.get('total_income', 0):,.2f}",
                f"  Gastos: R$ {summary.get('total_expenses', 0):,.2f}",
                f"  {emoji} Saldo: R$ {balance:,.2f}",
            ])
        
        top_expenses = finance.get("top_expenses", [])
        if top_expenses:
            lines.append("\n🔝 TOP GASTOS:")
            for i, t in enumerate(top_expenses[:5], 1):
                lines.append(
                    f"  {i}. R$ {t.get('amount', 0):,.2f} - "
                    f"{t.get('description', '')} ({t.get('category', '')})"
                )
        
        transactions = finance.get("transactions", [])
        if transactions:
            total = finance.get("transactions_total", len(transactions))
            lines.append(f"\n📋 TRANSAÇÕES ({len(transactions)} de {total}):")
            for t in transactions[:10]:
                emoji = "🟢" if t.get("type") == "income" else "🔴"
                lines.append(
                    f"  {emoji} {t.get('date', '')} | R$ {t.get('amount', 0):,.2f} | "
                    f"{t.get('description', '')} | {t.get('category', '')}"
                )
        
        previous = finance.get("previous_month", {})
        if previous and previous.get("summary"):
            prev_summary = previous["summary"]
            lines.append(f"\n📅 MÊS ANTERIOR ({previous.get('period', '')}):")
            lines.append(f"  Saldo: R$ {prev_summary.get('balance', 0):,.2f}")
        
        return "\n".join(lines) if lines else ""
    
    def _format_reminders(self, reminders: Dict[str, Any]) -> str:
        """Formata lembretes para prompt."""
        active = reminders.get("active", [])
        if not active:
            return ""
        
        lines = [
            f"⏰ LEMBRETES ({reminders.get('total_active', 0)} ativos)",
        ]
        
        for r in active[:5]:
            recurring = " 🔄" if r.get("is_recurring") else ""
            lines.append(f"  • {r.get('title', '')} - {r.get('scheduled_time', '')}{recurring}")
        
        return "\n".join(lines)
    
    def _format_meetings(self, meetings: Dict[str, Any]) -> str:
        """Formata reuniões para prompt."""
        recent = meetings.get("recent", [])
        if not recent:
            return ""
        
        lines = ["📅 REUNIÕES RECENTES:"]
        
        for m in recent[:3]:
            lines.append(f"  • {m.get('title', '')} - {m.get('date', '')}")
        
        return "\n".join(lines)
    
    def _format_goals(self, goals: Dict[str, Any]) -> str:
        """Formata metas para prompt."""
        active = goals.get("active", [])
        if not active:
            return ""
        
        lines = ["🎯 METAS:"]
        
        for g in active[:3]:
            lines.append(f"  • {g.get('content', '')}")
        
        return "\n".join(lines)
    
    def estimate_tokens(self, text: str) -> int:
        """Estima número de tokens (aproximado)."""
        return len(text) // 4


def compress_context(
    full_context: Dict[str, Any],
    intent: str = "general"
) -> str:
    """
    Função helper para comprimir e formatar contexto.
    
    Args:
        full_context: Contexto completo
        intent: Intenção detectada
        
    Returns:
        String formatada para prompt
    """
    compressor = ContextCompressor(intent)
    compressed = compressor.compress(full_context)
    return compressor.format_for_prompt(compressed)
