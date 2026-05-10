from pydantic import BaseModel
from typing import List

class AudioUrlResponse(BaseModel):
    voice_id: str
    description: str
    url: str

class NewsTTSUrlResponse(BaseModel):
    news_id: int
    audio_urls: List[AudioUrlResponse]
