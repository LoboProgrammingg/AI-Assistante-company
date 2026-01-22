-- Migração: Alterar coluna embedding de TEXT para VECTOR(768)
-- Data: Janeiro 2026
-- Motivo: Corrigir erro "cannot cast type json to vector"

-- 1. Garantir que a extensão pgvector está habilitada
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Fazer backup dos dados existentes (opcional - execute manualmente se necessário)
-- CREATE TABLE document_embeddings_backup AS SELECT * FROM document_embeddings;

-- 3. Limpar embeddings inválidos (que estão em formato incorreto)
-- Os embeddings antigos estavam em formato Python str() que não é compatível com pgvector
UPDATE document_embeddings SET embedding = NULL WHERE embedding IS NOT NULL;

-- 4. Alterar o tipo da coluna para vector(768)
-- Nota: Isso só funciona se os dados forem NULL ou estiverem em formato correto
ALTER TABLE document_embeddings 
ALTER COLUMN embedding TYPE vector(768) 
USING NULL;

-- 5. Criar índice para busca vetorial eficiente (opcional mas recomendado)
CREATE INDEX IF NOT EXISTS idx_document_embeddings_vector 
ON document_embeddings 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 6. Após a migração, re-indexar todos os documentos:
-- python -c "
-- from app.database import SessionLocal
-- from app.services.embedding_service import EmbeddingService
-- from app.models import Document
-- 
-- db = SessionLocal()
-- service = EmbeddingService(db)
-- documents = db.query(Document).filter(Document.send_to_ai == True).all()
-- for doc in documents:
--     if doc.extracted_content:
--         service.index_document(doc.id, doc.extracted_content)
--         print(f'Re-indexado: {doc.title}')
-- db.close()
-- "
