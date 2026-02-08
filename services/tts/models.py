from pydantic import BaseModel, Field
from typing import List, Optional


class TTSRequest(BaseModel):
    """Request model for TTS generation."""
    
    text: str = Field(
        ...,
        description="Text to convert to speech",
        min_length=1,
        max_length=5000
    )
    voice_id: Optional[str] = Field(
        None,
        description="ID of the preset voice to use (e.g., 'Binh', 'Doan'). If not provided, uses the first available voice."
    )
    ref_audio: Optional[str] = Field(
        None,
        description="Path to reference audio for voice cloning"
    )
    ref_text: Optional[str] = Field(
        None,
        description="Text spoken in reference audio"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "text": "Xin chào, tôi là trợ lý AI của IntelliNews.",
                "voice_id": "Doan"
            }
        }


class TTSResponse(BaseModel):
    """Response model for TTS generation."""
    
    success: bool = Field(..., description="Whether generation was successful")
    filename: str = Field(..., description="Generated audio filename")
    file_path: str = Field(..., description="Full path to generated audio file")
    download_url: str = Field(..., description="URL to download the audio file")
    message: str = Field(default="", description="Additional message or error details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "filename": "tts_20260207_224000_abc123.wav",
                "file_path": "outputs/tts/tts_20260207_224000_abc123.wav",
                "download_url": "/api/tts/audio/tts_20260207_224000_abc123.wav",
                "message": "Audio generated successfully"
            }
        }


class AudioInfo(BaseModel):
    """Information about a generated audio file."""
    
    voice_id: str = Field(..., description="ID of the voice used (e.g., 'Doan', 'Ly')")
    description: str = Field(..., description="Human-readable voice description (e.g., 'Giọng nam miền Bắc')")
    url: Optional[str] = Field(None, description="Public URL to the audio file in MinIO")
    s3_key: Optional[str] = Field(None, description="S3 object key in MinIO bucket")
    presigned_url: Optional[str] = Field(None, description="Presigned URL with temporary access")
    filename: Optional[str] = Field(None, description="Original filename of the audio file")
    
    class Config:
        json_schema_extra = {
            "example": {
                "voice_id": "Doan",
                "description": "Giọng nam miền Bắc",
                "url": "http://localhost:8333/audio-files/tts/abc123.wav",
                "s3_key": "tts/abc123.wav",
                "presigned_url": "http://localhost:8333/audio-files/tts/abc123.wav?...",
                "filename": "tts_20260207_224000_abc123.wav"
            }
        }


class NewsTTSResponse(BaseModel):
    """Response model for news article TTS generation."""
    
    news_id: int = Field(..., description="ID of the news article")
    audio_files: List[AudioInfo] = Field(..., description="List of generated audio files for different voices")
    cached: bool = Field(default=False, description="Whether the result was retrieved from cache")
    message: str = Field(default="", description="Additional information or status message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "news_id": 123,
                "audio_files": [
                    {
                        "voice_id": "Doan",
                        "description": "Giọng nam miền Bắc",
                        "url": "http://localhost:8333/audio-files/tts/news_123_doan.wav"
                    },
                    {
                        "voice_id": "Ly",
                        "description": "Giọng nữ miền Nam",
                        "url": "http://localhost:8333/audio-files/tts/news_123_ly.wav"
                    }
                ],
                "cached": False,
                "message": "Audio generated successfully"
            }
        }

