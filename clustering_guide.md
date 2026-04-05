# Hướng dẫn triển khai News Clustering Pipeline

> Stack: FastAPI + PostgreSQL + pgvector + PhoBERT + HDBSCAN

---

## Tổng quan pipeline

```
DB (news_embeddings)
        ↓
  Fetch embeddings 24h
        ↓
  Cluster theo category (HDBSCAN)
        ↓
  Tính trending score
        ↓
  Tìm bài đại diện
        ↓
  Gọi Summarization service sinh summary
        ↓
  Lưu vào trending_clusters
        ↓
  API trả về frontend
```

---

## Bước 1 — Chuẩn bị DB

### 1.1 Thêm bảng `trending_clusters`

Bảng `news_embeddings` đã có `cluster_id` và `trending_score`. bảng mới `trending_clusters` sẽ lưu thông tin cluster

> Cần tối thiểu **3 bài/category trong 24h** thì HDBSCAN mới tạo được cluster.

---

## Bước 2 — Cài đặt dependencies

```bash
pip install hdbscan numpy sqlalchemy asyncpg apscheduler
```

Lưu ý với `hdbscan` trên một số môi trường cần thêm:

```bash
pip install hdbscan --no-binary :all:
# hoặc
conda install -c conda-forge hdbscan
```

---

## Bước 3 — Viết Clustering Service

### 3.1 Fetch embeddings từ DB

### 3.2 Chạy HDBSCAN

---

## Bước 4 — Tính Trending Score

```python
def compute_trending_score(articles: list) -> float:
    """
    score = article_count × velocity_multiplier × recency_weight

    velocity_multiplier:
      - Tỉ lệ bài xuất hiện trong 2h gần nhất
      - Cluster đang "nóng lên" được boost mạnh
      - Range: 1.0 (không có bài mới) → 3.0 (toàn bài mới)

    recency_weight:
      - Dựa trên bài mới nhất trong cluster
      - Cluster cũ dần mất điểm theo hàm decay
      - 0h cũ ≈ 1.0, 6h cũ ≈ 0.36, 24h cũ ≈ 0.12
    """
```

---

## Bước 5 — Lưu kết quả vào DB

## Bước 7 — Scheduler chạy định kỳ

## Bước 8 — Sinh summary bằng summarization service

## Bước 9 — API endpoint

Tạo file `app/routers/trending.py`:

Đăng ký router vào `main.py`:

## Điều chỉnh tham số HDBSCAN

| Tham số | Mặc định | Tăng lên khi | Giảm xuống khi |
|---|---|---|---|
| `min_cluster_size` | 3 | Muốn cluster lớn hơn, ít cluster hơn | Tin ít, muốn nhạy hơn |
| `min_samples` | 2 | Muốn cluster chặt, ít noise | Tin ít, cluster hay rỗng |
| `cluster_selection_epsilon` | 0.15 | Muốn merge cluster gần nhau | Muốn tách biệt hơn |

---

## Checklist triển khai

- [ ] Tạo bảng `trending_clusters`
- [ ] Cài `hdbscan`, `apscheduler`, `anthropic`
- [ ] Tạo `clustering_service.py`
- [ ] Tạo `scheduler.py` và đăng ký vào `main.py`
- [ ] Test pipeline thủ công bằng cách gọi `run_clustering_pipeline` trực tiếp
- [ ] Xác nhận dữ liệu ghi vào `trending_clusters` đúng
- [ ] Tạo API endpoint `/trending`
- [ ] Monitor log để đảm bảo job chạy đúng giờ