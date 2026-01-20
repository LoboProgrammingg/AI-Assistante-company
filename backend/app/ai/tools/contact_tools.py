"""
Tools de Contatos e Mensagens Agendadas com Pydantic Schemas para LangGraph.
"""

import logging
from typing import List, Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CriarContatoSchema(BaseModel):
    """Schema para criar contato."""

    nome: str = Field(description="Nome do contato", min_length=2, max_length=100)
    telefone: str = Field(description="Número de telefone com DDD (ex: 11999999999)")
    grupo: Optional[str] = Field(
        description="Grupo do contato (ex: Família, Trabalho, Funcionários, Clientes)", default="Geral"
    )
    notas: Optional[str] = Field(description="Observações sobre o contato", default=None)


class ListarContatosSchema(BaseModel):
    """Schema para listar contatos."""

    grupo: Optional[str] = Field(description="Filtrar por grupo específico", default=None)
    busca: Optional[str] = Field(description="Termo de busca por nome", default=None)


class AgendarMensagemSchema(BaseModel):
    """Schema para agendar mensagem."""

    mensagem: str = Field(description="Conteúdo da mensagem a ser enviada")
    data_hora: str = Field(description="Data e hora para envio (formato: YYYY-MM-DD HH:MM)")
    destinatario_nome: Optional[str] = Field(description="Nome do contato destinatário", default=None)
    destinatario_telefone: Optional[str] = Field(description="Telefone do destinatário (se não for contato)", default=None)
    grupo: Optional[str] = Field(description="Nome do grupo para enviar mensagem a todos os contatos", default=None)


class ListarMensagensAgendadasSchema(BaseModel):
    """Schema para listar mensagens agendadas."""

    status: Optional[str] = Field(description="Filtrar por status: pending, sent, failed, cancelled", default=None)


@tool(args_schema=CriarContatoSchema)
def criar_contato(nome: str, telefone: str, grupo: str = "Geral", notas: Optional[str] = None) -> dict:
    """
    Adiciona um novo contato.
    Use quando o usuário quiser salvar um contato com número de telefone.
    """
    return {
        "action": "create_contact",
        "contact": {"name": nome, "phone_number": telefone, "group_name": grupo, "notes": notas},
        "status": "pending_execution",
    }


@tool(args_schema=ListarContatosSchema)
def listar_contatos(grupo: Optional[str] = None, busca: Optional[str] = None) -> dict:
    """
    Lista os contatos do usuário.
    Use quando o usuário quiser ver seus contatos.
    """
    return {"action": "list_contacts", "filters": {"grupo": grupo, "busca": busca}, "status": "pending_execution"}


@tool(args_schema=AgendarMensagemSchema)
def agendar_mensagem(
    mensagem: str,
    data_hora: str,
    destinatario_nome: Optional[str] = None,
    destinatario_telefone: Optional[str] = None,
    grupo: Optional[str] = None,
) -> dict:
    """
    Agenda uma mensagem para ser enviada automaticamente.
    Use quando o usuário quiser enviar uma mensagem em uma data/hora específica.
    Pode ser para um contato, um número específico ou para um grupo inteiro.
    """
    return {
        "action": "schedule_message",
        "scheduled_message": {
            "message": mensagem,
            "scheduled_time": data_hora,
            "recipient_name": destinatario_nome,
            "recipient_phone": destinatario_telefone,
            "group_name": grupo,
        },
        "status": "pending_execution",
    }


@tool(args_schema=ListarMensagensAgendadasSchema)
def listar_mensagens_agendadas(status: Optional[str] = None) -> dict:
    """
    Lista as mensagens agendadas do usuário.
    Use quando o usuário quiser ver suas mensagens programadas.
    """
    return {"action": "list_scheduled_messages", "filters": {"status": status}, "status": "pending_execution"}


class ContactTools:
    """Agregador de tools de contatos e mensagens agendadas."""

    @staticmethod
    def get_all_tools() -> List:
        return [criar_contato, listar_contatos, agendar_mensagem, listar_mensagens_agendadas]

    @staticmethod
    def execute_tool_result(result: dict, db, user_id: int) -> dict:
        """Executa o resultado de uma tool no banco."""
        from app.services.contact_service import ContactService
        from app.services.scheduled_message_service import ScheduledMessageService

        action = result.get("action")

        if action == "create_contact":
            contact_data = result.get("contact", {})
            try:
                service = ContactService(db)
                contact = service.create_from_dict(user_id, contact_data)
                return {
                    "success": True,
                    "message": f"Contato '{contact.name}' salvo no grupo '{contact.group_name}'!",
                    "data": {"id": contact.id, "name": contact.name, "phone": contact.phone_number, "group": contact.group_name},
                }
            except Exception as e:
                logger.error(f"Erro ao criar contato: {e}")
                return {"success": False, "error": str(e)}

        elif action == "list_contacts":
            filters = result.get("filters", {})
            try:
                service = ContactService(db)
                result = service.list(user_id, group_name=filters.get("grupo"), search=filters.get("busca"))
                contacts = [
                    {"id": c.id, "name": c.name, "phone": c.phone_number, "group": c.group_name}
                    for c in result["items"]
                ]
                return {"success": True, "data": contacts, "total": result["total"]}
            except Exception as e:
                logger.error(f"Erro ao listar contatos: {e}")
                return {"success": False, "error": str(e)}

        elif action == "schedule_message":
            msg_data = result.get("scheduled_message", {})
            try:
                service = ScheduledMessageService(db)
                scheduled = service.create_from_entities(user_id, msg_data)
                return {
                    "success": True,
                    "message": f"Mensagem agendada para {scheduled.scheduled_time.strftime('%d/%m/%Y às %H:%M')}!",
                    "data": {
                        "id": scheduled.id,
                        "recipient": scheduled.recipient_name or scheduled.group_name or scheduled.recipient_phone,
                        "scheduled_time": scheduled.scheduled_time.isoformat(),
                    },
                }
            except Exception as e:
                logger.error(f"Erro ao agendar mensagem: {e}")
                return {"success": False, "error": str(e)}

        elif action == "list_scheduled_messages":
            filters = result.get("filters", {})
            try:
                service = ScheduledMessageService(db)
                messages = service.list(user_id, status=filters.get("status"))
                return {"success": True, "data": messages}
            except Exception as e:
                logger.error(f"Erro ao listar mensagens agendadas: {e}")
                return {"success": False, "error": str(e)}

        return {"success": False, "error": "Ação desconhecida"}
