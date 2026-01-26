"""
Executors - Executores de ações por domínio.

Cada executor é responsável por um domínio específico:
- finance.py: Transações financeiras
- reminder.py: Lembretes
- meeting.py: Reuniões (banco local)
- calendar.py: Google Calendar
- contact.py: Contatos
- message.py: Mensagens agendadas
- todoist.py: Tarefas do Todoist
- integrations.py: Pesquisas e APIs externas
"""

from app.ai.graph_v3.executors.executor import ExecutorNode

__all__ = ["ExecutorNode"]
