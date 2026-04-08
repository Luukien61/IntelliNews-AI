# 🔍 Phân tích nguyên nhân Clustering kém

## Vấn đề chính: Cosine similarity giữa các bài trong cùng cluster rất thấp (0.02–0.30)

Sau khi phân tích code, tôi tìm ra **2 nguyên nhân gốc rễ**:

---

## ❌ Nguyên nhân #1: Embedding chỉ dùng TITLE, không có content

> [!CAUTION]
> Đây là nguyên nhân quan trọng nhất — embeddings không chứa đủ ngữ nghĩa.

Trong [ai_processor_service.py](file:///home/luukien/Downloads/PycharmProjects/IntelliNews-AI/services/ai_processor_service.py#L95-L121), method `_run_embedding()` **chỉ dùng `title`** để tạo embedding:

```python
# Line 106 — CHỈ dùng title!
embedding = await asyncio.to_thread(recommendation_service.generate_embedding, title)
```

Trong khi `recommendation_service.index_article()` dùng **title + description**:
```python
# Line 147 — dùng title + description
text = f"{title} {description}" if description else title
```

**Vấn đề**: Kafka event (`process_news_item`) nhận được `contentPlainText` nhưng method `_run_embedding()` bỏ qua nó, chỉ truyền `title`. Kết quả là embedding chỉ capture được ngữ nghĩa từ tiêu đề (rất ngắn), dẫn đến:
- 2 bài khác chủ đề nhưng có từ chung trong tiêu đề → cosine cao giả
- 2 bài cùng chủ đề nhưng tiêu đề khác nhau → cosine thấp giả  

**Ví dụ từ log**: "Dự báo thời tiết" và "Hoa bàn bung nở, phủ vàng góc trời Hà Nội" cho cosine = 0.222, trong khi đáng lẽ phải gần 0 vì hoàn toàn khác chủ đề.

---

## ❌ Nguyên nhân #2: `cluster_selection_epsilon = 0.15` quá lỏng

> [!WARNING]
> HDBSCAN đang gom quá nhiều bài không liên quan vào cùng cluster.

Với normalized embeddings (L2-norm = 1), khoảng cách Euclidean liên hệ với cosine similarity qua:

$$d_{euclidean} = \sqrt{2 - 2 \cdot cos(\theta)}$$

| Cosine Similarity | Euclidean Distance |
|---|---|
| 0.95 (rất giống) | 0.316 |
| 0.90 | 0.447 |
| 0.80 | 0.632 |
| 0.70 | 0.775 |
| 0.50 | 1.000 |
| 0.20 | 1.265 |
| 0.00 (không liên quan) | 1.414 |

`epsilon = 0.15` cho phép HDBSCAN merge các cluster nhỏ nếu khoảng cách giữa chúng ≤ 0.15. Trong không gian 768 chiều, **hầu hết tất cả các điểm** nằm trong khoảng cách Euclidean 1.0–1.4 của nhau (curse of dimensionality), nên epsilon=0.15 không phải vấn đề chính ở đây.

**Nhưng khi kết hợp với embeddings quá yếu (chỉ từ title)**, HDBSCAN thấy tất cả các điểm đều gần nhau tương đương → gom thành cluster lớn.

---

## ❌ Nguyên nhân #3: UMAP bị skip cho hầu hết categories

Log cho thấy `n_neighbors=30` (runtime, có thể từ .env override) nhưng code default là `5`:

```
Category 'THOI_SU': skipping UMAP — only 16 samples (need > 30)
```

Khi UMAP bị skip, HDBSCAN phải làm việc trên không gian 768 chiều → **curse of dimensionality** khiến khoảng cách Euclidean giữa mọi cặp điểm đều gần bằng nhau → clustering vô nghĩa.

---

## ✅ Giải pháp đề xuất

### Fix 1: Dùng title + content cho embedding (quan trọng nhất)

Trong `ai_processor_service.py`, sửa `_run_embedding()`:

```diff
- async def _run_embedding(self, news_id: int, title: str, category: str, published_at):
+ async def _run_embedding(self, news_id: int, title: str, content: str, category: str, published_at):
      """Generate title embedding and store in DB."""
      db = SessionLocal()
      try:
          existing = db.query(NewsEmbedding).filter(
              NewsEmbedding.news_id == news_id
          ).first()
          if existing:
              return

-         embedding = await asyncio.to_thread(recommendation_service.generate_embedding, title)
+         # Combine title + content for richer semantic embedding
+         text = f"{title} {content}" if content else title
+         text = clean_text_for_ai(text)
+         embedding = await asyncio.to_thread(recommendation_service.generate_embedding, text)
```

### Fix 2: Giảm `clustering_umap_n_neighbors` đúng = 5 (kiểm tra .env)

Đảm bảo `.env` không override `CLUSTERING_UMAP_N_NEIGHBORS` lên 30. Config code đã đúng (`5`), nhưng runtime cho thấy giá trị khác.

### Fix 3: Tăng epsilon hoặc chuyển HDBSCAN sang metric `cosine` trực tiếp

```python
clusterer = hdbscan.HDBSCAN(
    min_cluster_size=self.settings.clustering_min_size,
    min_samples=self.settings.clustering_min_samples,
    cluster_selection_epsilon=0.0,  # Để HDBSCAN tự quyết
    metric="cosine",  # Dùng cosine trực tiếp thay vì euclidean trên normalized vectors
)
```

Hoặc nếu giữ euclidean trên normalized vectors, set `epsilon = 0.0` để HDBSCAN không merge các cluster nhỏ một cách quá dễ dàng.

### Fix 4: Re-generate tất cả embeddings

Sau khi fix #1, cần xóa embeddings cũ và re-generate lại với title + content.

---

## 🎯 Tóm tắt

| Vấn đề | Mức độ | Fix |
|---|---|---|
| Embedding chỉ từ title | 🔴 Critical | Dùng title + content |
| UMAP bị skip (n_neighbors quá cao) | 🟡 Medium | Kiểm tra .env, đảm bảo = 5 |
| HDBSCAN epsilon/metric | 🟡 Medium | metric="cosine", epsilon=0.0 |
| Cần re-generate embeddings | 🔴 Critical | Xóa + rebuild |
