import logging
import os
from typing import List, Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models import User
from app.schemas.document import (
    DocumentCategoryEnum,
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentStatsResponse,
    DocumentUpdate,
)
from app.services.document_service import DocumentService
from app.services.embedding_service import EmbeddingService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".doc", ".docx", ".md", ".csv", ".json", ".xml"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_file(file: UploadFile) -> None:
    """Valida arquivo de upload."""
    import os

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tipo de arquivo não permitido. Permitidos: {', '.join(ALLOWED_EXTENSIONS)}",
        )


@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    category: str = Form("other"),
    tags: str = Form(""),
    send_to_ai: bool = Form(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Faz upload de um documento.
    """
    validate_file(file)

    # Ler conteúdo do arquivo
    content = await file.read()
    file_size = len(content)

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Arquivo muito grande. Máximo: {MAX_FILE_SIZE // (1024*1024)}MB",
        )

    service = DocumentService(db)

    # Gerar nome único
    filename = service.generate_filename(file.filename)
    file_path = service.get_upload_path(filename)

    # Salvar arquivo
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Criar documento
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

    try:
        category_enum = DocumentCategoryEnum(category)
    except ValueError:
        category_enum = DocumentCategoryEnum.OTHER

    data = DocumentCreate(
        title=title, description=description, category=category_enum, tags=tags_list, send_to_ai=send_to_ai
    )

    document = service.create(
        user_id=current_user.id,
        filename=filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        data=data,
    )

    # Se send_to_ai, extrair texto
    if send_to_ai:
        try:
            await extract_document_content(document.id, file_path, file.content_type, db)
        except Exception as e:
            logger.error(f"Erro ao extrair conteúdo: {e}")

    return document


@router.get("/", response_model=DocumentListResponse)
def list_documents(
    category: Optional[str] = None,
    send_to_ai: Optional[bool] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista documentos do usuário."""
    service = DocumentService(db)
    return service.list(
        user_id=current_user.id, category=category, send_to_ai=send_to_ai, search=search, page=page, limit=limit
    )


@router.get("/stats", response_model=DocumentStatsResponse)
def get_document_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retorna estatísticas de documentos."""
    service = DocumentService(db)
    return service.get_stats(current_user.id)


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Busca documento por ID."""
    service = DocumentService(db)
    document = service.get_by_id(current_user.id, document_id)

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    return document


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    token: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Faz download de um documento."""
    service = DocumentService(db)
    document = service.get_by_id(current_user.id, document_id)

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    file_path = document.file_path

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado no servidor")

    return FileResponse(
        path=file_path,
        filename=document.original_filename or document.filename,
        media_type=document.mime_type or "application/octet-stream",
    )


@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: int,
    data: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Atualiza documento."""
    service = DocumentService(db)
    document = service.update(current_user.id, document_id, data)

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    return document


@router.post("/{document_id}/toggle-ai", response_model=DocumentResponse)
def toggle_document_ai(document_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Alterna envio para IA."""
    service = DocumentService(db)
    document = service.get_by_id(current_user.id, document_id)

    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    # Verificar limite
    if not document.send_to_ai:
        ai_count = service.count_ai_documents(current_user.id)
        if ai_count >= 25:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Limite de 25 documentos para IA atingido"
            )

    data = DocumentUpdate(send_to_ai=not document.send_to_ai)
    return service.update(current_user.id, document_id, data)


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    permanent: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove documento."""
    service = DocumentService(db)

    if permanent:
        success = service.delete_permanently(current_user.id, document_id)
    else:
        success = service.delete(current_user.id, document_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado")

    return {"message": "Documento removido com sucesso"}


async def extract_document_content(document_id: int, file_path: str, mime_type: str, db: Session):
    """Extrai conteúdo de texto do documento."""
    import os

    content_text = ""

    try:
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".txt" or ext == ".md":
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content_text = await f.read()

        elif ext == ".pdf":
            try:
                import PyPDF2

                with open(file_path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        content_text += page.extract_text() or ""
            except ImportError:
                logger.warning("PyPDF2 não instalado, pulando extração de PDF")

        elif ext == ".csv":
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content_text = await f.read()

        elif ext == ".json":
            import json

            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                data = await f.read()
                content_text = json.dumps(json.loads(data), indent=2, ensure_ascii=False)

        if content_text:
            # Atualizar conteúdo no documento
            service = DocumentService(db)
            service.update_content(document_id, content_text[:50000], [])

            # Indexar com embeddings para busca semântica
            try:
                embedding_service = EmbeddingService(db)
                indexed_chunks = embedding_service.index_document(document_id, content_text)
                logger.info(f"Documento {document_id} indexado com {indexed_chunks} chunks de embedding")
            except Exception as emb_error:
                logger.error(f"Erro ao indexar embeddings do documento {document_id}: {emb_error}")

    except Exception as e:
        logger.error(f"Erro ao extrair conteúdo do documento {document_id}: {e}")
        # Marcar como falha
        document = db.query(Document).filter(Document.id == document_id).first()
        if document:
            document.embedding_status = "failed"
            db.commit()
