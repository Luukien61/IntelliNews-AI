"""
News Clustering Service using HDBSCAN.

Pipeline:
1. Fetch embeddings from the last 24h from `news_embeddings`
2. Cluster per category using HDBSCAN
3. Compute trending score for each cluster
4. Find representative articles (closest to centroid)
5. Generate summary for the top cluster's representative article
6. Persist results into `trending_clusters`
"""
import logging
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Tuple
import hdbscan

import numpy as np
from sqlalchemy import text
from sqlalchemy.orm import Session

from config import settings
from db.database import SessionLocal
from db.models import NewsEmbedding, TrendingCluster

logger = logging.getLogger(__name__)


class ClusteringService:
    """Runs the clustering + scoring pipeline."""

    def __init__(self):
        self.settings = settings

    # Trending score constants (not from settings)
    VELOCITY_MULTIPLIER_MIN = 1.0
    VELOCITY_MULTIPLIER_MAX = 3.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run_pipeline(self) -> Dict[str, Any]:
        """
        Execute the full clustering pipeline:
        fetch → cluster → score → persist.

        Returns a summary dict for logging / API response.
        """
        logger.info("=== Clustering pipeline START ===")
        logger.info(
            f"Config: lookback={self.settings.clustering_lookback_hours}h, "
            f"min_size={self.settings.clustering_min_size}, "
            f"min_samples={self.settings.clustering_min_samples}, "
            f"epsilon={self.settings.clustering_epsilon}, "
            f"window={self.settings.clustering_window_hours}h, "
            f"umap={'ON' if self.settings.clustering_umap_enabled else 'OFF'}"
            f"{f' ({self.settings.clustering_umap_n_components}d)' if self.settings.clustering_umap_enabled else ''}"
        )

        db: Session = SessionLocal()
        try:
            # 1. Fetch recent embeddings
            embeddings_by_cat = self._fetch_recent_embeddings(db)

            if not embeddings_by_cat:
                logger.info("No recent embeddings found – skipping pipeline")
                return {"status": "skipped", "reason": "no_data"}

            total_clusters = 0
            all_cluster_results: List[Dict[str, Any]] = []

            for category, records in embeddings_by_cat.items():
                if len(records) < self.settings.clustering_min_size:
                    logger.info(
                        f"Category '{category}' has only {len(records)} articles "
                        f"(min {self.settings.clustering_min_size}) – skipping"
                    )
                    continue

                # 2. Cluster
                clusters = self._cluster_category(category, records)
                if not clusters:
                    continue

                # 3. Score + find representatives
                scored = self._score_clusters(category, clusters)

                # 4. Update cluster_id on news_embeddings rows
                self._update_embedding_cluster_ids(db, clusters)

                all_cluster_results.extend(scored)
                total_clusters += len(scored)

            # 5. Persist into trending_clusters (upsert)
            if all_cluster_results:
                self._persist_trending_clusters(db, all_cluster_results)

            db.commit()
            logger.info(
                f"=== Clustering pipeline END  — {total_clusters} clusters across "
                f"{len(embeddings_by_cat)} categories ==="
            )
            return {
                "status": "ok",
                "categories_processed": len(embeddings_by_cat),
                "total_clusters": total_clusters,
            }

        except Exception as exc:
            db.rollback()
            logger.error(f"Clustering pipeline failed: {exc}", exc_info=True)
            return {"status": "error", "error": str(exc)}
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Step 1 – Fetch embeddings
    # ------------------------------------------------------------------

    def _fetch_recent_embeddings(
        self, db: Session
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Fetch embeddings from the last LOOKBACK_HOURS hours,
        grouped by category.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.settings.clustering_lookback_hours)

        rows = (
            db.query(NewsEmbedding)
            .filter(NewsEmbedding.published_at >= cutoff)
            .all()
        )

        if not rows:
            # Fallback: get embeddings regardless of published_at
            # (useful when published_at is NULL for older data)
            logger.warning(
                f"No embeddings with published_at in last {self.settings.clustering_lookback_hours}h – "
                "falling back to ALL latest embeddings"
            )
            rows = (
                db.query(NewsEmbedding)
                .order_by(NewsEmbedding.created_at.desc())
                .limit(1000)
                .all()
            )

        grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in rows:
            grouped[r.category].append({
                "news_id": r.news_id,
                "embedding": np.array(r.embedding, dtype=np.float32),
                "published_at": r.published_at or r.created_at,
                "title": r.title,
            })

        logger.info(
            f"Fetched {len(rows)} embeddings across {len(grouped)} categories"
        )
        return dict(grouped)

    def get_all_embeddings_for_clustering(
            self, category: Optional[str] = None
    ) -> Tuple[List[int], np.ndarray]:
        """
        Export all embeddings (not just recent ones) for use with external clustering or re-clustering.

        Args:
            category: Optional category filter

        Returns:
            Tuple of (news_ids, embedding_matrix) where embedding_matrix
            is a numpy array of shape (n, 768).
        """
        db: Session = SessionLocal()
        try:
            query = db.query(NewsEmbedding)
            if category:
                query = query.filter(NewsEmbedding.category == category)
            records = query.all()

            news_ids = [r.news_id for r in records]
            embeddings = np.array([r.embedding for r in records], dtype=np.float32)
            return news_ids, embeddings
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Step 2 – HDBSCAN clustering
    # ------------------------------------------------------------------

    def _cluster_category(
        self,
        category: str,
        records: List[Dict[str, Any]],
    ) -> Dict[int, List[Dict[str, Any]]]:
        """
        Run HDBSCAN on the records of a single category.
        Optionally reduces dimensionality with UMAP first (768 → n_components).
        Returns {cluster_label: [records]} (noise label -1 excluded).
        """
        embeddings_matrix = np.vstack([r["embedding"] for r in records])

        # Optional UMAP dimension reduction (768 → n_components)
        if (
            self.settings.clustering_umap_enabled
            and len(records) > self.settings.clustering_umap_n_neighbors
        ):
            import umap
            logger.info(
                f"Category '{category}': reducing {embeddings_matrix.shape[1]}d → "
                f"{self.settings.clustering_umap_n_components}d with UMAP "
                f"(n_neighbors={self.settings.clustering_umap_n_neighbors}, "
                f"min_dist={self.settings.clustering_umap_min_dist})"
            )
            reducer = umap.UMAP(
                n_components=self.settings.clustering_umap_n_components,
                n_neighbors=self.settings.clustering_umap_n_neighbors,
                min_dist=self.settings.clustering_umap_min_dist,
                metric=self.settings.clustering_umap_metric,
                random_state=42
            )
            embeddings_matrix = reducer.fit_transform(embeddings_matrix)
        else:
            if self.settings.clustering_umap_enabled:
                logger.info(
                    f"Category '{category}': skipping UMAP — only {len(records)} samples "
                    f"(need > {self.settings.clustering_umap_n_neighbors})"
                )

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=self.settings.clustering_min_size,
            min_samples=self.settings.clustering_min_samples,
            cluster_selection_epsilon=self.settings.clustering_epsilon,
            metric="euclidean",
        )
        labels = clusterer.fit_predict(embeddings_matrix)

        clusters: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for idx, label in enumerate(labels):
            if label == -1:
                continue  # noise
            rec = records[idx].copy()
            rec["cluster_label"] = int(label)
            clusters[int(label)].append(rec)

        for cid, items in clusters.items():
            titles = [f"- {it['title']}" for it in items]
            logger.info(f"Cluster {cid} ({len(items)} articles):\n" + "\n".join(titles))

        logger.info(
            f"Category '{category}': {len(clusters)} clusters found "
            f"(noise: {sum(1 for l in labels if l == -1)})"
        )
        return dict(clusters)

    # ------------------------------------------------------------------
    # Step 3 – Trending score
    # ------------------------------------------------------------------

    def _validate_cluster_coherence(
        self,
        articles: List[Dict[str, Any]],
        min_avg_cosine: float = 0.75,
    ) -> bool:
        """
        Trả về False nếu cluster không đủ coherent.
        Tính avg pairwise cosine similarity giữa các bài trong cluster.
        (Embeddings từ DB đã được L2-normalize lúc index)
        """
        if len(articles) < 2:
            return True
        
        embeddings = np.vstack([a["embedding"] for a in articles])
        
        # Cosine similarity matrix
        sim_matrix = embeddings @ embeddings.T
        
        # Lấy upper triangle (loại diagonal)
        n = len(articles)
        upper_indices = np.triu_indices(n, k=1)
        avg_sim = sim_matrix[upper_indices].mean()
        
        logger.info(f"--- Cluster Coherence (avg: {avg_sim:.3f}) ---")
        for i, j in zip(upper_indices[0], upper_indices[1]):
            score = sim_matrix[i, j]
            t1 = articles[i].get('title', str(articles[i].get('news_id')))[:50]
            t2 = articles[j].get('title', str(articles[j].get('news_id')))[:50]
            logger.info(f"  [{score:.3f}] {t1}... <-> {t2}...")
        
        if avg_sim < min_avg_cosine:
            logger.info(
                f"Cluster rejected: avg_cosine={avg_sim:.3f} < {min_avg_cosine}"
            )
            return False
        return True

    def _score_clusters(
        self,
        category: str,
        clusters: Dict[int, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """
        Compute trending_score for each cluster and identify representatives.

        score = article_count × velocity_multiplier × recency_weight

        velocity_multiplier  – ratio of articles published in the last
                               VELOCITY_WINDOW_HOURS (boosted to 1.0–3.0)
        recency_weight       – exponential decay based on the *newest*
                               article in the cluster
        """
        now = datetime.now(timezone.utc)
        velocity_cutoff = now - timedelta(hours=self.settings.clustering_window_hours)
        results: List[Dict[str, Any]] = []

        for cluster_id, articles in clusters.items():
            # Validate trước khi score
            if not self._validate_cluster_coherence(
                articles, min_avg_cosine=self.settings.clustering_coherence_threshold
            ):
                continue

            article_count = len(articles)

            # --- Velocity multiplier ---
            recent_count = sum(
                1 for a in articles
                if a["published_at"]
                and a["published_at"].astimezone(timezone.utc) >= velocity_cutoff
            )
            ratio = recent_count / article_count
            velocity_multiplier = (
                self.VELOCITY_MULTIPLIER_MIN
                + ratio * (self.VELOCITY_MULTIPLIER_MAX - self.VELOCITY_MULTIPLIER_MIN)
            )

            # --- Recency weight ---
            newest_published = max(
                (
                    a["published_at"].astimezone(timezone.utc)
                    for a in articles
                    if a["published_at"]
                ),
                default=now,
            )
            hours_old = (now - newest_published).total_seconds() / 3600
            recency_weight = math.exp(-self.settings.clustering_decay_lambda * hours_old)

            trending_score = article_count * velocity_multiplier * recency_weight

            # --- Representative article (closest to centroid) ---
            rep_ids = self._find_representatives(articles, top_k=3)

            # --- Period ---
            all_dates = [
                a["published_at"].astimezone(timezone.utc)
                for a in articles
                if a["published_at"]
            ]
            period_start = min(all_dates) if all_dates else now
            period_end = max(all_dates) if all_dates else now

            results.append({
                "cluster_id": cluster_id,
                "category": category,
                "article_count": article_count,
                "trending_score": round(trending_score, 4),
                "representative_ids": rep_ids,
                "period_start": period_start,
                "period_end": period_end,
                "articles": articles,  # kept in memory for summary gen
            })

        # Sort descending by trending_score
        results.sort(key=lambda x: x["trending_score"], reverse=True)
        return results

    @staticmethod
    def _find_representatives(
        articles: List[Dict[str, Any]], top_k: int = 3
    ) -> List[int]:
        """Find articles closest to the cluster centroid."""
        embeddings = np.vstack([a["embedding"] for a in articles])
        centroid = embeddings.mean(axis=0)

        distances = np.linalg.norm(embeddings - centroid, axis=1)
        top_indices = np.argsort(distances)[:top_k]

        return [articles[i]["news_id"] for i in top_indices]

    # ------------------------------------------------------------------
    # Step 4 – Update cluster_id on news_embeddings
    # ------------------------------------------------------------------

    def _update_embedding_cluster_ids(
        self,
        db: Session,
        clusters: Dict[int, List[Dict[str, Any]]],
    ):
        """Write cluster_id + trending_score back to news_embeddings rows."""
        for cluster_id, articles in clusters.items():
            news_ids = [a["news_id"] for a in articles]
            db.execute(
                text(
                    "UPDATE news_embeddings "
                    "SET cluster_id = :cid, updated_at = NOW() "
                    "WHERE news_id = ANY(:ids)"
                ),
                {"cid": cluster_id, "ids": news_ids},
            )

    # ------------------------------------------------------------------
    # Step 5 – Persist to trending_clusters
    # ------------------------------------------------------------------

    def _persist_trending_clusters(
        self, db: Session, results: List[Dict[str, Any]]
    ):
        """Upsert rows into trending_clusters."""
        # Clear stale data first
        db.query(TrendingCluster).delete()

        from sqlalchemy.dialects.postgresql import insert
        values = []
        for r in results:
            # First representative is the primary one
            primary_id = r["representative_ids"][0] if r["representative_ids"] else None
            
            values.append({
                "cluster_id": r["cluster_id"],
                "category": r["category"],
                "article_count": r["article_count"],
                "trending_score": r["trending_score"],
                "primary_rep_id": primary_id,
                "representative_ids": r["representative_ids"],
                "period_start": r["period_start"],
                "period_end": r["period_end"]
            })
            
        if values:
            stmt = insert(TrendingCluster).values(values)
            stmt = stmt.on_conflict_do_update(
                constraint="trending_clusters_cluster_id_category_key",
                set_={
                    "article_count": stmt.excluded.article_count,
                    "trending_score": stmt.excluded.trending_score,
                    "primary_rep_id": stmt.excluded.primary_rep_id,
                    "representative_ids": stmt.excluded.representative_ids,
                    "period_start": stmt.excluded.period_start,
                    "period_end": stmt.excluded.period_end,
                    "created_at": text("NOW()"),
                }
            )
            db.execute(stmt)
            
        logger.info(f"Persisted {len(results)} trending_clusters rows")

    # _generate_top_summaries removed as we now link to news_ai_results table

    # ------------------------------------------------------------------
    # Query helpers (used by API)
    # ------------------------------------------------------------------

    def get_trending_clusters(
        self,
        db: Session,
        category: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Read trending clusters from DB ordered by score.
        Optionally filtered by category.
        """
        query = db.query(TrendingCluster)

        if category:
            query = query.filter(TrendingCluster.category == category)

        rows = query.order_by(TrendingCluster.trending_score.desc()).limit(limit).all()

        return [
            {
                "cluster_id": r.cluster_id,
                "category": r.category,
                "article_count": r.article_count,
                "trending_score": r.trending_score,
                "primary_rep_id": r.primary_rep_id,
                "representative_ids": list(r.representative_ids or []),
                "period_start": r.period_start.isoformat() if r.period_start else None,
                "period_end": r.period_end.isoformat() if r.period_end else None,
            }
            for r in rows
        ]

    def get_top_trending(
        self,
        db: Session,
        hours: float = 4.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get clusters created within the last `hours` hours, sorted by score.
        This is the primary API for the frontend 'trending' section.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        rows = (
            db.query(TrendingCluster)
            .filter(TrendingCluster.created_at >= cutoff)
            .order_by(TrendingCluster.trending_score.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "cluster_id": r.cluster_id,
                "category": r.category,
                "article_count": r.article_count,
                "trending_score": r.trending_score,
                "primary_rep_id": r.primary_rep_id,
                "representative_ids": list(r.representative_ids or []),
                "period_start": r.period_start.isoformat() if r.period_start else None,
                "period_end": r.period_end.isoformat() if r.period_end else None,
            }
            for r in rows
        ]


# Global singleton
clustering_service = ClusteringService()
