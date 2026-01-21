"""
Tools de Finanças com Pydantic Schemas para LangGraph.
Seguindo melhores práticas: validação automática de tipos.
"""

import logging
from datetime import datetime
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Timezone padrão: Cuiabá-MT (UTC-4)
TIMEZONE_DEFAULT = ZoneInfo("America/Cuiaba")


def get_current_datetime() -> datetime:
    """Retorna data/hora atual no timezone de Cuiabá-MT."""
    return datetime.now(TIMEZONE_DEFAULT)


class RegistrarTransacaoSchema(BaseModel):
    """Schema para registrar transação financeira."""

    valor: float = Field(description="Valor da transação em reais (ex: 150.00)", gt=0, le=1000000)
    descricao: str = Field(
        description="Descrição da transação (ex: 'Almoço no restaurante')", min_length=2, max_length=200
    )
    categoria: str = Field(
        description="Categoria: Alimentação, Transporte, Moradia, Saúde, Educação, Lazer, Vestuário, Tecnologia, Serviços, Outros",
        default="Outros",
    )
    tipo: Literal["expense", "income"] = Field(
        description="'expense' para gasto/despesa, 'income' para receita/ganho", default="expense"
    )
    data: Optional[str] = Field(
        description="Data da transação (formato: YYYY-MM-DD). Se não informada, usa hoje.", default=None
    )


class ConsultarFinancasSchema(BaseModel):
    """Schema para consultar finanças."""

    periodo: str = Field(
        description="Período da consulta. Opções: 'hoje', 'semana', 'mes' (mês atual), 'ano', 'tudo'. "
        "OU nome do mês específico: 'janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', "
        "'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro'.",
        default="mes",
    )
    ano: Optional[int] = Field(
        description="Ano específico para consulta (ex: 2025, 2026). Se não informado, usa o ano atual.",
        default=None,
    )
    busca: Optional[str] = Field(
        description="Busca por descrição. Ex: 'uber', 'almoço', 'salário'. Filtra transações que contenham essa palavra.",
        default=None,
    )
    categoria: Optional[str] = Field(description="Filtrar por categoria específica (opcional)", default=None)
    tipo: Optional[Literal["expense", "income"]] = Field(
        description="Filtrar por tipo: expense ou income (opcional)", default=None
    )


class DeletarTransacaoSchema(BaseModel):
    """Schema para deletar transação."""

    descricao: str = Field(description="Descrição ou termo para encontrar a(s) transação(ões) a deletar (ex: 'uber', 'fralda')")
    data: Optional[str] = Field(description="Data: 'hoje' para apenas transações de hoje, ou None para todas", default="hoje")


class AtualizarTransacaoSchema(BaseModel):
    """Schema para atualizar/editar transação."""

    descricao_busca: str = Field(description="Descrição atual da transação para encontrá-la (ex: 'software', 'venda')")
    novo_valor: Optional[float] = Field(description="Novo valor da transação", default=None)
    nova_descricao: Optional[str] = Field(description="Nova descrição da transação", default=None)
    novo_tipo: Optional[Literal["expense", "income"]] = Field(description="Novo tipo: expense ou income", default=None)


@tool(args_schema=RegistrarTransacaoSchema)
def registrar_transacao(
    valor: float, descricao: str, categoria: str = "Outros", tipo: str = "expense", data: Optional[str] = None
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
            "date": data or get_current_datetime().strftime("%Y-%m-%d"),
        },
        "status": "pending_execution",
    }


@tool(args_schema=ConsultarFinancasSchema)
def consultar_financas(
    periodo: str = "mes", ano: Optional[int] = None, categoria: Optional[str] = None, tipo: Optional[str] = None
) -> dict:
    """
    Consulta o histórico financeiro do usuário.
    Use quando o usuário quiser ver seus gastos, receitas ou saldo.
    Suporta meses específicos como 'janeiro', 'fevereiro', etc.
    """
    return {
        "action": "query_finance",
        "filters": {"periodo": periodo, "ano": ano, "categoria": categoria, "tipo": tipo},
        "status": "pending_execution",
    }


@tool(args_schema=DeletarTransacaoSchema)
def deletar_transacao(descricao: str, data: Optional[str] = "hoje") -> dict:
    """
    Deleta transações financeiras por descrição.
    Use quando o usuário pedir para remover/deletar um gasto ou receita.
    Exemplos: "delete o uber", "remove a fralda", "apaga os gastos com almoço"
    """
    return {
        "action": "delete_finance",
        "filters": {"descricao": descricao, "data": data},
        "status": "pending_execution",
    }


@tool(args_schema=AtualizarTransacaoSchema)
def atualizar_transacao(
    descricao_busca: str,
    novo_valor: Optional[float] = None,
    nova_descricao: Optional[str] = None,
    novo_tipo: Optional[str] = None,
) -> dict:
    """
    Atualiza/edita uma transação financeira existente.
    Use quando o usuário quiser corrigir um valor, descrição ou tipo de uma transação já registrada.
    Exemplos: "na verdade eram 400 reais", "corrija o valor do software para 400"
    """
    updates = {}
    if novo_valor is not None:
        updates["amount"] = novo_valor
    if nova_descricao is not None:
        updates["description"] = nova_descricao
    if novo_tipo is not None:
        updates["type"] = novo_tipo
    
    return {
        "action": "update_finance",
        "filters": {"descricao": descricao_busca},
        "updates": updates,
        "status": "pending_execution",
    }


class FinanceTools:
    """Agregador de tools de finanças."""

    @staticmethod
    def get_all_tools() -> List:
        return [registrar_transacao, consultar_financas, deletar_transacao, atualizar_transacao]

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
                service.create_from_entities(user_id, finance_data)
                return {
                    "success": True,
                    "message": f"Transação de R${finance_data['amount']:.2f} registrada!",
                    "data": finance_data,
                }
            except Exception as e:
                logger.error(f"Erro ao criar transação: {e}")
                return {"success": False, "error": str(e)}

        elif action == "query_finance":
            filters = result.get("filters", {})
            try:
                periodo = filters.get("periodo", "mes")
                ano = filters.get("ano")
                busca = filters.get("busca")
                finances = service.get_summary_by_period(user_id, periodo, ano, busca)
                return {"success": True, "data": finances}
            except Exception as e:
                logger.error(f"Erro ao consultar finanças: {e}")
                return {"success": False, "error": str(e)}

        elif action == "delete_finance":
            filters = result.get("filters", {})
            try:
                delete_result = service.delete_by_filters(user_id, filters)
                count = delete_result.get("deleted_count", 0)
                items = delete_result.get("deleted_items", [])
                if count > 0:
                    return {"success": True, "message": f"{count} transação(ões) deletada(s): {', '.join(items)}"}
                return {"success": False, "message": "Nenhuma transação encontrada com essa descrição."}
            except Exception as e:
                logger.error(f"Erro ao deletar transação: {e}")
                return {"success": False, "error": str(e)}

        elif action == "update_finance":
            filters = result.get("filters", {})
            updates = result.get("updates", {})
            try:
                update_result = service.update_by_filters(user_id, filters, updates)
                if update_result.get("success"):
                    old = update_result["old"]
                    new = update_result["new"]
                    return {
                        "success": True,
                        "message": f"Transação atualizada: '{old['description']}' R${old['amount']:.2f} → '{new['description']}' R${new['amount']:.2f}",
                    }
                return {"success": False, "message": update_result.get("error", "Transação não encontrada")}
            except Exception as e:
                logger.error(f"Erro ao atualizar transação: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Ação desconhecida"}
