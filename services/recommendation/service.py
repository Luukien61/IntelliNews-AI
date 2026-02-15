"""
Content-Based Recommendation Service for IntelliNews.

Uses PhoBERT embeddings to find similar news articles based on
title + description text. Embeddings are stored in PostgreSQL
and recommendation results are cached in Redis.
"""
import logging
import json
from typing import List, Optional, Tuple

import numpy as np
import torch
from transformers import AutoTokenizer, AutoModel
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session

from config import settings
from db.database import SessionLocal
from db.models import NewsEmbedding
from services.news_client import news_client
from .models import RecommendedNewsItem
from ..constants import KEY_TITLE, KEY_DESCRIPTION, KEY_CONTENT, KEY_ID, KEY_CATEGORY

logger = logging.getLogger(__name__)


class ContentRecommendationService:
    """
    Content-based recommendation using PhoBERT embeddings.
    
    Flow:
    1. Index: For each article, generate a 768-dim PhoBERT [CLS] embedding 
       from title + description, store in PostgreSQL.
    2. Recommend: Given a news_id, load its embedding, compute cosine similarity
       against all embeddings (optionally filtered by category), return top-K.
    3. Cache: Cache recommendation results in Redis with configurable TTL.
    """

    def __init__(self, model_name: str = None, device: str = None):
        self.model_name = model_name or settings.phobert_model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._redis = None
        self._model = None
        self._tokenizer = None
        logger.info(f"ContentRecommendationService initialized (model will be lazy-loaded)")

    def _ensure_model_loaded(self):
        """Lazy-load PhoBERT model (reuses same model as summarizer if already in memory)."""
        if self._model is None:
            logger.info(f"Loading PhoBERT model: {self.model_name} on {self.device}")
            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModel.from_pretrained(self.model_name).to(self.device)
            self._model.eval()
            logger.info("PhoBERT model loaded for recommendation service")

    async def _get_redis(self):
        """Get or create Redis connection (lazy initialization)."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(
                    settings.redis_url,
                    decode_responses=False
                )
                # Test connection
                await self._redis.ping()
                logger.info(f"Redis connected: {settings.redis_url}")
            except Exception as e:
                logger.warning(f"Redis not available, caching disabled: {e}")
                self._redis = None
        return self._redis

    def generate_embedding(self, text: str) -> np.ndarray:
        """
        Generate a 768-dim PhoBERT [CLS] embedding for the given text.
        
        Args:
            text: Input Vietnamese text (typically title + description)
            
        Returns:
            768-dim numpy array
        """
        self._ensure_model_loaded()

        inputs = self._tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=256
        ).to(self.device)

        with torch.no_grad():
            outputs = self._model(**inputs)

        # Use [CLS] token embedding, convert to list for pgvector
        embedding = outputs.last_hidden_state[:, 0, :].cpu().numpy()[0]
        return embedding.tolist()

    async def index_article(self, news_id: int) -> bool:
        """
        Generate and store embedding for a single article.
        
        Args:
            news_id: News item ID to index
            
        Returns:
            True if indexed successfully, False if skipped (already exists)
        """
        db: Session = SessionLocal()
        try:
            # Check if already indexed
            existing = db.query(NewsEmbedding).filter(
                NewsEmbedding.news_id == news_id
            ).first()
            if existing:
                logger.info(f"Article {news_id} already indexed, skipping")
                return False

            # Fetch article content from backend
            content = await news_client.get_news_content(
                news_id, fields=[KEY_TITLE, KEY_DESCRIPTION]
            )

            title = content.get(KEY_TITLE, "")
            description = content.get(KEY_DESCRIPTION, "")

            if not title:
                logger.warning(f"Article {news_id} has no title, skipping")
                return False

            # Combine title + description for embedding
            text = f"{title} {description}" if description else title

            # Generate embedding
            embedding = self.generate_embedding(text)

            # We need category info — fetch from the AI list endpoint
            # For single article, we can get it from the content endpoint
            # But the current internal API doesn't return category
            # So we fetch from the list endpoint by searching
            category = await self._get_article_category(news_id)

            # Store in database (pgvector handles list→vector conversion)
            news_embedding = NewsEmbedding(
                news_id=news_id,
                category=category or "UNKNOWN",
                title=title,
                embedding=embedding
            )
            db.add(news_embedding)
            db.commit()

            # Invalidate cache for this category
            await self._invalidate_cache(category)

            logger.info(f"Indexed article {news_id} (category: {category})")
            return True

        except Exception as e:
            db.rollback()
            logger.error(f"Failed to index article {news_id}: {e}")
            raise
        finally:
            db.close()

    async def _get_article_category(self, news_id: int) -> Optional[str]:
        """Try to fetch article category from backend."""
        try:
            # Search through news list to find the category
            data = await news_client.get_news_list_for_ai(page=0, size=200)
            for item in data.get(KEY_CONTENT, []):
                if item.get(KEY_ID) == news_id:
                    return item.get(KEY_CATEGORY, "UNKNOWN")
        except Exception as e:
            logger.warning(f"Could not fetch category for news_id={news_id}: {e}")
        return "UNKNOWN"

    async def index_articles_batch(
            self,
            page: int = 0,
            size: int = 50,
            category: Optional[str] = None
    ) -> Tuple[int, int]:
        """
        Generate and store embeddings for a batch of articles.
        
        Args:
            page: Page number (0-indexed)
            size: Number of articles per batch
            category: Optional category filter
            
        Returns:
            Tuple of (indexed_count, skipped_count)
        """
        # Fetch articles from backend
        if category:
            data = await news_client.get_news_by_category_for_ai(category, page, size)
        else:
            data = await news_client.get_news_list_for_ai(page, size)

        articles = data.get(KEY_CONTENT, [])

        if not articles:
            logger.info("No articles to index")
            return 0, 0

        indexed = 0
        skipped = 0
        db: Session = SessionLocal()

        try:
            # Get already-indexed news_ids
            existing_ids = set()
            article_ids = [a[KEY_ID] for a in articles]
            existing_records = db.query(NewsEmbedding.news_id).filter(
                NewsEmbedding.news_id.in_(article_ids)
            ).all()
            existing_ids = {r.news_id for r in existing_records}

            for article in articles:
                news_id = article[KEY_ID]

                if news_id in existing_ids:
                    skipped += 1
                    continue

                title = article.get(KEY_TITLE, "")
                description = article.get(KEY_DESCRIPTION, "")
                art_category = article.get(KEY_CATEGORY, "UNKNOWN")

                if not title:
                    skipped += 1
                    continue

                # Combine title + description
                text = f"{title} {description}" if description else title

                # Generate embedding
                embedding = self.generate_embedding(text)

                # Store in database (pgvector handles list→vector conversion)
                news_embedding = NewsEmbedding(
                    news_id=news_id,
                    category=art_category,
                    title=title,
                    embedding=embedding
                )
                db.add(news_embedding)
                indexed += 1

            db.commit()
            logger.info(f"Batch indexing complete: {indexed} indexed, {skipped} skipped")

        except Exception as e:
            db.rollback()
            logger.error(f"Batch indexing failed: {e}")
            raise
        finally:
            db.close()

        return indexed, skipped

    async def get_similar_articles(
            self,
            news_id: int,
            limit: int = 10,
            category_filter: Optional[str] = None
    ) -> Tuple[List[RecommendedNewsItem], bool]:
        """
        Find similar articles based on cosine similarity of embeddings.
        
        Args:
            news_id: Source article ID
            limit: Number of similar articles to return
            category_filter: Optional category to filter results
            
        Returns:
            Tuple of (list of RecommendedNewsItem, is_cached)
        """
        # Check Redis cache first
        cache_key = f"rec:{news_id}:{limit}:{category_filter or 'all'}"
        cached_result = await self._get_from_cache(cache_key)
        if cached_result is not None:
            logger.info(f"Cache hit for {cache_key}")
            return cached_result, True

        db: Session = SessionLocal()
        try:
            # Get source article embedding
            source = db.query(NewsEmbedding).filter(
                NewsEmbedding.news_id == news_id
            ).first()

            if not source:
                logger.warning(f"No embedding found for news_id={news_id}")
                return [], False

            source_embedding = np.array(source.embedding)

            # Load candidate embeddings (optionally filtered by category)
            query = db.query(NewsEmbedding).filter(
                NewsEmbedding.news_id != news_id
            )
            if category_filter:
                query = query.filter(NewsEmbedding.category == category_filter)

            candidates = query.all()

            if not candidates:
                logger.info(f"No candidates found for similarity search")
                return [], False

            # Compute cosine similarity (pgvector returns lists, convert to numpy)
            candidate_embeddings = np.array([
                c.embedding for c in candidates
            ])

            similarities = cosine_similarity(
                source_embedding.reshape(1, -1),
                candidate_embeddings
            )[0]

            # Get top-K indices
            top_k = min(limit, len(similarities))
            top_indices = np.argsort(similarities)[::-1][:top_k]

            # Build response
            recommendations = []
            for idx in top_indices:
                candidate = candidates[idx]
                score = float(similarities[idx])

                # Skip very low similarity scores  
                if score < 0.1:
                    continue

                recommendations.append(RecommendedNewsItem(
                    news_id=candidate.news_id,
                    title=candidate.title,
                    category=candidate.category,
                    similarity_score=round(score, 4)
                ))

            # Cache the result in Redis
            await self._set_to_cache(cache_key, recommendations)

            logger.info(
                f"Generated {len(recommendations)} recommendations for news_id={news_id}"
            )
            return recommendations, False

        except Exception as e:
            logger.error(f"Similarity search failed for news_id={news_id}: {e}")
            raise
        finally:
            db.close()

    async def _get_from_cache(self, key: str) -> Optional[List[RecommendedNewsItem]]:
        """Get recommendation results from Redis cache."""
        redis = await self._get_redis()
        if redis is None:
            return None
        try:
            data = await redis.get(key)
            if data:
                items_data = json.loads(data)
                return [RecommendedNewsItem(**item) for item in items_data]
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
        return None

    async def _set_to_cache(self, key: str, items: List[RecommendedNewsItem]):
        """Store recommendation results in Redis cache."""
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            data = json.dumps([item.model_dump() for item in items])
            await redis.set(key, data, ex=settings.recommendation_cache_ttl)
            logger.debug(f"Cached {len(items)} items with key={key}")
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    async def _invalidate_cache(self, category: Optional[str] = None):
        """Invalidate recommendation cache (when new articles are indexed)."""
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            # Invalidate all recommendation keys (simple approach)
            # In production, you'd use a more targeted pattern
            pattern = "rec:*"
            async for key in redis.scan_iter(match=pattern, count=100):
                await redis.delete(key)
            logger.debug("Recommendation cache invalidated")
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")

    def get_embedding_stats(self) -> dict:
        """Get statistics about stored embeddings."""
        db: Session = SessionLocal()
        try:
            total = db.query(NewsEmbedding).count()

            # Count by category
            from sqlalchemy import func
            category_counts = db.query(
                NewsEmbedding.category,
                func.count(NewsEmbedding.id)
            ).group_by(NewsEmbedding.category).all()

            return {
                "total_embeddings": total,
                "by_category": {cat: count for cat, count in category_counts}
            }
        finally:
            db.close()


# Global service instance (lazy-loaded)
recommendation_service = ContentRecommendationService()
