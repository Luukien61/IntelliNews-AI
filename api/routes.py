from fastapi import APIRouter
from api.endpoints import tts, recommendation, summarization

# Main API router
api_router = APIRouter()

# Include all feature routers
api_router.include_router(tts.router)
# api_router.include_router(recommendation.router)
# api_router.include_router(summarization.router)
