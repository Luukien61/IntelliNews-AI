import logging

from db.database import get_db
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from services.tts import tts_service, NewsTTSUrlResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tts", tags=["TTS"])


@router.get("/news/{news_id}", response_model=NewsTTSUrlResponse)
async def get_news_audio_url(
    news_id: int,
    db: Session = Depends(get_db)
):
    """
    Get CloudFront URLs for TTS audio of a news article.
    """
    result = tts_service.get_news_audio_urls(news_id=news_id, db=db)
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Không tìm thấy audio cho bài viết {news_id}"
        )
        
    return result
