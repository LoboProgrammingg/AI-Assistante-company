# Tools para LangGraph com Pydantic schemas
from app.ai.tools.contact_tools import (
    ContactTools,
    criar_contato,
    listar_contatos,
)
from app.ai.tools.finance_tools import (
    FinanceTools,
    consultar_financas,
    deletar_transacao,
    registrar_transacao,
)
from app.ai.tools.meeting_tools import (
    MeetingTools,
    criar_reuniao,
    listar_reunioes,
)
from app.ai.tools.reminder_tools import (
    ReminderTools,
    criar_lembrete,
    deletar_lembrete,
    listar_lembretes,
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
