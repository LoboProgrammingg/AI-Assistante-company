"""
Tools de Reuniões com Pydantic Schemas para LangGraph.
"""
from typing import Optional, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)


class CriarReuniaoSchema(BaseModel):
    """Schema para criar reunião."""
    titulo: str = Field(
        description="Título da reunião (ex: 'Reunião de alinhamento')",
        min_length=2,
        max_length=200
    )
    data_hora: str = Field(
        description="Data e hora da reunião (formato: YYYY-MM-DD HH:MM)"
    )
    participantes: Optional[List[str]] = Field(
        description="Lista de participantes (nomes ou contatos)",
        default=[]
    )
    duracao_minutos: int = Field(
        description="Duração em minutos",
        default=60,
        ge=15,
        le=480
    )
    local: Optional[str] = Field(
        description="Local ou link da reunião",
        default=None
    )


class ListarReunioesSchema(BaseModel):
    """Schema para listar reuniões."""
    periodo: str = Field(
        description="Período: hoje, amanha, semana, mes",
        default="semana"
    )


@tool(args_schema=CriarReuniaoSchema)
def criar_reuniao(
    titulo: str,
    data_hora: str,
    participantes: List[str] = [],
    duracao_minutos: int = 60,
    local: Optional[str] = None
) -> dict:
    """
    Agenda uma nova reunião.
    Use quando o usuário quiser marcar uma reunião ou compromisso.
    """
    return {
        "action": "create_meeting",
        "meeting": {
            "title": titulo,
            "scheduled_time": data_hora,
            "participants": participantes,
            "duration_minutes": duracao_minutos,
            "location": local
        },
        "status": "pending_execution"
    }


@tool(args_schema=ListarReunioesSchema)
def listar_reunioes(periodo: str = "semana") -> dict:
    """
    Lista as reuniões agendadas.
    Use quando o usuário quiser ver suas reuniões.
    """
    return {
        "action": "list_meetings",
        "filters": {"periodo": periodo},
        "status": "pending_execution"
    }


class MeetingTools:
    """Agregador de tools de reuniões."""
    
    @staticmethod
    def get_all_tools() -> List:
        return [criar_reuniao, listar_reunioes]
    
    @staticmethod
    def execute_tool_result(result: dict, db, user_id: int) -> dict:
        """Executa o resultado de uma tool no banco."""
        from app.services.meeting_service import MeetingService
        
        action = result.get("action")
        service = MeetingService(db)
        
        if action == "create_meeting":
            meeting_data = result.get("meeting", {})
            try:
                created = service.create_from_entities(user_id, meeting_data)
                return {
                    "success": True,
                    "message": f"Reunião '{meeting_data['title']}' agendada!",
                    "data": meeting_data
                }
            except Exception as e:
                logger.error(f"Erro ao criar reunião: {e}")
                return {"success": False, "error": str(e)}
        
        elif action == "list_meetings":
            try:
                meetings = service.get_upcoming(user_id)
                return {"success": True, "data": meetings}
            except Exception as e:
                logger.error(f"Erro ao listar reuniões: {e}")
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Ação desconhecida"}
