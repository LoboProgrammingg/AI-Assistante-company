import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import google.generativeai as genai
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "models/gemini-embedding-001"
EMBEDDING_DIMENSION = 768
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


def utc_now():
    return datetime.now(timezone.utc)


class EmbeddingService:
    """Serviço para geração e busca de embeddings com Gemini + pgvector."""

    def __init__(self, db: Session):
        self.db = db
        genai.configure(api_key=settings.GOOGLE_API_KEY)

    def generate_embedding(self, text: str) -> List[float]:
        """Gera embedding para um texto usando Gemini."""
        try:
            result = genai.embed_content(model=EMBEDDING_MODEL, content=text, task_type="retrieval_document")
            return result["embedding"]
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {e}")
            return []

    def generate_query_embedding(self, query: str) -> List[float]:
        """Gera embedding para uma query de busca."""
        try:
            result = genai.embed_content(model=EMBEDDING_MODEL, content=query, task_type="retrieval_query")
            return result["embedding"]
        except Exception as e:
            logger.error(f"Erro ao gerar embedding de query: {e}")
            return []

    def chunk_text(self, text: str) -> List[str]:
        """Divide texto em chunks com overlap."""
        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):
            end = start + CHUNK_SIZE
            chunk = text[start:end]

            # Tentar quebrar em ponto final ou espaço
            if end < len(text):
                last_period = chunk.rfind(".")
                last_space = chunk.rfind(" ")

                if last_period > CHUNK_SIZE // 2:
                    end = start + last_period + 1
                    chunk = text[start:end]
                elif last_space > CHUNK_SIZE // 2:
                    end = start + last_space
                    chunk = text[start:end]

            chunks.append(chunk.strip())
            start = end - CHUNK_OVERLAP

            if start >= len(text):
                break

        return chunks

    def index_document(self, document_id: int, content: str) -> int:
        """Indexa um documento criando embeddings para cada chunk."""
        if not content:
            return 0

        # Limpar embeddings antigos
        self.db.execute(text("DELETE FROM document_embeddings WHERE document_id = :doc_id"), {"doc_id": document_id})

        chunks = self.chunk_text(content)
        indexed = 0

        for i, chunk in enumerate(chunks):
            if not chunk:
                continue

            embedding = self.generate_embedding(chunk)
            if not embedding:
                continue

            # Inserir embedding como texto (cast para vector será feito na busca)
            emb_str = str(embedding)
            self.db.execute(
                text(
                    """
                    INSERT INTO document_embeddings (document_id, chunk_index, chunk_text, embedding)
                    VALUES (:doc_id, :idx, :text, :emb)
                """
                ),
                {"doc_id": document_id, "idx": i, "text": chunk, "emb": emb_str},
            )
            indexed += 1

        self.db.commit()
        logger.info(f"Documento {document_id} indexado com {indexed} chunks")
        return indexed

    def search_similar(self, user_id: int, query: str, limit: int = 5, threshold: float = 0.7) -> List[Dict[str, Any]]:
        """Busca chunks similares à query usando similaridade de cosseno."""
        try:
            query_embedding = self.generate_query_embedding(query)
            if not query_embedding:
                return []

            # Buscar usando pgvector com filtro por usuário
            query_emb_str = str(query_embedding)
            result = self.db.execute(
                text(
                    f"""
                    SELECT 
                        de.chunk_text,
                        de.chunk_index,
                        d.id as document_id,
                        d.title,
                        d.category,
                        1 - (de.embedding::vector(768) <=> '{query_emb_str}'::vector(768)) as similarity
                    FROM document_embeddings de
                    JOIN documents d ON de.document_id = d.id
                    WHERE d.user_id = :user_id 
                        AND d.send_to_ai = true 
                        AND d.is_active = true
                        AND de.embedding IS NOT NULL
                    ORDER BY de.embedding::vector(768) <=> '{query_emb_str}'::vector(768)
                    LIMIT :limit
                """
                ),
                {"user_id": user_id, "limit": limit},
            )

            results = []
            for row in result:
                if row.similarity >= threshold:
                    results.append(
                        {
                            "chunk_text": row.chunk_text,
                            "document_id": row.document_id,
                            "title": row.title,
                            "category": row.category,
                            "similarity": float(row.similarity),
                            "chunk_index": row.chunk_index,
                        }
                    )

            return results
        except Exception as e:
            logger.warning(f"Erro na busca semântica: {e}")
            self.db.rollback()
            return []

    def get_relevant_context(self, user_id: int, query: str, max_tokens: int = 2000) -> str:
        """Retorna contexto relevante dos documentos para a query."""
        similar_chunks = self.search_similar(user_id, query, limit=5, threshold=0.5)

        if not similar_chunks:
            return ""

        context_parts = ["CONTEXTO DOS DOCUMENTOS DO USUÁRIO:"]
        total_chars = 0
        max_chars = max_tokens * 4  # Aproximação

        for chunk in similar_chunks:
            chunk_text = chunk["chunk_text"]
            if total_chars + len(chunk_text) > max_chars:
                break

            context_parts.append(f"\n📄 **{chunk['title']}** (relevância: {chunk['similarity']:.0%}):\n{chunk_text}")
            total_chars += len(chunk_text)

        return "\n".join(context_parts)


