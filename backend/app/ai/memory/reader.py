"""
Memory Reader Node - Leitura seletiva de memórias.

Responsabilidades:
- Buscar memórias relevantes para o contexto atual
- Filtrar por tipo, confiança e recência
- NUNCA inventar memórias
- Retornar máximo de itens configurado

REGRAS CRÍTICAS:
- Sem LLM - 100% determinístico
- Sempre com user_id (isolamento)
- Limite de itens por query
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.ai.memory.types import (
    MemoryItem,
    MemoryType,
    MemoryLayer,
    MemoryQuery,
    Importance,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Tentar importar modelo UserMemory (v3)
try:
    from app.models.user_memory import UserMemory as UserMemoryModel
    HAS_USER_MEMORY_MODEL = True
except ImportError:
    HAS_USER_MEMORY_MODEL = False

logger = logging.getLogger(__name__)


# Estratégia de leitura por intent
INTENT_MEMORY_STRATEGY = {
    "finance": {
        "types": [MemoryType.PREFERENCE, MemoryType.HABIT, MemoryType.RECURRENCE],
        "categories": ["finance"],
        "max_items": 5,
        "min_confidence": 0.6,
    },
    "reminder": {
        "types": [MemoryType.PREFERENCE, MemoryType.HABIT, MemoryType.RECURRENCE],
        "categories": ["personal", "work", "general"],
        "max_items": 3,
        "min_confidence": 0.5,
    },
    "health": {
        "types": [MemoryType.CONSTRAINT, MemoryType.RECURRENCE, MemoryType.PREFERENCE],
        "categories": ["health"],
        "max_items": 5,
        "min_confidence": 0.7,
    },
    "calendar": {
        "types": [MemoryType.PREFERENCE, MemoryType.RECURRENCE],
        "categories": ["work", "personal"],
        "max_items": 3,
        "min_confidence": 0.5,
    },
    "contact": {
        "types": [MemoryType.PREFERENCE, MemoryType.IDENTITY],
        "categories": ["personal", "work"],
        "max_items": 3,
        "min_confidence": 0.5,
    },
    "goals": {
        "types": [MemoryType.PREFERENCE, MemoryType.HABIT, MemoryType.DECISION],
        "categories": ["finance", "personal"],
        "max_items": 5,
        "min_confidence": 0.5,
    },
    "patterns": {
        "types": [MemoryType.HABIT, MemoryType.RECURRENCE, MemoryType.EVENT],
        "categories": ["finance"],
        "max_items": 10,
        "min_confidence": 0.4,
    },
    "general": {
        "types": [MemoryType.PREFERENCE, MemoryType.IDENTITY, MemoryType.CONSTRAINT],
        "categories": ["general"],
        "max_items": 5,
        "min_confidence": 0.5,
    },
}


class MemoryReaderNode:
    """
    Nó de leitura de memória - 100% determinístico.
    
    NUNCA inventa memória.
    Apenas seleciona memórias existentes por relevância.
    """
    
    def __init__(self, db: "Session" = None):
        self.db = db
    
    def read(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Lê memórias relevantes para o estado atual.
        
        Input (state):
            - user_id: int
            - intent: str
            - entities: dict
        
        Output (state update):
            - relevant_memories: List[MemoryItem]
            - memory_context: str (resumo comprimido)
        """
        user_id = state.get("user_id")
        intent = state.get("intent", "general")
        entities = state.get("entities", {})
        
        if not user_id:
            logger.warning("[MEMORY_READER] user_id ausente")
            return {"relevant_memories": [], "memory_context": ""}
        
        try:
            # 1. Obter estratégia para o intent
            strategy = self._get_strategy(intent)
            
            # 2. Buscar memórias
            memories = self._fetch_memories(user_id, strategy)
            
            # 3. Filtrar por relevância
            relevant = self._filter_by_relevance(memories, intent, entities)
            
            # 4. Atualizar last_accessed
            self._update_access(relevant)
            
            logger.info(
                f"[MEMORY_READER] user={user_id} | intent={intent} | "
                f"found={len(memories)} | relevant={len(relevant)}"
            )
            
            return {
                "relevant_memories": relevant,
                "memory_context": "",  # Será construído pelo ContextBuilder
            }
            
        except Exception as e:
            logger.error(f"[MEMORY_READER] Erro: {e}")
            return {"relevant_memories": [], "memory_context": ""}
    
    def _get_strategy(self, intent: str) -> Dict:
        """Obtém estratégia de leitura para o intent."""
        return INTENT_MEMORY_STRATEGY.get(
            intent, 
            INTENT_MEMORY_STRATEGY["general"]
        )
    
    def _fetch_memories(self, user_id: int, strategy: Dict) -> List[MemoryItem]:
        """Busca memórias do banco."""
        if not self.db:
            return self._fetch_from_memory_manager(user_id, strategy)
        
        # Tentar usar modelo UserMemory v3
        if HAS_USER_MEMORY_MODEL:
            try:
                return self._fetch_from_user_memory(user_id, strategy)
            except Exception as e:
                logger.warning(f"[MEMORY_READER] UserMemory fallback: {e}")
        
        # Fallback para MemoryManager legado
        return self._fetch_from_memory_manager(user_id, strategy)
    
    def _fetch_from_user_memory(self, user_id: int, strategy: Dict) -> List[MemoryItem]:
        """Busca memórias do modelo UserMemory v3."""
        query = self.db.query(UserMemoryModel).filter(
            UserMemoryModel.user_id == user_id,
            UserMemoryModel.confidence >= strategy["min_confidence"],
            UserMemoryModel.is_archived == False,
        )
        
        # Filtrar por tipos
        if strategy.get("types"):
            type_values = [t.value for t in strategy["types"]]
            query = query.filter(UserMemoryModel.memory_type.in_(type_values))
        
        # Ordenar por importância e recência
        query = query.order_by(
            UserMemoryModel.importance.desc(),
            UserMemoryModel.last_accessed.desc(),
        )
        
        # Limitar resultados
        query = query.limit(strategy["max_items"] * 2)
        
        results = query.all()
        
        return [self._model_to_item(r) for r in results]
    
    def _fetch_from_memory_manager(self, user_id: int, strategy: Dict) -> List[MemoryItem]:
        """Fallback: busca do MemoryManager existente."""
        if not self.db:
            logger.warning("[MEMORY_READER] db não disponível para MemoryManager")
            return []
        
        try:
            from app.ai.memory import MemoryManager
            
            manager = MemoryManager(self.db, user_id)
            context = manager.get_full_context()
            
            items = []
            
            # Converter preferências
            for pref in context.get("preferences", []):
                items.append(MemoryItem(
                    user_id=user_id,
                    memory_type=MemoryType.PREFERENCE,
                    key="preference",
                    value=pref,
                    summary=pref[:100],
                    confidence=0.7,
                ))
            
            # Converter fatos
            for fact in context.get("facts", []):
                items.append(MemoryItem(
                    user_id=user_id,
                    memory_type=MemoryType.IDENTITY,
                    key="fact",
                    value=fact,
                    summary=fact[:100],
                    confidence=0.7,
                ))
            
            # Converter hábitos
            for habit in context.get("habits", []):
                items.append(MemoryItem(
                    user_id=user_id,
                    memory_type=MemoryType.HABIT,
                    key="habit",
                    value=habit,
                    summary=habit[:100],
                    confidence=0.7,
                ))
            
            return items[:strategy["max_items"]]
            
        except Exception as e:
            logger.error(f"[MEMORY_READER] MemoryManager error: {e}")
            return []
    
    def _filter_by_relevance(
        self,
        memories: List[MemoryItem],
        intent: str,
        entities: Dict,
    ) -> List[MemoryItem]:
        """Filtra memórias por relevância ao contexto."""
        if not memories:
            return []
        
        scored = []
        for mem in memories:
            score = self._calculate_relevance(mem, intent, entities)
            if score >= 0.3:
                scored.append((mem, score))
        
        # Ordenar por score
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # Retornar top N
        strategy = self._get_strategy(intent)
        max_items = strategy.get("max_items", 10)
        
        return [m for m, _ in scored[:max_items]]
    
    def _calculate_relevance(
        self,
        memory: MemoryItem,
        intent: str,
        entities: Dict,
    ) -> float:
        """Calcula score de relevância de 0.0 a 1.0."""
        score = 0.0
        
        # 1. Correspondência de categoria (+0.3)
        entity_categories = entities.get("categories", [])
        if memory.category in entity_categories or memory.category == "general":
            score += 0.3
        
        # 2. Recência (+0.25)
        if memory.last_accessed:
            days = (datetime.now() - memory.last_accessed).days
            if days < 7:
                score += 0.25
            elif days < 30:
                score += 0.15
            elif days < 90:
                score += 0.05
        
        # 3. Frequência de uso (+0.2)
        if memory.access_count > 10:
            score += 0.2
        elif memory.access_count > 5:
            score += 0.1
        elif memory.access_count > 0:
            score += 0.05
        
        # 4. Importância (+0.15)
        importance_scores = {
            Importance.CRITICAL: 0.15,
            Importance.HIGH: 0.12,
            Importance.MEDIUM: 0.08,
            Importance.LOW: 0.03,
        }
        score += importance_scores.get(memory.importance, 0.05)
        
        # 5. Confiança (+0.1)
        score += memory.confidence * 0.1
        
        return min(score, 1.0)
    
    def _update_access(self, memories: List[MemoryItem]):
        """Atualiza timestamp de acesso."""
        if not self.db or not memories:
            return
        
        try:
            from app.models import UserMemory
            
            now = datetime.now()
            for mem in memories:
                if mem.memory_id:
                    self.db.query(UserMemory).filter(
                        UserMemory.id == mem.memory_id
                    ).update({
                        "last_accessed": now,
                        "access_count": UserMemory.access_count + 1,
                    })
            
            self.db.commit()
        except Exception as e:
            logger.error(f"[MEMORY_READER] Update access error: {e}")
    
    def _model_to_item(self, model: Any) -> MemoryItem:
        """Converte modelo do banco para MemoryItem."""
        return MemoryItem(
            memory_id=str(model.id),
            user_id=model.user_id,
            memory_type=MemoryType(model.memory_type) if model.memory_type else MemoryType.CONTEXT,
            category=model.category or "general",
            key=model.key or "",
            value=model.value,
            summary=model.summary or str(model.value)[:100],
            confidence=model.confidence or 0.5,
            importance=Importance(model.importance) if model.importance else Importance.MEDIUM,
            created_at=model.created_at,
            updated_at=model.updated_at,
            last_accessed=model.last_accessed,
            access_count=model.access_count or 0,
        )


def read_relevant_memories(
    user_id: int,
    intent: str,
    entities: Dict = None,
    db: "Session" = None,
) -> List[MemoryItem]:
    """Função auxiliar para leitura de memórias."""
    reader = MemoryReaderNode(db=db)
    result = reader.read({
        "user_id": user_id,
        "intent": intent,
        "entities": entities or {},
    })
    return result.get("relevant_memories", [])
