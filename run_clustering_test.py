import asyncio
import logging
import json
from datetime import datetime

# Cấu hình logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

from services.clustering.service import clustering_service

async def main():
    print("🚀 Bắt đầu gọi pipeline Clustering & Scoring...")
    
    # Chạy pipeline thủ công
    result = await clustering_service.run_pipeline()
    
    print("\n✅ Kết quả trả về từ Pipeline:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
