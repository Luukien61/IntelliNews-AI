-- PostgreSQL Schema for IntelliNews AI Service
-- Stores AI processing results (TTS audio, summaries)

-- News AI Results table - stores AI processing results for news items
CREATE TABLE IF NOT EXISTS news_ai_results
(
    id              BIGSERIAL PRIMARY KEY,
    news_id         BIGINT NOT NULL UNIQUE, -- Reference to news_items.id in news-service

    -- Audio files stored in MinIO (minimum 2 voices)
    -- Format: [
    --   {"voice_id": "Doan", "description": "Giọng nam miền Bắc", "url": "...", "s3_key": "..."},
    --   {"voice_id": "Ly", "description": "Giọng nữ miền Nam", "url": "...", "s3_key": "..."}
    -- ]
    audio_files     JSONB  NOT NULL DEFAULT '[]',

    -- Summaries (moved from news-service)
    summary_short   TEXT,
    summary_medium  TEXT,
    summary_default TEXT,

    -- Metadata
    created_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_news_ai_results_news_id ON news_ai_results (news_id);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS
$$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_news_ai_results_updated_at
    BEFORE UPDATE
    ON news_ai_results
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- pgvector extension for embedding storage
-- =============================================================================
CREATE EXTENSION IF NOT EXISTS vector;

-- News Embeddings table - stores PhoBERT embeddings for content-based recommendation
CREATE TABLE IF NOT EXISTS news_embeddings
(
    id             BIGSERIAL PRIMARY KEY,
    news_id        BIGINT      NOT NULL UNIQUE, -- Reference to news_items.id in news-service
    category       VARCHAR(50) NOT NULL,        -- Cached category for filtering
    title          TEXT        NOT NULL,        -- Cached title for response
    embedding      VECTOR(768) NOT NULL,        -- PhoBERT CLS token embedding (768 dimensions)
    cluster_id     INT,                         -- Optional cluster ID for grouping similar news items
    trending_score FLOAT,                       -- Optional trending score for ranking

    -- Metadata
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at   TIMESTAMPTZ,
    updated_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_news_embeddings_news_id ON news_embeddings (news_id);
CREATE INDEX IF NOT EXISTS idx_news_embeddings_category ON news_embeddings (category);

-- IVFFlat index for fast approximate nearest neighbor search
-- Note: This index should be created AFTER inserting initial data for best performance.
-- Run manually after initial batch indexing:
-- CREATE INDEX IF NOT EXISTS idx_news_embeddings_vector ON news_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Reuse the same update trigger for news_embeddings
CREATE TRIGGER update_news_embeddings_updated_at
    BEFORE UPDATE
    ON news_embeddings
    FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

---

CREATE TABLE IF NOT EXISTS trending_clusters (
    id                  BIGSERIAL PRIMARY KEY,
    cluster_id          INT NOT NULL,
    category            VARCHAR(50) NOT NULL,
    article_count       INT NOT NULL DEFAULT 0,
    trending_score      FLOAT NOT NULL DEFAULT 0,
    primary_rep_id      BIGINT,                  -- news_id tiêu biểu dùng để lấy summary
    representative_ids  BIGINT[],                -- danh sách các news_id trong cluster
    period_start        TIMESTAMPTZ,             -- window thời gian của cluster này
    period_end          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT NOW(),

    UNIQUE (cluster_id, category)                -- mỗi cluster chỉ 1 record per category
);

CREATE INDEX IF NOT EXISTS idx_trending_clusters_score 
    ON trending_clusters (trending_score DESC);

CREATE INDEX IF NOT EXISTS idx_trending_clusters_category
    ON trending_clusters (category, trending_score DESC);
