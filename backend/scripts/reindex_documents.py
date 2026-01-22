#!/usr/bin/env python3
"""
Script para re-indexar todos os documentos do sistema.
Executar após a migração da coluna embedding para tipo vector(768).

Uso:
    cd backend
    python scripts/reindex_documents.py
"""

import logging
import sys
from pathlib import Path

# Adicionar o diretório backend ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import Document
from app.services.embedding_service import EmbeddingService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def reindex_all_documents():
    """Re-indexa todos os documentos que devem ser enviados para a IA."""
    db = SessionLocal()
    
    try:
        service = EmbeddingService(db)
        
        # Buscar documentos ativos com send_to_ai = True
        documents = (
            db.query(Document)
            .filter(Document.send_to_ai == True, Document.is_active == True)
            .all()
        )
        
        logger.info(f"Encontrados {len(documents)} documentos para re-indexar")
        
        success_count = 0
        error_count = 0
        
        for doc in documents:
            try:
                content = doc.extracted_content or ""
                if not content:
                    logger.warning(f"Documento {doc.id} ({doc.title}) sem conteúdo extraído")
                    continue
                
                chunks_indexed = service.index_document(doc.id, content)
                logger.info(f"✅ Re-indexado: {doc.title} ({chunks_indexed} chunks)")
                success_count += 1
                
            except Exception as e:
                logger.error(f"❌ Erro ao re-indexar documento {doc.id}: {e}")
                error_count += 1
        
        logger.info(f"\n=== RESUMO ===")
        logger.info(f"Sucesso: {success_count}")
        logger.info(f"Erros: {error_count}")
        logger.info(f"Total: {len(documents)}")
        
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Iniciando re-indexação de documentos...")
    reindex_all_documents()
    logger.info("Re-indexação concluída!")
