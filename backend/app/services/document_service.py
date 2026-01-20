import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import Document, DocumentCategory
from app.schemas.document import DocumentCreate, DocumentUpdate

logger = logging.getLogger(__name__)

DOCUMENTS_UPLOAD_DIR = "/app/uploads/documents"
MAX_AI_DOCUMENTS = 25


def utc_now():
    return datetime.now(timezone.utc)


class DocumentService:
    """Serviço para gerenciamento de documentos."""

    def __init__(self, db: Session):
        self.db = db
        os.makedirs(DOCUMENTS_UPLOAD_DIR, exist_ok=True)

    def create(
        self,
        user_id: int,
        filename: str,
        original_filename: str,
        file_path: str,
        file_size: int,
        mime_type: str,
        data: DocumentCreate,
    ) -> Document:
        """Cria um novo documento."""
        # Verificar limite de documentos para IA
        if data.send_to_ai:
            ai_count = self.count_ai_documents(user_id)
            if ai_count >= MAX_AI_DOCUMENTS:
                data.send_to_ai = False
                logger.warning(f"Limite de documentos IA atingido para user {user_id}")

        document = Document(
            user_id=user_id,
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_size=file_size,
            mime_type=mime_type,
            title=data.title or original_filename,
            description=data.description,
            category=DocumentCategory(data.category.value),
            tags=data.tags,
            send_to_ai=data.send_to_ai,
            embedding_status="pending" if data.send_to_ai else "not_required",
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        logger.info(f"Documento criado: {document.id} para user {user_id}")
        return document

    def get_by_id(self, user_id: int, document_id: int) -> Optional[Document]:
        """Busca documento por ID."""
        return (
            self.db.query(Document)
            .filter(and_(Document.id == document_id, Document.user_id == user_id, Document.is_active == True))
            .first()
        )

    def list(
        self,
        user_id: int,
        category: Optional[str] = None,
        send_to_ai: Optional[bool] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Lista documentos com filtros e paginação."""
        query = self.db.query(Document).filter(and_(Document.user_id == user_id, Document.is_active == True))

        if category:
            query = query.filter(Document.category == DocumentCategory(category))

        if send_to_ai is not None:
            query = query.filter(Document.send_to_ai == send_to_ai)

        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                Document.title.ilike(search_filter)
                | Document.description.ilike(search_filter)
                | Document.original_filename.ilike(search_filter)
            )

        total = query.count()
        pages = (total + limit - 1) // limit if limit > 0 else 1
        offset = (page - 1) * limit

        items = query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()

        ai_count = self.count_ai_documents(user_id)

        return {
            "items": items,
            "total": total,
            "page": page,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1,
            "ai_count": ai_count,
            "ai_limit": MAX_AI_DOCUMENTS,
        }

    def update(self, user_id: int, document_id: int, data: DocumentUpdate) -> Optional[Document]:
        """Atualiza um documento."""
        document = self.get_by_id(user_id, document_id)
        if not document:
            return None

        update_data = data.model_dump(exclude_unset=True)

        # Verificar limite de IA se estiver ativando
        if update_data.get("send_to_ai") and not document.send_to_ai:
            ai_count = self.count_ai_documents(user_id)
            if ai_count >= MAX_AI_DOCUMENTS:
                update_data["send_to_ai"] = False
                logger.warning(f"Limite de documentos IA atingido para user {user_id}")

        for field, value in update_data.items():
            if field == "category" and value:
                value = DocumentCategory(value.value)
            setattr(document, field, value)

        # Atualizar status de embedding se necessário
        if update_data.get("send_to_ai") and document.embedding_status == "not_required":
            document.embedding_status = "pending"

        document.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(document)
        logger.info(f"Documento atualizado: {document_id}")
        return document

    def delete(self, user_id: int, document_id: int) -> bool:
        """Remove documento (soft delete)."""
        document = self.get_by_id(user_id, document_id)
        if not document:
            return False

        document.is_active = False
        document.updated_at = utc_now()
        self.db.commit()
        logger.info(f"Documento removido: {document_id}")
        return True

    def delete_permanently(self, user_id: int, document_id: int) -> bool:
        """Remove documento permanentemente."""
        document = self.get_by_id(user_id, document_id)
        if not document:
            return False

        # Remover arquivo físico
        if os.path.exists(document.file_path):
            try:
                os.remove(document.file_path)
            except Exception as e:
                logger.error(f"Erro ao remover arquivo: {e}")

        self.db.delete(document)
        self.db.commit()
        logger.info(f"Documento removido permanentemente: {document_id}")
        return True

    def count_ai_documents(self, user_id: int) -> int:
        """Conta documentos enviados para IA."""
        return (
            self.db.query(func.count(Document.id))
            .filter(and_(Document.user_id == user_id, Document.send_to_ai == True, Document.is_active == True))
            .scalar()
            or 0
        )

    def get_stats(self, user_id: int) -> Dict[str, Any]:
        """Retorna estatísticas de documentos."""
        documents = self.db.query(Document).filter(and_(Document.user_id == user_id, Document.is_active == True)).all()

        by_category = {}
        total_size = 0
        ai_count = 0

        for doc in documents:
            cat = doc.category.value if doc.category else "other"
            by_category[cat] = by_category.get(cat, 0) + 1
            total_size += doc.file_size or 0
            if doc.send_to_ai:
                ai_count += 1

        return {
            "total_documents": len(documents),
            "ai_documents": ai_count,
            "ai_limit": MAX_AI_DOCUMENTS,
            "by_category": by_category,
            "total_size_bytes": total_size,
        }

    def get_ai_documents(self, user_id: int) -> List[Document]:
        """Retorna documentos marcados para IA."""
        return (
            self.db.query(Document)
            .filter(and_(Document.user_id == user_id, Document.send_to_ai == True, Document.is_active == True))
            .order_by(Document.created_at.desc())
            .all()
        )

    def update_content(self, document_id: int, content_text: str, chunks: List[str] = None) -> bool:
        """Atualiza conteúdo extraído do documento."""
        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return False

        document.content_text = content_text
        document.content_chunks = chunks or []
        document.embedding_status = "completed"
        document.updated_at = utc_now()
        self.db.commit()
        return True

    def generate_filename(self, original_filename: str) -> str:
        """Gera nome único para arquivo."""
        ext = os.path.splitext(original_filename)[1]
        return f"{uuid.uuid4().hex}{ext}"

    def get_upload_path(self, filename: str) -> str:
        """Retorna caminho completo para upload."""
        return os.path.join(DOCUMENTS_UPLOAD_DIR, filename)
