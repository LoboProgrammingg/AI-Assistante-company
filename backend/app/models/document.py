"""
Modelos de documentos e embeddings para RAG.
"""

import enum

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.models.base import Base, utc_now


class DocumentCategory(enum.Enum):
    """Categorias de documentos."""

    WORK = "work"
    PERSONAL = "personal"
    STUDY = "study"
    FINANCE = "finance"
    HEALTH = "health"
    LEGAL = "legal"
    OTHER = "other"


class Document(Base):
    """Documentos do usuário para RAG."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Informações do arquivo
    filename = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)  # Em bytes
    mime_type = Column(String(100), nullable=True)

    # Metadados
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    category = Column(Enum(DocumentCategory), default=DocumentCategory.OTHER)
    tags = Column(JSON, default=[])

    # Conteúdo extraído para RAG
    content_text = Column(Text, nullable=True)  # Texto extraído do documento
    content_chunks = Column(JSON, default=[])  # Chunks para embedding
    embedding_status = Column(String(20), default="pending")  # pending, processing, completed, failed

    # Controle de IA
    send_to_ai = Column(Boolean, default=False)  # Se deve ser usado como contexto para IA

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    user = relationship("User", back_populates="documents")
    embeddings = relationship("DocumentEmbedding", back_populates="document", cascade="all, delete-orphan")


class DocumentEmbedding(Base):
    """Embeddings de chunks de documentos para busca vetorial."""

    __tablename__ = "document_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)

    # Chunk info
    chunk_index = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)

    # Embedding armazenado como vector(3072) do pgvector
    embedding = Column(Text, nullable=True)  # Tipo real no banco é vector(3072)

    # Timestamps
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    document = relationship("Document", back_populates="embeddings")
