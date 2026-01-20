"""
Tools de Finanças com Pydantic Schemas para LangGraph.
Seguindo melhores práticas: validação automática de tipos.
"""
from typing import Optional, List, Literal
from datetime import date, datetime
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


class RegistrarTransacaoSchema(BaseModel):
    """Schema para registrar transação financeira."""
    valor: float = Field(
        description="Valor da transação em reais (ex: 150.00)",
        gt=0,
        le=1000000
    )
    descricao: str = Field(
        description="Descrição da transação (ex: 'Almoço no restaurante')",
        min_length=2,
        max_length=200
    )
    categoria: str = Field(
        description="Categoria: Alimentação, Transporte, Moradia, Saúde, Educação, Lazer, Vestuário, Tecnologia, Serviços, Outros",
        default="Outros"
    )
    tipo: Literal["expense", "income"] = Field(
        description="'expense' para gasto/despesa, 'income' para receita/ganho",
        default="expense"
    )
    data: Optional[str] = Field(
        description="Data da transação (formato: YYYY-MM-DD). Se não informada, usa hoje.",
        default=None
    )


class ConsultarFinancasSchema(BaseModel):
    """Schema para consultar finanças."""
    periodo: Literal["hoje", "semana", "mes", "ano", "tudo"] = Field(
        description="Período da consulta: hoje, semana, mes, ano ou tudo",
        default="mes"
    )
    categoria: Optional[str] = Field(
        description="Filtrar por categoria específica (opcional)",
        default=None
    )
    tipo: Optional[Literal["expense", "income"]] = Field(
        description="Filtrar por tipo: expense ou income (opcional)",
        default=None
    )


class DeletarTransacaoSchema(BaseModel):
    """Schema para deletar transação."""
    transacao_id: Optional[int] = Field(
        description="ID da transação a deletar (se conhecido)",
        default=None
    )
    descricao: Optional[str] = Field(
        description="Descrição parcial para encontrar a transação",
        default=None
    )
    ultima: bool = Field(
        description="Se True, deleta a última transação registrada",
        default=False
    )


@tool(args_schema=RegistrarTransacaoSchema)
def registrar_transacao(
    valor: float,
    descricao: str,
    categoria: str = "Outros",
    tipo: str = "expense",
    data: Optional[str] = None
) -> dict:
    """
    Registra uma transação financeira (gasto ou receita) no sistema.
    Use quando o usuário quiser anotar um gasto ou receita.
    """
    return {
        "action": "create_finance",
        "finance": {
            "amount": valor,
            "description": descricao,
            "category": categoria,
            "type": tipo,
            "date": data or datetime.now().strftime("%Y-%m-%d")
        },
        "status": "pending_execution"
    }


@tool(args_schema=ConsultarFinancasSchema)
def consultar_financas(
    periodo: str = "mes",
    categoria: Optional[str] = None,
    tipo: Optional[str] = None
) -> dict:
    """
    Consulta o histórico financeiro do usuário.
    Use quando o usuário quiser ver seus gastos, receitas ou saldo.
    """
    return {
        "action": "query_finance",
        "filters": {
            "periodo": periodo,
            "categoria": categoria,
            "tipo": tipo
        },
        "status": "pending_execution"
    }


@tool(args_schema=DeletarTransacaoSchema)
def deletar_transacao(
    transacao_id: Optional[int] = None,
    descricao: Optional[str] = None,
    ultima: bool = False
) -> dict:
    """
    Deleta uma transação financeira.
    Use quando o usuário quiser remover um registro de gasto ou receita.
    """
    return {
        "action": "delete_finance",
        "filters": {
            "id": transacao_id,
            "descricao": descricao,
            "ultima": ultima
        },
        "status": "pending_execution"
    }


class FinanceTools:
    """Agregador de tools de finanças."""
    
    @staticmethod
    def get_all_tools() -> List:
        return [registrar_transacao, consultar_financas, deletar_transacao]
    
    @staticmethod
    def execute_tool_result(result: dict, db, user_id: int) -> dict:
        """
        Executa o resultado de uma tool no banco de dados.
        Separação: LLM decide, este método executa.
        """
        from app.services.finance_service import FinanceService
        
        action = result.get("action")
        service = FinanceService(db)
        
        if action == "create_finance":
            finance_data = result.get("finance", {})
            try:
                created = service.create_from_entities(user_id, finance_data)
                return {
                    "success": True,
                    "message": f"Transação de R${finance_data['amount']:.2f} registrada!",
                    "data": finance_data
                }
            except Exception as e:
                logger.error(f"Erro ao criar transação: {e}")
                return {"success": False, "error": str(e)}
        
        elif action == "query_finance":
            filters = result.get("filters", {})
            try:
                finances = service.get_summary(user_id, filters.get("periodo", "mes"))
                return {
                    "success": True,
                    "data": finances
                }
            except Exception as e:
                logger.error(f"Erro ao consultar finanças: {e}")
                return {"success": False, "error": str(e)}
        
        elif action == "delete_finance":
            filters = result.get("filters", {})
            try:
                deleted = service.delete_by_filters(user_id, filters)
                return {
                    "success": True,
                    "message": "Transação deletada com sucesso!"
                }
            except Exception as e:
                logger.error(f"Erro ao deletar transação: {e}")
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Ação desconhecida"}
