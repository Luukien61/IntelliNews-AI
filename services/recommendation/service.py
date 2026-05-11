"""
Content-Based Recommendation Service for IntelliNews.

Uses SentenceTransformer (vietnamese-bi-encoder) embeddings to find similar
news articles based on title + description text. Embeddings are stored in
PostgreSQL and recommendation results are cached in Redis.
"""
import logging
import json
import math
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy.orm import Session
from underthesea import word_tokenize

from config import settings
from db.database import SessionLocal
from db.models import NewsEmbedding
from services.news_client import news_client
from .models import RecommendedNewsItem
from ..constants import KEY_TITLE, KEY_DESCRIPTION, KEY_CONTENT, KEY_ID, KEY_CATEGORY
from services.redis_service import redis_service
from services.utils.text import clean_text_for_ai

logger = logging.getLogger(__name__)


class ContentRecommendationService:
    """
    Content-based recommendation using SentenceTransformer embeddings.
    
    Flow:
    1. Index: For each article, word-segment the text (underthesea),
       then generate a normalized 768-dim embedding via SentenceTransformer,
       store in PostgreSQL.
    2. Recommend: Given a news_id, load its embedding, compute cosine similarity
       against same-category embeddings, return top-K.
    3. Cache: Cache recommendation results in Redis with configurable TTL.
    """

    def __init__(self, model_name: str = None, device: str = None):
        self.model_name = model_name or settings.embedding_model_name
        self.device = device or "cpu"
        self._model: Optional[SentenceTransformer] = None
        logger.info(f"ContentRecommendationService initialized (model will be lazy-loaded)")

    def _ensure_model_loaded(self):
        """Lazy-load SentenceTransformer model."""
        if self._model is None:
            from services.model_lock import global_model_load_lock
            with global_model_load_lock:
                if self._model is None:
                    logger.info(f"Loading SentenceTransformer model: {self.model_name}")
                    self._model = SentenceTransformer(self.model_name, device=self.device)
                    
                    # Warm up underthesea tokenizer while holding the lock
                    # to prevent multi-threading race conditions on first use
                    try:
                        logger.info("Warming up underthesea word_tokenize...")
                        word_tokenize("warm up", format="text")
                    except Exception as e:
                        logger.warning(f"Failed to warm up underthesea tokenizer: {e}")
                        
                    logger.info("SentenceTransformer model loaded for recommendation service")

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate a normalized 768-dim embedding for the given text.
        
        Steps:
        1. Vietnamese word segmentation via underthesea
        2. Encode with SentenceTransformer (normalized)
        
        Args:
            text: Input Vietnamese text (typically title + description)
            
        Returns:
            768-dim normalized list of floats
        """
        if not text or not text.strip():
            raise ValueError("Input text is empty or None")
            
        self._ensure_model_loaded()

        try:
            # Word segmentation (required by vietnamese-bi-encoder)
            segmented_text = word_tokenize(text, format="text")
        except Exception as e:
            logger.error(f"underthesea word_tokenize failed: {e}")
            logger.warning("Falling back to unsegmented text (may reduce quality)")
            segmented_text = text

        # SentenceTransformer.encode() handles tokenization + pooling internally
        embedding = self._model.encode(
            segmented_text,
            normalize_embeddings=True,  # L2-normalize for cosine similarity
            show_progress_bar=False
        )

        return embedding.tolist()

    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Generate normalized embeddings for a batch of texts.
        Much faster than calling generate_embedding() in a loop.

        Args:
            texts: List of Vietnamese texts
            batch_size: Batch size for encoding (tune based on RAM/GPU)

        Returns:
            numpy array of shape (len(texts), 768), L2-normalized
        """
        self._ensure_model_loaded()

        try:
            # Word-segment all texts
            segmented_texts = [word_tokenize(t, format="text") for t in texts]
        except Exception as e:
            logger.error(f"underthesea word_tokenize failed in batch: {e}")
            logger.warning("Falling back to unsegmented texts (may reduce quality)")
            segmented_texts = texts

        # Batch encode
        embeddings = self._model.encode(
            segmented_texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=True
        )

        return embeddings

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

            # Combine title + description for embedding and clean it
            text = f"{title} {description}" if description else title
            text = clean_text_for_ai(text)

            # Generate embedding
            embedding = self.generate_embedding(text)

            # We need category info — fetch from the AI list endpoint
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
            await self._invalidate_cache()

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
        Uses batch encoding for much faster performance.
        
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

        db: Session = SessionLocal()

        try:
            # Get already-indexed news_ids
            article_ids = [a[KEY_ID] for a in articles]
            existing_records = db.query(NewsEmbedding.news_id).filter(
                NewsEmbedding.news_id.in_(article_ids)
            ).all()
            existing_ids = {r.news_id for r in existing_records}

            # Filter to only new articles with titles
            new_articles = [
                a for a in articles
                if a[KEY_ID] not in existing_ids and a.get(KEY_TITLE)
            ]

            if not new_articles:
                skipped = len(articles)
                logger.info(f"No new articles to index ({skipped} skipped)")
                return 0, skipped

            # Prepare texts for batch encoding and clean them
            texts = [
                clean_text_for_ai(f"{a.get(KEY_TITLE, '')} {a.get(KEY_DESCRIPTION, '')}")
                for a in new_articles
            ]

            # Batch encode all at once (much faster than one-by-one)
            embeddings = self.generate_embeddings_batch(texts, batch_size=32)

            # Store in database
            for article, embedding in zip(new_articles, embeddings):
                news_embedding = NewsEmbedding(
                    news_id=article[KEY_ID],
                    category=article.get(KEY_CATEGORY, "UNKNOWN"),
                    title=article.get(KEY_TITLE, ""),
                    embedding=embedding.tolist()
                )
                db.add(news_embedding)

            db.commit()

            indexed = len(new_articles)
            skipped = len(articles) - indexed
            logger.info(f"Batch indexing complete: {indexed} indexed, {skipped} skipped")
            return indexed, skipped

        except Exception as e:
            db.rollback()
            logger.error(f"Batch indexing failed: {e}")
            raise
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Recency boost
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_recency(published_at, now: datetime, decay_lambda: float) -> float:
        """
        Exponential recency score in [0, 1].
        Returns 1.0 for brand-new articles, decays toward 0 as articles age.
        Half-life = ln(2) / decay_lambda  (default λ=0.1 → half-life ≈ 6.9 h).
        Returns 0.0 when published_at is None (treated as very old).
        """
        if published_at is None:
            return 0.0
        try:
            pub = (
                published_at.astimezone(timezone.utc)
                if published_at.tzinfo
                else published_at.replace(tzinfo=timezone.utc)
            )
            hours_old = max(0.0, (now - pub).total_seconds() / 3600)
            return math.exp(-decay_lambda * hours_old)
        except Exception:
            return 0.0

    def _boosted_score(self, similarity: float, published_at, now: datetime) -> float:
        """
        Blend cosine similarity with recency boost.

        final = (1 − w) × similarity + w × recency
            w  = settings.recommendation_recency_weight  (default 0.3)
            recency = exp(−λ × hours_old)

        This keeps the score in [0, 1] and only penalises older articles
        relative to fresher ones of equal content similarity.
        """
        w = settings.recommendation_recency_weight
        recency = self._compute_recency(
            published_at, now, settings.recommendation_recency_decay_lambda
        )
        return round((1.0 - w) * similarity + w * recency, 4)

    # ------------------------------------------------------------------
    # Similarity search strategies
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_candidate_category(source: NewsEmbedding, category_filter: Optional[str]) -> str:
        """Use explicit API filter when set; otherwise same category as the source row."""
        if category_filter and str(category_filter).strip():
            return str(category_filter).strip()
        return source.category

    async def get_similar_articles(
            self,
            news_id: int,
            limit: int = 10,
            strategy: str = "pgvector",
            category_filter: Optional[str] = None,
    ) -> Tuple[List[RecommendedNewsItem], bool]:
        """
        Find similar articles based on cosine similarity of embeddings.
        Candidates are restricted to one category: ``category_filter`` when provided,
        otherwise the source article's category.
        
        Args:
            news_id: Source article ID
            limit: Number of similar articles to return
            strategy: Similarity computation strategy:
                       "pgvector" — SQL-level cosine distance (recommended)
                       "dot"      — numpy dot product (fast, requires normalized embeddings)
                       "sklearn"  — sklearn cosine_similarity (fallback)
            category_filter: Optional category name (e.g. enum string) to search within
            
        Returns:
            Tuple of (list of RecommendedNewsItem, is_cached)
        """
        db: Session = SessionLocal()
        try:
            source = db.query(NewsEmbedding).filter(
                NewsEmbedding.news_id == news_id
            ).first()

            if not source:
                logger.warning(f"No embedding found for news_id={news_id}")
                return [], False

            filter_cat = self._resolve_candidate_category(source, category_filter)
            cache_key = f"rec:{news_id}:{limit}:cat:{filter_cat}"

            cached_result = await self._get_from_cache(cache_key)
            if cached_result is not None:
                logger.info(f"Cache hit for {cache_key}")
                return cached_result, True

            if strategy == "pgvector":
                recommendations = self._similar_pgvector(db, source, limit, filter_cat)
            elif strategy == "dot":
                recommendations = self._similar_dot_product(db, source, limit, filter_cat)
            else:
                recommendations = self._similar_sklearn(db, source, limit, filter_cat)

            await self._set_to_cache(cache_key, recommendations)

            logger.info(
                f"Generated {len(recommendations)} recommendations for news_id={news_id} "
                f"(strategy={strategy}, category={filter_cat})"
            )
            return recommendations, False

        except Exception as e:
            logger.error(f"Similarity search failed for news_id={news_id}: {e}")
            raise
        finally:
            db.close()

    def _similar_pgvector(
            self, db: Session, source: NewsEmbedding, limit: int, candidate_category: str
    ) -> List[RecommendedNewsItem]:
        """
        Strategy A — pgvector cosine distance (SQL-level, most scalable).
        Fetches limit×3 candidates first, then re-ranks with recency boost.
        """
        now = datetime.now(timezone.utc)
        fetch_limit = limit * 3  # over-fetch so recency re-ranking doesn't cut good results

        results = (
            db.query(NewsEmbedding)
            .filter(
                NewsEmbedding.news_id != source.news_id,
                NewsEmbedding.category == candidate_category
            )
            .order_by(
                NewsEmbedding.embedding.cosine_distance(source.embedding)
            )
            .limit(fetch_limit)
            .all()
        )

        source_emb = np.array(source.embedding)
        recommendations = []
        for r in results:
            candidate_emb = np.array(r.embedding)
            norm = np.linalg.norm(source_emb) * np.linalg.norm(candidate_emb)
            similarity = float(np.dot(source_emb, candidate_emb) / norm) if norm else 0.0

            if similarity < 0.1:
                continue

            final_score = self._boosted_score(similarity, r.published_at, now)
            recommendations.append(RecommendedNewsItem(
                news_id=r.news_id,
                title=r.title,
                category=r.category,
                similarity_score=final_score,
            ))

        # Re-rank after recency boost and return top limit
        recommendations.sort(key=lambda x: x.similarity_score, reverse=True)
        return recommendations[:limit]

    def _similar_dot_product(
            self, db: Session, source: NewsEmbedding, limit: int, candidate_category: str
    ) -> List[RecommendedNewsItem]:
        """
        Strategy B — numpy dot product (fast, requires normalized embeddings).
        When embeddings are L2-normalized, cosine_similarity = dot product.
        """
        candidates = (
            db.query(NewsEmbedding)
            .filter(
                NewsEmbedding.news_id != source.news_id,
                NewsEmbedding.category == candidate_category
            )
            .all()
        )

        if not candidates:
            return []

        now = datetime.now(timezone.utc)
        source_embedding = np.array(source.embedding)
        candidate_embeddings = np.array([c.embedding for c in candidates])

        # dot product = cosine similarity when vectors are normalized
        similarities = candidate_embeddings @ source_embedding

        # Apply recency boost before ranking
        boosted = np.array([
            self._boosted_score(float(sim), c.published_at, now)
            for sim, c in zip(similarities, candidates)
        ])

        top_k = min(limit, len(boosted))
        top_indices = np.argsort(boosted)[::-1][:top_k]

        recommendations = []
        for idx in top_indices:
            if float(similarities[idx]) < 0.1:   # filter on raw similarity, not boosted
                continue
            candidate = candidates[idx]
            recommendations.append(RecommendedNewsItem(
                news_id=candidate.news_id,
                title=candidate.title,
                category=candidate.category,
                similarity_score=float(boosted[idx]),
            ))

        return recommendations

    def _similar_sklearn(
            self, db: Session, source: NewsEmbedding, limit: int, candidate_category: str
    ) -> List[RecommendedNewsItem]:
        """
        Strategy C — sklearn cosine_similarity (original approach, fallback).
        """
        candidates = (
            db.query(NewsEmbedding)
            .filter(
                NewsEmbedding.news_id != source.news_id,
                NewsEmbedding.category == candidate_category
            )
            .all()
        )

        if not candidates:
            return []

        now = datetime.now(timezone.utc)
        source_embedding = np.array(source.embedding)
        candidate_embeddings = np.array([c.embedding for c in candidates])

        similarities = cosine_similarity(
            source_embedding.reshape(1, -1),
            candidate_embeddings
        )[0]

        # Apply recency boost before ranking
        boosted = np.array([
            self._boosted_score(float(sim), c.published_at, now)
            for sim, c in zip(similarities, candidates)
        ])

        top_k = min(limit, len(boosted))
        top_indices = np.argsort(boosted)[::-1][:top_k]

        recommendations = []
        for idx in top_indices:
            if float(similarities[idx]) < 0.1:   # filter on raw similarity, not boosted
                continue
            candidate = candidates[idx]
            recommendations.append(RecommendedNewsItem(
                news_id=candidate.news_id,
                title=candidate.title,
                category=candidate.category,
                similarity_score=float(boosted[idx]),
            ))

        return recommendations

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _get_from_cache(self, key: str) -> Optional[List[RecommendedNewsItem]]:
        """Get recommendation results from Redis cache."""
        redis = await redis_service.get_redis()
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
        redis = await redis_service.get_redis()
        if redis is None:
            return
        try:
            data = json.dumps([item.model_dump() for item in items])
            await redis.set(key, data, ex=settings.recommendation_cache_ttl)
            logger.debug(f"Cached {len(items)} items with key={key}")
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    async def _invalidate_cache(self):
        """Invalidate recommendation cache (when new articles are indexed)."""
        redis = await redis_service.get_redis()
        if redis is None:
            return
        try:
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
