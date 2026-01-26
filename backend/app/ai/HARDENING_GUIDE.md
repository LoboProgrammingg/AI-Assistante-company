# IRIS Graph v3 - Guia de Hardening para Produção

**Versão:** 1.0  
**Data:** Janeiro 2026  
**Fase:** Consolidação e Hardening

---

## 📋 Sumário Executivo

Este documento detalha os passos necessários para levar o IRIS Graph v3 de desenvolvimento para produção real, garantindo confiabilidade, observabilidade e manutenibilidade.

### Diagnóstico Atual

| Componente | Status | Ação Necessária |
|------------|--------|-----------------|
| Graph v3 Core | ✅ Implementado | Validar em staging |
| Agentes Especializados | ✅ Implementado | Testar isolamento |
| MemoryReader/Writer | ⚠️ Parcial | Modelo UserMemory não existe |
| Modelo UserMemory | ❌ **NÃO EXISTE** | Criar modelo completo |
| Redis Working Memory | ❌ Não configurado | Projetar e implementar |
| Jobs de Decay | ❌ Não existe | Implementar |
| Dashboard Auditoria | ❌ Não existe | Projetar |

### ⚠️ CRÍTICA: Modelo ConversationMemory Insuficiente

O modelo atual `ConversationMemory` é um key-value store genérico:
```python
# Atual - INSUFICIENTE
class ConversationMemory(Base):
    id, user_id, key, value (JSON), context_window, created_at, updated_at, accessed_at
```

**Faltam campos críticos:**
- `memory_type` (preference, habit, constraint, etc.)
- `layer` (session, working, longterm, episodic)
- `confidence` (0.0 - 1.0)
- `importance` (low, medium, high, critical)
- `source` (user_explicit, user_implicit, inference, system)
- `expires_at` (TTL)
- `last_confirmed` (quando foi reforçado)
- `origin_session_id` (auditoria)

---

## 1. Checklist de Staging para Graph v3

### 1.1 Pré-Requisitos

```bash
# Variáveis obrigatórias
IRIS_GRAPH_VERSION=v3
GOOGLE_API_KEY=<key>
DATABASE_URL=postgresql://...
REDIS_URL=redis://...  # Novo
```

### 1.2 Checklist de Validação

#### Infraestrutura
- [ ] PostgreSQL acessível e com migrações aplicadas
- [ ] Redis configurado e acessível
- [ ] Modelo UserMemory criado (migração aplicada)
- [ ] Índices de memória criados

#### Funcional
- [ ] Intent classification funcionando (16 intents)
- [ ] Todos os 8 agentes respondendo
- [ ] Confidence scoring retornando valores válidos
- [ ] Memórias sendo lidas corretamente
- [ ] Memórias sendo escritas corretamente
- [ ] Templates de resposta funcionando

#### Comparação v2 vs v3
- [ ] Latência p50 similar ou melhor
- [ ] Latência p95 < 2s
- [ ] Taxa de erro < 1%
- [ ] Intents classificados corretamente (sample de 100 mensagens)

### 1.3 Estratégia de Rollback

```python
# Em caso de falha crítica em v3
# 1. Alterar variável de ambiente
IRIS_GRAPH_VERSION=v2

# 2. Reiniciar serviço
# O migration.py já suporta isso nativamente

# 3. Monitorar logs por regressões
```

### 1.4 Flags de Segurança

```python
# app/config.py - Adicionar flags
GRAPH_V3_ENABLED = os.getenv("IRIS_GRAPH_VERSION", "v2") == "v3"
GRAPH_V3_MEMORY_ENABLED = os.getenv("IRIS_V3_MEMORY", "false").lower() == "true"
GRAPH_V3_DECAY_ENABLED = os.getenv("IRIS_V3_DECAY", "false").lower() == "true"
```

**Estratégia de ativação gradual:**
1. `IRIS_GRAPH_VERSION=v3` + `IRIS_V3_MEMORY=false` → v3 sem novo sistema de memória
2. `IRIS_GRAPH_VERSION=v3` + `IRIS_V3_MEMORY=true` → v3 com memória completa
3. `IRIS_GRAPH_VERSION=v3` + `IRIS_V3_MEMORY=true` + `IRIS_V3_DECAY=true` → produção completa

### 1.5 Métricas de Sucesso para Staging

| Métrica | Threshold Mínimo | Ideal |
|---------|------------------|-------|
| Latência p50 | < 800ms | < 500ms |
| Latência p95 | < 2s | < 1s |
| Taxa de erro | < 2% | < 0.5% |
| Accuracy de intent | > 90% | > 95% |
| Memórias escritas/hora | > 0 | > 10 |
| Cache hit ratio | > 50% | > 80% |

---

## 2. Modelo UserMemory - Proposta Final

### 2.1 Avaliação do Modelo Atual

**ConversationMemory (atual):**
- ❌ Sem tipos de memória
- ❌ Sem confidence/importance
- ❌ Sem TTL/expiração
- ❌ Sem auditoria
- ❌ Sem source tracking
- ✅ Isolamento por user_id
- ✅ Timestamps básicos

