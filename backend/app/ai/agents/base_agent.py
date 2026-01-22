import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.config import settings

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Classe base para todos os agentes especializados."""

    def __init__(self, name: str, description: str, model: Optional[str] = None, temperature: float = 0.7):
        self.name = name
        self.description = description
        self.llm = ChatGoogleGenerativeAI(
            model=model or settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=temperature,
            max_output_tokens=35000,
        )

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Prompt de sistema do agente."""
        pass

    @abstractmethod
    async def process(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma mensagem.

        Args:
            message: Mensagem do usuário
            context: Contexto adicional

        Returns:
            Dict com resposta e entidades extraídas
        """
        pass

    @abstractmethod
    def extract_entities(self, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extrai entidades relevantes da mensagem.

        Args:
            message: Mensagem do usuário
            context: Contexto adicional

        Returns:
            Dict com entidades extraídas
        """
        pass

    async def invoke_llm(self, prompt: str, include_system: bool = True) -> str:
        """
        Invoca o LLM com o prompt (versão assíncrona).

        Args:
            prompt: Prompt do usuário
            include_system: Incluir system prompt

        Returns:
            Resposta do LLM
        """
        messages = []

        if include_system:
            messages.append(SystemMessage(content=self.system_prompt))

        messages.append(HumanMessage(content=prompt))

        try:
            response = await self.llm.ainvoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Erro ao invocar LLM no agente {self.name}: {e}")
            raise

    def invoke_llm_sync(self, prompt: str, include_system: bool = True) -> str:
        """
        Invoca o LLM com o prompt (versão síncrona).

        Args:
            prompt: Prompt do usuário
            include_system: Incluir system prompt

        Returns:
            Resposta do LLM
        """
        messages = []

        if include_system:
            messages.append(SystemMessage(content=self.system_prompt))

        messages.append(HumanMessage(content=prompt))

        try:
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
            logger.error(f"Erro ao invocar LLM no agente {self.name}: {e}")
            raise

    def format_context(self, context: Dict[str, Any]) -> str:
        """Formata contexto para inclusão no prompt."""
        parts = []

        if context.get("user_name"):
            parts.append(f"Nome do usuário: {context['user_name']}")

        if context.get("timezone"):
            parts.append(f"Timezone: {context['timezone']}")

        if context.get("current_time"):
            parts.append(f"Horário atual: {context['current_time']}")

        return "\n".join(parts) if parts else "Sem contexto adicional"

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
