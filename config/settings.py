from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
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
    
    # Recommendation Configuration (Placeholder)
    recommendation_model_path: str = ""
    
    # Summarization Configuration (Placeholder)
    summarization_model_path: str = ""
    
    @property
    def tts_output_path(self) -> Path:
        """Get TTS output directory as Path object."""
        path = Path(self.tts_output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


# Global settings instance
settings = Settings()
