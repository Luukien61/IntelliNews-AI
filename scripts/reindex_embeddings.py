import asyncio
import logging
import os
import sys

# Add parent dir to path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.database import SessionLocal
from services.recommendation.service import recommendation_service
from services.redis_service import redis_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def main():
    logger.info("🚀 Bắt đầu quá trình Re-index cho dữ liệu đang có trong DB...")
    
    db = SessionLocal()
    from db.models import NewsEmbedding
    try:
        # Xóa Cache Redis trước
        logger.info("Đang xóa cache Redis...")
        redis = await redis_service.get_redis()
        if redis:
            await redis.flushdb()
            logger.info("✅ Đã clear Redis cache.")
            
        # Lấy tất cả records hiện có
        logger.info("Đang lấy tất cả records từ bảng news_embeddings...")
        records = db.query(NewsEmbedding).filter(NewsEmbedding.title != None, NewsEmbedding.title != "").all()
        total_records = len(records)
        
        if total_records == 0:
            logger.info("Không có dữ liệu trong DB để re-index.")
            return
            
        logger.info(f"Tìm thấy {total_records} bài viết cần update embeddings.")
        
        # Batching properties
        batch_size = 128
        total_processed = 0
        from services.utils.text import clean_text_for_ai
        
        for i in range(0, total_records, batch_size):
            batch_records = records[i:i + batch_size]
            
            # Chuẩn bị text và clean
            texts = [clean_text_for_ai(r.title) for r in batch_records]
            
            # Generate new embeddings in batch
            new_embeddings = recommendation_service.generate_embeddings_batch(texts, batch_size=batch_size)
            
            # Update lại vào DB
            for record, new_emb in zip(batch_records, new_embeddings):
                record.embedding = new_emb.tolist()
                
            db.commit()
            total_processed += len(batch_records)
            logger.info(f"Đã xử lý: {total_processed}/{total_records} ({(total_processed/total_records)*100:.1f}%)")
            
        logger.info(f"🎉 Hoàn tất Re-indexing cho {total_processed} bài viết sẵn có trong DB!")
        
    except Exception as e:
        logger.error(f"❌ Có lỗi xảy ra: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
