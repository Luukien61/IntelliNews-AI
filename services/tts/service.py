from sqlalchemy.orm import Session
from typing import Optional
from config import settings
from db.models import NewsAIResult
from .models import NewsTTSUrlResponse, AudioUrlResponse

class TTSService:
    """Service layer for TTS interactions"""
    
    def get_news_audio_urls(self, news_id: int, db: Session) -> Optional[NewsTTSUrlResponse]:
        """Get CloudFront URLs for TTS audio files of a given news article"""
        existing = db.query(NewsAIResult).filter(NewsAIResult.news_id == news_id).first()
        
        if not existing or not existing.audio_files:
            return None
            
        urls = []
        cloudfront_url = settings.cloudfront_url.rstrip('/')
        
        for audio in existing.audio_files:
            if isinstance(audio, dict):
                filename = audio.get("filename")
                voice_id = audio.get("voice_id", settings.default_tts_voice)
                description = audio.get("description", "BTV Khanh Trang")
            else:
                # Assume it's a string (filename)
                filename = str(audio)
                voice_id = settings.default_tts_voice
                description = "BTV Khanh Trang"
                
            if filename:
                if filename.startswith("http"):
                    filename = filename.split("/")[-1]
                urls.append(
                    AudioUrlResponse(
                        voice_id=voice_id,
                        description=description,
                        url=f"{cloudfront_url}/{filename}"
                    )
                )
                
        return NewsTTSUrlResponse(
            news_id=news_id,
            audio_urls=urls
        )

# Global service instance
tts_service = TTSService()
