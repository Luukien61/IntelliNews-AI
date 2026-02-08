-- PostgreSQL Schema for IntelliNews AI Service
-- Stores AI processing results (TTS audio, summaries)

-- News AI Results table - stores AI processing results for news items
CREATE TABLE IF NOT EXISTS news_ai_results (
    id BIGSERIAL PRIMARY KEY,
    news_id BIGINT NOT NULL UNIQUE,  -- Reference to news_items.id in news-service
    
    -- Audio files stored in MinIO (minimum 2 voices)
    -- Format: [
    --   {"voice_id": "Doan", "description": "Giọng nam miền Bắc", "url": "...", "s3_key": "..."},
    --   {"voice_id": "Ly", "description": "Giọng nữ miền Nam", "url": "...", "s3_key": "..."}
    -- ]
    audio_files JSONB NOT NULL DEFAULT '[]',
    
    -- Summaries (moved from news-service)
    summary_short TEXT,
    summary_medium TEXT,
    summary_default TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_news_ai_results_news_id ON news_ai_results(news_id);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_news_ai_results_updated_at
    BEFORE UPDATE ON news_ai_results
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
