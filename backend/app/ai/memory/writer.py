"""
Memory Writer Node - Escrita seletiva de memórias.

Responsabilidades:
- Decidir SE algo deve ser memorizado
- Classificar tipo e importância
- Nunca salvar ruído ou emoções momentâneas
- Atualizar memória existente quando apropriado

REGRAS CRÍTICAS:
- Sem LLM - 100% baseado em regras
- Dados sensíveis requerem confirmação
- Auditoria completa de todas as operações
"""

import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.ai.memory.types import (
    MemoryItem,
    MemoryType,
    MemoryLayer,
    MemorySource,
    Importance,
    MemoryWriteResult,
    SOURCE_CONFIDENCE,
    MEMORY_LIMITS,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Tentar importar modelo UserMemory (v3)
try:
    from app.models.user_memory import (
        UserMemory as UserMemoryModel,
        MemoryAuditLog,
        MemoryTypeEnum,
        MemoryLayerEnum,
        ImportanceEnum,
        MemorySourceEnum,
    )
    HAS_USER_MEMORY_MODEL = True
except ImportError:
    HAS_USER_MEMORY_MODEL = False

logger = logging.getLogger(__name__)


# Padrões que DEVEM ser salvos
SAVE_PATTERNS = {
    MemoryType.PREFERENCE: [
        (r"(?:eu )?(?:gosto|adoro|amo|prefiro|curto) (?:de |muito )?(.+)", "general"),
        (r"(?:meu|minha) (?:favorit[oa]|preferid[oa]) (?:é|são) (.+)", "general"),
        (r"prefiro (?:ser chamad[oa] de |que me chamem de )(.+)", "identity"),
    ],
    MemoryType.CONSTRAINT: [
        (r"(?:tenho )?alergia (?:a |de )?(.+)", "health"),
        (r"(?:sou )?(?:alérgic[oa]|intolerante) (?:a |de )?(.+)", "health"),
        (r"(?:não posso|não consigo|não devo) (.+)", "general"),
        (r"(?:sou )?vegetarian[oa]|vegan[oa]", "health"),
    ],
    MemoryType.HABIT: [
        (r"(?:sempre|geralmente|normalmente) (?:eu )?(.+?) (?:às|todo|toda|nos|nas) (.+)", "general"),
        (r"(?:eu )?(.+?) (?:todo dia|toda semana|todo mês)", "general"),
        (r"(?:costumo|tenho o hábito de) (.+)", "general"),
    ],
    MemoryType.IDENTITY: [
        (r"(?:meu nome|me chamo) (?:é )?(.+)", "identity"),
        (r"(?:trabalho|sou|atuo) (?:como )?(.+?)(?:\s|$)", "work"),
        (r"(?:moro|vivo|resido) (?:em|na|no) (.+)", "personal"),
        (r"(?:tenho|sou pai|sou mãe de) (\d+) (?:filho|filha|anos)", "personal"),
    ],
    MemoryType.RECURRENCE: [
        (r"(?:pago|recebo) (.+?) (?:todo|dia|mês) (\d+)", "finance"),
        (r"(?:tenho|vou) (?:ao|à) (.+?) (?:toda|todo) (.+)", "general"),
        (r"(.+?) (?:é|são) (?:toda|todo) (.+)", "general"),
    ],
}

# Padrões que NUNCA devem ser salvos
DISCARD_PATTERNS = [
    r"(?:estou|tô|to) (?:triste|feliz|cansad[oa]|animad[oa]|com raiva|irritad[oa])",
    r"(?:acho|penso|acredito) que (?:talvez|pode ser)",
    r"(?:talvez|quem sabe|pode ser|sei lá)",
    r"(?:hoje|agora|neste momento|nessa hora)",
    r"(?:obrigad[oa]|valeu|ok|tá|blz|beleza)",
    r"^(?:sim|não|ok|tá|beleza)$",
    r"(?:oi|olá|bom dia|boa tarde|boa noite)",
]

# Dados sensíveis que requerem confirmação
SENSITIVE_PATTERNS = [
    r"(?:cpf|rg|identidade|cnh)",
    r"(?:senha|password|pin|código)",
    r"(?:cartão|conta bancária|agência)",
    r"(?:doença|diagnóstico|medicamento|remédio)",
    r"(?:salário|renda|quanto ganho)",
]

# Importância por tipo
TYPE_IMPORTANCE = {
    MemoryType.CONSTRAINT: Importance.CRITICAL,
    MemoryType.IDENTITY: Importance.HIGH,
    MemoryType.PREFERENCE: Importance.MEDIUM,
    MemoryType.HABIT: Importance.MEDIUM,
    MemoryType.RECURRENCE: Importance.HIGH,
    MemoryType.EVENT: Importance.LOW,
    MemoryType.ACTION: Importance.LOW,
    MemoryType.DECISION: Importance.MEDIUM,
}


class MemoryWriterNode:
    """
    Nó de escrita de memória - 100% baseado em regras.
    
    Decide o que memorizar usando padrões determinísticos.
    LLM NUNCA decide o que salvar.
    """
    
    def __init__(self, db: "Session" = None):
        self.db = db
    
    def write(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analisa estado e decide o que memorizar.
        
        Input (state):
            - user_id: int
            - message: str
            - intent: str
            - entities: dict
            - execution_result: dict
        
        Output (state update):
            - memory_operations: List[MemoryWriteResult]
        """
        user_id = state.get("user_id")
        message = state.get("message", "")
        intent = state.get("intent", "")
        entities = state.get("entities", {})
        execution_result = state.get("execution_result", {})
        
        if not user_id or not message:
            return {"memory_operations": []}
        
        operations = []
        
        try:
            # 1. Verificar se deve descartar
            if self._should_discard(message):
                logger.debug(f"[MEMORY_WRITER] Descartando: ruído/emoção")
                return {"memory_operations": []}
            
            # 2. Verificar dados sensíveis
            if self._contains_sensitive(message):
                logger.info(f"[MEMORY_WRITER] Dados sensíveis detectados - requer confirmação")
                # Não salvar automaticamente
                return {"memory_operations": []}
            
            # 3. Detectar memórias a partir da mensagem
            detected = self._detect_memories(message, user_id)
            
            for memory in detected:
                result = self._save_memory(memory)
                operations.append(result)
            
            # 4. Registrar ação executada (episódico)
            if execution_result.get("success"):
                action_memory = self._create_action_memory(
                    user_id, 
                    execution_result,
                    intent,
                )
                if action_memory:
                    result = self._save_memory(action_memory)
                    operations.append(result)
            
            if operations:
                logger.info(
                    f"[MEMORY_WRITER] user={user_id} | "
                    f"operations={len(operations)} | "
                    f"created={sum(1 for o in operations if o.action == 'created')}"
                )
            
            return {"memory_operations": operations}
            
        except Exception as e:
            logger.error(f"[MEMORY_WRITER] Erro: {e}")
            return {"memory_operations": []}
    
    def _should_discard(self, message: str) -> bool:
        """Verifica se mensagem deve ser descartada."""
        message_lower = message.lower().strip()
        
        # Mensagens muito curtas
        if len(message_lower) < 5:
            return True
        
        # Padrões de descarte
        for pattern in DISCARD_PATTERNS:
            if re.search(pattern, message_lower):
                return True
        
        return False
    
    def _contains_sensitive(self, message: str) -> bool:
        """Verifica se contém dados sensíveis."""
        message_lower = message.lower()
        for pattern in SENSITIVE_PATTERNS:
            if re.search(pattern, message_lower):
                return True
        return False
    
    def _detect_memories(self, message: str, user_id: int) -> List[MemoryItem]:
        """Detecta memórias a partir de padrões."""
        message_lower = message.lower()
        memories = []
        
        for memory_type, patterns in SAVE_PATTERNS.items():
            for pattern, category in patterns:
                match = re.search(pattern, message_lower)
                if match:
                    content = match.group(1).strip() if match.groups() else ""
                    
                    if content and len(content) > 2:
                        memory = MemoryItem(
                            memory_id=str(uuid.uuid4()),
                            user_id=user_id,
                            memory_type=memory_type,
                            layer=MemoryLayer.LONGTERM,
                            category=category,
                            key=self._generate_key(memory_type, content),
                            value=content,
                            summary=content[:100],
                            confidence=SOURCE_CONFIDENCE[MemorySource.USER_IMPLICIT],
                            importance=TYPE_IMPORTANCE.get(memory_type, Importance.MEDIUM),
                            source=MemorySource.USER_IMPLICIT,
                            created_at=datetime.now(),
                            updated_at=datetime.now(),
                            last_accessed=datetime.now(),
                        )
                        memories.append(memory)
                        break  # Apenas um match por tipo
        
        return memories
    
    def _generate_key(self, memory_type: MemoryType, content: str) -> str:
        """Gera chave semântica para a memória."""
        # Simplificar content para chave
        key_content = re.sub(r"[^a-z0-9\s]", "", content.lower())
        key_content = "_".join(key_content.split()[:3])
        return f"{memory_type.value}_{key_content}"
    
    def _create_action_memory(
        self,
        user_id: int,
        execution_result: Dict,
        intent: str,
    ) -> Optional[MemoryItem]:
        """Cria memória episódica de ação executada."""
        action_type = execution_result.get("action_type", "")
        
        # Apenas ações significativas
        significant_actions = {
            "create_finance", "create_reminder", "create_goal",
            "create_event", "create_contact", "schedule_message",
        }
        
        if action_type not in significant_actions:
            return None
        
        data = execution_result.get("data", {})
        summary = f"Executou {action_type}"
        
        if data.get("amount"):
            summary += f": R$ {data['amount']}"
        if data.get("title"):
            summary += f": {data['title'][:50]}"
        
        return MemoryItem(
            memory_id=str(uuid.uuid4()),
            user_id=user_id,
            memory_type=MemoryType.ACTION,
            layer=MemoryLayer.EPISODIC,
            category=intent or "general",
            key=f"action_{action_type}_{datetime.now().strftime('%Y%m%d')}",
            value={"action": action_type, "data": data},
            summary=summary[:100],
            confidence=1.0,
            importance=Importance.LOW,
            source=MemorySource.SYSTEM,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            last_accessed=datetime.now(),
            expires_at=datetime.now() + timedelta(days=90),
        )
    
    def _save_memory(self, memory: MemoryItem) -> MemoryWriteResult:
        """Salva ou atualiza memória."""
        if not self.db:
            return self._save_to_memory_manager(memory)
        
        # Usar modelo UserMemory v3 se disponível
        if HAS_USER_MEMORY_MODEL:
            try:
                return self._save_to_user_memory(memory)
            except Exception as e:
                logger.warning(f"[MEMORY_WRITER] UserMemory fallback: {e}")
        
        # Fallback para MemoryManager legado
        return self._save_to_memory_manager(memory)
    
    def _save_to_user_memory(self, memory: MemoryItem) -> MemoryWriteResult:
        """Salva memória no modelo UserMemory v3."""
        # Verificar se já existe
        existing = self.db.query(UserMemoryModel).filter(
            UserMemoryModel.user_id == memory.user_id,
            UserMemoryModel.key == memory.key,
        ).first()
        
        if existing:
            # Atualizar existente
            old_confidence = existing.confidence
            new_confidence = min(old_confidence + 0.1, 1.0)
            
            # Log de auditoria
            audit = MemoryAuditLog(
                user_id=memory.user_id,
                memory_id=existing.id,
                operation="update",
                old_confidence=old_confidence,
                new_confidence=new_confidence,
                old_value=existing.value,
                new_value=memory.value if existing.value != memory.value else None,
                reason="reinforcement",
            )
            self.db.add(audit)
            
            existing.confidence = new_confidence
            existing.updated_at = datetime.now()
            existing.last_confirmed = datetime.now()
            existing.access_count = (existing.access_count or 0) + 1
            
            # Atualizar valor se diferente
            if existing.value != memory.value:
                existing.value = memory.value
                existing.summary = memory.summary
            
            self.db.commit()
            
            return MemoryWriteResult(
                success=True,
                action="updated",
                memory_id=str(existing.id),
                message=f"Confiança aumentada: {old_confidence:.2f} → {new_confidence:.2f}",
            )
        
        else:
            # Verificar limite
            self._check_limit_v3(memory.user_id, memory.memory_type)
            
            # Mapear enums
            mem_type = MemoryTypeEnum(memory.memory_type.value)
            layer = MemoryLayerEnum(memory.layer.value)
            importance = ImportanceEnum(memory.importance.value)
            source = MemorySourceEnum(memory.source.value)
            
            # Criar nova
            new_memory = UserMemoryModel(
                user_id=memory.user_id,
                memory_type=mem_type,
                layer=layer,
                category=memory.category,
                key=memory.key,
                value=memory.value,
                summary=memory.summary,
                confidence=memory.confidence,
                importance=importance,
                source=source,
                created_at=memory.created_at,
                updated_at=memory.updated_at,
                last_accessed=memory.last_accessed,
                expires_at=memory.expires_at,
            )
            
            self.db.add(new_memory)
            self.db.flush()  # Para obter o ID
            
            # Log de auditoria
            audit = MemoryAuditLog(
                user_id=memory.user_id,
                memory_id=new_memory.id,
                operation="create",
                new_value=memory.value,
                new_confidence=memory.confidence,
                reason="detected_pattern",
            )
            self.db.add(audit)
            
            self.db.commit()
            
            return MemoryWriteResult(
                success=True,
                action="created",
                memory_id=str(new_memory.id),
                message=f"Memória criada: {memory.memory_type.value}",
            )
    
    def _check_limit_v3(self, user_id: int, memory_type: MemoryType) -> bool:
        """Verifica e aplica limite de memórias por tipo (v3)."""
        try:
            from app.models.user_memory import MEMORY_LIMITS as V3_LIMITS
            
            mem_type = MemoryTypeEnum(memory_type.value)
            limit = V3_LIMITS.get(mem_type, 50)
            
            count = self.db.query(UserMemoryModel).filter(
                UserMemoryModel.user_id == user_id,
                UserMemoryModel.memory_type == mem_type,
                UserMemoryModel.is_archived == False,
            ).count()
            
            if count >= limit:
                # Arquivar memórias mais antigas com menor confiança
                to_archive = self.db.query(UserMemoryModel).filter(
                    UserMemoryModel.user_id == user_id,
                    UserMemoryModel.memory_type == mem_type,
                    UserMemoryModel.is_archived == False,
                ).order_by(
                    UserMemoryModel.confidence,
                    UserMemoryModel.last_accessed,
                ).limit(5).all()
                
                for mem in to_archive:
                    mem.is_archived = True
                    mem.layer = MemoryLayerEnum.ARCHIVED
                    
                    # Log de auditoria
                    audit = MemoryAuditLog(
                        user_id=user_id,
                        memory_id=mem.id,
                        operation="archive",
                        old_confidence=mem.confidence,
                        reason="limit_exceeded",
                    )
                    self.db.add(audit)
                
                logger.info(f"[MEMORY_WRITER] Arquivadas {len(to_archive)} memórias por limite")
            
            return True
            
        except Exception as e:
            logger.error(f"[MEMORY_WRITER] Limit check error: {e}")
            return True
    
    def _save_to_memory_manager(self, memory: MemoryItem) -> MemoryWriteResult:
        """Fallback: salvar via MemoryManager existente."""
        try:
            from app.ai.memory import MemoryManager
            
            manager = MemoryManager(self.db, memory.user_id)
            
            if memory.memory_type == MemoryType.PREFERENCE:
                manager.add_preference(memory.value)
            elif memory.memory_type in [MemoryType.IDENTITY, MemoryType.CONSTRAINT]:
                manager.add_fact(memory.value, category=memory.category)
            elif memory.memory_type == MemoryType.HABIT:
                manager.add_habit(memory.value)
            else:
                manager.add_fact(memory.summary, category=memory.category)
            
            return MemoryWriteResult(
                success=True,
                action="created",
                message="Salvo via MemoryManager",
            )
            
        except Exception as e:
            logger.error(f"[MEMORY_WRITER] MemoryManager error: {e}")
            return MemoryWriteResult(
                success=False,
                action="error",
                message=str(e),
            )
    
    def _check_limit(self, user_id: int, memory_type: MemoryType) -> bool:
        """Verifica e aplica limite de memórias por tipo."""
        if not self.db:
            return True
        
        try:
            from app.models import UserMemory
            
            limit = MEMORY_LIMITS.get(memory_type, 50)
            count = self.db.query(UserMemory).filter(
                UserMemory.user_id == user_id,
                UserMemory.memory_type == memory_type.value,
            ).count()
            
            if count >= limit:
                # Remover memórias mais antigas com menor confiança
                to_delete = self.db.query(UserMemory).filter(
                    UserMemory.user_id == user_id,
                    UserMemory.memory_type == memory_type.value,
                ).order_by(
                    UserMemory.confidence,
                    UserMemory.last_accessed,
                ).limit(5).all()
                
                for mem in to_delete:
                    self.db.delete(mem)
                
                self.db.commit()
                logger.info(f"[MEMORY_WRITER] Removidas {len(to_delete)} memórias antigas")
            
            return True
            
        except Exception as e:
            logger.error(f"[MEMORY_WRITER] Limit check error: {e}")
            return True


def write_memory_if_relevant(
    user_id: int,
    message: str,
    intent: str = "",
    entities: Dict = None,
    execution_result: Dict = None,
    db: "Session" = None,
) -> List[MemoryWriteResult]:
    """Função auxiliar para escrita de memória."""
    writer = MemoryWriterNode(db=db)
    result = writer.write({
        "user_id": user_id,
        "message": message,
        "intent": intent,
        "entities": entities or {},
        "execution_result": execution_result or {},
    })
    return result.get("memory_operations", [])
