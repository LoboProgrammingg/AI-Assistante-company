"""
PersistentMemoryService - Serviço CENTRALIZADO de memória persistente.

Este serviço é a ÚNICA fonte de verdade para memória do usuário.
Todos os agentes DEVEM usar este serviço para ler/escrever memórias.

Arquitetura:
- PostgreSQL: Fonte de verdade (UserMemory + ConversationHistory)
- Redis: Cache de alta performance (TTL 1h)
- Memória Local: Cache de instância (vida da requisição)

REGRAS:
1. NUNCA inventar memória - apenas ler do banco
2. SEMPRE persistir no PostgreSQL primeiro
3. Invalidar cache ao escrever
4. Carregar memória completa no início de cada requisição
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def utc_now():
    """Retorna datetime atual em UTC."""
    return datetime.now(timezone.utc)


class PersistentMemoryService:
    """
    Serviço centralizado de memória persistente.
    
    ÚNICA fonte de verdade para memórias do usuário.
    Usado por TODOS os agentes (Cognitive, Responder, Executors).
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._cache: Dict[str, Any] = {}
        self._loaded = False

    # ========================================================================
    # CARREGAMENTO COMPLETO (Chamado no início de cada requisição)
    # ========================================================================

    def load_full_memory(self) -> Dict[str, Any]:
        """
        Carrega TODA a memória do usuário em uma única operação.
        
        Returns:
            Dict com todas as memórias organizadas por tipo
        """
        if self._loaded and self._cache:
            return self._cache

        try:
            memory = {
                "user_profile": self._load_user_profile(),
                "preferences": self._load_preferences(),
                "facts": self._load_facts(),
                "constraints": self._load_constraints(),
                "habits": self._load_habits(),
                "conversation_history": self._load_conversation_history(),
                "recent_actions": self._load_recent_actions(),
                "learned_patterns": self._load_learned_patterns(),
            }

            self._cache = memory
            self._loaded = True

            total_items = sum(
                len(v) if isinstance(v, list) else (1 if v else 0)
                for v in memory.values()
            )
            logger.info(
                f"[MEMORY] Loaded {total_items} memory items for user {self.user_id}"
            )

            return memory

        except Exception as e:
            logger.error(f"[MEMORY] Error loading memory: {e}", exc_info=True)
            return self._get_empty_memory()

    def _get_empty_memory(self) -> Dict[str, Any]:
        """Retorna estrutura vazia de memória."""
        return {
            "user_profile": {},
            "preferences": [],
            "facts": [],
            "constraints": [],
            "habits": [],
            "conversation_history": [],
            "recent_actions": [],
            "learned_patterns": [],
        }

    # ========================================================================
    # LOADERS INDIVIDUAIS
    # ========================================================================

    def _load_user_profile(self) -> Dict[str, Any]:
        """Carrega perfil básico do usuário."""
        try:
            from app.models import User

            user = self.db.query(User).filter(User.id == self.user_id).first()
            if user:
                return {
                    "name": user.name or "",
                    "email": user.email or "",
                    "phone": user.phone_number or "",
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "timezone": getattr(user, "timezone", "America/Sao_Paulo"),
                }
        except Exception as e:
            logger.warning(f"[MEMORY] Error loading user profile: {e}")
        return {}

    def _load_preferences(self) -> List[Dict[str, Any]]:
        """Carrega preferências do usuário."""
        return self._load_memories_by_type("preference")

    def _load_facts(self) -> List[Dict[str, Any]]:
        """Carrega fatos conhecidos sobre o usuário."""
        return self._load_memories_by_type("identity")

    def _load_constraints(self) -> List[Dict[str, Any]]:
        """Carrega restrições/limitações do usuário."""
        return self._load_memories_by_type("constraint")

    def _load_habits(self) -> List[Dict[str, Any]]:
        """Carrega hábitos do usuário."""
        return self._load_memories_by_type("habit")

    def _load_memories_by_type(self, memory_type: str) -> List[Dict[str, Any]]:
        """Carrega memórias de um tipo específico."""
        try:
            from app.models.user_memory import MemoryTypeEnum, UserMemory

            type_enum = MemoryTypeEnum(memory_type)

            memories = (
                self.db.query(UserMemory)
                .filter(
                    and_(
                        UserMemory.user_id == self.user_id,
                        UserMemory.memory_type == type_enum,
                        UserMemory.is_archived == False,
                        UserMemory.confidence >= 0.3,
                    )
                )
                .order_by(desc(UserMemory.confidence), desc(UserMemory.last_accessed))
                .limit(50)
                .all()
            )

            return [
                {
                    "id": m.id,
                    "key": m.key,
                    "value": m.value,
                    "summary": m.summary or str(m.value)[:100],
                    "confidence": m.confidence,
                    "category": m.category,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in memories
            ]

        except Exception as e:
            logger.warning(f"[MEMORY] Error loading {memory_type} memories: {e}")
            return []

    def _load_conversation_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Carrega histórico de conversas recentes."""
        try:
            from app.models import Message

            messages = (
                self.db.query(Message)
                .filter(Message.user_id == self.user_id)
                .order_by(desc(Message.created_at))
                .limit(limit)
                .all()
            )

            history = []
            for m in reversed(messages):
                # Mensagem do usuário
                if m.content or m.audio_transcription:
                    history.append({
                        "role": "user",
                        "content": m.content or m.audio_transcription or "",
                        "timestamp": m.created_at.isoformat() if m.created_at else None,
                        "intent": m.intent,
                    })

                # Resposta da IA
                if m.ai_response:
                    history.append({
                        "role": "assistant",
                        "content": m.ai_response,
                        "timestamp": m.created_at.isoformat() if m.created_at else None,
                    })

            return history

        except Exception as e:
            logger.warning(f"[MEMORY] Error loading conversation history: {e}")
            return []

    def _load_recent_actions(self, days: int = 7) -> List[Dict[str, Any]]:
        """Carrega ações recentes executadas."""
        try:
            from app.models.user_memory import MemoryTypeEnum, UserMemory

            cutoff = utc_now() - timedelta(days=days)

            actions = (
                self.db.query(UserMemory)
                .filter(
                    and_(
                        UserMemory.user_id == self.user_id,
                        UserMemory.memory_type == MemoryTypeEnum.ACTION,
                        UserMemory.created_at >= cutoff,
                    )
                )
                .order_by(desc(UserMemory.created_at))
                .limit(20)
                .all()
            )

            return [
                {
                    "action": m.key,
                    "data": m.value,
                    "summary": m.summary,
                    "timestamp": m.created_at.isoformat() if m.created_at else None,
                }
                for a in actions
                for m in [a]
            ]

        except Exception as e:
            logger.warning(f"[MEMORY] Error loading recent actions: {e}")
            return []

    def _load_learned_patterns(self) -> List[Dict[str, Any]]:
        """Carrega padrões aprendidos."""
        try:
            from app.models.user_memory import MemoryTypeEnum, UserMemory

            patterns = (
                self.db.query(UserMemory)
                .filter(
                    and_(
                        UserMemory.user_id == self.user_id,
                        UserMemory.memory_type.in_([
                            MemoryTypeEnum.RECURRENCE,
                            MemoryTypeEnum.HABIT,
                        ]),
                        UserMemory.is_archived == False,
                        UserMemory.confidence >= 0.5,
                    )
                )
                .order_by(desc(UserMemory.confidence))
                .limit(20)
                .all()
            )

            return [
                {
                    "pattern": m.summary or m.key,
                    "type": m.memory_type.value,
                    "confidence": m.confidence,
                }
                for m in patterns
            ]

        except Exception as e:
            logger.warning(f"[MEMORY] Error loading patterns: {e}")
            return []

    # ========================================================================
    # FORMATAÇÃO PARA PROMPTS
    # ========================================================================

    def build_memory_context(self, max_chars: int = 3000) -> str:
        """
        Constrói contexto de memória formatado para os prompts do LLM.
        
        Args:
            max_chars: Limite máximo de caracteres
            
        Returns:
            String formatada com memórias relevantes
        """
        memory = self.load_full_memory()
        
        lines = ["═" * 50, "🧠 MEMÓRIA PERSISTENTE DO USUÁRIO", "═" * 50, ""]

        # Perfil
        profile = memory.get("user_profile", {})
        if profile.get("name"):
            lines.append(f"👤 Nome: {profile['name']}")

        # Preferências
        preferences = memory.get("preferences", [])
        if preferences:
            lines.append("")
            lines.append("💜 PREFERÊNCIAS:")
            for p in preferences[:10]:
                lines.append(f"  • {p['summary']}")

        # Fatos/Identidade
        facts = memory.get("facts", [])
        if facts:
            lines.append("")
            lines.append("📋 FATOS CONHECIDOS:")
            for f in facts[:10]:
                lines.append(f"  • {f['summary']}")

        # Restrições (CRÍTICO - sempre incluir)
        constraints = memory.get("constraints", [])
        if constraints:
            lines.append("")
            lines.append("⚠️ RESTRIÇÕES/LIMITAÇÕES (RESPEITAR SEMPRE):")
            for c in constraints:
                lines.append(f"  • {c['summary']}")

        # Hábitos
        habits = memory.get("habits", [])
        if habits:
            lines.append("")
            lines.append("🔄 HÁBITOS:")
            for h in habits[:5]:
                lines.append(f"  • {h['summary']}")

        # Padrões aprendidos
        patterns = memory.get("learned_patterns", [])
        if patterns:
            lines.append("")
            lines.append("📊 PADRÕES DETECTADOS:")
            for p in patterns[:5]:
                lines.append(f"  • {p['pattern']} (conf: {p['confidence']:.0%})")

        # Histórico de conversas recente
        history = memory.get("conversation_history", [])
        if history:
            lines.append("")
            lines.append("💬 CONVERSAS RECENTES:")
            for msg in history[-10:]:
                role_emoji = "👤" if msg["role"] == "user" else "🤖"
                content = msg["content"][:150]
                if len(msg["content"]) > 150:
                    content += "..."
                lines.append(f"  {role_emoji} {content}")

        lines.append("")
        lines.append("═" * 50)

        context = "\n".join(lines)

        # Truncar se necessário
        if len(context) > max_chars:
            context = context[:max_chars - 100] + "\n... [truncado]"

        return context

    def get_conversation_summary(self, last_n: int = 10) -> str:
        """Retorna resumo das últimas conversas."""
        memory = self.load_full_memory()
        history = memory.get("conversation_history", [])[-last_n:]

        if not history:
            return "Nenhuma conversa anterior registrada."

        lines = []
        for msg in history:
            role = "Usuário" if msg["role"] == "user" else "Assistente"
            content = msg["content"][:200]
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    # ========================================================================
    # ESCRITA DE MEMÓRIAS
    # ========================================================================

    def save_memory(
        self,
        memory_type: str,
        key: str,
        value: Any,
        summary: str = None,
        category: str = "general",
        confidence: float = 0.7,
        source: str = "user_implicit",
    ) -> bool:
        """
        Salva ou atualiza uma memória.
        
        Args:
            memory_type: Tipo da memória (preference, constraint, habit, etc)
            key: Chave única
            value: Valor a armazenar
            summary: Resumo legível (para prompts)
            category: Categoria
            confidence: Confiança (0.0 a 1.0)
            source: Origem (user_explicit, user_implicit, inference, system)
            
        Returns:
            True se salvo com sucesso
        """
        try:
            from app.models.user_memory import (
                ImportanceEnum,
                MemoryAuditLog,
                MemoryLayerEnum,
                MemorySourceEnum,
                MemoryTypeEnum,
                UserMemory,
            )

            type_enum = MemoryTypeEnum(memory_type)
            source_enum = MemorySourceEnum(source)

            # Verificar se já existe
            existing = (
                self.db.query(UserMemory)
                .filter(
                    and_(
                        UserMemory.user_id == self.user_id,
                        UserMemory.key == key,
                    )
                )
                .first()
            )

            if existing:
                # Atualizar existente - aumentar confiança
                old_conf = existing.confidence
                new_conf = min(old_conf + 0.1, 1.0)

                existing.confidence = new_conf
                existing.updated_at = utc_now()
                existing.last_confirmed = utc_now()
                existing.access_count = (existing.access_count or 0) + 1

                if existing.value != value:
                    existing.value = value
                    existing.summary = summary or str(value)[:100]

                # Auditoria
                audit = MemoryAuditLog(
                    user_id=self.user_id,
                    memory_id=existing.id,
                    operation="update",
                    old_confidence=old_conf,
                    new_confidence=new_conf,
                    reason="reinforcement",
                )
                self.db.add(audit)

                logger.info(f"[MEMORY] Updated memory: {key} ({old_conf:.2f} → {new_conf:.2f})")

            else:
                # Criar nova
                new_memory = UserMemory(
                    user_id=self.user_id,
                    memory_type=type_enum,
                    layer=MemoryLayerEnum.LONGTERM,
                    category=category,
                    key=key,
                    value=value,
                    summary=summary or str(value)[:100],
                    confidence=confidence,
                    importance=ImportanceEnum.MEDIUM,
                    source=source_enum,
                    created_at=utc_now(),
                    updated_at=utc_now(),
                    last_accessed=utc_now(),
                )

                self.db.add(new_memory)
                self.db.flush()

                # Auditoria
                audit = MemoryAuditLog(
                    user_id=self.user_id,
                    memory_id=new_memory.id,
                    operation="create",
                    new_value=value,
                    new_confidence=confidence,
                    reason="learned",
                )
                self.db.add(audit)

                logger.info(f"[MEMORY] Created memory: {key} (type={memory_type})")

            self.db.commit()
            self._invalidate_cache()
            return True

        except Exception as e:
            logger.error(f"[MEMORY] Error saving memory: {e}", exc_info=True)
            self.db.rollback()
            return False

    def save_conversation(self, user_message: str, ai_response: str, intent: str = "") -> bool:
        """
        Salva uma conversa no histórico.
        
        Args:
            user_message: Mensagem do usuário
            ai_response: Resposta da IA
            intent: Intent detectado
            
        Returns:
            True se salvo com sucesso
        """
        try:
            from app.models import Message

            # Criar registro de mensagem
            message = Message(
                user_id=self.user_id,
                content=user_message,
                ai_response=ai_response,
                intent=intent,
                direction="incoming",
                created_at=utc_now(),
            )

            self.db.add(message)
            self.db.commit()

            logger.debug(f"[MEMORY] Saved conversation for user {self.user_id}")
            self._invalidate_cache()
            return True

        except Exception as e:
            logger.error(f"[MEMORY] Error saving conversation: {e}")
            self.db.rollback()
            return False

    def learn_from_interaction(
        self,
        message: str,
        intent: str,
        entities: Dict[str, Any],
        response: str,
    ) -> None:
        """
        Aprende automaticamente com uma interação.
        
        Analisa a mensagem e extrai informações para memorizar.
        """
        import re

        message_lower = message.lower()

        # Padrões para aprendizado
        learning_patterns = [
            # Preferências
            (r"(?:eu )?(?:gosto|adoro|amo|prefiro) (?:de )?(.+)", "preference"),
            (r"prefiro (?:ser chamad[oa] de )?(.+)", "preference"),
            # Identidade
            (r"(?:meu nome|me chamo) (?:é )?(.+)", "identity"),
            (r"(?:trabalho|sou|atuo) (?:como )?(.+?)(?:\s|$)", "identity"),
            (r"(?:moro|vivo) (?:em|na|no) (.+)", "identity"),
            # Restrições
            (r"(?:tenho )?alergia (?:a |de )?(.+)", "constraint"),
            (r"(?:não posso|não consigo) (.+)", "constraint"),
            # Hábitos
            (r"(?:sempre|geralmente) (?:eu )?(.+)", "habit"),
            (r"(?:costumo|tenho o hábito de) (.+)", "habit"),
        ]

        for pattern, memory_type in learning_patterns:
            match = re.search(pattern, message_lower)
            if match:
                content = match.group(1).strip()
                if content and len(content) > 3:
                    key = f"{memory_type}_{content[:30].replace(' ', '_')}"
                    self.save_memory(
                        memory_type=memory_type,
                        key=key,
                        value=content,
                        summary=content[:100],
                        source="user_implicit",
                    )
                    break

    # ========================================================================
    # UTILITÁRIOS
    # ========================================================================

    def _invalidate_cache(self) -> None:
        """Invalida cache local."""
        self._cache.clear()
        self._loaded = False

    def get_user_name(self) -> str:
        """Retorna nome do usuário."""
        memory = self.load_full_memory()
        return memory.get("user_profile", {}).get("name", "")

    def has_constraint(self, keyword: str) -> bool:
        """Verifica se usuário tem restrição com determinada palavra-chave."""
        memory = self.load_full_memory()
        constraints = memory.get("constraints", [])
        keyword_lower = keyword.lower()
        
        for c in constraints:
            if keyword_lower in str(c.get("value", "")).lower():
                return True
            if keyword_lower in str(c.get("summary", "")).lower():
                return True
        
        return False

    def get_preference(self, category: str) -> Optional[str]:
        """Busca preferência por categoria."""
        memory = self.load_full_memory()
        preferences = memory.get("preferences", [])
        
        for p in preferences:
            if p.get("category") == category:
                return p.get("summary") or str(p.get("value"))
        
        return None

    def count_memories(self) -> Dict[str, int]:
        """Conta memórias por tipo."""
        memory = self.load_full_memory()
        return {
            "preferences": len(memory.get("preferences", [])),
            "facts": len(memory.get("facts", [])),
            "constraints": len(memory.get("constraints", [])),
            "habits": len(memory.get("habits", [])),
            "conversation_history": len(memory.get("conversation_history", [])),
            "recent_actions": len(memory.get("recent_actions", [])),
            "patterns": len(memory.get("learned_patterns", [])),
        }


# ============================================================================
# FUNÇÃO AUXILIAR PARA USO RÁPIDO
# ============================================================================

def get_memory_service(db: Session, user_id: int) -> PersistentMemoryService:
    """Factory function para criar serviço de memória."""
    return PersistentMemoryService(db, user_id)
