"""HTTP Client for News Service API."""
import logging
from typing import Optional, List

import httpx

from config import settings

logger = logging.getLogger(__name__)


class NewsServiceClient:
    """
    Client to communicate with News Service API.
    Used to fetch news content for AI processing.
    """
    
    def __init__(self):
        self.base_url = settings.news_service_url
        self.timeout = settings.news_service_timeout
    
    async def get_news_content(
        self,
        news_id: int,
        fields: Optional[List[str]] = None
    ) -> dict:
        """
        Get specific fields from a news item.
        
        Args:
            news_id: ID of the news item
            fields: List of fields to retrieve (title, description, content_plain_text)
                   If None, returns all fields.
        
        Returns:
            Dict containing requested fields and id
            
        Raises:
            httpx.HTTPStatusError: If request fails
            httpx.RequestError: If connection fails
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            params = {}
            if fields:
                params["fields"] = fields
            
            url = f"{self.base_url}/api/v1/internal/content/{news_id}"
            logger.info(f"Fetching news content from: {url} with fields: {fields}")
            
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Successfully fetched content for news_id={news_id}")
            return data
    
    async def check_news_exists(self, news_id: int) -> bool:
        """
        Check if a news item exists.
        
        Args:
            news_id: ID of the news item
            
        Returns:
            True if news exists, False otherwise
        """
        try:
            await self.get_news_content(news_id, fields=["title"])
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            raise

    async def get_news_list_for_ai(self, page: int = 0, size: int = 50) -> dict:
        """
        Get paginated news list for AI processing (embedding generation).
        
        Args:
            page: Page number (0-indexed)
            size: Page size
            
        Returns:
            Paginated response with lightweight news items
            {content: [{id, title, description, category, publisherId}], totalPages, totalElements, ...}
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}/api/v1/internal/news/list"
            params = {"page": page, "size": size}
            logger.info(f"Fetching news list for AI: page={page}, size={size}")
            
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fetched {len(data.get('content', []))} items (page {page})")
            return data

    async def get_news_by_category_for_ai(
        self, category: str, page: int = 0, size: int = 50
    ) -> dict:
        """
        Get news items by category for AI processing.
        
        Args:
            category: News category (e.g., 'CONG_NGHE', 'THE_THAO')
            page: Page number (0-indexed)
            size: Page size
            
        Returns:
            Paginated response with lightweight news items filtered by category
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            url = f"{self.base_url}/api/v1/internal/news/category/{category}"
            params = {"page": page, "size": size}
            logger.info(f"Fetching news by category '{category}' for AI: page={page}, size={size}")
            
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"Fetched {len(data.get('content', []))} items for category '{category}'")
            return data


# Global client instance
news_client = NewsServiceClient()
