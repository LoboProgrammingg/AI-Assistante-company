"""
Advisor Agent - Consultor para decisões.

Funcionalidades:
- Simulações financeiras (comprar vs alugar, financiamento, etc)
- Projeções de gastos
- Análise de compromissos
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
class AdvisorAgent(SpecializedAgent):
    """Agente consultor para decisões."""

    name = "advisor"
    description = "Ajuda em decisões financeiras e pessoais"
    supported_intents = ["advisor", "conselho", "simular", "projeção", "decisão"]

    def _register_tools(self) -> Dict[str, callable]:
        """Registra tools do agente."""
        return {
            "simulate_scenario": self._simulate_scenario,
            "read_financial_state": self._read_financial_state,
            "read_commitments": self._read_commitments,
            "run_projection": self._run_projection,
        }

    async def process(self, message: str, entities: Dict[str, Any] = None) -> AgentResult:
        """Processa solicitação de consultoria."""
        entities = entities or {}
        message_lower = message.lower()

        # PRIORIDADE 1: Verificar ação específica das entities (do CognitiveNode)
        # Isso permite que o LLM determine a intenção corretamente
        action_hint = entities.get("action") or entities.get("action_type", "")

        if action_hint == "financial_state":
            return await self._handle_financial_state_with_analysis(message)

        if action_hint == "simulate_scenario":
            return await self._handle_simulation(message, entities)

        if action_hint == "run_projection":
            return await self._handle_projection(message, entities)

        # PRIORIDADE 2: Pattern matching por palavras-chave
        # Simulação financeira
        if any(k in message_lower for k in ["simular", "simulação", "se eu"]):
            return await self._handle_simulation(message, entities)

        # Projeção
        if any(k in message_lower for k in ["projeção", "projetar", "futuro", "daqui"]):
            return await self._handle_projection(message, entities)

        # Estado financeiro / Análise
        if any(k in message_lower for k in ["situação", "estado", "como estou", "analise", "análise", "finanças", "financas", "baseando"]):
            return await self._handle_financial_state_with_analysis(message)

        # Compromissos
        if any(k in message_lower for k in ["compromisso", "obrigação", "pendência"]):
            return await self._handle_commitments()

        # FALLBACK: Se chegou aqui com intent advisor, fazer análise financeira
        return await self._handle_financial_state_with_analysis(message)

    async def _handle_simulation(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Simula cenário financeiro."""
        import re

        # Extrair valores mencionados
        amounts = re.findall(r"r?\$?\s*([\d.,]+)", message.lower())
        values = []
        for a in amounts:
            try:
                values.append(float(a.replace(".", "").replace(",", ".")))
            except ValueError:
                pass

        if not values:
            return AgentResult(
                success=True,
                action="simulate_scenario",
                data={},
                message='💭 Para simular um cenário, me diga os valores envolvidos.\n\nExemplo: _"Se eu gastar R$ 500 por mês com X, como fica meu orçamento?"_',
            )

        # Simulação básica
        amount = values[0]

        # Buscar contexto financeiro
        if self.db and self.user_id:
            try:
                from app.services.finance_service import FinanceService

                service = FinanceService(self.db)
                summary = service.get_summary_by_period(self.user_id, "mes")

                s = summary.get("summary", {})
                income = s.get("total_income", 0)
                expense = s.get("total_expense", 0)

                new_expense = expense + amount
                new_balance = income - new_expense

                lines = [f"📊 *Simulação: + R$ {amount:,.2f}/mês*\n"]
                lines.append(f"Receita atual: R$ {income:,.2f}")
                lines.append(f"Gastos atuais: R$ {expense:,.2f}")
                lines.append(f"Novo gasto: R$ {new_expense:,.2f}")
                lines.append("")

                if new_balance >= 0:
                    lines.append(f"💚 Saldo projetado: R$ {new_balance:,.2f}")
                    savings_rate = (new_balance / income * 100) if income > 0 else 0
                    lines.append(f"📈 Taxa de poupança: {savings_rate:.1f}%")
                else:
                    lines.append(f"🔴 *Déficit projetado:* R$ {abs(new_balance):,.2f}")
                    lines.append("⚠️ _Este gasto comprometeria seu orçamento._")

                return AgentResult(
                    success=True,
                    action="simulate_scenario",
                    data={"amount": amount, "new_balance": new_balance},
                    message="\n".join(lines),
                )

            except Exception as e:
                logger.error(f"[ADVISOR] Erro na simulação: {e}")

        # Simulação genérica
        annual = amount * 12
        return AgentResult(
            success=True,
            action="simulate_scenario",
            data={"amount": amount},
            message=f"📊 *Simulação:*\n\n• Mensal: R$ {amount:,.2f}\n• Anual: R$ {annual:,.2f}\n\n_Registre suas receitas para uma análise mais completa._",
        )

    async def _handle_projection(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Projeta cenário futuro."""
        if not self.db or not self.user_id:
            return AgentResult(success=False, action="error", error="Sem acesso")

        try:
            from app.services.finance_service import FinanceService

            service = FinanceService(self.db)

            summary = service.get_summary_by_period(self.user_id, "mes")
            s = summary.get("summary", {})

            income = s.get("total_income", 0)
            expense = s.get("total_expense", 0)
            monthly_savings = income - expense

            lines = ["📈 *Projeção Financeira*\n"]
            lines.append(f"Base: economia de R$ {monthly_savings:,.2f}/mês\n")

            projections = [
                ("3 meses", 3),
                ("6 meses", 6),
                ("1 ano", 12),
            ]

            for label, months in projections:
                projected = monthly_savings * months
                emoji = "💚" if projected > 0 else "🔴"
                lines.append(f"{emoji} {label}: R$ {projected:,.2f}")

            if monthly_savings < 0:
                lines.append("\n⚠️ _Com gastos maiores que receitas, a projeção é negativa._")

            return AgentResult(
                success=True,
                action="run_projection",
                data={"monthly_savings": monthly_savings},
                message="\n".join(lines),
            )

        except Exception as e:
            logger.error(f"[ADVISOR] Erro na projeção: {e}")
            return AgentResult(success=False, action="error", error=str(e))

    async def _handle_financial_state(self) -> AgentResult:
        """Mostra estado financeiro atual (versão simples)."""
        return await self._handle_financial_state_with_analysis("")

    async def _handle_financial_state_with_analysis(self, message: str) -> AgentResult:
        """Análise financeira completa com dados reais do banco."""
        if not self.db or not self.user_id:
            return AgentResult(success=False, action="error", error="Sem acesso ao banco")

        try:
            from app.services.finance_service import FinanceService

            service = FinanceService(self.db)

            # Buscar dados do mês atual
            summary = service.get_summary_by_period(self.user_id, "mes")
            s = summary.get("summary", {})
            by_category = summary.get("by_category", [])

            income = s.get("total_income", 0)
            expense = s.get("total_expenses", s.get("total_expense", 0))
            balance = income - expense
            count = s.get("count", 0)

            # Buscar top gastos
            top_data = service.get_top_transactions(
                user_id=self.user_id,
                limit=5,
                tipo="expense",
                periodo="mes",
                ordenacao="maior",
            )
            top_expenses = top_data.get("transactions", [])

            # Construir análise
            lines = ["� *Análise Financeira - Janeiro 2026*\n"]

            # Resumo
            lines.append("*💰 Resumo do Mês:*")
            lines.append(f"📥 Receitas: R$ {income:,.2f}")
            lines.append(f"📤 Gastos: R$ {expense:,.2f}")

            if balance >= 0:
                lines.append(f"💚 Saldo: R$ {balance:,.2f}")
                if income > 0:
                    savings_rate = (balance / income) * 100
                    lines.append(f"📈 Taxa de poupança: {savings_rate:.1f}%")
            else:
                lines.append(f"🔴 *Déficit:* R$ {abs(balance):,.2f}")

            # Top 5 gastos
            if top_expenses:
                lines.append("\n*🔝 Maiores Gastos:*")
                for i, t in enumerate(top_expenses[:5], 1):
                    amount = t.get("amount", 0)
                    desc = t.get("description", "Sem descrição")[:25]
                    cat = t.get("category", "")
                    lines.append(f"{i}. R$ {amount:,.2f} - {desc}")

            # Gastos por categoria
            if by_category:
                expense_cats = [c for c in by_category if c.get("type") == "expense"][:5]
                if expense_cats:
                    lines.append("\n*📁 Por Categoria:*")
                    for cat in expense_cats:
                        cat_name = cat.get("category", "Outros")
                        cat_total = cat.get("total", 0)
                        lines.append(f"• {cat_name}: R$ {cat_total:,.2f}")

            # Observações
            lines.append(f"\n_{count} transações registradas_")

            # Insight
            if balance > 0 and income > 0:
                if balance / income > 0.3:
                    lines.append("\n✅ *Ótimo!* Você está economizando mais de 30% da renda.")
                elif balance / income > 0.1:
                    lines.append("\n👍 Você está no caminho certo, economizando parte da renda.")
            elif balance < 0:
                lines.append("\n⚠️ *Atenção:* Seus gastos superam suas receitas este mês.")

            return AgentResult(
                success=True,
                action="financial_state",
                data={
                    "income": income,
                    "expense": expense,
                    "balance": balance,
                    "count": count,
                    "top_expenses": top_expenses,
                },
                message="\n".join(lines),
            )

        except Exception as e:
            logger.error(f"[ADVISOR] Erro na análise financeira: {e}")
            return AgentResult(success=False, action="error", error=str(e))

    async def _handle_commitments(self) -> AgentResult:
        """Lista compromissos pendentes."""
        if not self.db or not self.user_id:
            return AgentResult(success=False, action="error", error="Sem acesso")

        try:
            from app.services.reminder_service import ReminderService

            service = ReminderService(self.db)

            reminders, total = service.list_by_user(self.user_id, status="active", limit=10)

            if not reminders:
                return AgentResult(
                    success=True,
                    action="read_commitments",
                    data={"commitments": []},
                    message="✅ Você não tem compromissos pendentes registrados.",
                )

            lines = ["📋 *Compromissos Pendentes*\n"]
            for r in reminders[:10]:
                time_str = r.scheduled_time.strftime("%d/%m %H:%M") if r.scheduled_time else ""
                lines.append(f"• {r.title} - {time_str}")

            if total > 10:
                lines.append(f"\n_+{total - 10} outros_")

            return AgentResult(
                success=True,
                action="read_commitments",
                data={"count": total},
                message="\n".join(lines),
            )

        except Exception as e:
            return AgentResult(success=False, action="error", error=str(e))

    async def _handle_advice(self, message: str) -> AgentResult:
        """Dá conselho geral."""
        lines = [
            "🧠 *Consultoria Financeira*\n",
            "Posso ajudar você a:",
            '• Simular cenários (_"se eu gastar X..."_)',
            "• Ver projeções futuras",
            "• Analisar sua situação atual",
            "• Listar compromissos\n",
            "_O que você gostaria de saber?_",
        ]

        return AgentResult(
            success=True,
            action="advice",
            data={},
            message="\n".join(lines),
        )

    # === Tool implementations ===

    def _simulate_scenario(self, params: Dict) -> Dict[str, Any]:
        return {"success": False, "error": "Use process()"}

    def _read_financial_state(self) -> Dict[str, Any]:
        return {"success": False, "error": "Use process()"}

    def _read_commitments(self) -> Dict[str, Any]:
        return {"success": False, "error": "Use process()"}

    def _run_projection(self, months: int = 12) -> Dict[str, Any]:
        return {"success": False, "error": "Use process()"}
