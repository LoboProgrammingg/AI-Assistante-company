"""
Cognitive Node - Classificação + Extração + Decisão Cognitiva.

Responsabilidade ÚNICA:
1. Entender a intenção real do usuário
2. Classificar o domínio (intent)
3. Extrair entidades relevantes
4. Decidir a ação
5. Definir NECESSIDADES COGNITIVAS (flags)

Usa Gemini Flash com prompt otimizado para JSON estruturado.
Implementa retry com backoff exponencial para resiliência.
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
from app.ai.graph_v3.state import ExtractedAction, IRISStateV3
from app.ai.llm.retry import invoke_llm_with_retry

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


class CognitiveNode:
    """Nó cognitivo - classifica, extrai e decide em UMA chamada LLM."""

    def __init__(self, llm_fast: "ChatGoogleGenerativeAI"):
        self.llm_fast = llm_fast

    # ------------------------------------------------------------------
    # ENTRYPOINT
    # ------------------------------------------------------------------

    def process(self, state: IRISStateV3) -> Dict[str, Any]:
        last_message = state["messages"][-1]
        message_content = last_message.content

        # 1. Early exit para mensagens triviais
        early = self._check_early_exit(message_content)
        if early:
            logger.info(f"[COGNITIVE] ⚡ Early exit: {early['intent']}")
            return early

        # 2. Construir prompt
        prompt = COGNITIVE_PROMPT.format(
            datetime_context=get_datetime_context(),
            context_prompt=state.get("context_prompt", "")[:500] or "Nenhum",
            message=message_content[:1000],
        )

        # 3. Chamar LLM com retry
        try:
            response = invoke_llm_with_retry(
                self.llm_fast,
                prompt,
                operation_name="COGNITIVE",
                max_attempts=3
            )
            logger.info(f"[COGNITIVE] Raw response: {response.content[:300]}")

            parsed = self._parse_response(response.content, message_content)

            logger.info(
                f"[COGNITIVE] 🧠 intent={parsed['intent']} | "
                f"action={parsed['action'].action_type if parsed.get('action') else 'none'} | "
                f"confidence={parsed.get('confidence', 0):.0%} | "
                f"user_data={parsed.get('needs_user_data')} | "
                f"web={parsed.get('needs_web')} | "
                f"analysis={parsed.get('needs_analysis')}"
            )

            return parsed

        except Exception as e:
            logger.error(f"[COGNITIVE] ❌ Erro: {e}", exc_info=True)
            return self._fallback_result(message_content)

    # ------------------------------------------------------------------
    # EARLY EXIT
    # ------------------------------------------------------------------

    def _check_early_exit(self, message: str) -> Optional[Dict[str, Any]]:
        msg = message.lower().strip()

        greetings = ["oi", "olá", "ola", "hey", "eai", "e aí", "bom dia", "boa tarde", "boa noite"]
        if msg in greetings or (len(msg) < 15 and any(g in msg for g in greetings)):
            return {
                "intent": "general",
                "confidence": 0.95,
                "needs_user_data": False,
                "needs_web": False,
                "needs_analysis": False,
                "action": ExtractedAction(
                    action_type="direct_response",
                    params={"response_hint": "saudacao"},
                    confidence=0.95,
                ),
                "entities": {},
                "early_exit": True,
                "response_template": self._get_greeting_response(),
            }

        thanks = ["obrigado", "obrigada", "valeu", "vlw", "thanks"]
        if any(t in msg for t in thanks) and len(msg) < 30:
            return {
                "intent": "general",
                "confidence": 0.95,
                "needs_user_data": False,
                "needs_web": False,
                "needs_analysis": False,
                "action": ExtractedAction(
                    action_type="direct_response",
                    params={"response_hint": "agradecimento"},
                    confidence=0.95,
                ),
                "entities": {},
                "early_exit": True,
                "response_template": "Por nada! 😊 Estou aqui se precisar.",
            }

        return None

    def _get_greeting_response(self) -> str:
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "Bom dia! ☀️ Como posso ajudar?"
        elif 12 <= hour < 18:
            return "Boa tarde! 👋 Como posso ajudar?"
        return "Boa noite! 🌙 Como posso ajudar?"

    # ------------------------------------------------------------------
    # PARSE LLM RESPONSE
    # ------------------------------------------------------------------

    def _parse_response(self, response_content: str, original_message: str) -> Dict[str, Any]:
        try:
            content = response_content.strip()
            content = content.replace("```json", "").replace("```", "").strip()

            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end]

            parsed = json.loads(json_str)

            intent = parsed.get("intent", "general")
            action_type = parsed.get("action", "none")
            confidence = float(parsed.get("confidence", 0.5))
            entities = parsed.get("entities", {})

            # 🔑 FLAGS COGNITIVAS (o pulo do gato)
            needs_user_data = bool(parsed.get("needs_user_data", False))
            needs_web = bool(parsed.get("needs_web", False))
            needs_analysis = bool(parsed.get("needs_analysis", False))

            entities["original_message"] = original_message

            if action_type not in VALID_ACTIONS:
                action_type = DEFAULT_ACTIONS.get(intent, "needs_llm_response")

            action = ExtractedAction(
                action_type=action_type,
                params=entities,
                confidence=confidence,
                requires_confirmation=action_type in DANGEROUS_ACTIONS,
            )

            return {
                "intent": intent,
                "confidence": confidence,
                "needs_user_data": needs_user_data,
                "needs_web": needs_web,
                "needs_analysis": needs_analysis,
                "action": action,
                "entities": entities,
                "early_exit": False,
                "response_template": None,
            }

        except Exception as e:
            logger.warning(f"[COGNITIVE] Parse error: {e}", exc_info=True)

        return self._fallback_result(original_message)

    # ------------------------------------------------------------------
    # FALLBACK
    # ------------------------------------------------------------------

    def _fallback_result(self, message: str) -> Dict[str, Any]:
        return {
            "intent": "general",
            "confidence": 0.3,
            "needs_user_data": False,
            "needs_web": False,
            "needs_analysis": False,
            "action": ExtractedAction(
                action_type="needs_llm_response",
                params={"original_message": message[:500]},
                confidence=0.3,
            ),
            "entities": {},
            "early_exit": False,
            "response_template": None,
        }

    # ------------------------------------------------------------------
    # ROUTING
    # ------------------------------------------------------------------

    @staticmethod
    def route_after_cognitive(state: IRISStateV3) -> str:
        if state.get("error"):
            return "end"

        if state.get("early_exit") and state.get("response_template"):
            return "end"

        action = state.get("action")
        if not action:
            return "responder"

        if action.action_type in {"direct_response", "needs_llm_response", "none"}:
            return "responder"

        return "executor"
