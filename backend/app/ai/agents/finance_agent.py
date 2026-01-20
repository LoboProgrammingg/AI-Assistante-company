"""
Agente especializado em finanças pessoais.
Utiliza prompts e constantes centralizados para fácil manutenção.
"""

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.ai.agents.base_agent import BaseAgent
from app.ai.agents.constants.finance_constants import FinanceConstants
from app.ai.agents.prompts.finance_prompts import FinancePrompts
from app.utils.timezone_helper import get_current_time_for_user

logger = logging.getLogger(__name__)


def get_user_finances(
    db: Session, user_id: int, start_date: date = None, end_date: date = None, category: str = None
) -> List[Dict]:
    """Consulta finanças reais do usuário no banco de dados."""
    from app.models import Finance, FinanceCategory

    query = db.query(Finance).filter(Finance.user_id == user_id)

    if start_date:
        query = query.filter(Finance.transaction_date >= start_date)
    if end_date:
        query = query.filter(Finance.transaction_date <= end_date)

    # Filtrar por categoria se especificada
    if category:
        cat = db.query(FinanceCategory).filter(FinanceCategory.name.ilike(f"%{category}%")).first()
        if cat:
            query = query.filter(Finance.category_id == cat.id)

    finances = query.order_by(Finance.transaction_date.desc()).limit(50).all()

    result = []
    for f in finances:
        cat_name = f.category.name if f.category else "Outros"
        result.append(
            {
                "id": f.id,
                "type": f.type.value if f.type else "expense",
                "amount": f.amount,
                "description": f.description,
                "category": cat_name,
                "date": f.transaction_date.strftime("%d/%m/%Y") if f.transaction_date else "",
                "tags": f.tags or [],
            }
        )
    return result