class ClassificationCacheService:
    """Cache de classificações para evitar chamadas repetidas à LLM."""

    def __init__(self, db: Session):
        self.db = db

    def _hash_message(self, message: str) -> str:
        """Gera hash do texto normalizado."""
        normalized = message.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:64]

    def get_cached(self, message: str) -> Optional[Dict[str, Any]]:
        """Busca classificação no cache."""
        try:
            msg_hash = self._hash_message(message)

            result = self.db.execute(
                text(
                    """
                    UPDATE classification_cache 
                    SET hit_count = hit_count + 1, last_used_at = :now
                    WHERE message_hash = :hash
                    RETURNING intent, confidence, entities
                """
                ),
                {"hash": msg_hash, "now": utc_now()},
            )

            row = result.fetchone()
            if row:
                self.db.commit()
                logger.debug(f"Cache hit para classificação: {msg_hash[:8]}...")
                return {"intent": row.intent, "confidence": row.confidence, "entities": row.entities or {}}

            return None
        except Exception as e:
            logger.warning(f"Erro ao buscar cache: {e}")
            self.db.rollback()
            return None

    def cache_classification(self, message: str, intent: str, confidence: float, entities: Dict = None) -> None:
        """Salva classificação no cache."""
        msg_hash = self._hash_message(message)

        try:
            self.db.execute(
                text(
                    """
                    INSERT INTO classification_cache (message_hash, intent, confidence, entities)
                    VALUES (:hash, :intent, :confidence, :entities::jsonb)
                    ON CONFLICT (message_hash) DO UPDATE SET
                        intent = :intent,
                        confidence = :confidence,
                        entities = :entities::jsonb,
                        hit_count = classification_cache.hit_count + 1,
                        last_used_at = :now
                """
                ),
                {
                    "hash": msg_hash,
                    "intent": intent,
                    "confidence": confidence,
                    "entities": json.dumps(entities or {}),
                    "now": utc_now(),
                },
            )
            self.db.commit()
            logger.debug(f"Classificação cacheada: {msg_hash[:8]}...")
        except Exception as e:
            logger.error(f"Erro ao cachear classificação: {e}")
            self.db.rollback()

    def cleanup_old_entries(self, days: int = 30) -> int:
        """Remove entradas antigas do cache."""
        result = self.db.execute(
            text(
                """
                DELETE FROM classification_cache 
                WHERE last_used_at < NOW() - INTERVAL ':days days'
                RETURNING id
            """
            ),
            {"days": days},
        )
        count = result.rowcount
        self.db.commit()
        return count


