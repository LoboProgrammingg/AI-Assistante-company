"""
Router Node - Classificação e roteamento de intenções.

Responsável por:
- Classificar a intenção do usuário (fast ou via LLM)
- Rotear para o agente especializado correto
- Proteção contra loops infinitos
"""

import json
import logging
from typing import TYPE_CHECKING

from langchain_core.messages import BaseMessage

from app.ai.agents.prompts.classifier_prompts import ClassifierPrompts
from app.ai.state import IRISState, UserContext
from app.core.llm_optimizer import get_optimizer

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class RouterNode:
    """Nó responsável pela classificação e roteamento."""

    def __init__(self, llm_fast: "ChatGoogleGenerativeAI"):
        """
        Args:
            llm_fast: LLM rápido para classificação (ex: gemini-flash)
        """
        self.llm_fast = llm_fast

    def route(self, state: IRISState) -> IRISState:
        """
        Classifica intenção e roteia para o agente correto.
        Implementa proteção contra loops.
        """
        # Proteção contra loops
        state["step_count"] = state.get("step_count", 0) + 1
        if state["step_count"] > state.get("max_steps", 15):
            state["error"] = "Limite de passos atingido"
            state["intent"] = "error"
            return state

        last_message = state["messages"][-1]
        optimizer = get_optimizer()

        # Tentar classificação rápida (sem LLM)
        use_fast, fast_intent = optimizer.should_use_fast_classification(last_message.content)
        if use_fast and fast_intent:
            state["intent"] = fast_intent
            state["confidence"] = 0.85
            logger.info(f"[ROUTER] ⚡ Fast: {fast_intent}")
            return state

        # Classificação com LLM rápido (flash)
        user_ctx = state.get("user_context") or {}
        is_audio = user_ctx.is_audio if isinstance(user_ctx, UserContext) else False

        classification_prompt = ClassifierPrompts.get_classification_prompt(
            conversation_history=self._format_conversation(state),
            message=last_message.content,
            audio_hint=ClassifierPrompts.get_audio_hint(len(last_message.content)) if is_audio else "",
        )

        optimizer.track_call()
        response = self.llm_fast.invoke(classification_prompt)

        try:
            json_start = response.content.find("{")
            json_end = response.content.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                classification = json.loads(response.content[json_start:json_end])
                state["intent"] = classification.get("intent", "general")
                state["confidence"] = classification.get("confidence", 0.5)
                state["entities"] = classification.get("entities", {})
            else:
                state["intent"] = "general"
                state["confidence"] = 0.5
        except Exception as e:
            logger.error(f"Erro na classificação: {e}")
            state["intent"] = "general"
            state["confidence"] = 0.3

        logger.info(f"[ROUTER] 🎯 Intent: {state['intent']} ({state['confidence']:.0%})")
        return state

    def _format_conversation(self, state: IRISState) -> str:
        """Formata histórico de conversa para contexto."""
        memory_ctx = state.get("memory_context")
        if not memory_ctx:
            return ""

        conversation = memory_ctx.conversation if hasattr(memory_ctx, "conversation") else []
        if not conversation:
            return ""

        lines = []
        for msg in conversation[-5:]:
            role = "Usuário" if msg.get("role") == "user" else "Assistente"
            content = msg.get("content", "")[:150]
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    @staticmethod
    def route_by_intent(state: IRISState) -> str:
        """Determina próximo nó baseado na intenção."""
        if state.get("error"):
            return "error"
        return state.get("intent", "general")

    @staticmethod
    def should_execute_tools(state: IRISState) -> str:
        """Decide se deve executar tools ou responder."""
        if state.get("error"):
            return "error"

        # Se há tool_calls pendentes, executar
        if state.get("tool_calls"):
            return "execute"

        return "respond"
