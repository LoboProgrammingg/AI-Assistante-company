"""
Memory Agent - Gerenciador de memória de longo prazo.

Detecta e armazena:
- Preferências (gosta de X, não gosta de Y)
- Hábitos (sempre faz X às segundas)
- Informações pessoais (aniversário, trabalho)
- Recorrências (paga conta X todo dia 10)
- Aversões (alérgico a X, não come Y)

Restrições:
- Nunca salvar senhas ou dados financeiros sensíveis
- Pedir confirmação para dados médicos
- Não salvar tudo - ser seletivo
"""

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List

from app.ai.agents.base import AgentResult, SpecializedAgent
from app.ai.agents.registry import AgentRegistry

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# Padrões para detectar informações relevantes
MEMORY_PATTERNS = {
    "preference_positive": [
        r"(?:eu )?(?:gosto|adoro|amo|prefiro|curto) (?:de |muito )?(.+)",
        r"(?:meu|minha) (?:favorit[oa]|preferid[oa]) (?:é|são) (.+)",
        r"(.+) é (?:meu|minha) (?:favorit[oa]|preferid[oa])",
    ],
    "preference_negative": [
        r"(?:eu )?(?:não gosto|odeio|detesto|não curto) (?:de )?(.+)",
        r"(?:tenho )?alergia (?:a |de )?(.+)",
        r"sou (?:alérgic[oa]|intolerante) (?:a |de )?(.+)",
    ],
    "habit": [
        r"(?:sempre|geralmente|normalmente) (?:eu )?(.+) (?:às|todo|toda|nos|nas) (.+)",
        r"(?:eu )?(.+) (?:todo dia|toda semana|todo mês)",
    ],
    "personal_info": [
        r"(?:meu|minha) (?:nome|apelido) (?:é|:) (.+)",
        r"(?:moro|trabalho|estudo) (?:em|na|no) (.+)",
        r"(?:faço|sou) (.+) (?:de profissão|profissionalmente)",
        r"(?:meu aniversário|nasci) (?:é|em|no dia) (.+)",
    ],
    "recurrence": [
        r"(?:pago|recebo) (.+) (?:todo|dia|mês) (.+)",
        r"(?:tenho|vou) (?:ao|à) (.+) (?:todo|toda) (.+)",
    ],
}

# Categorias de memória
MEMORY_CATEGORIES = [
    "preference",
    "habit",
    "personal",
    "recurrence",
    "health",
    "work",
    "family",
    "finance_pattern",
]

# Dados sensíveis que NÃO devem ser salvos
SENSITIVE_PATTERNS = [
    r"senha",
    r"password",
    r"cpf",
    r"rg\s*\d",
    r"cartão.*\d{4}",
    r"conta.*\d{4,}",
    r"agência",
]


