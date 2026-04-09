"""
IntelliNews AI Service - FastAPI Application
TTS, Recommendation, and Summarization services
"""
# IMPORTANT: Import cpu_limiter FIRST before any AI libraries
# This sets environment variables to limit CPU usage
import services.cpu_limiter

import os
import logging
import warnings
import asyncio

# Suppress HuggingFace Hub deprecation warnings
warnings.filterwarnings("ignore", category=UserWarning, module="huggingface_hub")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from api.routes import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO if settings.debug else logging.WARNING,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Force INFO level for our own services if they are not already set
if not settings.debug:
    logging.getLogger("services").setLevel(logging.INFO)
    logging.getLogger("api").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Service for IntelliNews - TTS, Recommendation, and Summarization",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Debug mode: {settings.debug}")
    logger.info(f"API prefix: {settings.api_prefix}")
    
    # Configure PyTorch CPU threads mapping to ai_max_cores
    try:
        import torch
        import os
        os.environ["OMP_NUM_THREADS"] = str(settings.ai_max_cores)
        os.environ["MKL_NUM_THREADS"] = str(settings.ai_max_cores)
        torch.set_num_threads(settings.ai_max_cores)
        torch.set_num_interop_threads(settings.ai_max_cores)
        logger.info(f"PyTorch max cores configured to: {settings.ai_max_cores}")
    except Exception as e:
        logger.warning(f"Could not configure PyTorch thread count: {e}")
    
    # Initialize database tables (optional - can use migrations instead)
    try:
        from db.database import init_db
        init_db()
    except Exception as e:
        logger.warning(f"Database initialization skipped: {e}")
    
    # Start Kafka Consumer in the background
    try:
        from services.kafka_consumer_service import kafka_consumer_service
        asyncio.create_task(kafka_consumer_service.start())
        logger.info("Kafka consumer task created")
    except Exception as e:
        logger.error(f"Failed to start Kafka consumer: {e}")

    # Start Clustering Scheduler
    try:
        from services.clustering.scheduler import clustering_scheduler
        await clustering_scheduler.start()
    except Exception as e:
        logger.error(f"Failed to start clustering scheduler: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("Shutting down IntelliNews AI Service")
    try:
        from services.kafka_consumer_service import kafka_consumer_service
        kafka_consumer_service.stop()
        logger.info("Kafka consumer stopped")
    except Exception as e:
        logger.error(f"Error stopping Kafka consumer: {e}")

    # Stop Clustering Scheduler
    try:
        from services.clustering.scheduler import clustering_scheduler
        clustering_scheduler.stop()
    except Exception as e:
        logger.error(f"Error stopping clustering scheduler: {e}")
