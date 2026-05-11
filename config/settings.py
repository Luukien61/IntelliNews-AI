from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
import multiprocessing

def get_default_cores() -> int:
    return max(1, multiprocessing.cpu_count() // 2)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore' # Allow extra environment variables
    )
    
    # Server Configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    api_prefix: str = "/api"
    
    # Application
    app_name: str = "IntelliNews AI Service"
    app_version: str = "0.1.0"
    debug: bool = True
    
    # TTS Configuration
    default_tts_voice: str = "Trang"
    tts_event_audio_key: str = "filename"  # The key to extract from audioFiles in TTS completed event
    
    # S3 Storage Configuration (MinIO hoặc S3-compatible; endpoint 8333 = MinIO trong docker)
    cloudfront_url: str = "https://d213zhtaqpkk71.cloudfront.net"
    
    # Database Configuration (PostgreSQL for AI results)
    database_url: str = "postgresql://ai_user:ai_password@localhost:5436/intellinews_ai"
    
    # News Service Configuration (for fetching news content)
    news_service_url: str = "http://localhost:8081"
    news_service_timeout: int = 30  # seconds
    
    # Recommendation Configuration
    recommendation_model_path: str = ""
    recommendation_cache_ttl: int = 3600  # Redis cache TTL in seconds (1 hour)
    recommendation_top_k: int = 10  # Default number of recommendations
    # Recency boost: final = (1 - weight) * similarity + weight * exp(-lambda * hours_old)
    # weight=0.0 → pure similarity; weight=1.0 → pure recency
    # lambda=0.1 → half-life ≈ 13.9h (article loses half its recency score after ~13.9h)
    recommendation_recency_weight: float = 0.2
    recommendation_recency_decay_lambda: float = 0.05

    # Redis Configuration (for recommendation caching)
    redis_url: str = "redis://localhost:6379/0"
    
    # Summarization Configuration
    phobert_model_name: str = "vinai/phobert-base"
    vit5_model_name: str = "VietAI/vit5-base-vietnews-summarization"
    # ViT5 min output length (90 or 128 characters)
    vit5_min_length: int = 90  # Minimum length for ViT5 generated summaries
    # Ratio of sentences to keep per summary type:
    # summary_short  → ViT5 abstractive (min 128/90 chars, configurable)
    # summary_default → PhoBERT extractive (0.3 ≈ 3 sentences)
    summarization_short_ratio: float = 0.2
    summarization_default_ratio: float = 0.3

    # Embedding Model Configuration (for recommendation & clustering)
    embedding_model_name: str = "bkai-foundation-models/vietnamese-bi-encoder"
    
    # Kafka Configuration
    kafka_bootstrap_servers: str = "localhost:29092"
    kafka_group_id: str = "ai-service-group"
    kafka_topic_news_fetched: str = "news.fetched-events"
    kafka_topic_tts_completed: str = "tts.completed-events"
    kafka_topic_ai_processed: str = "news.ai-processed-events"  # Emitted when ALL AI tasks are done
    kafka_auto_offset_reset: str = "latest"
    kafka_event_concurrency: bool = True
    
    # AI Processing Configuration
    ai_process_parallel: bool = True
    ai_process_max_workers: int = 4
    ai_max_cores: int = Field(default_factory=get_default_cores)

    
    @property
    def tts_output_path(self) -> Path:
        """Get TTS output directory as Path object."""
        path = Path(self.tts_output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global settings instance
settings = Settings()