**Conclusão:** Modelo atual é insuficiente. Necessário criar `UserMemory`.

### 2.2 Modelo Proposto

```python
# app/models/user_memory.py

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, Float, ForeignKey, 
    Integer, JSON, String, Text, Index
)
from sqlalchemy.orm import relationship
from app.models.base import Base, utc_now
import enum


class MemoryTypeEnum(enum.Enum):
    PREFERENCE = "preference"
    HABIT = "habit"
    RECURRENCE = "recurrence"
    CONSTRAINT = "constraint"
    IDENTITY = "identity"
    EVENT = "event"
    DECISION = "decision"
    ACTION = "action"
    CONTEXT = "context"
    INFERENCE = "inference"


class MemoryLayerEnum(enum.Enum):
    SESSION = "session"
    WORKING = "working"
    LONGTERM = "longterm"
    EPISODIC = "episodic"
    ARCHIVED = "archived"


class ImportanceEnum(enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MemorySourceEnum(enum.Enum):
    USER_EXPLICIT = "user_explicit"
    USER_IMPLICIT = "user_implicit"
    INFERENCE = "inference"
    SYSTEM = "system"


class UserMemory(Base):
    """
    Modelo de memória estruturada para o sistema IRIS v3.
    
    REGRAS:
    - Sempre filtrar por user_id (isolamento obrigatório)
    - Confidence decai automaticamente via jobs
    - Constraints nunca expiram automaticamente
    """
    __tablename__ = "user_memories"

    # Identificação
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Classificação
    memory_type = Column(
        Enum(MemoryTypeEnum), 
        nullable=False, 
        default=MemoryTypeEnum.CONTEXT,
        index=True
    )
    layer = Column(
        Enum(MemoryLayerEnum), 
        nullable=False, 
        default=MemoryLayerEnum.LONGTERM
    )
    category = Column(String(50), default="general", index=True)
    
    # Conteúdo
    key = Column(String(255), nullable=False, index=True)
    value = Column(JSON, nullable=False)
    summary = Column(String(200))  # Resumo para contexto LLM
    
    # Metadados de Confiança
    confidence = Column(Float, default=0.5, index=True)
    importance = Column(
        Enum(ImportanceEnum), 
        default=ImportanceEnum.MEDIUM
    )
    source = Column(
        Enum(MemorySourceEnum), 
        default=MemorySourceEnum.USER_IMPLICIT
    )
    
    # Temporalidade
    created_at = Column(DateTime, default=utc_now, index=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)
    last_accessed = Column(DateTime, default=utc_now, index=True)
    last_confirmed = Column(DateTime)  # Quando foi reforçado pelo usuário
    expires_at = Column(DateTime, index=True)  # TTL
    access_count = Column(Integer, default=0)
    
    # Auditoria
    origin_session_id = Column(String(100))
    origin_message_id = Column(String(100))
    
    # Flags
    requires_confirmation = Column(Boolean, default=False)
    is_sensitive = Column(Boolean, default=False)
    is_archived = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="memories")

    # Índices compostos para queries frequentes
    __table_args__ = (
        Index('idx_user_type_confidence', 'user_id', 'memory_type', 'confidence'),
        Index('idx_user_category', 'user_id', 'category'),
        Index('idx_user_layer', 'user_id', 'layer'),
        Index('idx_expires', 'expires_at'),
        Index('idx_decay', 'last_accessed', 'confidence'),
    )


class MemoryAuditLog(Base):
    """
    Log de auditoria para operações de memória.
    
    Registra todas as operações para compliance e debugging.
    """
    __tablename__ = "memory_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    memory_id = Column(Integer, ForeignKey("user_memories.id"), nullable=True)
    
    # Operação
    operation = Column(String(50), nullable=False)  # create, update, delete, decay, override
    
    # Snapshot
    old_value = Column(JSON)
    new_value = Column(JSON)
    old_confidence = Column(Float)
    new_confidence = Column(Float)
    
    # Contexto
    reason = Column(String(255))  # "user_override", "decay_job", "system_cleanup"
    session_id = Column(String(100))
    
    created_at = Column(DateTime, default=utc_now, index=True)
```

### 2.3 Migração Segura

```python
# alembic/versions/xxxx_add_user_memory.py

def upgrade():
    # 1. Criar nova tabela (não afeta ConversationMemory)
    op.create_table('user_memories', ...)
    op.create_table('memory_audit_logs', ...)
    
    # 2. Criar índices
    op.create_index(...)
    
    # 3. NÃO migrar dados automaticamente
    # Dados serão populados gradualmente pelo sistema

def downgrade():
    op.drop_table('memory_audit_logs')
    op.drop_table('user_memories')
```

**Estratégia de Migração de Dados:**
1. Manter `ConversationMemory` funcionando (v2)
2. Novo sistema `UserMemory` para v3
3. Dados migrados sob demanda quando usuário interage
4. Após 30 dias, deprecar ConversationMemory