class AgentMetricsService:
    """Serviço para tracking de métricas dos agentes."""

    def __init__(self, db: Session):
        self.db = db

    def log_action(
        self,
        user_id: int,
        agent_name: str,
        action_type: str,
        success: bool,
        confidence: float = None,
        response_time_ms: int = None,
    ) -> None:
        """Registra uma ação de agente."""
        try:
            self.db.execute(
                text(
                    """
                    INSERT INTO agent_metrics 
                    (user_id, agent_name, action_type, success, confidence, response_time_ms)
                    VALUES (:user_id, :agent, :action, :success, :conf, :time)
                """
                ),
                {
                    "user_id": user_id,
                    "agent": agent_name,
                    "action": action_type,
                    "success": success,
                    "conf": confidence,
                    "time": response_time_ms,
                },
            )
            self.db.commit()
        except Exception as e:
            logger.error(f"Erro ao registrar métrica: {e}")
            self.db.rollback()

    def get_accuracy_by_agent(self, days: int = 30) -> Dict[str, Dict[str, Any]]:
        """Retorna accuracy por agente."""
        result = self.db.execute(
            text(
                """
                SELECT 
                    agent_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
                    AVG(confidence) as avg_confidence,
                    AVG(response_time_ms) as avg_response_time
                FROM agent_metrics
                WHERE created_at > NOW() - INTERVAL ':days days'
                GROUP BY agent_name
            """
            ),
            {"days": days},
        )

        metrics = {}
        for row in result:
            metrics[row.agent_name] = {
                "total": row.total,
                "successes": row.successes,
                "accuracy": (row.successes / row.total * 100) if row.total > 0 else 0,
                "avg_confidence": float(row.avg_confidence) if row.avg_confidence else 0,
                "avg_response_time_ms": float(row.avg_response_time) if row.avg_response_time else 0,
            }

        return metrics

    def get_user_stats(self, user_id: int, days: int = 30) -> Dict[str, Any]:
        """Retorna estatísticas de um usuário."""
        result = self.db.execute(
            text(
                """
                SELECT 
                    agent_name,
                    action_type,
                    COUNT(*) as count,
                    SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes
                FROM agent_metrics
                WHERE user_id = :user_id 
                    AND created_at > NOW() - INTERVAL ':days days'
                GROUP BY agent_name, action_type
                ORDER BY count DESC
            """
            ),
            {"user_id": user_id, "days": days},
        )

        stats = {"by_agent": {}, "total_actions": 0, "total_successes": 0}
        for row in result:
            if row.agent_name not in stats["by_agent"]:
                stats["by_agent"][row.agent_name] = {}

            stats["by_agent"][row.agent_name][row.action_type] = {"count": row.count, "successes": row.successes}
            stats["total_actions"] += row.count
            stats["total_successes"] += row.successes

        return stats


class FeedbackService:
    """Serviço para gerenciar feedback do usuário."""

    def __init__(self, db: Session):
        self.db = db

    def save_feedback(
        self,
        user_id: int,
        feedback_type: str,
        rating: int = None,
        agent_name: str = None,
        message_id: int = None,
        comment: str = None,
        context: Dict = None,
    ) -> bool:
        """Salva feedback do usuário."""
        try:
            self.db.execute(
                text(
                    """
                    INSERT INTO user_feedback 
                    (user_id, feedback_type, rating, agent_name, message_id, comment, context)
                    VALUES (:user_id, :type, :rating, :agent, :msg_id, :comment, :context)
                """
                ),
                {
                    "user_id": user_id,
                    "type": feedback_type,
                    "rating": rating,
                    "agent": agent_name,
                    "msg_id": message_id,
                    "comment": comment,
                    "context": context or {},
                },
            )
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar feedback: {e}")
            self.db.rollback()
            return False

    def get_feedback_summary(self, days: int = 30) -> Dict[str, Any]:
        """Retorna resumo de feedbacks."""
        result = self.db.execute(
            text(
                """
                SELECT 
                    feedback_type,
                    agent_name,
                    AVG(rating) as avg_rating,
                    COUNT(*) as count
                FROM user_feedback
                WHERE created_at > NOW() - INTERVAL ':days days'
                GROUP BY feedback_type, agent_name
            """
            ),
            {"days": days},
        )

        summary = {"by_type": {}, "by_agent": {}}
        for row in result:
            if row.feedback_type not in summary["by_type"]:
                summary["by_type"][row.feedback_type] = {"count": 0, "avg_rating": 0}
            summary["by_type"][row.feedback_type]["count"] += row.count

            if row.agent_name:
                if row.agent_name not in summary["by_agent"]:
                    summary["by_agent"][row.agent_name] = {"count": 0, "ratings": []}
                summary["by_agent"][row.agent_name]["count"] += row.count
                if row.avg_rating:
                    summary["by_agent"][row.agent_name]["ratings"].append(float(row.avg_rating))

        # Calcular médias
        for agent, data in summary["by_agent"].items():
            if data["ratings"]:
                data["avg_rating"] = sum(data["ratings"]) / len(data["ratings"])
            del data["ratings"]

        return summary
