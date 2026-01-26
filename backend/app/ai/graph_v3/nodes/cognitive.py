"""
Cognitive Node - Classificação + Extração em uma chamada LLM.

Responsabilidade ÚNICA:
1. Classifica intenção
2. Extrai entidades/slots
3. Decide a ação a executar

Usa Gemini Flash com prompt otimizado para JSON estruturado.
"""

import json
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from app.ai.datetime_utils import get_datetime_context
from app.ai.graph_v3.state import ActionType, ExtractedAction, IRISStateV3

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


COGNITIVE_PROMPT = '''Analise a mensagem e retorne JSON.

DATA/HORA: {datetime_context}
CONTEXTO: {context_prompt}

MENSAGEM: "{message}"

REGRAS DE CLASSIFICAÇÃO:

1. FINANCE - Dinheiro:
   - "gastei X", "paguei X", "comprei X", "adicione que gastei X", "registre gasto de X", "gasto de X com Y" → create_finance (tipo=expense)
   - "recebi X", "ganhei X", "salário" → create_finance (tipo=income)
   - "quanto gastei", "meus gastos", "quais foram os gastos", "gastos esse mês", "despesas do mês" → query_finance
   - "delete o gasto", "apaga X" → delete_finance
   - "mude o valor para" → update_finance

2. REMINDER - Lembretes pessoais:
   - "me lembra", "lembrete", "avisa" → create_reminder
   - "meus lembretes" → list_reminders
   - "delete lembrete" → delete_reminder
   - "mude o horário do lembrete" → update_reminder

3. MEETING/CALENDAR - Eventos e reuniões:
   - "agenda reunião", "marca evento", "aula" → create_event
   - "minha agenda", "próximos eventos" → list_events
   - "estou livre às 14h?" → check_availability
   - "salva reunião no banco" → create_meeting (banco local)

4. CONTACT - Contatos:
   - "salva contato", "adiciona X número Y" → create_contact
   - "meus contatos" → list_contacts
   - "delete contato" → delete_contact
   - "mude o telefone do" → update_contact

5. MESSAGE - Mensagens agendadas:
   - "envia mensagem às 10h", "agenda msg" → schedule_message
   - "mensagens agendadas" → list_scheduled_messages

6. TODOIST - Tarefas:
   - "anota tarefa", "cria tarefa", "add no todoist" → create_todoist_task
   - "minhas tarefas" → list_todoist_tasks
   - "terminei a tarefa", "conclui tarefa" → complete_todoist_task
   - "delete tarefa" → delete_todoist_task
   - "mude o prazo da tarefa" → update_todoist_task
   - "tarefas urgentes" → check_todoist_alerts

7. SEARCH - Pesquisas e integrações:
   - "pesquisa sobre", "busca" → web_search
   - "notícias sobre" → search_news
   - "cotação PETR4", "ação da" → get_stock
   - "bitcoin", "ethereum" → get_crypto
   - "clima em", "tempo em" → get_weather

8. TRANSCRIPTION - Textos longos de reunião:
   - Texto >500 chars com diálogo → summarize_transcription

9. BILLS - Faturas e boletos (imagens/PDF):
   - Imagem de fatura/boleto → extract_invoice
   - "faturas pendentes" → list_bills
   - Criar lembrete de pagamento → create_bill_reminder

10. MEMORY - Preferências e memórias:
    - "gosto de X", "não gosto de Y" → save_preference
    - "o que você sabe sobre mim" → read_memory
    - "esquece que eu" → delete_memory

11. PATTERNS - Análise de padrões:
    - "análise dos meus gastos" → analyze_patterns
    - "padrões financeiros" → analyze_patterns
    - "anomalias" → detect_anomalies

12. GOALS - Metas pessoais/financeiras:
    - "quero economizar X", "meta de juntar X", "adicionar meta", "quero juntar X" → create_goal
    - "minhas metas" → list_goals
    - "progresso da meta" → goal_progress

13. SUBSCRIPTIONS - Assinaturas:
    - "minhas assinaturas" → list_subscriptions
    - "quanto gasto com streaming" → analyze_subscriptions

14. ADVISOR - Consultoria:
    - "simular cenário" → simulate_scenario
    - "projeção financeira" → run_projection
    - "situação financeira" → financial_state

15. HEALTH - Organização de saúde:
    - "lembrete de remédio" → create_health_reminder
    - "agenda de saúde" → health_schedule
    - (NÃO diagnostica ou sugere tratamentos)

16. GENERAL - Conversa/perguntas:
    - Saudações simples → direct_response
    - Perguntas complexas → needs_llm_response

EXTRAIA entidades relevantes:
- Finance: valor, descricao, categoria, tipo, data
- Reminder: titulo, horario (YYYY-MM-DD HH:MM), descricao
- Meeting: titulo, data_hora, duracao_minutos, participantes
- Contact: nome, telefone, grupo
- Message: mensagem, data_hora, destinatario_nome, destinatario_telefone, grupo
- Todoist: content, due_string, priority

JSON OBRIGATÓRIO:
{{"intent": "finance|reminder|meeting|contact|message|todoist|search|bills|memory|patterns|goals|subscriptions|advisor|health|general|transcription", "action": "action_type", "confidence": 0.0-1.0, "entities": {{}}, "response_hint": "dica curta se for direct_response"}}'''