---

## 3. Redis para Working Memory

### 3.1 Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                     REDIS WORKING MEMORY                     │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Session Context (user:{id}:session:{sid})          │    │
│  │  TTL: 4 horas                                        │    │
│  │  Conteúdo: última mensagem, entities, intent atual   │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Working Memory (user:{id}:working)                  │    │
│  │  TTL: 24 horas                                       │    │
│  │  Conteúdo: memórias ativas, contexto recente         │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Memory Cache (user:{id}:memory_cache)               │    │
│  │  TTL: 1 hora                                         │    │
│  │  Conteúdo: cache de memórias do PostgreSQL           │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Estrutura de Keys

```python
# Padrão de keys
REDIS_KEYS = {
    # Sessão ativa
    "session": "iris:user:{user_id}:session:{session_id}",
    
    # Working memory (24h)
    "working": "iris:user:{user_id}:working",
    
    # Cache de memórias do PostgreSQL
    "memory_cache": "iris:user:{user_id}:memory_cache",
    
    # Contexto compilado para LLM
    "context": "iris:user:{user_id}:context",
    
    # Lock para operações de escrita
    "lock": "iris:user:{user_id}:lock",
}
```

### 3.3 TTL Dinâmico por Risco

```python
# app/ai/memory/redis_manager.py

class RedisWorkingMemory:
    """Gerenciador de Working Memory no Redis."""
    
    # TTL por tipo de operação
    TTL_CONFIG = {
        "session": 4 * 3600,      # 4 horas
        "working": 24 * 3600,     # 24 horas
        "memory_cache": 3600,     # 1 hora
        "context": 300,           # 5 minutos
    }
    
    # TTL dinâmico por risco
    TTL_BY_RISK = {
        "low": 1800,        # 30 min - saudações, perguntas simples
        "medium": 7200,     # 2 horas - consultas, buscas
        "high": 14400,      # 4 horas - ações financeiras
        "critical": 86400,  # 24 horas - decisões importantes
    }
    
    def get_ttl_for_action(self, action_type: str) -> int:
        """Retorna TTL apropriado para o tipo de ação."""
        risk_map = {
            # Baixo risco
            "direct_response": "low",
            "greeting": "low",
            "query_finance": "low",
            
            # Médio risco
            "list_reminders": "medium",
            "list_contacts": "medium",
            "search": "medium",
            
            # Alto risco
            "create_finance": "high",
            "create_reminder": "high",
            "schedule_message": "high",
            
            # Crítico
            "delete_finance": "critical",
            "create_goal": "critical",
        }
        
        risk = risk_map.get(action_type, "medium")
        return self.TTL_BY_RISK[risk]
```

### 3.4 Quando NÃO Usar Redis

```python
# Redis é para dados EFÊMEROS. NÃO usar para:

# ❌ Memórias permanentes (usar PostgreSQL)
# ❌ Auditoria (usar PostgreSQL)
# ❌ Dados que precisam sobreviver restart
# ❌ Dados sensíveis sem encryption

# ✅ Usar Redis para:
# ✅ Cache de contexto entre requests
# ✅ Session state
# ✅ Working memory temporária
# ✅ Locks distribuídos
```

### 3.5 Implementação

