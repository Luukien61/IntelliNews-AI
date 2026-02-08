import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path

from services.tts import TTSRequest, TTSResponse, tts_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["TTS"])


@router.get("/voices")
async def list_voices():
    """
    List all available preset voices.
    
    Returns:
        List of available voices with their IDs and descriptions
    """
    try:
        voices = tts_service.list_voices()
        return {
            "voices": [
                {"description": desc, "voice_id": voice_id}
                for desc, voice_id in voices
            ]
        }
    except Exception as e:
        logger.error(f"Failed to list voices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list voices: {str(e)}"
        )


@router.post("/generate", response_model=TTSResponse)
async def generate_speech(request: TTSRequest):
    """
    Generate speech from text using VieNeu TTS.
    
    Args:
        request: TTS generation request with text, optional voice_id, and optional voice cloning parameters
        
    Returns:
        Response with audio file information and download URL
    """
    try:
        logger.info(f"Received TTS request for text: {request.text[:50]}...")
        if request.voice_id:
            logger.info(f"Using voice: {request.voice_id}")
        
        # Generate speech
        file_path = tts_service.synthesize(
            text=request.text,
            voice_id=request.voice_id,
            ref_audio=request.ref_audio,
            ref_text=request.ref_text
        )
        
        # Extract filename from path
        filename = Path(file_path).name
        download_url = f"/api/tts/audio/{filename}"
        
        return TTSResponse(
            success=True,
            filename=filename,
            file_path=file_path,
            download_url=download_url,
            message="Audio generated successfully"
        )
        
    except Exception as e:
        logger.error(f"TTS generation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate speech: {str(e)}"
        )


@router.get("/audio/{filename}")
async def get_audio_file(filename: str):
    """
    Download generated audio file.
    
    Args:
        filename: Name of the audio file
        
    Returns:
        Audio file as FileResponse
    """
    try:
        file_path = tts_service.get_audio_path(filename)
        
        if not file_path:
            raise HTTPException(
                status_code=404,
                detail=f"Audio file not found: {filename}"
            )
        
        return FileResponse(
            path=file_path,
            media_type="audio/wav",
            filename=filename
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve audio file: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve audio file: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """Check TTS service health."""
    return {
        "status": "healthy",
        "service": "TTS",
        "model": "VieNeu-TTS-0.3B-q8-gguf"
    }
