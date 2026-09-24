"""Open Library provider for book discovery and archive.org full-text links."""

from typing import List, Optional
import httpx

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class OpenLibraryProvider(BaseProvider):
    """Searches Open Library's comprehensive book catalog with links to Internet Archive editions."""

    name = "Open Library"
    supported_formats = ["PDF", "EPUB"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        items: List[ResourceItem] = []
        url = "https://openlibrary.org/search.json"
        params = {
            "q": query,
            "limit": str(limit),
            "fields": "key,title,author_name,first_publish_year,ia,has_fulltext,ebook_access",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params, headers=DEFAULT_HEADERS)
                if resp.status_code != 200:
                    return items

                data = resp.json()
                docs = data.get("docs", [])

                for doc in docs:
                    # Check if there is an open text / archive.org link
                    ia_ids = doc.get("ia", [])
                    if not ia_ids:
                        continue

                    identifier = ia_ids[0]
                    title = doc.get("title", "Untitled")
                    authors = doc.get("author_name", [])
                    year = doc.get("first_publish_year")

                    target_fmt = "PDF" if not file_format or file_format.upper() == "PDF" else "EPUB"
                    dl_ext = target_fmt.lower()

                    download_url = f"https://archive.org/download/{identifier}/{identifier}.{dl_ext}"
                    key = doc.get("key", "")
                    details_url = f"https://openlibrary.org{key}" if key else f"https://archive.org/details/{identifier}"

                    item = ResourceItem(
                        title=title,
                        download_url=download_url,
                        format=target_fmt,
                        source=self.name,
                        authors=authors[:3],
                        year=int(year) if year and str(year).isdigit() else None,
                        details_url=details_url,
                        description=f"Open Library Edition (IA: {identifier})",
                        score=82.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items