# Ações válidas
VALID_ACTIONS = {
    "create_finance", "query_finance", "delete_finance", "update_finance",
    "create_reminder", "list_reminders", "delete_reminder", "update_reminder",
    "create_meeting", "list_meetings",
    "create_event", "list_events", "check_availability",
    "create_contact", "list_contacts", "delete_contact", "update_contact",
    "schedule_message", "list_scheduled_messages",
    "create_todoist_task", "list_todoist_tasks", "complete_todoist_task",
    "update_todoist_task", "delete_todoist_task", "check_todoist_alerts",
    "web_search", "search_news", "get_stock", "get_crypto", "get_weather",
    "summarize_transcription",
    # Bills Agent
    "extract_invoice", "list_bills", "create_bill_reminder",
    # Memory Agent
    "save_preference", "read_memory", "delete_memory",
    # Patterns Agent
    "analyze_patterns", "detect_anomalies",
    # Goals Agent
    "create_goal", "list_goals", "goal_progress",
    # Subscriptions Agent
    "list_subscriptions", "analyze_subscriptions",
    # Advisor Agent
    "simulate_scenario", "run_projection", "financial_state",
    # Health Agent
    "create_health_reminder", "health_schedule",
    # Respostas
    "direct_response", "needs_llm_response",
    "none",
}

# Ações padrão por intent
DEFAULT_ACTIONS = {
    "finance": "query_finance",
    "reminder": "list_reminders",
    "meeting": "list_events",
    "calendar": "list_events",
    "contact": "list_contacts",
    "message": "list_scheduled_messages",
    "todoist": "list_todoist_tasks",
    "search": "web_search",
    "transcription": "summarize_transcription",
    "bills": "extract_invoice",
    "memory": "read_memory",
    "patterns": "analyze_patterns",
    "goals": "list_goals",
    "subscriptions": "list_subscriptions",
    "advisor": "financial_state",
    "health": "health_schedule",
    "general": "needs_llm_response",
}

# Ações que precisam de confirmação
DANGEROUS_ACTIONS = {
    "delete_finance", "delete_reminder", "delete_contact",
    "schedule_message",
}


