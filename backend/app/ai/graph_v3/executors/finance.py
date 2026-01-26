"""
Finance Executor - Execução de ações financeiras.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.state import ExecutionResult

logger = logging.getLogger(__name__)


class FinanceExecutor:
    """Executor de ações financeiras."""
    
    @staticmethod
    def create(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Cria transação financeira."""
        from app.services.finance_service import FinanceService
        
        try:
            service = FinanceService(db)
            
            finance_data = {
                "amount": params.get("valor", params.get("amount", 0)),
                "description": params.get("descricao", params.get("description", "")),
                "category": params.get("categoria", params.get("category", "Outros")),
                "type": params.get("tipo", params.get("type", "expense")),
                "date": params.get("data", params.get("date")),
            }
            
            service.create_from_entities(user_id, finance_data)
            
            amount = finance_data["amount"]
            desc = finance_data["description"]
            tipo = "Gasto" if finance_data["type"] == "expense" else "Receita"
            
            template = f"✅ {tipo} registrado: *{desc}* - R$ {amount:.2f}"
            
            return ExecutionResult(
                success=True,
                action_type="create_finance",
                data={"finance": finance_data},
                response_template=template,
            )
        except Exception as e:
            logger.error(f"Erro ao criar transação: {e}")
            return ExecutionResult(success=False, action_type="create_finance", error=str(e))
    
    @staticmethod
    def query(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Consulta finanças."""
        from app.services.finance_service import FinanceService
        
        try:
            service = FinanceService(db)
            
            periodo = params.get("periodo", "mes")
            ano = params.get("ano")
            busca = params.get("busca")
            
            summary = service.get_summary_by_period(user_id, periodo, ano, busca)
            
            # Usar formatação diferente se for busca filtrada
            if busca and summary.get("transactions"):
                template = FinanceExecutor._format_filtered_transactions(summary, busca)
            else:
                template = FinanceExecutor._format_summary(summary, periodo)
            
            return ExecutionResult(
                success=True,
                action_type="query_finance",
                data=summary,
                response_template=template,
            )
        except Exception as e:
            logger.error(f"Erro ao consultar finanças: {e}")
            return ExecutionResult(success=False, action_type="query_finance", error=str(e))
    
    @staticmethod
    def _format_summary(summary: Dict, periodo: str) -> str:
        """Formata resumo financeiro."""
        s = summary.get("summary", {})
        
        # Compatibilidade: service retorna 'total_expenses' (plural)
        total_expense = s.get("total_expenses", s.get("total_expense", 0))
        total_income = s.get("total_income", 0)
        balance = s.get("balance", 0)
        count = s.get("count", 0)
        
        # Calcular count a partir de by_category se não vier direto
        if count == 0:
            by_category = summary.get("by_category", [])
            count = sum(cat.get("transactions_count", 0) for cat in by_category)
        
        # Se ainda não tem count mas tem valores, inferir que há transações
        if count == 0 and (total_expense > 0 or total_income > 0):
            count = 1  # Pelo menos 1
        
        periodo_text = {
            "hoje": "de hoje", "semana": "da semana", 
            "mes": "do mês", "ano": "do ano", "tudo": "totais"
        }.get(periodo, f"de {periodo}")
        
        if count == 0:
            return f"📊 Nenhuma transação encontrada {periodo_text}."
        
        emoji = "🟢" if balance >= 0 else "🔴"
        return f"""📊 *Resumo financeiro {periodo_text}*

💸 Gastos: R$ {total_expense:,.2f}
💰 Receitas: R$ {total_income:,.2f}
{emoji} Saldo: R$ {balance:,.2f}

_{count} transação(ões)_"""
    
    @staticmethod
    def _format_filtered_transactions(data: Dict, busca: str) -> str:
        """Formata transações filtradas por busca."""
        transactions = data.get("transactions", [])
        s = data.get("summary", {})
        
        count = len(transactions)
        total_expenses = s.get("total_expenses", 0)
        total_income = s.get("total_income", 0)
        
        if count == 0:
            return f"🔍 Nenhuma transação encontrada com *{busca}*."
        
        # Listar até 5 transações
        lines = [f"🔍 *Transações com '{busca}':*\n"]
        
        for t in transactions[:5]:
            emoji = "🟢" if t.get("type") == "income" else "🔴"
            amount = t.get("amount", 0)
            desc = t.get("description", "")[:30]
            date_str = t.get("date", "")[:10]
            lines.append(f"{emoji} R$ {amount:.2f} - {desc} ({date_str})")
        
        if count > 5:
            lines.append(f"\n_... e mais {count - 5} transação(ões)_")
        
        # Totais
        if total_expenses > 0 or total_income > 0:
            lines.append(f"\n💸 *Total gastos:* R$ {total_expenses:,.2f}")
            if total_income > 0:
                lines.append(f"💰 *Total receitas:* R$ {total_income:,.2f}")
        
        return "\n".join(lines)
    
    @staticmethod
    def delete(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Deleta transação financeira."""
        from app.services.finance_service import FinanceService
        
        try:
            service = FinanceService(db)
            result = service.delete_by_filters(user_id, params)
            
            count = result.get("deleted_count", 0)
            items = result.get("deleted_items", [])
            
            if count > 0:
                template = f"🗑️ Deletado: {', '.join(items[:3])}"
                if count > 3:
                    template += f" (+{count - 3})"
            else:
                template = "❌ Nenhuma transação encontrada."
            
            return ExecutionResult(success=count > 0, action_type="delete_finance", data=result, response_template=template)
        except Exception as e:
            return ExecutionResult(success=False, action_type="delete_finance", error=str(e))
    
    @staticmethod
    def update(params: Dict, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Atualiza transação financeira."""
        from app.services.finance_service import FinanceService
        
        try:
            service = FinanceService(db)
            
            filters = {"descricao": params.get("descricao_busca", params.get("descricao", ""))}
            updates = {}
            
            if params.get("novo_valor") or params.get("amount"):
                updates["amount"] = params.get("novo_valor", params.get("amount"))
            if params.get("nova_descricao") or params.get("description"):
                updates["description"] = params.get("nova_descricao", params.get("description"))
            if params.get("novo_tipo") or params.get("type"):
                updates["type"] = params.get("novo_tipo", params.get("type"))
            
            result = service.update_by_filters(user_id, filters, updates)
            
            if result.get("success"):
                template = "✏️ Transação atualizada!"
            else:
                template = f"❌ {result.get('error', 'Transação não encontrada')}"
            
            return ExecutionResult(success=result.get("success", False), action_type="update_finance", data=result, response_template=template)
        except Exception as e:
            return ExecutionResult(success=False, action_type="update_finance", error=str(e))
