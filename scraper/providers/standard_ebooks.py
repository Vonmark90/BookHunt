"""Standard Ebooks provider for high-quality public-domain EPUB eBooks."""

import re
import warnings
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class StandardEbooksProvider(BaseProvider):
    """Searches Standard Ebooks catalog of beautifully formatted, open-access EPUBs."""

    name = "Standard Ebooks"
    supported_formats = ["EPUB"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        # Standard Ebooks focuses strictly on EPUB / eBook formats
        if file_format and file_format.upper() not in ["EPUB", "ALL"]:
            return []

        items: List[ResourceItem] = []
        url = "https://standardebooks.org/feeds/opds/all"
        params = {"query": query}

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(url, params=params, headers=DEFAULT_HEADERS)
                if resp.status_code != 200:
                    return items

                soup = BeautifulSoup(resp.text, "html.parser")
                entries = soup.find_all("entry")

                for entry in entries[:limit]:
                    title_elem = entry.find("title")
                    title = title_elem.get_text(strip=True) if title_elem else "Untitled"

                    authors = [
                        a.find("name").get_text(strip=True)
                        for a in entry.find_all("author")
                        if a.find("name")
                    ]

                    # Published year
                    published_elem = (
                        entry.find("published")
                        or entry.find("dc:issued")
                        or entry.find("updated")
                    )
                    year = None
                    if published_elem:
                        m = re.match(r"^(\d{4})", published_elem.get_text(strip=True))
                        if m:
                            year = int(m.group(1))

                    summary_elem = entry.find("summary")
                    summary = (
                        summary_elem.get_text(strip=True).replace("\n", " ")
                        if summary_elem
                        else ""
                    )

                    # Links
                    epub_url = None
                    size_bytes = None
                    details_url = None

                    for link in entry.find_all("link"):
                        href = link.get("href", "")
                        rel = link.get("rel", "")
                        link_type = link.get("type", "")

                        if rel == "alternate" and not details_url:
                            details_url = href

                        if "epub" in link_type and "advanced" not in href and "kepub" not in href:
                            epub_url = href
                            length = link.get("length")
                            if length and length.isdigit():
                                size_bytes = int(length)

                    if not epub_url:
                        continue

                    item = ResourceItem(
                        title=title,
                        download_url=epub_url,
                        format="EPUB",
                        source=self.name,
                        authors=authors,
                        year=year,
                        details_url=details_url or epub_url,
                        size_bytes=size_bytes,
                        description=summary[:280] + "..." if len(summary) > 280 else summary,
                        score=92.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items
