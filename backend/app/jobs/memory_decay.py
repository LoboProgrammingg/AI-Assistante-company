"""
Jobs de Decay e Manutenção de Memória.

Este módulo contém os jobs automáticos para:
- Decay de confiança ao longo do tempo
- Expiração de memórias com TTL
- Limpeza de memórias arquivadas antigas

Agendamento recomendado:
- MemoryDecayJob: diariamente às 03:00 UTC
- MemoryExpirationJob: a cada 6 horas
- MemoryCleanupJob: semanalmente (domingos às 04:00 UTC)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def utc_now():
    """Retorna datetime atual em UTC."""
    return datetime.now(timezone.utc)


# Tentar importar modelo UserMemory
try:
    from app.models.user_memory import (
        DECAY_CONFIG,
        ImportanceEnum,
        MemoryAuditLog,
        MemoryLayerEnum,
        MemoryTypeEnum,
        UserMemory,
    )

    HAS_USER_MEMORY = True
except ImportError:
    HAS_USER_MEMORY = False
    logger.warning("[MEMORY_DECAY] UserMemory model não disponível")


class MemoryDecayJob:
    """
    Job de decay de confiança de memórias.

    Reduz a confiança de memórias não acessadas ao longo do tempo.
    Memórias com confiança muito baixa são arquivadas.

    REGRAS:
    - Constraints (restrições) NUNCA decaem
    - Importância CRITICAL nunca decai
    - Taxa de decay varia por tipo de memória
    - Memórias arquivadas são mantidas para auditoria
    """

    def __init__(self, db: Session):
        self.db = db
        self.stats = {
            "processed": 0,
            "decayed": 0,
            "archived": 0,
            "preserved": 0,
            "errors": 0,
        }

    def run(self) -> Dict[str, int]:
        """
        Executa decay em todas as memórias elegíveis.

        Returns:
            Dict com estatísticas de processamento
        """
        if not HAS_USER_MEMORY:
            logger.warning("[DECAY_JOB] UserMemory não disponível")
            return {"error": "UserMemory not available"}

        logger.info("[DECAY_JOB] Iniciando job de decay...")

        try:
            # Buscar memórias não arquivadas
            memories = (
                self.db.query(UserMemory)
                .filter(
                    UserMemory.is_archived == False,
                    UserMemory.layer.in_(
                        [
                            MemoryLayerEnum.LONGTERM,
                            MemoryLayerEnum.EPISODIC,
                        ]
                    ),
                )
                .all()
            )

            self.stats["processed"] = len(memories)

            for memory in memories:
                try:
                    result = self._process_memory(memory)
                    self.stats[result] += 1
                except Exception as e:
                    logger.error(f"[DECAY_JOB] Erro ao processar memória {memory.id}: {e}")
                    self.stats["errors"] += 1

            self.db.commit()

            logger.info(f"[DECAY_JOB] Concluído: {self.stats}")
            return self.stats

        except Exception as e:
            logger.error(f"[DECAY_JOB] Erro fatal: {e}")
            self.db.rollback()
            return {"error": str(e)}

    def _process_memory(self, memory: UserMemory) -> str:
        """
        Processa decay de uma memória individual.

        Returns:
            "decayed" | "archived" | "preserved"
        """
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
        last_access = memory.last_accessed or memory.created_at
        days_since_access = (utc_now() - last_access).days

        # Não aplicar decay se acessado recentemente
        if days_since_access < 1:
            return "preserved"

        # 4. Aplicar decay
        old_confidence = memory.confidence
        decay_amount = decay_rate * days_since_access
        new_confidence = max(min_confidence, old_confidence - decay_amount)

        if new_confidence < old_confidence:
            # Registrar auditoria
            self._log_decay(memory, old_confidence, new_confidence, days_since_access)
            memory.confidence = new_confidence
            memory.updated_at = utc_now()

            # 5. Arquivar se abaixo do mínimo útil
            if new_confidence < 0.2:
                memory.is_archived = True
                memory.layer = MemoryLayerEnum.ARCHIVED
                logger.debug(f"[DECAY_JOB] Memória {memory.id} arquivada (conf={new_confidence:.2f})")
                return "archived"

            logger.debug(f"[DECAY_JOB] Memória {memory.id} decay: {old_confidence:.2f} → {new_confidence:.2f}")
            return "decayed"

        return "preserved"

    def _log_decay(
        self,
        memory: UserMemory,
        old_conf: float,
        new_conf: float,
        days: int,
    ) -> None:
        """Registra operação de decay no audit log."""
        log = MemoryAuditLog(
            user_id=memory.user_id,
            memory_id=memory.id,
            operation="decay",
            old_confidence=old_conf,
            new_confidence=new_conf,
            reason=f"decay_job_days_{days}",
        )
        self.db.add(log)


class MemoryExpirationJob:
    """
    Job de expiração de memórias com TTL.

    Arquiva memórias que atingiram sua data de expiração.
    """

    def __init__(self, db: Session):
        self.db = db

    def run(self) -> Dict[str, int]:
        """
        Remove/arquiva memórias expiradas.

        Returns:
            Dict com estatísticas
        """
        if not HAS_USER_MEMORY:
            return {"error": "UserMemory not available"}

        logger.info("[EXPIRATION_JOB] Iniciando job de expiração...")

        now = utc_now()

        try:
            # Buscar memórias expiradas
            expired = (
                self.db.query(UserMemory)
                .filter(
                    UserMemory.expires_at <= now,
                    UserMemory.is_archived == False,
                )
                .all()
            )

            for memory in expired:
                # Log antes de arquivar
                log = MemoryAuditLog(
                    user_id=memory.user_id,
                    memory_id=memory.id,
                    operation="expire",
                    old_value={"summary": memory.summary},
                    old_confidence=memory.confidence,
                    reason="ttl_expired",
                )
                self.db.add(log)

                memory.is_archived = True
                memory.layer = MemoryLayerEnum.ARCHIVED
                memory.updated_at = now

            self.db.commit()

            logger.info(f"[EXPIRATION_JOB] Arquivadas: {len(expired)} memórias")
            return {"expired": len(expired)}

        except Exception as e:
            logger.error(f"[EXPIRATION_JOB] Erro: {e}")
            self.db.rollback()
            return {"error": str(e)}


class MemoryCleanupJob:
    """
    Job de limpeza de memórias arquivadas antigas.

    Remove permanentemente memórias arquivadas há mais de X dias.
    Mantém audit logs para compliance.
    """

    def __init__(self, db: Session):
        self.db = db

    def run(self, retention_days: int = 90) -> Dict[str, int]:
        """
        Remove memórias arquivadas antigas.

        Args:
            retention_days: Dias para manter memórias arquivadas

        Returns:
            Dict com estatísticas
        """
        if not HAS_USER_MEMORY:
            return {"error": "UserMemory not available"}

        logger.info(f"[CLEANUP_JOB] Iniciando limpeza (retenção: {retention_days} dias)...")

        cutoff = utc_now() - timedelta(days=retention_days)

        try:
            # Contar antes de deletar
            to_delete = (
                self.db.query(UserMemory)
                .filter(
                    UserMemory.is_archived == True,
                    UserMemory.updated_at < cutoff,
                )
                .all()
            )

            count = len(to_delete)

            # Log final antes de deletar
            for memory in to_delete:
                log = MemoryAuditLog(
                    user_id=memory.user_id,
                    memory_id=memory.id,
                    operation="delete_permanent",
                    old_value=memory.to_dict(),
                    reason=f"cleanup_retention_{retention_days}d",
                )
                self.db.add(log)

            # Deletar memórias
            for memory in to_delete:
                self.db.delete(memory)

            self.db.commit()

            logger.info(f"[CLEANUP_JOB] Deletadas: {count} memórias")
            return {"deleted": count}

        except Exception as e:
            logger.error(f"[CLEANUP_JOB] Erro: {e}")
            self.db.rollback()
            return {"error": str(e)}


class MemoryReinforcementJob:
    """
    Job para reforçar memórias frequentemente acessadas.

    Aumenta a confiança de memórias que são acessadas com frequência.
    """

    REINFORCEMENT_THRESHOLD = 5  # Acessos mínimos para reforço
    REINFORCEMENT_AMOUNT = 0.05  # +5% por reforço

    def __init__(self, db: Session):
        self.db = db

    def run(self) -> Dict[str, int]:
        """
        Reforça memórias frequentemente acessadas.
        """
        if not HAS_USER_MEMORY:
            return {"error": "UserMemory not available"}

        logger.info("[REINFORCEMENT_JOB] Iniciando job de reforço...")

        try:
            # Buscar memórias com alto acesso recente
            memories = (
                self.db.query(UserMemory)
                .filter(
                    UserMemory.is_archived == False,
                    UserMemory.access_count >= self.REINFORCEMENT_THRESHOLD,
                    UserMemory.confidence < 0.95,  # Não ultrapassar 0.95
                )
                .all()
            )

            reinforced = 0

            for memory in memories:
                # Calcular reforço baseado em acessos
                reinforcement = min(self.REINFORCEMENT_AMOUNT * (memory.access_count / 10), 0.1)  # Máximo 10% por ciclo

                old_conf = memory.confidence
                new_conf = min(old_conf + reinforcement, 0.95)

                if new_conf > old_conf:
                    memory.confidence = new_conf
                    memory.access_count = 0  # Reset contador
                    memory.updated_at = utc_now()

                    # Log de auditoria
                    log = MemoryAuditLog(
                        user_id=memory.user_id,
                        memory_id=memory.id,
                        operation="reinforce",
                        old_confidence=old_conf,
                        new_confidence=new_conf,
                        reason="high_access_count",
                    )
                    self.db.add(log)
                    reinforced += 1

            self.db.commit()

            logger.info(f"[REINFORCEMENT_JOB] Reforçadas: {reinforced} memórias")
            return {"reinforced": reinforced}

        except Exception as e:
            logger.error(f"[REINFORCEMENT_JOB] Erro: {e}")
            self.db.rollback()
            return {"error": str(e)}


def run_all_memory_jobs(db: Session) -> Dict[str, Dict]:
    """
    Executa todos os jobs de memória.

    Útil para execução manual ou teste.
    """
    results = {}

    results["decay"] = MemoryDecayJob(db).run()
    results["expiration"] = MemoryExpirationJob(db).run()
    results["reinforcement"] = MemoryReinforcementJob(db).run()

    return results
