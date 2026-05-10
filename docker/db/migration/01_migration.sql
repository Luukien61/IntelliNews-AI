alter table news_embeddings drop column if exists trending_score;
alter table news_embeddings add column if not exists cluster_id INT;
alter table news_embeddings add column if not exists published_at TIMESTAMPTZ;