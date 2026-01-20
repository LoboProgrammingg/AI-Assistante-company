# Tools para LangGraph com Pydantic schemas
from app.ai.tools.finance_tools import (
    registrar_transacao,
    consultar_financas,
    deletar_transacao,
    FinanceTools,
)
from app.ai.tools.reminder_tools import (
    criar_lembrete,
    listar_lembretes,
    deletar_lembrete,
    ReminderTools,
)
from app.ai.tools.meeting_tools import (
    criar_reuniao,
    listar_reunioes,
    MeetingTools,
)
from app.ai.tools.contact_tools import (
    criar_contato,
    listar_contatos,
    ContactTools,
)

__all__ = [
    # Finance
    "registrar_transacao",
    "consultar_financas",
    "deletar_transacao",
    "FinanceTools",
    # Reminder
    "criar_lembrete",
    "listar_lembretes",
    "deletar_lembrete",
    "ReminderTools",
    # Meeting
    "criar_reuniao",
    "listar_reunioes",
    "MeetingTools",
    # Contact
    "criar_contato",
    "listar_contatos",
    "ContactTools",
]