```python
# app/ai/memory/redis_working.py

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis

from app.config import settings

logger = logging.getLogger(__name__)


class RedisWorkingMemory:
    """
    Working Memory em Redis para IRIS v3.
    
    Camada intermediária entre sessão e PostgreSQL.
    """
    
    def __init__(self):
        self.redis = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        self.prefix = "iris"
    
    def _key(self, key_type: str, user_id: int, **kwargs) -> str:
        """Gera key padronizada."""
        base = f"{self.prefix}:user:{user_id}:{key_type}"
        if kwargs.get("session_id"):
            base += f":{kwargs['session_id']}"
        return base
    
    # ========== SESSION ==========
    
    def set_session_context(
        self,
        user_id: int,
        session_id: str,
        context: Dict[str, Any],
        ttl: int = 14400,  # 4 horas
    ) -> None:
        """Salva contexto da sessão atual."""
        key = self._key("session", user_id, session_id=session_id)
        self.redis.setex(key, ttl, json.dumps(context))
    
    def get_session_context(
        self,
        user_id: int,
        session_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Recupera contexto da sessão."""
        key = self._key("session", user_id, session_id=session_id)
        data = self.redis.get(key)
        return json.loads(data) if data else None
    
    # ========== WORKING MEMORY ==========
    
    def add_to_working(
        self,
        user_id: int,
        memory_key: str,
        value: Any,
        ttl: int = 86400,  # 24 horas
    ) -> None:
        """Adiciona item à working memory."""
        key = self._key("working", user_id)
        
        # Usar hash para múltiplos itens
        self.redis.hset(key, memory_key, json.dumps(value))
        self.redis.expire(key, ttl)
    
    def get_working_memory(self, user_id: int) -> Dict[str, Any]:
        """Retorna toda working memory."""
        key = self._key("working", user_id)
        data = self.redis.hgetall(key)
        return {k: json.loads(v) for k, v in data.items()}
    
    def clear_working(self, user_id: int) -> None:
        """Limpa working memory."""
        key = self._key("working", user_id)
        self.redis.delete(key)
    
    # ========== MEMORY CACHE ==========
    
    def cache_memories(
        self,
        user_id: int,
        memories: List[Dict],
        ttl: int = 3600,
    ) -> None:
        """Cache de memórias do PostgreSQL."""
        key = self._key("memory_cache", user_id)
        self.redis.setex(key, ttl, json.dumps(memories))
    
    def get_cached_memories(self, user_id: int) -> Optional[List[Dict]]:
        """Recupera memórias cacheadas."""
        key = self._key("memory_cache", user_id)
        data = self.redis.get(key)
        return json.loads(data) if data else None
    
    def invalidate_memory_cache(self, user_id: int) -> None:
        """Invalida cache de memórias (após escrita)."""
        key = self._key("memory_cache", user_id)
        self.redis.delete(key)
    
    # ========== CONTEXT ==========
    
    def cache_llm_context(
        self,
        user_id: int,
        context: str,
        ttl: int = 300,  # 5 min
    ) -> None:
        """Cache do contexto compilado para LLM."""
        key = self._key("context", user_id)
        self.redis.setex(key, ttl, context)
    
    def get_cached_context(self, user_id: int) -> Optional[str]:
        """Recupera contexto cacheado."""
        key = self._key("context", user_id)
        return self.redis.get(key)
```

---

## 4. Jobs de Decay de Confiança

### 4.1 Filosofia

```
┌─────────────────────────────────────────────────────────────┐
│                    MEMORY DECAY PHILOSOPHY                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  "Nenhuma memória é eterna por padrão."                     │
│                                                              │
│  - Preferências podem mudar                                  │
│  - Hábitos podem ser abandonados                             │
│  - Informações ficam desatualizadas                          │
│                                                              │
│  EXCEÇÃO: Constraints críticas (alergias, restrições)        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Regras de Decay por Tipo

```python
# Configuração de decay por tipo de memória

DECAY_CONFIG = {
    # Tipo: (decay_rate_per_day, min_confidence, never_decay)
    
    # Nunca decai automaticamente
    MemoryType.CONSTRAINT: (0.0, 0.5, True),
    
    # Decay lento
    MemoryType.IDENTITY: (0.002, 0.3, False),      # -0.2%/dia
    MemoryType.PREFERENCE: (0.005, 0.3, False),    # -0.5%/dia
    MemoryType.HABIT: (0.01, 0.3, False),          # -1%/dia
    
    # Decay médio
    MemoryType.RECURRENCE: (0.02, 0.2, False),     # -2%/dia
    MemoryType.DECISION: (0.02, 0.2, False),       # -2%/dia
    
    # Decay rápido
    MemoryType.EVENT: (0.03, 0.1, False),          # -3%/dia
    MemoryType.ACTION: (0.05, 0.1, False),         # -5%/dia
    MemoryType.CONTEXT: (0.1, 0.0, False),         # -10%/dia
    MemoryType.INFERENCE: (0.1, 0.0, False),       # -10%/dia
}

# Reforço por acesso
REINFORCEMENT_ON_ACCESS = 0.05  # +5% ao acessar
REINFORCEMENT_ON_CONFIRM = 0.2  # +20% ao confirmar explicitamente
```

### 4.3 Pseudo-código dos Jobs

```python
# app/jobs/memory_decay.py

import logging
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.models.user_memory import UserMemory, MemoryTypeEnum, ImportanceEnum
from app.models.user_memory import MemoryAuditLog

logger = logging.getLogger(__name__)


