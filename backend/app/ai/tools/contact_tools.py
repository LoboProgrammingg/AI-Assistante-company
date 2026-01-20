"""
Tools de Contatos com Pydantic Schemas para LangGraph.
"""

import logging
from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CriarContatoSchema(BaseModel):
    """Schema para criar contato."""

    nome: str = Field(description="Nome do contato", min_length=2, max_length=100)
    telefone: Optional[str] = Field(description="Número de telefone com DDD (ex: 11999999999)", default=None)
    email: Optional[str] = Field(description="Email do contato", default=None)
    grupo: Optional[str] = Field(description="Grupo do contato (ex: Família, Trabalho, Amigos)", default="Geral")


class ListarContatosSchema(BaseModel):
    """Schema para listar contatos."""

    grupo: Optional[str] = Field(description="Filtrar por grupo específico", default=None)
    busca: Optional[str] = Field(description="Termo de busca por nome", default=None)


@tool(args_schema=CriarContatoSchema)
def criar_contato(nome: str, telefone: Optional[str] = None, email: Optional[str] = None, grupo: str = "Geral") -> dict:
    """
    Adiciona um novo contato.
    Use quando o usuário quiser salvar um contato.
    """
    return {
        "action": "create_contact",
        "contact": {"name": nome, "phone": telefone, "email": email, "group": grupo},
        "status": "pending_execution",
    }


@tool(args_schema=ListarContatosSchema)
def listar_contatos(grupo: Optional[str] = None, busca: Optional[str] = None) -> dict:
    """
    Lista os contatos do usuário.
    Use quando o usuário quiser ver seus contatos.
    """
    return {"action": "list_contacts", "filters": {"grupo": grupo, "busca": busca}, "status": "pending_execution"}


class ContactTools:
    """Agregador de tools de contatos."""

    @staticmethod
    def get_all_tools() -> List:
        return [criar_contato, listar_contatos]

    @staticmethod
    def execute_tool_result(result: dict, db, user_id: int) -> dict:
        """Executa o resultado de uma tool no banco."""
        from app.services.contact_service import ContactService

        action = result.get("action")
        service = ContactService(db)

        if action == "create_contact":
            contact_data = result.get("contact", {})
            try:
                service.create_contact(user_id, contact_data)
                return {"success": True, "message": f"Contato '{contact_data['name']}' salvo!", "data": contact_data}
            except Exception as e:
                logger.error(f"Erro ao criar contato: {e}")
                return {"success": False, "error": str(e)}

        elif action == "list_contacts":
            filters = result.get("filters", {})
            try:
                contacts = service.get_contacts(user_id, filters.get("grupo"))
                return {"success": True, "data": contacts}
            except Exception as e:
                logger.error(f"Erro ao listar contatos: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Ação desconhecida"}
