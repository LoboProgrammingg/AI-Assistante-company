"""
ContextBuilder - Constrói contexto formatado para o LLM.

Transforma dados brutos do UserDataLoader em prompts otimizados
para que a IA tenha informação completa e relevante.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.context.user_data_loader import UserDataLoader

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Constrói contexto formatado para prompts do LLM."""

    def __init__(self, db: Session, user_id: int, user_name: str = ""):
        self.db = db
        self.user_id = user_id
        self.user_name = user_name
        self.data_loader = UserDataLoader(db, user_id)
        self._context: Optional[Dict[str, Any]] = None

    def build_full_context(self) -> str:
        """
        Constrói contexto completo formatado para o LLM.

        Returns:
            String formatada com todos os dados do usuário
        """
        self._context = self.data_loader.load_full_context()

        parts = [
            self._build_header(),
            self._build_finance_context(),
            self._build_reminders_context(),
            self._build_meetings_context(),
            self._build_goals_context(),
        ]

        return "\n\n".join(filter(None, parts))

    def build_finance_context(self, include_transactions: bool = True) -> str:
        """Constrói contexto financeiro detalhado."""
        if not self._context:
            self._context = self.data_loader.load_full_context()

        return self._build_finance_context(include_transactions)

    def get_raw_data(self) -> Dict[str, Any]:
        """Retorna dados brutos carregados."""
        if not self._context:
            self._context = self.data_loader.load_full_context()
        return self._context

    def _build_header(self) -> str:
        """Constrói cabeçalho do contexto."""
        now = datetime.now()

        lines = [
            "=" * 50,
            "📊 CONTEXTO COMPLETO DO USUÁRIO",
            "=" * 50,
            f"👤 Usuário: {self.user_name}" if self.user_name else "",
            f"📅 Data/Hora: {now.strftime('%d/%m/%Y %H:%M')}",
            f"📆 Dia da semana: {self._get_weekday_name(now.weekday())}",
        ]

        return "\n".join(filter(None, lines))

    def _build_finance_context(self, include_transactions: bool = True) -> str:
        """Constrói seção de finanças."""
        finance = self._context.get("finance", {})
        current = finance.get("current_month", {})
        previous = finance.get("previous_month", {})

        summary = current.get("summary", {})

        lines = [
            "💰 FINANÇAS",
            "-" * 30,
            "",
            f"📅 Período atual: {current.get('period', 'N/A')}",
            f"💵 Receitas: R$ {summary.get('total_income', 0):,.2f}",
            f"💸 Gastos: R$ {summary.get('total_expenses', 0):,.2f}",
            f"{'🟢' if summary.get('balance', 0) >= 0 else '🔴'} Saldo: R$ {summary.get('balance', 0):,.2f}",
            f"📈 Taxa de poupança: {summary.get('savings_rate', 0):.1f}%",
            f"📊 Total de transações: {summary.get('count', 0)}",
        ]

        # Top 5 maiores gastos
        top_expenses = finance.get("top_expenses", [])[:5]
        if top_expenses:
            lines.append("")
            lines.append("🔝 TOP 5 MAIORES GASTOS DO MÊS:")
            for i, t in enumerate(top_expenses, 1):
                lines.append(f"  {i}. R$ {t['amount']:,.2f} - {t['description']} ({t['category']}) - {t['date']}")

        # Gastos por categoria
        by_category = current.get("by_category", [])
        expense_cats = [c for c in by_category if c.get("type") == "expense"][:5]
        if expense_cats:
            lines.append("")
            lines.append("📁 GASTOS POR CATEGORIA:")
            for cat in expense_cats:
                lines.append(f"  • {cat['category']}: R$ {cat['total']:,.2f} ({cat['count']} transações)")

        # Mês anterior para comparação
        if previous:
            prev_summary = previous.get("summary", {})
            lines.append("")
            lines.append(f"📅 MÊS ANTERIOR ({previous.get('period', 'N/A')}):")
            lines.append(f"  💵 Receitas: R$ {prev_summary.get('total_income', 0):,.2f}")
            lines.append(f"  💸 Gastos: R$ {prev_summary.get('total_expenses', 0):,.2f}")
            lines.append(
                f"  {'🟢' if prev_summary.get('balance', 0) >= 0 else '🔴'} Saldo: R$ {prev_summary.get('balance', 0):,.2f}"
            )

        # Lista de transações (se solicitado)
        if include_transactions:
            transactions = current.get("transactions", [])[:20]
            if transactions:
                lines.append("")
                lines.append("📋 ÚLTIMAS 20 TRANSAÇÕES:")
                for t in transactions:
                    emoji = "🟢" if t["type"] == "income" else "🔴"
                    lines.append(
                        f"  {emoji} {t['date']} | R$ {t['amount']:,.2f} | {t['description']} | {t['category']}"
                    )

        return "\n".join(lines)

    def _build_reminders_context(self) -> str:
        """Constrói seção de lembretes."""
        reminders = self._context.get("reminders", {})
        active = reminders.get("active", [])

        if not active:
            return "⏰ LEMBRETES\n" + "-" * 30 + "\nNenhum lembrete ativo."

        lines = [
            "⏰ LEMBRETES",
            "-" * 30,
            f"Total ativos: {reminders.get('total_active', 0)}",
            f"Próximos 7 dias: {reminders.get('upcoming_count', 0)}",
            "",
        ]

        for r in active[:10]:
            time_str = r.get("scheduled_time", "Sem horário")
            recurring = " 🔄" if r.get("is_recurring") else ""
            lines.append(f"  • {r['title']} - {time_str}{recurring}")

        if len(active) > 10:
            lines.append(f"  ... e mais {len(active) - 10} lembretes")

        return "\n".join(lines)

    def _build_meetings_context(self) -> str:
        """Constrói seção de reuniões."""
        meetings = self._context.get("meetings", {})
        recent = meetings.get("recent", [])

        if not recent:
            return "📅 REUNIÕES\n" + "-" * 30 + "\nNenhuma reunião recente."

        lines = [
            "📅 REUNIÕES RECENTES",
            "-" * 30,
        ]

        for m in recent[:5]:
            date_str = m.get("date", "Sem data")
            lines.append(f"  • {m.get('title', 'Sem título')} - {date_str}")
            if m.get("summary"):
                lines.append(f"    Resumo: {m['summary'][:100]}...")

        return "\n".join(lines)

    def _build_goals_context(self) -> str:
        """Constrói seção de metas."""
        goals = self._context.get("goals", {})
        active = goals.get("active", [])

        if not active:
            return "🎯 METAS\n" + "-" * 30 + "\nNenhuma meta definida."

        lines = [
            "🎯 METAS ATIVAS",
            "-" * 30,
        ]

        for g in active:
            lines.append(f"  • {g.get('content', 'Meta sem descrição')}")

        return "\n".join(lines)

    def _get_weekday_name(self, weekday: int) -> str:
        """Retorna nome do dia da semana."""
        names = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
        return names[weekday] if 0 <= weekday <= 6 else "Desconhecido"

    def build_query_context(self, query_type: str, params: Dict[str, Any] = None) -> str:
        """
        Constrói contexto específico para um tipo de consulta.

        Args:
            query_type: Tipo de consulta (finance, reminders, etc)
            params: Parâmetros adicionais
        """
        params = params or {}

        if query_type == "finance":
            return self._build_finance_query_context(params)
        elif query_type == "reminders":
            return self._build_reminders_context()
        elif query_type == "meetings":
            return self._build_meetings_context()
        elif query_type == "goals":
            return self._build_goals_context()
        else:
            return self.build_full_context()

    def _build_finance_query_context(self, params: Dict[str, Any]) -> str:
        """Constrói contexto para consulta financeira específica."""
        period = params.get("period", "mes")
        search_term = params.get("search")
        limit = params.get("limit")
        order = params.get("order", "maior")
        filter_type = params.get("type")

        # Buscar dados do período
        data = self.data_loader.get_finance_for_period(period)
        transactions = data.get("transactions", [])

        # Filtrar por tipo se especificado
        if filter_type:
            transactions = [t for t in transactions if t["type"] == filter_type]

        # Buscar por termo se especificado
        if search_term:
            search_lower = search_term.lower()
            transactions = [
                t
                for t in transactions
                if search_lower in t["description"].lower() or search_lower in t["category"].lower()
            ]

        # Ordenar
        if order == "maior":
            transactions = sorted(transactions, key=lambda x: x["amount"], reverse=True)
        elif order == "menor":
            transactions = sorted(transactions, key=lambda x: x["amount"])

        # Limitar
        if limit:
            transactions = transactions[: int(limit)]

        # Construir resposta
        summary = self._calculate_filtered_summary(transactions)

        lines = [
            f"📊 DADOS FINANCEIROS - {data.get('period', 'Período')}",
            "-" * 40,
            f"Total de transações encontradas: {len(transactions)}",
            f"💵 Total receitas: R$ {summary['total_income']:,.2f}",
            f"💸 Total gastos: R$ {summary['total_expenses']:,.2f}",
            "",
            "📋 TRANSAÇÕES:",
        ]

        for i, t in enumerate(transactions[:20], 1):
            emoji = "🟢" if t["type"] == "income" else "🔴"
            lines.append(f"{i}. {emoji} R$ {t['amount']:,.2f} - {t['description']} ({t['category']}) - {t['date']}")

        if len(transactions) > 20:
            lines.append(f"... e mais {len(transactions) - 20} transações")

        return "\n".join(lines)

    def _calculate_filtered_summary(self, transactions: List[Dict]) -> Dict[str, float]:
        """Calcula resumo de transações filtradas."""
        total_income = sum(t["amount"] for t in transactions if t["type"] == "income")
        total_expenses = sum(t["amount"] for t in transactions if t["type"] == "expense")

        return {
            "total_income": total_income,
            "total_expenses": total_expenses,
            "total": total_income + total_expenses,
        }