class MemoryDecayJob:
    """
    Job de decay de confiança de memórias.
    
    Executar: diariamente às 03:00 UTC
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def run(self) -> dict:
        """Executa decay em todas as memórias elegíveis."""
        stats = {
            "processed": 0,
            "decayed": 0,
            "archived": 0,
            "preserved": 0,
        }
        
        # 1. Buscar memórias não arquivadas
        memories = self.db.query(UserMemory).filter(
            UserMemory.is_archived == False,
            UserMemory.layer.in_(["longterm", "episodic"]),
        ).all()
        
        stats["processed"] = len(memories)
        
        for memory in memories:
            result = self._process_memory(memory)
            stats[result] += 1
        
        self.db.commit()
        logger.info(f"[DECAY_JOB] Resultado: {stats}")
        
        return stats
    
    def _process_memory(self, memory: UserMemory) -> str:
        """Processa decay de uma memória."""
        config = DECAY_CONFIG.get(memory.memory_type)
        if not config:
            return "preserved"
        
        decay_rate, min_confidence, never_decay = config
        
        # 1. Verificar se nunca decai
        if never_decay:
            return "preserved"
        
        # 2. Verificar importância crítica
        if memory.importance == ImportanceEnum.CRITICAL:
            return "preserved"
        
        # 3. Calcular dias desde último acesso
        days_since_access = (datetime.utcnow() - memory.last_accessed).days
        
        # 4. Aplicar decay
        old_confidence = memory.confidence
        decay_amount = decay_rate * days_since_access
        new_confidence = max(min_confidence, old_confidence - decay_amount)
        
        if new_confidence < old_confidence:
            # Registrar auditoria
            self._log_decay(memory, old_confidence, new_confidence)
            memory.confidence = new_confidence
            
            # 5. Arquivar se abaixo do mínimo útil
            if new_confidence < 0.2:
                memory.is_archived = True
                memory.layer = MemoryLayerEnum.ARCHIVED
                return "archived"
            
            return "decayed"
        
        return "preserved"
    
    def _log_decay(
        self,
        memory: UserMemory,
        old_conf: float,
        new_conf: float,
    ) -> None:
        """Registra operação de decay no audit log."""
        log = MemoryAuditLog(
            user_id=memory.user_id,
            memory_id=memory.id,
            operation="decay",
            old_confidence=old_conf,
            new_confidence=new_conf,
            reason="decay_job",
        )
        self.db.add(log)


class MemoryExpirationJob:
    """
    Job de expiração de memórias com TTL.
    
    Executar: a cada 6 horas
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def run(self) -> dict:
        """Remove memórias expiradas."""
        now = datetime.utcnow()
        
        # Buscar memórias expiradas
        expired = self.db.query(UserMemory).filter(
            UserMemory.expires_at <= now,
            UserMemory.is_archived == False,
        ).all()
        
        for memory in expired:
            # Log antes de arquivar
            log = MemoryAuditLog(
                user_id=memory.user_id,
                memory_id=memory.id,
                operation="expire",
                old_value={"summary": memory.summary},
                reason="ttl_expired",
            )
            self.db.add(log)
            
            memory.is_archived = True
            memory.layer = MemoryLayerEnum.ARCHIVED
        
        self.db.commit()
        logger.info(f"[EXPIRATION_JOB] Arquivadas: {len(expired)} memórias")
        
        return {"expired": len(expired)}


