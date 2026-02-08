import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session

from db.database import get_db
from services.tts import (
    TTSRequest, TTSResponse, AudioInfo, NewsTTSResponse,
    tts_service, news_tts_service, AVAILABLE_VOICES
)

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


@router.post("/news/{news_id}", response_model=NewsTTSResponse)
async def generate_tts_for_news(
    news_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate TTS audio for a news article.
    
    This endpoint:
    1. Checks if TTS audio already exists in database (cache)
    2. If cached, returns existing audio links immediately
    3. If not cached, fetches content from news-service
    4. Generates audio for multiple voices (male and female)
    5. Uploads to MinIO and saves to database
    
    Args:
        db:
        news_id: ID of the news article from news-service
        
    Returns:
        NewsTTSResponse with list of audio files and their descriptions
    """
    try:
        logger.info(f"Received TTS request for news_id={news_id}")
        
        # Generate or get cached audio
        audio_files, cached = await news_tts_service.get_or_generate_audio(
            news_id=news_id,
            db=db
        )
        
        # Convert to AudioInfo models
        audio_info_list = [
            AudioInfo(
                voice_id=af.get("voice_id"),
                description=af.get("description"),
                url=af.get("url"),
                s3_key=af.get("s3_key"),
                presigned_url=af.get("presigned_url"),
                filename=af.get("filename")
            )
            for af in audio_files
        ]
        
        message = "Trả về từ cache" if cached else "Đã tạo audio thành công"
        
        return NewsTTSResponse(
            news_id=news_id,
            audio_files=audio_info_list,
            cached=cached,
            message=message
        )
        
    except ValueError as e:
        logger.warning(f"News item not found: {e}")
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except RuntimeError as e:
        logger.error(f"TTS generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi tạo audio: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error in news TTS: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi không xác định: {str(e)}"
        )


@router.get("/news/{news_id}", response_model=NewsTTSResponse)
async def get_news_audio(
    news_id: int,
    db: Session = Depends(get_db)
):
    """
    Get cached TTS audio for a news article (without generating if not exists).
    
    Args:
        db:
        news_id: ID of the news article
        
    Returns:
        NewsTTSResponse with cached audio files or 404 if not found
    """
    cached_audio = news_tts_service.get_cached_audio(news_id=news_id, db=db)
    
    if not cached_audio:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy audio cho bài viết {news_id}. Sử dụng POST để tạo mới."
        )
    
    audio_info_list = [
        AudioInfo(
            voice_id=af.get("voice_id"),
            description=af.get("description"),
            url=af.get("url"),
            s3_key=af.get("s3_key"),
            presigned_url=af.get("presigned_url"),
            filename=af.get("filename")
        )
        for af in cached_audio
    ]
    
    return NewsTTSResponse(
        news_id=news_id,
        audio_files=audio_info_list,
        cached=True,
        message="Trả về từ cache"
    )


@router.delete("/news/{news_id}")
async def delete_news_audio(
    news_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete cached TTS audio for a news article.
    
    Args:
        db:
        news_id: ID of the news article
        
    Returns:
        Success message or 404 if not found
    """
    deleted = news_tts_service.delete_audio(news_id=news_id, db=db)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy audio cho bài viết {news_id}"
        )
    
    return {"message": f"Đã xóa audio cho bài viết {news_id}"}


@router.get("/news/voices/available")
async def get_available_news_voices():
    """
    Get list of voices used for news TTS generation.
    
    Returns:
        List of available voices with IDs and descriptions
    """
    return {
        "voices": AVAILABLE_VOICES
    }

