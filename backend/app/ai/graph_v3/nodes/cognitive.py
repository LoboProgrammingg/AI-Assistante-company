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
from app.ai.graph_v3.prompts import (
    COGNITIVE_PROMPT,
    DANGEROUS_ACTIONS,
    DEFAULT_ACTIONS,
    VALID_ACTIONS,
)
from app.ai.graph_v3.state import ActionType, ExtractedAction, IRISStateV3

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


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

            action = result.get("action")
            action_type = action.action_type if action else "none"

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
                "action": ExtractedAction(
                    action_type="direct_response", params={"response_hint": "saudação"}, confidence=0.95
                ),
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
                "action": ExtractedAction(
                    action_type="direct_response", params={"response_hint": "agradecimento"}, confidence=0.95
                ),
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
            # Remover markdown code blocks se presentes
            content = response_content.strip()
            if content.startswith("```json"):
                content = content[7:]  # Remove ```json
            elif content.startswith("```"):
                content = content[3:]  # Remove ```
            if content.endswith("```"):
                content = content[:-3]  # Remove ``` final
            content = content.strip()

            json_start = content.find("{")
            json_end = content.rfind("}") + 1

            logger.info(f"[COGNITIVE] Parsing JSON: start={json_start}, end={json_end}")

            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                logger.info(f"[COGNITIVE] JSON string: {json_str[:200]}...")

                parsed = json.loads(json_str)

                intent = parsed.get("intent", "general")
                action_type = parsed.get("action", "none")
                confidence = float(parsed.get("confidence", 0.5))
                entities = parsed.get("entities", {})
                reasoning = parsed.get("reasoning", "")

                logger.info(f"[COGNITIVE] Parsed: intent={intent}, action={action_type}, conf={confidence}")

                # Sempre incluir mensagem original nas entities
                entities["original_message"] = original_message
                entities["reasoning"] = reasoning

                if action_type not in VALID_ACTIONS:
                    logger.warning(
                        f"[COGNITIVE] Action '{action_type}' not in VALID_ACTIONS, using default for intent '{intent}'"
                    )
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
            "action": ExtractedAction(
                action_type="needs_llm_response", params={"original_message": message[:500]}, confidence=0.3
            ),
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
