"""
Working Context Builder - Construção de contexto otimizado para LLM.

Responsabilidades:
- Comprimir memórias em contexto mínimo
- Priorizar informações críticas
- Garantir limite de tokens
- Formatar para consumo do LLM

REGRAS CRÍTICAS:
- Máximo 500 tokens de contexto
- Restrições SEMPRE incluídas
- Dados de auditoria NUNCA incluídos
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List

from app.ai.memory.types import (
    Importance,
    MemoryItem,
    MemoryLayer,
    MemoryType,
)

logger = logging.getLogger(__name__)


# Campos que NUNCA vão para o LLM
NEVER_TO_LLM = [
    "memory_id",
    "user_id",
    "origin_message_id",
    "origin_session_id",
    "update_history",
    "created_at",
    "updated_at",
    "last_accessed",
    "access_count",
    "expires_at",
]

# Tipos que NUNCA vão para o LLM
NEVER_TO_LLM_TYPES = [
    MemoryType.ACTION,
    MemoryType.INFERENCE,
]

# Limite de caracteres (~500 tokens)
MAX_CONTEXT_CHARS = 2000

# Prefixos por tipo de memória
TYPE_PREFIXES = {
    MemoryType.PREFERENCE: "👤",
    MemoryType.CONSTRAINT: "⚠️",
    MemoryType.HABIT: "🔄",
    MemoryType.IDENTITY: "📋",
    MemoryType.RECURRENCE: "📅",
    MemoryType.EVENT: "📌",
    MemoryType.DECISION: "✅",
}


class WorkingContextBuilder:
    """
    Construtor de contexto de trabalho para o LLM.

    Transforma memórias em contexto mínimo e útil.
    """

    def build(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Constrói contexto de trabalho a partir de memórias.

        Input (state):
            - relevant_memories: List[MemoryItem]
            - intent: str
            - user_name: str (opcional)

        Output (state update):
            - memory_context: str (contexto formatado)
            - context_metadata: dict (estatísticas)
        """
        memories = state.get("relevant_memories", [])
        intent = state.get("intent", "general")
        user_name = state.get("user_name", "")

        if not memories:
            return {
                "memory_context": "",
                "context_metadata": {"count": 0, "chars": 0},
            }

        # 1. Filtrar tipos não permitidos
        filtered = self._filter_allowed(memories)

        # 2. Priorizar por importância
        prioritized = self._prioritize(filtered, intent)

        # 3. Construir contexto formatado
        context = self._format_context(prioritized, user_name)

        # 4. Truncar se necessário
        if len(context) > MAX_CONTEXT_CHARS:
            context = self._truncate(context)

        logger.info(
            f"[CONTEXT_BUILDER] memories={len(memories)} → " f"filtered={len(filtered)} → context={len(context)} chars"
        )

        return {
            "memory_context": context,
            "context_metadata": {
                "count": len(filtered),
                "chars": len(context),
                "truncated": len(context) >= MAX_CONTEXT_CHARS,
            },
        }

    def _filter_allowed(self, memories: List[MemoryItem]) -> List[MemoryItem]:
        """Filtra memórias permitidas para contexto."""
        return [m for m in memories if m.memory_type not in NEVER_TO_LLM_TYPES]

    def _prioritize(self, memories: List[MemoryItem], intent: str) -> List[MemoryItem]:
        """Prioriza memórias por importância e relevância."""
        # Separar por importância
        critical = []
        high = []
        medium = []
        low = []

        for mem in memories:
            # Constraints sempre primeiro
            if mem.memory_type == MemoryType.CONSTRAINT:
                critical.append(mem)
            elif mem.importance == Importance.CRITICAL:
                critical.append(mem)
            elif mem.importance == Importance.HIGH:
                high.append(mem)
            elif mem.importance == Importance.MEDIUM:
                medium.append(mem)
            else:
                low.append(mem)

        # Ordenar cada grupo por confiança
        for group in [critical, high, medium, low]:
            group.sort(key=lambda m: m.confidence, reverse=True)

        return critical + high + medium + low

    def _format_context(self, memories: List[MemoryItem], user_name: str = "") -> str:
        """Formata memórias em contexto legível."""
        if not memories:
            return ""

        # Agrupar por tipo
        by_type = defaultdict(list)
        for mem in memories:
            by_type[mem.memory_type].append(mem)

        sections = []

        # 1. Restrições (SEMPRE primeiro)
        if MemoryType.CONSTRAINT in by_type:
            constraints = by_type[MemoryType.CONSTRAINT]
            items = [m.summary or m.value for m in constraints[:5]]
            sections.append("⚠️ RESTRIÇÕES: " + "; ".join(items))

        # 2. Identidade
        if MemoryType.IDENTITY in by_type:
            identity = by_type[MemoryType.IDENTITY][:3]
            items = [m.summary or m.value for m in identity]
            sections.append("📋 Sobre: " + "; ".join(items))

        # 3. Preferências
        if MemoryType.PREFERENCE in by_type:
            prefs = by_type[MemoryType.PREFERENCE][:3]
            items = [m.summary or m.value for m in prefs]
            sections.append("👤 Preferências: " + "; ".join(items))

        # 4. Hábitos e Recorrências
        habits_recurrence = by_type.get(MemoryType.HABIT, [])[:2] + by_type.get(MemoryType.RECURRENCE, [])[:2]
        if habits_recurrence:
            items = [m.summary or m.value for m in habits_recurrence]
            sections.append("🔄 Hábitos: " + "; ".join(items))

        # 5. Eventos recentes (se houver)
        if MemoryType.EVENT in by_type:
            events = by_type[MemoryType.EVENT][:2]
            items = [m.summary or m.value for m in events]
            sections.append("📌 Recente: " + "; ".join(items))

        context = "\n".join(sections)

        # Adicionar nome se disponível
        if user_name and context:
            context = f"[Usuário: {user_name}]\n" + context

        return context

    def _truncate(self, context: str) -> str:
        """Trunca contexto mantendo estrutura."""
        if len(context) <= MAX_CONTEXT_CHARS:
            return context

        # Truncar por linhas
        lines = context.split("\n")
        result_lines = []
        total_chars = 0

        for line in lines:
            # Priorizar linhas com ⚠️ (restrições)
            if "⚠️" in line:
                result_lines.insert(0, line)
                total_chars += len(line) + 1
            elif total_chars + len(line) < MAX_CONTEXT_CHARS - 50:
                result_lines.append(line)
                total_chars += len(line) + 1

        result = "\n".join(result_lines)

        if len(result) > MAX_CONTEXT_CHARS:
            result = result[: MAX_CONTEXT_CHARS - 3] + "..."

        return result


def build_working_context(
    memories: List[MemoryItem],
    intent: str = "",
    user_name: str = "",
) -> str:
    """Função auxiliar para construção de contexto."""
    builder = WorkingContextBuilder()
    result = builder.build(
        {
            "relevant_memories": memories,
            "intent": intent,
            "user_name": user_name,
        }
    )
    return result.get("memory_context", "")


def compress_for_llm(
    memories: List[MemoryItem],
    max_tokens: int = 500,
) -> str:
    """Comprime memórias para contexto de LLM com limite de tokens."""
    # Aproximação: 1 token ≈ 4 caracteres
    max_chars = max_tokens * 4

    context = build_working_context(memories)

    if len(context) > max_chars:
        context = context[: max_chars - 3] + "..."

    return context