@AgentRegistry.register
class MemoryAgent(SpecializedAgent):
    """Agente de memória de longo prazo."""

    name = "memory"
    description = "Gerencia memória e preferências do usuário"
    supported_intents = ["memory", "preference", "remember", "lembrar"]

    def _register_tools(self) -> Dict[str, callable]:
        """Registra tools do agente de memória."""
        return {
            "write_memory": self._write_memory,
            "read_memory": self._read_memory,
            "update_memory": self._update_memory,
            "delete_memory": self._delete_memory,
            "detect_memorable": self._detect_memorable,
        }

    async def process(self, message: str, entities: Dict[str, Any] = None) -> AgentResult:
        """Processa mensagem para detectar/gerenciar memórias."""
        entities = entities or {}
        message_lower = message.lower()

        # Verificar se é comando explícito
        if self._is_read_command(message_lower):
            return await self._handle_read(message, entities)

        if self._is_forget_command(message_lower):
            return await self._handle_forget(message, entities)

        # Detectar informações memoráveis
        return await self._detect_and_suggest(message, entities)

    def _is_read_command(self, message: str) -> bool:
        """Verifica se é comando de leitura."""
        patterns = [
            "o que você sabe",
            "o que sabe sobre",
            "lembra de",
            "você lembra",
            "minhas preferências",
            "meus dados",
        ]
        return any(p in message for p in patterns)

    def _is_forget_command(self, message: str) -> bool:
        """Verifica se é comando para esquecer."""
        patterns = [
            "esquece",
            "esqueça",
            "delete",
            "apaga",
            "remove",
            "não é mais",
        ]
        return any(p in message for p in patterns)

    async def _handle_read(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Lê memórias do usuário."""
        if not self.db or not self.user_id:
            return AgentResult(
                success=False,
                action="read_memory",
                error="Sem acesso ao banco",
            )

        try:
            from app.ai.memory import MemoryManager

            manager = MemoryManager(self.db, self.user_id)
            context = manager.get_full_context()

            if not context.get("preferences") and not context.get("facts"):
                return AgentResult(
                    success=True,
                    action="read_memory",
                    data={},
                    message="📭 Ainda não tenho memórias salvas sobre você.",
                )

            lines = ["🧠 *O que sei sobre você:*\n"]

            if context.get("preferences"):
                lines.append("*Preferências:*")
                for pref in context["preferences"][:5]:
                    lines.append(f"  • {pref}")

            if context.get("facts"):
                lines.append("\n*Informações:*")
                for fact in context["facts"][:5]:
                    lines.append(f"  • {fact}")

            if context.get("habits"):
                lines.append("\n*Hábitos:*")
                for habit in context["habits"][:3]:
                    lines.append(f"  • {habit}")

            return AgentResult(
                success=True,
                action="read_memory",
                data=context,
                message="\n".join(lines),
            )

        except Exception as e:
            self.log("error", f"Erro ao ler memórias: {e}")
            return AgentResult(success=False, action="read_memory", error=str(e))

    async def _handle_forget(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Remove memória."""
        # Extrair o que esquecer
        patterns = [
            r"esquece? (?:que )?(?:eu )?(.+)",
            r"apaga? (?:que )?(?:eu )?(.+)",
            r"delete? (?:a? )?memória (?:sobre |de )?(.+)",
        ]

        content = ""
        for pattern in patterns:
            match = re.search(pattern, message.lower())
            if match:
                content = match.group(1).strip()
                break

        if not content:
            return AgentResult(
                success=False,
                action="delete_memory",
                message="O que você quer que eu esqueça?",
                requires_confirmation=True,
            )

        return AgentResult(
            success=True,
            action="delete_memory",
            data={"content": content},
            message=f"Quer que eu esqueça sobre '{content}'?",
            requires_confirmation=True,
        )

    async def _detect_and_suggest(self, message: str, entities: Dict[str, Any]) -> AgentResult:
        """Detecta informações memoráveis e sugere salvamento."""
        # Verificar dados sensíveis
        if self._contains_sensitive_data(message):
            self.log("warning", "Dados sensíveis detectados - não salvando")
            return AgentResult(
                success=True,
                action="skip",
                message="",  # Silencioso
            )

        # Detectar padrões memoráveis
        detections = self._detect_patterns(message)

        if not detections:
            return AgentResult(
                success=True,
                action="no_memory",
                data={},
                message="",  # Nada para memorizar
            )

        # Encontrou algo para memorizar
        memories = []
        for category, content in detections:
            memories.append(
                {
                    "category": category,
                    "content": content,
                    "source": message[:100],
                }
            )

        # Se for informação de alta relevância, sugerir salvar
        if self._is_high_relevance(detections):
            return AgentResult(
                success=True,
                action="suggest_memory",
                data={"memories": memories},
                message=f"💡 Detectei: {detections[0][1]}\nDevo lembrar disso?",
                requires_confirmation=True,
            )

        # Para informações menores, salvar silenciosamente
        if self.db and self.user_id:
            try:
                from app.ai.memory import MemoryManager

                manager = MemoryManager(self.db, self.user_id)

                for mem in memories:
                    manager.add_fact(mem["content"], category=mem["category"])

                self.log("info", f"Salvo silenciosamente: {len(memories)} memórias")
            except Exception as e:
                self.log("error", f"Erro ao salvar memória: {e}")

        return AgentResult(
            success=True,
            action="auto_saved",
            data={"memories": memories},
            message="",  # Silencioso
        )

    def _contains_sensitive_data(self, text: str) -> bool:
        """Verifica se texto contém dados sensíveis."""
        text_lower = text.lower()
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_patterns(self, text: str) -> List[tuple]:
        """Detecta padrões memoráveis no texto."""
        detections = []
        text_lower = text.lower()

        for category, patterns in MEMORY_PATTERNS.items():
            for pattern in patterns:
                match = re.search(pattern, text_lower)
                if match:
                    content = match.group(1).strip() if match.groups() else ""
                    if content and len(content) > 2:
                        detections.append((category, content))

        return detections

    def _is_high_relevance(self, detections: List[tuple]) -> bool:
        """Verifica se as detecções são de alta relevância."""
        high_relevance_categories = {
            "preference_negative",  # Alergias, aversões
            "personal_info",
            "recurrence",
        }

        for category, _ in detections:
            if category in high_relevance_categories:
                return True
        return False

    # === Tool implementations ===

    def _write_memory(self, content: str, category: str = "general") -> Dict[str, Any]:
        """Escreve nova memória."""
        if not self.db or not self.user_id:
            return {"success": False, "error": "Sem acesso"}

        try:
            from app.ai.memory import MemoryManager

            manager = MemoryManager(self.db, self.user_id)
            manager.add_fact(content, category=category)

            return {
                "success": True,
                "message": f"✅ Memorizado: {content}",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _read_memory(self, category: str = None) -> Dict[str, Any]:
        """Lê memórias."""
        if not self.db or not self.user_id:
            return {"success": False, "error": "Sem acesso"}

        try:
            from app.ai.memory import MemoryManager

            manager = MemoryManager(self.db, self.user_id)
            context = manager.get_full_context()

            return {
                "success": True,
                "data": context,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _update_memory(self, old_content: str, new_content: str) -> Dict[str, Any]:
        """Atualiza memória existente."""
        # Implementação depende do MemoryManager
        return {"success": False, "error": "Não implementado"}

    def _delete_memory(self, content: str) -> Dict[str, Any]:
        """Remove memória."""
        # Implementação depende do MemoryManager
        return {"success": False, "error": "Não implementado"}

    def _detect_memorable(self, text: str) -> Dict[str, Any]:
        """Detecta informações memoráveis."""
        detections = self._detect_patterns(text)
        return {
            "success": True,
            "detections": detections,
            "is_sensitive": self._contains_sensitive_data(text),
        }