class FinanceAgent(BaseAgent):
    """Agente especializado em finanças pessoais."""

    def __init__(self):
        super().__init__(
            name="FinanceAgent",
            description="Especialista em registrar e analisar transações financeiras",
            temperature=0.3,
        )

    @property
    def system_prompt(self) -> str:
        return FinancePrompts.SYSTEM_PROMPT

    def process_sync(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa mensagem relacionada a finanças (versão síncrona)."""

        user_timezone = context.get("timezone", "America/Sao_Paulo")
        current_time = get_current_time_for_user(user_timezone)

        intent_prompt = FinancePrompts.get_intent_prompt(message)

        intent_response = self.invoke_llm_sync(intent_prompt)

        try:
            json_start = intent_response.find("{")
            json_end = intent_response.rfind("}") + 1
            intent_data = json.loads(intent_response[json_start:json_end])
        except:
            intent_data = {"intent": "clarify"}

        if intent_data.get("intent") == "register":
            return self._handle_register_sync(message, context, current_time)
        elif intent_data.get("intent") == "query":
            return self._handle_query_sync(message, context)
        elif intent_data.get("intent") == "delete":
            return self._handle_delete_sync(message, context)
        else:
            return {
                "response": "Poderia me dar mais detalhes? Você quer registrar um gasto/receita ou consultar seu histórico?",
                "entities": {},
                "next_action": "await_clarification",
                "confidence": 0.0,
            }

    async def process(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa mensagem relacionada a finanças (versão assíncrona - redireciona para síncrona)."""
        return self.process_sync(message, context)

    def _handle_register_sync(self, message: str, context: Dict[str, Any], current_time) -> Dict[str, Any]:
        """Processa registro de transação (versão síncrona). Suporta MÚLTIPLAS transações."""

        extraction_prompt = FinancePrompts.get_extraction_prompt(
            context=self.format_context(context),
            current_date=current_time.strftime("%d/%m/%Y"),
            current_year=current_time.year,
            current_month=current_time.month,
            message=message,
        )

        response = self.invoke_llm_sync(extraction_prompt)

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            extracted = json.loads(response[json_start:json_end])
            transactions = extracted.get("transactions", [])
        except:
            return {
                "response": "Não consegui entender os valores. Pode repetir? Ex: 'Gastei 50 reais com almoço e 30 com café'",
                "entities": {},
                "next_action": "await_clarification",
                "confidence": 0.0,
            }

        if not transactions:
            return {
                "response": "Não consegui identificar nenhuma transação. Pode repetir com os valores? Ex: 'Gastei 80 no café e 150 de gasolina'",
                "entities": {},
                "next_action": "await_clarification",
                "confidence": 0.0,
            }

        # Processar múltiplas transações
        if len(transactions) == 1:
            # Apenas uma transação - formato simples
            t = transactions[0]
            type_text = "Gasto" if t.get("type") == "expense" else "Receita"
            amount = t.get("amount", 0)
            category = t.get("category", "Outros")
            date_str = t.get("transaction_date", current_time.strftime("%Y-%m-%d"))

            try:
                date_formatted = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                date_formatted = date_str

            confirmation = f"✅ *{type_text} registrado!*\n\n💰 R$ {amount:.2f}\n📝 {t.get('description', message)}\n📁 Categoria: {category}\n📅 Data: {date_formatted}"

            return {
                "response": confirmation,
                "entities": {"finance": t},
                "next_action": "create_finance",
                "confidence": t.get("confidence", 0.8),
            }
        else:
            # Múltiplas transações
            confirmation_lines = [f"✅ *{len(transactions)} transações registradas!*\n"]

            total_expenses = 0
            total_income = 0

            for i, t in enumerate(transactions, 1):
                type_text = "📉 Gasto" if t.get("type") == "expense" else "📈 Receita"
                amount = t.get("amount", 0)
                category = t.get("category", "Outros")

                if t.get("type") == "expense":
                    total_expenses += amount
                else:
                    total_income += amount

                confirmation_lines.append(
                    f"{i}. {type_text}: R$ {amount:.2f} - {t.get('description', 'Sem descrição')} ({category})"
                )

            # Resumo
            confirmation_lines.append("")
            if total_expenses > 0:
                confirmation_lines.append(f"💸 Total gastos: R$ {total_expenses:.2f}")
            if total_income > 0:
                confirmation_lines.append(f"💰 Total receitas: R$ {total_income:.2f}")

            confirmation = "\n".join(confirmation_lines)

            return {
                "response": confirmation,
                "entities": {"finances": transactions},
                "next_action": "create_finances",
                "confidence": 0.9,
            }

    async def _handle_register(self, message: str, context: Dict[str, Any], current_time) -> Dict[str, Any]:
        """Processa registro de transação."""
        return self._handle_register_sync(message, context, current_time)

    def _detect_category_in_message(self, message: str) -> Optional[str]:
        """Detecta se a mensagem menciona uma categoria específica."""
        return FinanceConstants.detect_category_in_message(message)

    def _handle_query_sync(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa consulta financeira usando dados REAIS do banco (versão síncrona)."""

        db = context.get("db")
        user_id = context.get("user_id")
        user_timezone = context.get("timezone", "America/Sao_Paulo")
        current_time = get_current_time_for_user(user_timezone)
        today = current_time.date()

        if not db or not user_id:
            return {
                "response": "📊 Para consultar seu histórico financeiro, acesse a página de Finanças no menu.",
                "entities": {},
                "next_action": "query_finance",
                "confidence": 0.5,
            }

        message_lower = message.lower()

        # Detectar categoria mencionada
        category_filter = self._detect_category_in_message(message)

        # Determinar período baseado na mensagem
        start_date = today.replace(day=1)  # Default: mês atual
        end_date = today
        period_description = "este mês"

        if "hoje" in message_lower:
            start_date = today
            end_date = today
            period_description = f"hoje ({today.strftime('%d/%m/%Y')})"
        elif "semana" in message_lower:
            start_date = today - timedelta(days=7)
            period_description = "últimos 7 dias"
        elif "mês" in message_lower or "mes" in message_lower or "mensal" in message_lower:
            start_date = today.replace(day=1)
            period_description = "este mês"
        elif "ontem" in message_lower:
            start_date = today - timedelta(days=1)
            end_date = today - timedelta(days=1)
            period_description = f"ontem ({start_date.strftime('%d/%m/%Y')})"
        elif "ano" in message_lower:
            start_date = today.replace(month=1, day=1)
            period_description = "este ano"

        # Consultar dados REAIS do banco (com filtro de categoria se especificado)
        finances = get_user_finances(db, user_id, start_date, end_date, category_filter)

        # Montar descrição
        if category_filter:
            filter_desc = f" com **{category_filter}**"
        else:
            filter_desc = ""

        if not finances:
            if category_filter:
                return {
                    "response": f"📊 Você não tem gastos com **{category_filter}** {period_description}.",
                    "entities": {"query": {"period": period_description, "category": category_filter, "count": 0}},
                    "next_action": "query_finance",
                    "confidence": 1.0,
                }
            return {
                "response": f"📊 Você não tem transações registradas para {period_description}.",
                "entities": {"query": {"period": period_description, "count": 0}},
                "next_action": "query_finance",
                "confidence": 1.0,
            }

        # Calcular totais
        total_expense = sum(f["amount"] for f in finances if f["type"] == "expense")
        total_income = sum(f["amount"] for f in finances if f["type"] == "income")

        # Agrupar por categoria se não houver filtro
        if not category_filter:
            by_category = {}
            for f in finances:
                cat = f.get("category", "Outros")
                if cat not in by_category:
                    by_category[cat] = 0
                if f["type"] == "expense":
                    by_category[cat] += f["amount"]

        # Separar gastos e receitas
        expenses = [f for f in finances if f["type"] == "expense"]
        incomes = [f for f in finances if f["type"] == "income"]

        # Formatar resposta (WhatsApp usa *negrito* e _itálico_)
        if category_filter:
            response_lines = [f"📊 *Gastos com {category_filter}* ({period_description}):\n"]
        else:
            response_lines = [f"📊 *Suas transações {period_description}:*"]

        # Mostrar receitas primeiro
        if incomes and not category_filter:
            response_lines.append("")
            response_lines.append("*💰 Receitas:*")
            for i, f in enumerate(incomes[:5], 1):
                date_str = f.get("date", "")
                cat = f.get("category", "Outros")
                response_lines.append(f"{i}. 🟢 {f['description']} - R$ {f['amount']:.2f}")
                response_lines.append(f"    📁 {cat} | 📅 {date_str}")

        # Mostrar gastos
        if expenses:
            response_lines.append("")
            response_lines.append("*💸 Gastos:*")
            for i, f in enumerate(expenses[:10], 1):
                date_str = f.get("date", "")
                cat = f.get("category", "Outros")
                response_lines.append(f"{i}. 🔴 {f['description']} - R$ {f['amount']:.2f}")
                response_lines.append(f"    📁 {cat} | 📅 {date_str}")

        if len(finances) > 15:
            response_lines.append(f"\n_... e mais {len(finances) - 15} transações._")

        # Resumo
        response_lines.append("")
        response_lines.append("─" * 20)
        response_lines.append(f"*Total de gastos:* R$ {total_expense:.2f}")
        if total_income > 0:
            response_lines.append(f"*Total de receitas:* R$ {total_income:.2f}")
            saldo = total_income - total_expense
            emoji_saldo = "📈" if saldo >= 0 else "📉"
            response_lines.append(f"{emoji_saldo} *Saldo:* R$ {saldo:.2f}")

        # Resumo por categoria
        if by_category and not category_filter:
            response_lines.append("")
            response_lines.append("*Por categoria:*")
            sorted_cats = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
            for i, (cat, amount) in enumerate(sorted_cats[:5], 1):
                if amount > 0:
                    response_lines.append(f"{i}. {cat}: R$ {amount:.2f}")

        return {
            "response": "\n".join(response_lines),
            "entities": {
                "query": {
                    "period": period_description,
                    "total_expense": total_expense,
                    "total_income": total_income,
                    "count": len(finances),
                }
            },
            "next_action": "query_finance",
            "confidence": 1.0,
        }

    def _handle_delete_sync(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Processa solicitação de deleção de transação (versão síncrona)."""

        db = context.get("db")
        user_id = context.get("user_id")

        if not db or not user_id:
            return {
                "response": "❌ Para deletar transações, acesse a página de Finanças no menu.",
                "entities": {},
                "next_action": "none",
                "confidence": 0.5,
            }

        # Buscar transações recentes para identificar qual deletar
        from app.models import Finance

        recent = (
            db.query(Finance).filter(Finance.user_id == user_id).order_by(Finance.created_at.desc()).limit(10).all()
        )

        if not recent:
            return {
                "response": "📊 Você não tem transações registradas para deletar.",
                "entities": {},
                "next_action": "none",
                "confidence": 1.0,
            }

        # Usar IA para identificar qual transação deletar
        transactions_text = "\n".join(
            [
                f"ID {t.id}: {t.description} - R$ {t.amount:.2f} ({t.transaction_date.strftime('%d/%m/%Y')})"
                for t in recent
            ]
        )

        identify_prompt = FinancePrompts.get_delete_identification_prompt(
            message=message, transactions_text=transactions_text
        )

        response = self.invoke_llm_sync(identify_prompt)

        try:
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            identified = json.loads(response[json_start:json_end])
        except:
            identified = {"transaction_id": None}

        transaction_id = identified.get("transaction_id")

        if transaction_id:
            # Buscar a transação
            transaction = db.query(Finance).filter(Finance.id == transaction_id, Finance.user_id == user_id).first()

            if transaction:
                desc = transaction.description
                amount = transaction.amount

                return {
                    "response": f"🗑️ Transação encontrada: *{desc}* - R$ {amount:.2f}\n\nConfirma a exclusão? (sim/não)",
                    "entities": {"delete_finance": {"id": transaction_id, "description": desc, "amount": amount}},
                    "next_action": "confirm_delete_finance",
                    "confidence": 0.9,
                }

        # Listar transações para o usuário escolher
        options = "\n".join(
            [
                f"{i+1}. *{t.description}* - R$ {t.amount:.2f} ({t.transaction_date.strftime('%d/%m')})"
                for i, t in enumerate(recent[:5])
            ]
        )

        return {
            "response": f"🔍 Qual transação você quer deletar?\n\n{options}\n\nDiga qual você quer remover.",
            "entities": {"recent_finances": [{"id": t.id, "description": t.description} for t in recent[:5]]},
            "next_action": "await_delete_selection",
            "confidence": 0.7,
        }

    async def _handle_query(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper async para _handle_query_sync."""
        return self._handle_query_sync(message, context)

    async def _handle_delete(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Wrapper async para _handle_delete_sync."""
        return self._handle_delete_sync(message, context)

    def extract_entities(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extrai entidades de forma síncrona."""
        return {}
