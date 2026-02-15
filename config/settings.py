from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env.production",
        env_file_encoding="utf-8",
        case_sensitive=False
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
    tts_model_repo: str = "pnnbao-ump/VieNeu-TTS-0.3B-q8-gguf"
    tts_output_dir: str = "outputs/tts"
    default_tts_voice: str = "Doan"  # Options: Binh, Tuyen, Vinh, Doan, Ly, Ngoc
    
    # S3 Storage Configuration (MinIO hoặc S3-compatible; endpoint 8333 = MinIO trong docker)
    s3_endpoint_url: str = "http://localhost:8333"
    s3_access_key: str  # MINIO_ROOT_USER
    s3_secret_key: str  # MINIO_ROOT_PASSWORD
    s3_bucket_name: str = "audio-files"
    s3_audio_prefix: str = "tts"  # Prefix for TTS files in bucket
    
    # Database Configuration (PostgreSQL for AI results)
    database_url: str = "postgresql://ai_user:ai_password@localhost:5436/intellinews_ai"
    
    # News Service Configuration (for fetching news content)
    news_service_url: str = "http://localhost:8081"
    news_service_timeout: int = 30  # seconds
    
    # Recommendation Configuration
    recommendation_model_path: str = ""
    recommendation_cache_ttl: int = 3600  # Redis cache TTL in seconds (1 hour)
    recommendation_top_k: int = 10  # Default number of recommendations
    
    # Redis Configuration (for recommendation caching)
    redis_url: str = "redis://localhost:6379/0"
    
    # Summarization Configuration
    phobert_model_name: str = "vinai/phobert-base"
    vit5_model_name: str = "VietAI/vit5-base-vietnews-summarization"
    
    @property
    def tts_output_path(self) -> Path:
        """Get TTS output directory as Path object."""
        path = Path(self.tts_output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global settings instance
settings = Settings()
