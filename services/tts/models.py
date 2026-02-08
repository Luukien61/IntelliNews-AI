from pydantic import BaseModel, Field
from typing import Optional


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
