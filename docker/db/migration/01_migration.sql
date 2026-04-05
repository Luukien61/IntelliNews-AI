alter table news_embeddings add column if not exists trending_score FLOAT;
alter table news_embeddings add column if not exists cluster_id INT;
alter table news_embeddings add column if not exists published_at TIMESTAMPTZ;