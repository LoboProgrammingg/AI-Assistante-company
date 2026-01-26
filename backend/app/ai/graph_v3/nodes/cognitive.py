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


COGNITIVE_PROMPT = '''Você é um analisador semântico avançado. Sua função é ENTENDER A INTENÇÃO REAL do usuário, não apenas detectar palavras-chave.

DATA/HORA ATUAL: {datetime_context}
CONTEXTO DO USUÁRIO: {context_prompt}

MENSAGEM DO USUÁRIO: "{message}"

## ANÁLISE SEMÂNTICA

Pense no que o usuário REALMENTE quer saber ou fazer. Exemplos de raciocínio:

- "quais foram os 5 maiores gastos esse mês" → Quer ver TOP 5 gastos ordenados do maior para menor
- "como estou para economizar 5000 este mês" → Quer análise de progresso em relação a uma META financeira
- "me mostra meus gastos com alimentação" → Quer transações FILTRADAS por categoria/termo
- "quanto já gastei esse mês" → Quer RESUMO financeiro do período
- "tenho algum compromisso amanhã" → Quer verificar LEMBRETES/AGENDA

## INTENTS DISPONÍVEIS

1. **finance** - Qualquer coisa sobre dinheiro, gastos, receitas, transações, economia, orçamento
2. **reminder** - Lembretes, avisos, notificações pessoais
3. **meeting/calendar** - Eventos, reuniões, agenda, compromissos
4. **contact** - Gerenciar contatos, telefones, grupos
5. **message** - Mensagens agendadas para enviar depois
6. **todoist** - Tarefas, to-do list, produtividade
7. **search** - Pesquisas web, notícias, cotações, clima
8. **goals** - Metas financeiras ou pessoais, objetivos de economia
9. **advisor** - Simulações, projeções, análises financeiras complexas
10. **patterns** - Análise de padrões de gastos, anomalias
11. **general** - Conversas casuais, perguntas gerais (ÚLTIMO RECURSO)

## AÇÕES POR INTENT

### FINANCE:
- create_finance: Registrar novo gasto/receita
- query_finance: Consultar, listar, resumir transações
- delete_finance: Apagar transação
- update_finance: Modificar transação

### GOALS:
- create_goal: Criar nova meta de economia
- list_goals: Ver metas existentes  
- goal_progress: Ver progresso em relação a uma meta (inclui análise financeira)

### ADVISOR:
- financial_state: Análise da situação financeira atual
- run_projection: Projeções futuras
- simulate_scenario: Simular cenários "e se"

## EXTRAÇÃO DE ENTIDADES

Para FINANCE extraia:
- periodo: "hoje", "semana", "mes", "ano", "mes_anterior", ou nome do mês
- limite: número de itens a retornar (ex: 5, 10)
- ordenacao: "maior" ou "menor"
- tipo_filtro: "expense" (gastos), "income" (receitas), ou "all"
- busca: termo para filtrar por descrição/categoria
- valor: valor monetário mencionado
- descricao: descrição da transação
- categoria: categoria da transação

Para GOALS extraia:
- meta_valor: valor objetivo (ex: 5000)
- meta_periodo: período da meta (ex: "mes", "ano")
- meta_tipo: tipo da meta ("economia", "reducao_gastos", "investimento")

## REGRAS CRÍTICAS

1. Se o usuário menciona QUALQUER coisa sobre dinheiro → intent=finance ou goals
2. Se menciona "economizar", "poupar", "juntar", "meta" → pode ser goals com goal_progress
3. Se pede "maiores", "top", "ranking" de gastos → query_finance com limite e ordenacao="maior"
4. Se pede análise, situação, como está → advisor ou goal_progress
5. NUNCA use general se houver QUALQUER indicação de intent específico
6. Sempre inclua a mensagem original em "original_message" nas entities

## OUTPUT OBRIGATÓRIO (JSON)

```json
{{
  "intent": "<intent>",
  "action": "<action_type>",
  "confidence": <0.0-1.0>,
  "entities": {{
    "original_message": "<mensagem do usuário>",
    // outras entidades extraídas
  }},
  "reasoning": "<breve explicação do seu raciocínio>"
}}
```

Analise a mensagem e retorne APENAS o JSON:'''


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
            
            logger.info(f"[COGNITIVE] Raw LLM response: {response.content[:500]}")
            
            result = self._parse_response(response.content, message_content)
            
            action = result.get('action')
            action_type = action.action_type if action else 'none'
            
            logger.info(
                f"[COGNITIVE] 🧠 Intent: {result['intent']} | "
                f"Action: {action_type} | "
                f"Confidence: {result.get('confidence', 0):.0%}"
            )
            logger.info(f"[COGNITIVE] Entities: {result.get('entities', {})}")
            
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
                reasoning = parsed.get("reasoning", "")
                
                # Sempre incluir mensagem original nas entities
                entities["original_message"] = original_message
                entities["reasoning"] = reasoning
                
                if action_type not in VALID_ACTIONS:
                    action_type = DEFAULT_ACTIONS.get(intent, "needs_llm_response")
                
                # goal_progress deve ir para GoalsAgent (não converter para financial_state)
                # O GoalsAgent já busca dados financeiros e gera análise completa
                
                action = ExtractedAction(
                    action_type=action_type,
                    params=entities,
                    confidence=confidence,
                    requires_confirmation=action_type in DANGEROUS_ACTIONS,
                )
                
                early_exit = action_type == "direct_response"
                
                logger.info(f"[COGNITIVE] Reasoning: {reasoning[:100]}...")
                
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "action": action,
                    "entities": entities,
                    "early_exit": early_exit,
                    "response_template": None,
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
