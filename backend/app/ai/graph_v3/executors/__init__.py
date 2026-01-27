"""
Executors - Executores de ações por domínio.

Cada executor é responsável por um domínio específico:
- finance.py: Transações financeiras
- reminder.py: Lembretes
- meeting.py: Reuniões (transcrição de áudio)
- calendar.py: Google Calendar
- message.py: Mensagens agendadas
- integrations.py: Pesquisas e APIs externas
"""

from app.ai.graph_v3.executors.executor import ExecutorNode

__all__ = ["ExecutorNode"]
