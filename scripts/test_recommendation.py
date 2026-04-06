import asyncio
import logging
import sys
import os
import time

# Add parent dir to path so we can import services
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.recommendation.service import recommendation_service
from db.database import SessionLocal
from db.models import NewsEmbedding

logging.basicConfig(level=logging.INFO, format="%(message)s")

async def test_strategy(news_id: int, strategy: str, title: str):
    print(f"\n[{strategy.upper()} STRATEGY]")
    start_time = time.perf_counter()
    
    recs, cached = await recommendation_service.get_similar_articles(
        news_id=news_id, 
        limit=5, 
        strategy=strategy
    )
    
    elapsed = (time.perf_counter() - start_time) * 1000  # ms
    
    print(f"Thời gian tính toán: {elapsed:.2f} ms | Lấy từ cache: {cached}")
    print(f"Bản tin gốc ({news_id}): {title}")
    print("-" * 50)
    for i, rec in enumerate(recs):
        print(f"{i+1}. [Score: {rec.similarity_score:.4f} | {rec.category}] ({rec.news_id}) {rec.title}")
    
async def main():
    print("🚀 Bắt đầu test Recommendation Similarity Strategies...")
    
    db = SessionLocal()
    # Lấy một bài viết ngẫu nhiên có embeddings
    random_news = db.query(NewsEmbedding).first()
    db.close()
    
    if not random_news:
        print("❌ Không tìm thấy bài báo nào trong news_embeddings. Chạy reindex_embeddings.py trước.")
        return
        
    news_id = 1944
    title = random_news.title
    
    # Force clear cache for testing (optional, let's keep it clean to test true speed)
    from services.redis_service import redis_service
    redis = await redis_service.get_redis()
    if redis:
        await redis.delete(f"rec:{news_id}:5:cat")
    
    # 1. Test pgvector
    await test_strategy(news_id, "pgvector", title)
    
    if redis:
        await redis.delete(f"rec:{news_id}:5:cat")
        
    # 2. Test Dot Product
    await test_strategy(news_id, "dot", title)
    
    if redis:
        await redis.delete(f"rec:{news_id}:5:cat")
        
    # 3. Test Sklearn
    await test_strategy(news_id, "sklearn", title)

if __name__ == "__main__":
    asyncio.run(main())
