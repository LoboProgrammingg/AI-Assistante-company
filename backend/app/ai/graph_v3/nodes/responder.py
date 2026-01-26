"""
Responder Node - Geração de respostas complexas via LLM Pro.

Responsabilidade:
- Respostas que precisam de raciocínio
- Processamento de resultados de pesquisa
- Conversas gerais que não são templates

Usa Gemini Pro apenas quando realmente necessário.
"""

import logging
from typing import TYPE_CHECKING, Any, Dict

from langchain_core.messages import AIMessage

from app.ai.datetime_utils import get_datetime_context
from app.ai.graph_v3.state import IRISStateV3

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


RESPONSE_PROMPT = '''Você é IRIS, assistente pessoal inteligente e amigável.

DATA/HORA: {datetime_context}
{user_context}

CONTEXTO DA INTERAÇÃO:
- Intenção: {intent}
- Ação executada: {action_type}
- Resultado: {execution_summary}

MENSAGEM DO USUÁRIO: "{user_message}"

{rag_context}

REGRAS:
1. Seja concisa e natural (estilo WhatsApp)
2. Use *negrito* para destaques, _itálico_ para ênfase
3. Se houve erro, explique de forma amigável
4. Responda DIRETAMENTE ao que foi perguntado
5. Não repita informações desnecessárias

Responda:'''


GENERAL_PROMPT = '''Você é IRIS, assistente pessoal inteligente, amigável e extremamente capaz.

📅 DATA/HORA: {datetime_context}
{user_context}

## VOCÊ É UMA IA COMPLETA

Você possui TODO o conhecimento de um modelo de linguagem avançado.
RESPONDA QUALQUER PERGUNTA usando seu conhecimento.

{rag_context}

MENSAGEM: "{user_message}"

REGRAS:
1. Seja natural e amigável (estilo WhatsApp)
2. Responda COMPLETAMENTE ao que foi perguntado
3. Use *negrito* e _itálico_ para formatação
4. Seja concisa mas não superficial

Responda:'''


class ResponderNode:
    """Gerador de respostas via LLM Pro."""
    
    def __init__(self, llm: "ChatGoogleGenerativeAI"):
        self.llm = llm
    
    def respond(self, state: IRISStateV3) -> Dict[str, Any]:
        """Gera resposta usando LLM Pro."""
        # Se já tem template, usar direto
        template = state.get("response_template")
        if template:
            logger.info("[RESPONDER] ⚡ Usando template existente")
            return {"messages": [AIMessage(content=template)]}
        
        # Verificar se é resposta geral ou com contexto de execução
        execution_result = state.get("execution_result")
        
        if execution_result and not execution_result.response_template:
            return self._respond_with_context(state)
        
        return self._respond_general(state)
    
    def _respond_with_context(self, state: IRISStateV3) -> Dict[str, Any]:
        """Gera resposta com contexto de execução."""
        user_message = state["messages"][-1].content if state["messages"] else ""
        user_name = state.get("user_name", "")
        
        prompt = RESPONSE_PROMPT.format(
            datetime_context=get_datetime_context(),
            user_context=f"Usuário: {user_name}" if user_name else "",
            intent=state.get("intent", "general"),
            action_type=state.get("action").action_type if state.get("action") else "none",
            execution_summary=self._summarize_execution(state),
            user_message=user_message[:500],
            rag_context=f"DOCUMENTOS RELEVANTES:\n{state.get('rag_context', '')[:1000]}" if state.get("rag_context") else "",
        )
        
        try:
            response = self.llm.invoke(prompt)
            logger.info(f"[RESPONDER] 💬 Resposta: {len(response.content)} chars")
            return {"messages": [AIMessage(content=response.content)]}
        except Exception as e:
            logger.error(f"[RESPONDER] ❌ Erro: {e}")
            return {"messages": [AIMessage(content="Desculpe, tive um problema. Pode tentar novamente?")]}
    
    def _respond_general(self, state: IRISStateV3) -> Dict[str, Any]:
        """Gera resposta para conversas gerais."""
        user_message = state["messages"][-1].content if state["messages"] else ""
        user_name = state.get("user_name", "")
        rag_context = state.get("rag_context", "")
        
        prompt = GENERAL_PROMPT.format(
            datetime_context=get_datetime_context(),
            user_context=f"👤 Usuário: {user_name}" if user_name else "",
            rag_context=f"CONTEXTO DOS DOCUMENTOS:\n{rag_context[:1500]}" if rag_context else "",
            user_message=user_message,
        )
        
        try:
            response = self.llm.invoke(prompt)
            return {"messages": [AIMessage(content=response.content)]}
        except Exception as e:
            logger.error(f"[RESPONDER] ❌ Erro: {e}")
            return {"messages": [AIMessage(content="Tive um problema, pode repetir?")]}
    
    def _summarize_execution(self, state: IRISStateV3) -> str:
        """Resume resultado da execução para o prompt."""
        result = state.get("execution_result")
        if not result:
            return "Nenhuma ação executada"
        
        if result.success:
            data = result.data
            if isinstance(data, dict):
                parts = []
                for key, value in list(data.items())[:5]:
                    if isinstance(value, (list, dict)):
                        parts.append(f"{key}: {len(value) if isinstance(value, list) else 'dados'}")
                    else:
                        parts.append(f"{key}: {str(value)[:50]}")
                return f"Sucesso - {', '.join(parts)}"
            return f"Sucesso - {str(data)[:100]}"
        
        return f"Erro - {result.error or 'desconhecido'}"