class CognitiveNode:
    """Nó cognitivo - classifica, extrai e decide em UMA chamada LLM."""
    
    def __init__(self, llm_fast: "ChatGoogleGenerativeAI"):
        self.llm_fast = llm_fast
    
    def process(self, state: IRISStateV3) -> Dict[str, Any]:
        """Processa mensagem: classifica + extrai + decide."""
        last_message = state["messages"][-1]
        message_content = last_message.content
        
        # 1. Early exit para mensagens triviais
        early_result = self._check_early_exit(message_content)
        if early_result:
            logger.info(f"[COGNITIVE] ⚡ Early exit: {early_result['intent']}")
            return early_result
        
        # 2. Preparar prompt
        prompt = COGNITIVE_PROMPT.format(
            datetime_context=get_datetime_context(),
            context_prompt=state.get("context_prompt", "")[:500] or "Nenhum",
            message=message_content[:1000],
        )
        
        # 3. Chamar LLM Flash
        try:
            response = self.llm_fast.invoke(prompt)
            result = self._parse_response(response.content, message_content)
            
            logger.info(
                f"[COGNITIVE] 🧠 Intent: {result['intent']} | "
                f"Action: {result.get('action', {}).action_type if result.get('action') else 'none'} | "
                f"Confidence: {result.get('confidence', 0):.0%}"
            )
            return result
            
        except Exception as e:
            logger.error(f"[COGNITIVE] ❌ Erro: {e}")
            return self._fallback_result(message_content)
    
    def _check_early_exit(self, message: str) -> Optional[Dict[str, Any]]:
        """Verifica padrões triviais que não precisam de LLM."""
        msg_lower = message.lower().strip()
        
        # Saudações
        greetings = ["oi", "olá", "ola", "hey", "eai", "e aí", "bom dia", "boa tarde", "boa noite"]
        if msg_lower in greetings or (len(msg_lower) < 15 and any(g in msg_lower for g in greetings)):
            return {
                "intent": "general",
                "confidence": 0.95,
                "action": ExtractedAction(action_type="direct_response", params={"response_hint": "saudação"}, confidence=0.95),
                "entities": {},
                "early_exit": True,
                "response_template": self._get_greeting_response(),
            }
        
        # Agradecimentos
        thanks = ["obrigado", "obrigada", "valeu", "vlw", "thanks", "brigado"]
        if any(t in msg_lower for t in thanks) and len(msg_lower) < 30:
            return {
                "intent": "general",
                "confidence": 0.95,
                "action": ExtractedAction(action_type="direct_response", params={"response_hint": "agradecimento"}, confidence=0.95),
                "entities": {},
                "early_exit": True,
                "response_template": "Por nada! 😊 Estou aqui se precisar de algo mais.",
            }
        
        return None
    
    def _get_greeting_response(self) -> str:
        """Retorna saudação baseada no horário."""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "Bom dia! ☀️ Como posso ajudar?"
        elif 12 <= hour < 18:
            return "Boa tarde! 👋 Como posso ajudar?"
        return "Boa noite! 🌙 Como posso ajudar?"
    
    def _parse_response(self, response_content: str, original_message: str) -> Dict[str, Any]:
        """Parseia resposta JSON do LLM."""
        try:
            json_start = response_content.find("{")
            json_end = response_content.rfind("}") + 1
            
            if json_start >= 0 and json_end > json_start:
                parsed = json.loads(response_content[json_start:json_end])
                
                intent = parsed.get("intent", "general")
                action_type = parsed.get("action", "none")
                confidence = float(parsed.get("confidence", 0.5))
                entities = parsed.get("entities", {})
                response_hint = parsed.get("response_hint", "")
                
                if action_type not in VALID_ACTIONS:
                    action_type = DEFAULT_ACTIONS.get(intent, "needs_llm_response")
                
                action = ExtractedAction(
                    action_type=action_type,
                    params=entities,
                    confidence=confidence,
                    requires_confirmation=action_type in DANGEROUS_ACTIONS,
                )
                
                early_exit = action_type == "direct_response"
                
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "action": action,
                    "entities": entities,
                    "early_exit": early_exit,
                    "response_template": response_hint if early_exit else None,
                }
            
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[COGNITIVE] Parse error: {e}")
        
        return self._fallback_result(original_message)
    
    def _fallback_result(self, message: str) -> Dict[str, Any]:
        """Fallback seguro quando não consegue classificar."""
        return {
            "intent": "general",
            "confidence": 0.3,
            "action": ExtractedAction(action_type="needs_llm_response", params={"original_message": message[:500]}, confidence=0.3),
            "entities": {},
            "early_exit": False,
            "response_template": None,
        }
    
    @staticmethod
    def route_after_cognitive(state: IRISStateV3) -> str:
        """Determina próximo nó após classificação."""
        if state.get("error"):
            return "end"
        
        if state.get("early_exit") and state.get("response_template"):
            return "end"
        
        action = state.get("action")
        if not action:
            return "responder"
        
        response_only = {"direct_response", "needs_llm_response", "none"}
        if action.action_type in response_only:
            return "responder"
        
        return "executor"
