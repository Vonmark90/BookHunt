"""Base provider interface for search and scraping sources."""

from abc import ABC, abstractmethod
from typing import List, Optional
import httpx
from ..models import ResourceItem

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class BaseProvider(ABC):
    """Abstract base class for all book/paper/document search providers."""

    name: str = "Base"
    supported_formats: List[str] = ["PDF", "EPUB"]

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    @abstractmethod
    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        """Search the provider for resources matching the query.

        Args:
            query: Topic or keywords to search.
            limit: Maximum items to return.
            file_format: Optional format filter (e.g., 'PDF', 'EPUB', or None for all).

        Returns:
            List of ResourceItem objects.
        """
        pass

    async def verify_url(self, client: httpx.AsyncClient, url: str) -> Optional[int]:
        """Perform a quick HEAD/GET range request to verify if link is live and get content size."""
        try:
            resp = await client.head(url, timeout=5.0, follow_redirects=True, headers=DEFAULT_HEADERS)
            if resp.status_code == 200:
                length = resp.headers.get("content-length")
                return int(length) if length and length.isdigit() else None
        except Exception:
            pass
        return None