class MemoryCleanupJob:
    """
    Job de limpeza de memórias arquivadas antigas.
    
    Executar: semanalmente
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def run(self, retention_days: int = 90) -> dict:
        """Remove memórias arquivadas há mais de X dias."""
        cutoff = datetime.utcnow() - timedelta(days=retention_days)
        
        # Deletar memórias arquivadas antigas
        deleted = self.db.query(UserMemory).filter(
            UserMemory.is_archived == True,
            UserMemory.updated_at < cutoff,
        ).delete()
        
        self.db.commit()
        logger.info(f"[CLEANUP_JOB] Deletadas: {deleted} memórias")
        
        return {"deleted": deleted}
```

### 4.4 Agendamento (Celery/APScheduler)

```python
# app/jobs/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

# Decay: diariamente às 03:00 UTC
scheduler.add_job(
    MemoryDecayJob.run,
    'cron',
    hour=3,
    minute=0,
    id='memory_decay',
)

# Expiração: a cada 6 horas
scheduler.add_job(
    MemoryExpirationJob.run,
    'interval',
    hours=6,
    id='memory_expiration',
)

# Cleanup: domingos às 04:00 UTC
scheduler.add_job(
    MemoryCleanupJob.run,
    'cron',
    day_of_week='sun',
    hour=4,
    id='memory_cleanup',
)
```

---

## 5. Dashboard de Auditoria de Memória

### 5.1 Campos Essenciais

```python
# Visualização principal por usuário

MEMORY_DASHBOARD_FIELDS = {
    # Identificação
    "id": "ID",
    "user_id": "Usuário",
    "user_name": "Nome",
    
    # Conteúdo
    "memory_type": "Tipo",
    "category": "Categoria",
    "summary": "Resumo",
    "value": "Valor Completo",
    
    # Métricas
    "confidence": "Confiança",
    "importance": "Importância",
    "source": "Origem",
    
    # Temporalidade
    "created_at": "Criado em",
    "updated_at": "Atualizado em",
    "last_accessed": "Último Acesso",
    "last_confirmed": "Última Confirmação",
    "expires_at": "Expira em",
    "access_count": "Acessos",
    
    # Status
    "layer": "Camada",
    "is_archived": "Arquivado",
    "requires_confirmation": "Requer Confirmação",
}
```

### 5.2 Queries Principais

```sql
-- 1. Memórias por usuário (dashboard principal)
SELECT 
    m.id,
    m.memory_type,
    m.category,
    m.summary,
    m.confidence,
    m.importance,
    m.source,
    m.created_at,
    m.last_accessed,
    m.access_count
FROM user_memories m
WHERE m.user_id = :user_id
    AND m.is_archived = false
ORDER BY m.confidence DESC, m.last_accessed DESC
LIMIT 50;

-- 2. Memórias com baixa confiança (alerta)
SELECT 
    m.id,
    m.user_id,
    u.name as user_name,
    m.summary,
    m.confidence,
    m.last_accessed
FROM user_memories m
JOIN users u ON u.id = m.user_id
WHERE m.confidence < 0.3
    AND m.is_archived = false
ORDER BY m.confidence ASC
LIMIT 100;

-- 3. Histórico de operações (auditoria)
SELECT 
    l.id,
    l.operation,
    l.old_confidence,
    l.new_confidence,
    l.reason,
    l.created_at,
    m.summary
FROM memory_audit_logs l
LEFT JOIN user_memories m ON m.id = l.memory_id
WHERE l.user_id = :user_id
ORDER BY l.created_at DESC
LIMIT 100;

-- 4. Memórias por tipo (estatísticas)
SELECT 
    memory_type,
    COUNT(*) as total,
    AVG(confidence) as avg_confidence,
    AVG(access_count) as avg_access
FROM user_memories
WHERE user_id = :user_id
    AND is_archived = false
GROUP BY memory_type
ORDER BY total DESC;

-- 5. Memórias que expiraram recentemente
SELECT 
    m.id,
    m.user_id,
    m.summary,
    m.expires_at,
    l.created_at as expired_at
FROM memory_audit_logs l
JOIN user_memories m ON m.id = l.memory_id
WHERE l.operation = 'expire'
    AND l.created_at > NOW() - INTERVAL '7 days'
ORDER BY l.created_at DESC;
```

### 5.3 Métricas de Saúde da Memória

```python
# Métricas para monitoramento

MEMORY_HEALTH_METRICS = {
    # Por usuário
    "total_memories": "Total de memórias ativas",
    "avg_confidence": "Confiança média",
    "low_confidence_count": "Memórias com confiança < 0.3",
    "memories_by_type": "Distribuição por tipo",
    "memories_by_layer": "Distribuição por camada",
    
    # Sistema
    "total_users_with_memory": "Usuários com memórias",
    "memories_created_today": "Memórias criadas hoje",
    "memories_decayed_today": "Memórias com decay hoje",
    "memories_archived_today": "Memórias arquivadas hoje",
    
    # Performance
    "avg_access_count": "Média de acessos por memória",
    "cache_hit_ratio": "Taxa de cache hit",
    "memory_read_latency_p95": "Latência de leitura p95",
}
```

### 5.4 Alertas de Risco

```python
# Alertas automáticos

MEMORY_ALERTS = {
    # Alerta: Muitas memórias com baixa confiança
    "low_confidence_spike": {
        "condition": "COUNT(confidence < 0.3) / COUNT(*) > 0.3",
        "severity": "warning",
        "message": "Mais de 30% das memórias com baixa confiança",
    },
    
    # Alerta: Memória crítica não acessada
    "stale_critical_memory": {
        "condition": "importance = 'critical' AND last_accessed < NOW() - INTERVAL '30 days'",
        "severity": "info",
        "message": "Memória crítica não acessada há 30 dias",
    },
    
    # Alerta: Crescimento excessivo
    "memory_growth_spike": {
        "condition": "COUNT(created_at > NOW() - INTERVAL '1 day') > 100",
        "severity": "warning",
        "message": "Mais de 100 memórias criadas em 24h para um usuário",
    },
    
    # Alerta: Memória inconsistente
    "inconsistent_memory": {
        "condition": "confidence > 0.8 AND access_count = 0 AND created_at < NOW() - INTERVAL '7 days'",
        "severity": "warning",
        "message": "Memória com alta confiança nunca acessada",
    },
}
```

### 5.5 Ações de Correção

```python
# Endpoints de correção para o dashboard

# POST /api/admin/memory/{id}/override
async def override_memory(
    memory_id: int,
    new_value: dict,
    reason: str,
    admin_id: int,
):
    """
    Sobrescreve valor de uma memória com auditoria.
    """
    memory = db.query(UserMemory).get(memory_id)
    
    # Log antes da alteração
    log = MemoryAuditLog(
        user_id=memory.user_id,
        memory_id=memory_id,
        operation="admin_override",
        old_value=memory.value,
        new_value=new_value,
        reason=reason,
        session_id=f"admin:{admin_id}",
    )
    
    memory.value = new_value
    memory.updated_at = datetime.utcnow()
    
    db.add(log)
    db.commit()

# DELETE /api/admin/memory/{id}
async def delete_memory(
    memory_id: int,
    reason: str,
    admin_id: int,
):
    """
    Remove memória com auditoria completa.
    """
    memory = db.query(UserMemory).get(memory_id)
    
    # Log completo antes de deletar
    log = MemoryAuditLog(
        user_id=memory.user_id,
        memory_id=memory_id,
        operation="admin_delete",
        old_value=memory.to_dict(),
        reason=reason,
        session_id=f"admin:{admin_id}",
    )
    
    db.add(log)
    db.delete(memory)
    db.commit()
```

---

## 6. Melhorias Arquiteturais

### 6.1 MemoryWriter Híbrido

```python
# Arquitetura híbrida: Regras + LLM para classificação

class HybridMemoryWriter:
    """
    MemoryWriter com classificação semântica por LLM.
    
    REGRAS:
    - LLM NUNCA escreve diretamente no banco
    - LLM apenas classifica/sugere
    - Decisão final é determinística
    """
    
    def __init__(self, llm, db: Session):
        self.llm = llm
        self.db = db
        self.rule_writer = MemoryWriterNode(db)
    
    async def write(self, state: dict) -> dict:
        """
        Fluxo híbrido de escrita.
        
        1. Regras determinísticas tentam primeiro
        2. Se incerto, LLM classifica semanticamente
        3. Decisão final é sempre determinística
        """
        message = state.get("message", "")
        user_id = state.get("user_id")
        
        # 1. Tentar regras determinísticas primeiro
        rule_result = self.rule_writer.write(state)
        
        if rule_result.get("memory_operations"):
            # Regras foram suficientes
            return rule_result
        
        # 2. Se mensagem parece conter informação importante
        if self._might_contain_memory(message):
            # LLM classifica (não escreve!)
            classification = await self._classify_with_llm(message)
            
            if classification.get("should_save"):
                # 3. Decisão determinística baseada na classificação
                return self._save_from_classification(
                    user_id,
                    message,
                    classification,
                )
        
        return {"memory_operations": []}
    
    def _might_contain_memory(self, message: str) -> bool:
        """Heurística rápida para decidir se vale classificar."""
        keywords = [
            "gosto", "prefiro", "sempre", "nunca", "costumo",
            "meu", "minha", "trabalho", "moro", "tenho",
            "alérgico", "não posso", "preciso",
        ]
        return any(kw in message.lower() for kw in keywords)
    
    async def _classify_with_llm(self, message: str) -> dict:
        """
        LLM classifica semanticamente.
        
        RETORNA classificação, NÃO escreve nada.
        """
        prompt = f"""
        Analise a mensagem e identifique se contém informação pessoal relevante.
        
        Mensagem: "{message}"
        
        Responda em JSON:
        {{
            "should_save": true/false,
            "memory_type": "preference|habit|constraint|identity|null",
            "category": "finance|health|work|personal|general",
            "key": "chave semântica curta",
            "value": "valor extraído",
            "confidence": 0.0-1.0
        }}
        """
        
        response = await self.llm.ainvoke(prompt)
        return json.loads(response.content)
    
    def _save_from_classification(
        self,
        user_id: int,
        message: str,
        classification: dict,
    ) -> dict:
        """Salva memória baseado na classificação do LLM."""
        # Decisão determinística: só salva se confiança >= 0.6
        if classification.get("confidence", 0) < 0.6:
            return {"memory_operations": []}
        
        memory = UserMemory(
            user_id=user_id,
            memory_type=classification["memory_type"],
            category=classification["category"],
            key=classification["key"],
            value=classification["value"],
            summary=classification["value"][:100],
            confidence=classification["confidence"] * 0.8,  # Desconto por ser inferência
            source=MemorySourceEnum.INFERENCE,
        )
        
        self.db.add(memory)
        self.db.commit()
        
        return {
            "memory_operations": [{
                "action": "created",
                "memory_id": memory.id,
            }]
        }
```

### 6.2 Memory Override Flow

```python
# Fluxo de correção de memória pelo usuário

class MemoryOverrideHandler:
    """
    Trata correções explícitas do usuário.
    
    Exemplos:
    - "Na verdade não gosto mais de café"
    - "Meu nome agora é Maria"
    - "Não trabalho mais como engenheiro"
    """
    
    OVERRIDE_PATTERNS = [
        r"(?:na verdade|agora|não mais|mudei) (?:eu )?(?:não )?(gosto|prefiro|trabalho|moro)",
        r"(?:me chamo|meu nome (?:é|agora é)) (\w+)",
        r"(?:esquece|apaga|remove) (?:que |o que disse sobre )?(.+)",
    ]
    
    def detect_override(self, message: str) -> Optional[dict]:
        """Detecta se mensagem é uma correção."""
        for pattern in self.OVERRIDE_PATTERNS:
            match = re.search(pattern, message.lower())
            if match:
                return {
                    "type": "override",
                    "content": match.group(0),
                    "captured": match.groups(),
                }
        return None
    
    async def handle_override(
        self,
        user_id: int,
        override: dict,
        db: Session,
    ) -> dict:
        """Processa a correção."""
        # 1. Buscar memória relacionada
        # 2. Arquivar memória antiga com auditoria
        # 3. Criar nova memória (se aplicável)
        # 4. Confirmar ao usuário
        ...
```

### 6.3 Observabilidade

```python
# Logs estruturados para memória

import structlog

logger = structlog.get_logger()

# Leitura de memória
logger.info(
    "memory_read",
    user_id=user_id,
    intent=intent,
    memories_found=len(memories),
    memories_returned=len(filtered),
    cache_hit=cache_hit,
    latency_ms=latency,
)

# Escrita de memória
logger.info(
    "memory_write",
    user_id=user_id,
    operation=operation,  # created|updated|skipped
    memory_type=memory_type,
    confidence=confidence,
    source=source,
)

# Decay
logger.info(
    "memory_decay",
    user_id=user_id,
    memory_id=memory_id,
    old_confidence=old_conf,
    new_confidence=new_conf,
    days_since_access=days,
)
```

---

## 7. Riscos Identificados e Mitigação

### 7.1 Riscos Críticos

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| **Modelo UserMemory não criado** | Alto | Alta | Criar antes de staging |
| **Migração quebra dados existentes** | Alto | Média | Migração incremental, sem DROP |
| **Redis indisponível** | Médio | Baixa | Fallback para PostgreSQL |
| **Decay muito agressivo** | Médio | Média | Configuração conservadora inicial |

### 7.2 Riscos Operacionais

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| **Crescimento excessivo de memórias** | Médio | Média | Limites por usuário/tipo |
| **Latência de leitura** | Médio | Baixa | Cache Redis, índices |
| **Auditoria não funciona** | Baixo | Baixa | Testes antes de deploy |

### 7.3 Plano de Mitigação

```python
# 1. Feature flags para ativação gradual
IRIS_V3_MEMORY=false     # Começa desabilitado
IRIS_V3_DECAY=false      # Decay manual primeiro

# 2. Limites conservadores
MEMORY_LIMITS = {
    MemoryType.PREFERENCE: 30,   # Reduzido de 50
    MemoryType.HABIT: 20,        # Reduzido de 30
    MemoryType.EVENT: 50,        # Reduzido de 100
}

# 3. Decay conservador inicial
DECAY_CONFIG = {
    MemoryType.PREFERENCE: (0.002, 0.4, False),  # Decay mais lento
    ...
}

# 4. Alertas proativos
if low_confidence_ratio > 0.2:
    alert_ops_team("Memory health degraded")
```

---

## 8. Recomendações Finais para Produção

### 8.1 Ordem de Implementação

```
Semana 1:
├── Criar modelo UserMemory (migração)
├── Criar modelo MemoryAuditLog
├── Atualizar MemoryReader/Writer para usar UserMemory
└── Testar em staging com IRIS_V3_MEMORY=false

Semana 2:
├── Configurar Redis working memory
├── Implementar cache de memórias
├── Testar com IRIS_V3_MEMORY=true
└── Monitorar latência e cache hit

Semana 3:
├── Implementar jobs de decay
├── Testar decay em staging
├── Ativar IRIS_V3_DECAY=true
└── Monitorar saúde das memórias

Semana 4:
├── Criar endpoints de dashboard
├── Implementar alertas
├── Deploy em produção (gradual)
└── Monitorar métricas
```

### 8.2 Checklist Final de Produção

- [ ] Modelo UserMemory criado e migrado
- [ ] Índices de banco criados
- [ ] Redis configurado e testado
- [ ] Jobs de decay agendados
- [ ] Logs estruturados implementados
- [ ] Alertas configurados
- [ ] Dashboard de auditoria disponível
- [ ] Feature flags configuradas
- [ ] Rollback testado
- [ ] Documentação atualizada

### 8.3 Métricas de Sucesso

| Métrica | Threshold | Ação se Violado |
|---------|-----------|-----------------|
| Latência p95 | < 2s | Investigar, otimizar cache |
| Taxa de erro | < 1% | Rollback se > 5% |
| Memórias/usuário | < 500 | Ativar cleanup agressivo |
| Confiança média | > 0.5 | Ajustar decay |
| Cache hit | > 70% | Aumentar TTL |

---

## Críticas ao IRIS Graph v3 Atual

### O que está correto:
- ✅ Arquitetura de nós bem definida
- ✅ Separação de responsabilidades
- ✅ Confidence scoring implementado
- ✅ Agentes especializados isolados
- ✅ Regras determinísticas para escrita

### O que precisa correção:
- ❌ **Modelo UserMemory não existe** - MemoryReader/Writer vão falhar
- ❌ **Fallback para MemoryManager antigo** - Não aproveita arquitetura nova
- ❌ **Redis não configurado** - Working memory não funciona
- ❌ **Sem jobs de decay** - Memórias crescem indefinidamente
- ❌ **Sem auditoria real** - Não há MemoryAuditLog

### Prioridade Crítica:
1. **Criar modelo UserMemory** - Sem isso, v3 memory não funciona
2. **Criar migração** - Sem quebrar ConversationMemory
3. **Testar em staging** - Com feature flag desabilitada primeiro

---

*Documento gerado em Janeiro 2026*
