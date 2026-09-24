"""Standard Ebooks provider for high-quality public-domain EPUB eBooks."""

from __future__ import annotations

import re
import warnings
import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class StandardEbooksProvider(BaseProvider):
    """Searches Standard Ebooks catalog of beautifully formatted, open-access EPUBs."""

    name: str = "Standard Ebooks"
    supported_formats: list[str] = ["EPUB"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: str | None = None,
    ) -> list[ResourceItem]:
        # Standard Ebooks focuses strictly on EPUB / eBook formats
        if file_format and file_format.upper() not in ["EPUB", "ALL"]:
            return []

        items: list[ResourceItem] = []
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

                    authors: list[str] = []
                    for a in entry.find_all("author"):
                        name_elem = a.find("name")
                        if name_elem:
                            authors.append(name_elem.get_text(strip=True))

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
                    epub_url: str | None = None
                    size_bytes: int | None = None
                    details_url: str | None = None

                    for link in entry.find_all("link"):
                        raw_href = link.get("href", "")
                        href = str(raw_href) if raw_href else ""
                        raw_rel = link.get("rel", "")
                        rel = str(raw_rel) if raw_rel else ""
                        raw_type = link.get("type", "")
                        link_type = str(raw_type) if raw_type else ""

                        if rel == "alternate" and not details_url:
                            details_url = href

                        if "epub" in link_type and "advanced" not in href and "kepub" not in href:
                            epub_url = href
                            length = link.get("length")
                            if length:
                                length_str = str(length)
                                if length_str.isdigit():
                                    size_bytes = int(length_str)

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
