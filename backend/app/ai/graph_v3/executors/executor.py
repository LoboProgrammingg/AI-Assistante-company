"""
Executor Node - Orquestrador de executores por domínio.

Despacha ações para o executor específico.
"""

import logging
from typing import Any, Dict

from app.ai.graph_v3.executors.calendar import CalendarExecutor
from app.ai.graph_v3.executors.finance import FinanceExecutor
from app.ai.graph_v3.executors.integrations import IntegrationsExecutor
from app.ai.graph_v3.executors.meeting import MeetingExecutor
from app.ai.graph_v3.executors.message import MessageExecutor
from app.ai.graph_v3.executors.reminder import ReminderExecutor
from app.ai.graph_v3.executors.specialized import (
    SpecializedExecutor,
    is_specialized_action,
)
from app.ai.graph_v3.executors.task import TaskExecutor
from app.ai.graph_v3.state import ExecutionResult, ExtractedAction, IRISStateV3

logger = logging.getLogger(__name__)


# Mapeamento de ações para executores
ACTION_DISPATCHERS = {
    # Finanças
    "create_finance": FinanceExecutor.create,
    "query_finance": FinanceExecutor.query,
    "delete_finance": FinanceExecutor.delete,
    "update_finance": FinanceExecutor.update,
    # Lembretes
    "create_reminder": ReminderExecutor.create,
    "list_reminders": ReminderExecutor.list_all,
    "delete_reminder": ReminderExecutor.delete,
    "update_reminder": ReminderExecutor.update,
    # Reuniões (banco local)
    "create_meeting": MeetingExecutor.create,
    "list_meetings": MeetingExecutor.list_all,
    "summarize_transcription": MeetingExecutor.summarize_transcription,
    # Calendar (Google)
    "create_event": CalendarExecutor.create_event,
    "list_events": CalendarExecutor.list_events,
    "check_availability": CalendarExecutor.check_availability,
    # Mensagens agendadas
    "schedule_message": MessageExecutor.schedule,
    "list_scheduled_messages": MessageExecutor.list_all,
    # Tarefas
    "create_task": TaskExecutor.create,
    "list_tasks": TaskExecutor.list_all,
    "complete_task": TaskExecutor.complete,
    "delete_task": TaskExecutor.delete,
    "task_summary": TaskExecutor.get_summary,
    # Pesquisa e integrações
    "web_search": IntegrationsExecutor.web_search,
    "search_news": IntegrationsExecutor.search_news,
    "get_weather": IntegrationsExecutor.get_weather,
}


class ExecutorNode:
    """
    Executor de ações - despacha para o executor correto.

    Fluxo:
    1. Recebe action do cognitive_node
    2. Despacha para executor específico
    3. Retorna resultado com template (quando possível)
    """

    def execute(self, state: IRISStateV3) -> Dict[str, Any]:
        """Executa a ação extraída."""
        action = state.get("action")
        db = state.get("db")
        user_id = state.get("user_id")
        user_name = state.get("user_name", "")

        logger.info(f"[EXECUTOR] Action: {action.action_type if action else 'None'}")
        logger.info(f"[EXECUTOR] db={db is not None}, user_id={user_id}")

        if not action:
            return {
                "execution_result": ExecutionResult(
                    success=False,
                    action_type="none",
                    error="Nenhuma ação para executar",
                ),
            }

        try:
            result = self._dispatch(action, db, user_id, user_name)

            logger.info(
                f"[EXECUTOR] {'✅' if result.success else '❌'} "
                f"{action.action_type}: {result.data.get('message', result.error or 'OK')}"
            )

            return {
                "execution_result": result,
                "response_template": result.response_template,
                "early_exit": result.response_template is not None,
            }

        except Exception as e:
            logger.error(f"[EXECUTOR] ❌ Erro: {e}")
            return {
                "execution_result": ExecutionResult(
                    success=False,
                    action_type=action.action_type,
                    error=str(e),
                ),
            }

    def _dispatch(self, action: ExtractedAction, db: Any, user_id: int, user_name: str) -> ExecutionResult:
        """Despacha para o executor correto."""
        logger.info(f"[EXECUTOR] Dispatching: {action.action_type}")
        logger.info(f"[EXECUTOR] Is specialized: {is_specialized_action(action.action_type)}")

        # 1. Verificar se é ação de agente especializado
        if is_specialized_action(action.action_type):
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(
                    SpecializedExecutor.execute(action.action_type, action.params, db, user_id, user_name)
                )
            finally:
                loop.close()

        # 2. Verificar dispatcher tradicional
        dispatcher = ACTION_DISPATCHERS.get(action.action_type)

        if dispatcher:
            return dispatcher(action.params, db, user_id, user_name)

        # 3. Ação não suportada
        return ExecutionResult(
            success=False,
            action_type=action.action_type,
            error=f"Ação não implementada: {action.action_type}",
        )

    @staticmethod
    def route_after_executor(state: IRISStateV3) -> str:
        """Determina próximo nó após execução."""
        result = state.get("execution_result")

        # Se tem template pronto, vai direto para end
        if state.get("response_template") or (result and result.response_template):
            return "end"

        # Se falhou ou precisa de LLM, vai para responder
        return "responder"
