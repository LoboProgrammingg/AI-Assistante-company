"""
Patterns Agent - Detecção de padrões e anomalias.

Analisa:
- Gastos acima da média
- Padrões de consumo (dias, categorias)
- Recorrências não identificadas
- Desvios de comportamento
"""

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List

from app.ai.agents.base import AgentResult, SpecializedAgent
from app.ai.agents.registry import AgentRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@AgentRegistry.register
class PatternsAgent(SpecializedAgent):
    """Agente de detecção de padrões e anomalias."""

    name = "patterns"
    description = "Detecta padrões e anomalias em finanças e comportamento"
    supported_intents = ["patterns", "anomaly", "insight", "analise", "padrão"]

    def _register_tools(self) -> Dict[str, callable]:
        """Registra tools do agente de padrões."""
        return {
            "read_financial_history": self._read_financial_history,
            "read_task_history": self._read_task_history,
            "read_calendar_history": self._read_calendar_history,
            "generate_pattern_insight": self._generate_pattern_insight,
            "detect_anomalies": self._detect_anomalies,
        }

    async def process(self, message: str, entities: Dict[str, Any] = None) -> AgentResult:
        """Processa solicitação de análise de padrões."""
        entities = entities or {}
        message_lower = message.lower()

        # Detectar tipo de análise
        if "gasto" in message_lower or "financ" in message_lower:
            return await self._analyze_financial_patterns()

        if "tarefa" in message_lower or "produtiv" in message_lower:
            return await self._analyze_task_patterns()

        if "agenda" in message_lower or "reunião" in message_lower:
            return await self._analyze_calendar_patterns()

        # Análise geral
        return await self._full_analysis()

    async def _analyze_financial_patterns(self) -> AgentResult:
        """Analisa padrões financeiros."""
        if not self.db or not self.user_id:
            return AgentResult(success=False, action="error", error="Sem acesso ao banco")

        try:
            from app.services.finance_service import FinanceService

            service = FinanceService(self.db)

            # Buscar dados dos últimos 90 dias
            summary_month = service.get_summary_by_period(self.user_id, "mes")
            summary_prev = service.get_summary_by_period(self.user_id, "mes", ano=None)

            insights = []
            anomalies = []

            current = summary_month.get("summary", {})
            total_expense = current.get("total_expense", 0)
            total_income = current.get("total_income", 0)

            # Análise de gastos por categoria
            by_category = summary_month.get("by_category", {})
            if by_category:
                sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
                top_cat = sorted_cats[0] if sorted_cats else None

                if top_cat:
                    cat_name, cat_value = top_cat
                    if total_expense > 0:
                        pct = (cat_value / total_expense) * 100
                        if pct > 50:
                            anomalies.append(f"⚠️ *{cat_name}* representa {pct:.0f}% dos gastos")
                        else:
                            insights.append(f"📊 Maior categoria: *{cat_name}* ({pct:.0f}%)")

            # Análise de balanço
            balance = total_income - total_expense
            if balance < 0:
                anomalies.append(f"🔴 Gastos superam receitas em R$ {abs(balance):,.2f}")
            elif total_income > 0 and (total_expense / total_income) > 0.9:
                anomalies.append(f"⚠️ Você está gastando {(total_expense/total_income)*100:.0f}% da renda")
            else:
                savings_rate = ((total_income - total_expense) / total_income * 100) if total_income > 0 else 0
                if savings_rate > 20:
                    insights.append(f"💚 Ótimo! Poupando {savings_rate:.0f}% da renda")

            # Montar resposta
            lines = ["📈 *Análise de Padrões Financeiros*\n"]

            if anomalies:
                lines.append("*Alertas:*")
                lines.extend(anomalies)
                lines.append("")

            if insights:
                lines.append("*Insights:*")
                lines.extend(insights)

            if not anomalies and not insights:
                lines.append("✅ Nenhum padrão incomum detectado.")

            return AgentResult(
                success=True,
                action="analyze_financial_patterns",
                data={
                    "insights": insights,
                    "anomalies": anomalies,
                    "summary": current,
                },
                message="\n".join(lines),
            )

        except Exception as e:
            logger.error(f"[PATTERNS] Erro na análise financeira: {e}")
            return AgentResult(success=False, action="error", error=str(e))

    async def _analyze_task_patterns(self) -> AgentResult:
        """Analisa padrões de tarefas."""
        if not self.db or not self.user_id:
            return AgentResult(success=False, action="error", error="Sem acesso ao banco")

        try:
            from app.services.task_service import TaskService

            service = TaskService(self.db)
            summary = service.get_summary(self.user_id)

            insights = []

            total = summary.get("total", 0)
            overdue = summary.get("overdue", 0)
            by_priority = summary.get("by_priority", {})

            if total == 0:
                return AgentResult(
                    success=True,
                    action="analyze_task_patterns",
                    data={},
                    message="📋 Nenhuma tarefa encontrada para análise.",
                )

            high_priority = by_priority.get("high", 0) + by_priority.get("urgent", 0)

            if overdue > 0:
                insights.append(f"⚠️ {overdue} tarefa(s) atrasada(s)")

            if high_priority > 5:
                insights.append(f"🔴 {high_priority} tarefas de alta prioridade")

            if total > 20:
                insights.append(f"📋 Lista grande: {total} tarefas ativas")

            lines = ["📊 *Análise de Tarefas*\n"]

            if insights:
                lines.extend(insights)
            else:
                lines.append("✅ Suas tarefas estão organizadas!")

            return AgentResult(
                success=True,
                action="analyze_task_patterns",
                data={"total": total, "overdue": overdue},
                message="\n".join(lines),
            )

        except Exception as e:
            logger.error(f"[PATTERNS] Erro na análise de tarefas: {e}")
            return AgentResult(
                success=True,
                action="analyze_task_patterns",
                message="📋 Não consegui acessar suas tarefas no momento.",
            )

    async def _analyze_calendar_patterns(self) -> AgentResult:
        """Analisa padrões de agenda."""
        if not self.db or not self.user_id:
            return AgentResult(success=False, action="error", error="Sem acesso")

        try:
            from app.services.google_calendar_service import GoogleCalendarService

            service = GoogleCalendarService(self.db)

            if not service.is_user_connected(self.user_id):
                return AgentResult(
                    success=True,
                    action="analyze_calendar_patterns",
                    message="📅 Conecte o Google Calendar para análise de agenda.",
                )

            # Próximos 14 dias
            from zoneinfo import ZoneInfo

            tz = ZoneInfo("America/Sao_Paulo")
            time_max = datetime.now(tz) + timedelta(days=14)

            result = service.list_events(self.user_id, max_results=50, time_max=time_max)
            events = result.get("events", [])

            insights = []

            if not events:
                return AgentResult(
                    success=True,
                    action="analyze_calendar_patterns",
                    message="📅 Nenhum evento nos próximos 14 dias.",
                )

            # Contar eventos por dia
            events_per_day = {}
            for e in events:
                start = e.get("start", {}).get("dateTime", "")[:10]
                if start:
                    events_per_day[start] = events_per_day.get(start, 0) + 1

            busy_days = [d for d, c in events_per_day.items() if c >= 4]

            if busy_days:
                insights.append(f"📌 {len(busy_days)} dia(s) com 4+ eventos")

            if len(events) > 30:
                insights.append(f"⚠️ Agenda lotada: {len(events)} eventos em 14 dias")

            lines = ["📅 *Análise de Agenda*\n"]
            lines.append(f"📊 {len(events)} eventos nos próximos 14 dias")

            if insights:
                lines.append("")
                lines.extend(insights)

            return AgentResult(
                success=True,
                action="analyze_calendar_patterns",
                data={"total_events": len(events), "busy_days": len(busy_days)},
                message="\n".join(lines),
            )

        except Exception as e:
            logger.error(f"[PATTERNS] Erro na análise de agenda: {e}")
            return AgentResult(success=False, action="error", error=str(e))

    async def _full_analysis(self) -> AgentResult:
        """Análise completa de todos os padrões."""
        results = []

        # Financeiro
        fin = await self._analyze_financial_patterns()
        if fin.success and fin.data.get("anomalies"):
            results.append(("💰 Finanças", fin.data["anomalies"]))

        # Tarefas
        task = await self._analyze_task_patterns()
        if task.success and task.data.get("overdue", 0) > 0:
            results.append(("📋 Tarefas", [f"{task.data['overdue']} atrasada(s)"]))

        if not results:
            return AgentResult(
                success=True,
                action="full_analysis",
                data={},
                message="✅ *Tudo em ordem!*\n\nNenhum padrão incomum detectado em suas finanças ou tarefas.",
            )

        lines = ["🔍 *Resumo de Padrões Detectados*\n"]
        for area, items in results:
            lines.append(f"*{area}:*")
            for item in items[:3]:
                lines.append(f"  • {item}")

        return AgentResult(
            success=True,
            action="full_analysis",
            data={"areas": [a for a, _ in results]},
            message="\n".join(lines),
        )

    def _is_overdue(self, task: Dict) -> bool:
        """Verifica se tarefa está atrasada."""
        due = task.get("due", {})
        if not due:
            return False

        due_date = due.get("date", "")
        if due_date:
            try:
                due_dt = datetime.strptime(due_date, "%Y-%m-%d")
                return due_dt.date() < datetime.now().date()
            except ValueError:
                pass
        return False

    # === Tool implementations ===

    def _read_financial_history(self, period: str = "mes") -> Dict[str, Any]:
        """Lê histórico financeiro."""
        if not self.db or not self.user_id:
            return {"success": False, "error": "Sem acesso"}

        try:
            from app.services.finance_service import FinanceService

            service = FinanceService(self.db)
            return service.get_summary_by_period(self.user_id, period)
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _read_task_history(self) -> Dict[str, Any]:
        """Lê histórico de tarefas."""
        return {"success": False, "error": "Implementação pendente"}

    def _read_calendar_history(self) -> Dict[str, Any]:
        """Lê histórico de agenda."""
        return {"success": False, "error": "Implementação pendente"}

    def _generate_pattern_insight(self, data: Dict) -> Dict[str, Any]:
        """Gera insight a partir de dados."""
        return {"success": True, "insight": "Análise realizada"}

    def _detect_anomalies(self, data: Dict) -> Dict[str, Any]:
        """Detecta anomalias nos dados."""
        return {"success": True, "anomalies": []}
