-- Migration: Add Meeting Transcription Tables
-- Description: Adiciona tabelas para gravação e transcrição de reuniões
-- Date: 2026-01-27

-- Adicionar novas colunas na tabela meetings
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS google_event_id VARCHAR(255);
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS meet_url VARCHAR(500);
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS start_time TIMESTAMP WITH TIME ZONE;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS end_time TIMESTAMP WITH TIME ZONE;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS record_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'not_recorded';
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS error_message TEXT;

-- Criar índice para google_event_id
CREATE INDEX IF NOT EXISTS idx_meetings_google_event_id ON meetings(google_event_id);
CREATE INDEX IF NOT EXISTS idx_meetings_user_status ON meetings(user_id, status);

-- Criar tabela meeting_sessions
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
);

CREATE INDEX IF NOT EXISTS idx_meeting_sessions_meeting_id ON meeting_sessions(meeting_id);
CREATE INDEX IF NOT EXISTS idx_meeting_sessions_status ON meeting_sessions(status);

-- Criar tabela meeting_chunks
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
);

CREATE INDEX IF NOT EXISTS idx_meeting_chunks_session_id ON meeting_chunks(session_id);
CREATE INDEX IF NOT EXISTS idx_meeting_chunks_session_index ON meeting_chunks(session_id, chunk_index);

-- Criar tabela meeting_artifacts
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
);

CREATE INDEX IF NOT EXISTS idx_meeting_artifacts_meeting_id ON meeting_artifacts(meeting_id);

-- Comentários
COMMENT ON TABLE meeting_sessions IS 'Sessões de gravação de reuniões';
COMMENT ON TABLE meeting_chunks IS 'Chunks de áudio de uma sessão de gravação';
COMMENT ON TABLE meeting_artifacts IS 'Artefatos gerados (transcrição, resumo) de uma reunião';
COMMENT ON COLUMN meetings.status IS 'Status: not_recorded, recording, uploading, processing, ready, failed';
COMMENT ON COLUMN meeting_sessions.source_type IS 'Origem: realtime, manual_upload';
