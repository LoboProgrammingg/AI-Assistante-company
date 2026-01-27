"""
Migrations manuais para o projeto.

Como o projeto não usa Alembic, este módulo contém funções para
aplicar alterações incrementais no schema do banco de dados.

O SQLAlchemy create_all() só cria tabelas novas, não altera existentes.
Este módulo complementa isso adicionando colunas e índices faltantes.
"""

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def run_migrations(engine: Engine) -> None:
    """Executa todas as migrations pendentes."""
    logger.info("[MIGRATIONS] Verificando migrations pendentes...")
    
    with engine.connect() as conn:
        # Migration: Meeting transcription columns
        _migrate_meeting_transcription(conn)
        
        conn.commit()
    
    logger.info("[MIGRATIONS] Migrations concluídas")


def _migrate_meeting_transcription(conn) -> None:
    """Adiciona colunas de transcrição na tabela meetings."""
    
    # Verificar se a coluna google_event_id existe
    result = conn.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'meetings' AND column_name = 'google_event_id'
    """))
    
    if result.fetchone() is None:
        logger.info("[MIGRATIONS] Aplicando migration: meeting_transcription_columns")
        
        # Adicionar colunas na tabela meetings
        migrations = [
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS google_event_id VARCHAR(255)",
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS meet_url VARCHAR(500)",
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS description TEXT",
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS start_time TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS end_time TIMESTAMP WITH TIME ZONE",
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS record_enabled BOOLEAN DEFAULT FALSE",
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'not_recorded'",
            "ALTER TABLE meetings ADD COLUMN IF NOT EXISTS error_message TEXT",
        ]
        
        for sql in migrations:
            try:
                conn.execute(text(sql))
                logger.info(f"[MIGRATIONS] ✅ {sql[:60]}...")
            except Exception as e:
                logger.warning(f"[MIGRATIONS] ⚠️ {sql[:40]}... - {e}")
        
        # Criar índices
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_meetings_google_event_id ON meetings(google_event_id)",
            "CREATE INDEX IF NOT EXISTS idx_meetings_user_status ON meetings(user_id, status)",
        ]
        
        for sql in indices:
            try:
                conn.execute(text(sql))
            except Exception as e:
                logger.warning(f"[MIGRATIONS] ⚠️ Index: {e}")
        
        logger.info("[MIGRATIONS] ✅ meeting_transcription_columns aplicada")
    else:
        logger.info("[MIGRATIONS] meeting_transcription_columns já aplicada")


def _check_and_create_tables(conn) -> None:
    """Cria tabelas auxiliares se não existirem."""
    
    # meeting_sessions
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS meeting_sessions (
            id SERIAL PRIMARY KEY,
            meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
            source_type VARCHAR(50) DEFAULT 'realtime',
            status VARCHAR(50) DEFAULT 'recording',
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            ended_at TIMESTAMP WITH TIME ZONE,
            storage_path VARCHAR(500),
            assembled_audio_path VARCHAR(500),
            file_size_bytes INTEGER,
            duration_seconds INTEGER,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # meeting_chunks
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS meeting_chunks (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES meeting_sessions(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            file_path VARCHAR(500) NOT NULL,
            file_size_bytes INTEGER,
            start_ms INTEGER,
            end_ms INTEGER,
            duration_ms INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # meeting_artifacts
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS meeting_artifacts (
            id SERIAL PRIMARY KEY,
            meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
            transcript_text TEXT,
            transcript_language VARCHAR(10) DEFAULT 'pt-BR',
            transcript_confidence INTEGER,
            summary_json JSONB,
            executive_summary TEXT,
            short_summary VARCHAR(500),
            topics JSONB DEFAULT '[]',
            action_items JSONB DEFAULT '[]',
            decisions JSONB DEFAULT '[]',
            risks_blockers JSONB DEFAULT '[]',
            timestamps JSONB DEFAULT '[]',
            participants_detected JSONB DEFAULT '[]',
            transcription_model VARCHAR(100),
            summarization_model VARCHAR(100),
            processing_time_seconds INTEGER,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """))
    
    # Índices
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_meeting_sessions_meeting_id ON meeting_sessions(meeting_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_meeting_sessions_status ON meeting_sessions(status)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_meeting_chunks_session_id ON meeting_chunks(session_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS idx_meeting_artifacts_meeting_id ON meeting_artifacts(meeting_id)"))
