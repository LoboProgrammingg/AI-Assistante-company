"""
Base Agent - Classe base para agentes especializados.

Princípios:
- Cada agente tem suas próprias tools
- Nenhuma tool é global
- Confidence scoring obrigatório para ações críticas
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Resultado padronizado de processamento de agente."""

    success: bool
    action: str
    data: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    requires_confirmation: bool = False
    message: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ConfidenceScore:
    """Score de confiança para uma ação."""

    score: float  # 0.0 a 1.0
    reason: str
    can_auto_execute: bool = False  # True se score >= 0.9
    requires_confirmation: bool = False  # True se 0.5 <= score < 0.9

    @classmethod
    def from_score(cls, score: float, reason: str = "") -> "ConfidenceScore":
        return cls(
            score=score,
            reason=reason,
            can_auto_execute=score >= 0.9,
            requires_confirmation=0.5 <= score < 0.9,
        )


class SpecializedAgent(ABC):
    """
    Classe base para agentes especializados.

    Cada agente:
    - Tem suas próprias tools (não compartilhadas)
    - Implementa process() para processar mensagens
    - Implementa get_tools() para listar suas tools
    - Calcula confidence score para ações críticas
    """

    # Nome do agente (ex: "bills", "memory")
    name: str = "base"

    # Descrição curta
    description: str = "Agente base"

    # Intents que este agente processa
    supported_intents: List[str] = []

    def __init__(self, db: "Session" = None, user_id: int = None):
        self.db = db
        self.user_id = user_id
        self._tools = self._register_tools()

    @abstractmethod
    def _register_tools(self) -> Dict[str, callable]:
        """Registra as tools específicas deste agente."""
        pass

    @abstractmethod
    async def process(self, message: str, entities: Dict[str, Any] = None) -> AgentResult:
        """Processa mensagem e retorna resultado."""
        pass

    def get_tools(self) -> List[str]:
        """Retorna lista de nomes das tools disponíveis."""
        return list(self._tools.keys())

    def calculate_confidence(self, action: str, data: Dict[str, Any]) -> ConfidenceScore:
        """
        Calcula confidence score para uma ação.

        Sobrescrever em subclasses para lógica específica.
        """
        # Score padrão baseado em completude dos dados
        required_fields = self._get_required_fields(action)
        if not required_fields:
            return ConfidenceScore.from_score(0.8, "Ação sem campos obrigatórios")

        present = sum(1 for f in required_fields if data.get(f))
        score = present / len(required_fields)

        reason = f"{present}/{len(required_fields)} campos preenchidos"
        return ConfidenceScore.from_score(score, reason)

    def _get_required_fields(self, action: str) -> List[str]:
        """Retorna campos obrigatórios para uma ação."""
        return []

    def _execute_tool(self, tool_name: str, **kwargs) -> Any:
        """Executa uma tool registrada."""
        tool = self._tools.get(tool_name)
        if not tool:
            raise ValueError(f"Tool '{tool_name}' não encontrada no agente {self.name}")

        logger.info(f"[{self.name.upper()}] Executando tool: {tool_name}")
        return tool(**kwargs)

    def log(self, level: str, message: str):
        """Log padronizado com nome do agente."""
        prefix = f"[{self.name.upper()}]"
        getattr(logger, level)(f"{prefix} {message}")
