"""arXiv academic repository provider for scientific books, papers, and surveys."""

from __future__ import annotations

import re
import warnings
import httpx
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class ArxivProvider(BaseProvider):
    """Searches arXiv for academic papers, monographs, surveys, and research publications."""

    name: str = "arXiv"
    supported_formats: list[str] = ["PDF"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: str | None = None,
    ) -> list[ResourceItem]:
        # If user explicitly requested only EPUB, arXiv doesn't provide EPUB
        if file_format and file_format.upper() != "PDF":
            return []

        items: list[ResourceItem] = []
        clean_q = re.sub(r"[^\w\s]", " ", query).strip()
        params = {
            "search_query": f"all:{clean_q}",
            "start": 0,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        url = "https://export.arxiv.org/api/query"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params, headers=DEFAULT_HEADERS)
                if resp.status_code != 200:
                    return items

                soup = BeautifulSoup(resp.text, "html.parser")
                entries = soup.find_all("entry")

                for entry in entries:
                    title_elem = entry.find("title")
                    title = title_elem.get_text(strip=True).replace("\n", " ") if title_elem else "Untitled"

                    authors: list[str] = []
                    for a in entry.find_all("author"):
                        name_elem = a.find("name")
                        if name_elem:
                            authors.append(name_elem.get_text(strip=True))

                    published_elem = entry.find("published")
                    year = None
                    if published_elem:
                        m = re.match(r"^(\d{4})", published_elem.get_text(strip=True))
                        if m:
                            year = int(m.group(1))

                    summary_elem = entry.find("summary")
                    summary = summary_elem.get_text(strip=True).replace("\n", " ") if summary_elem else ""

                    # Find PDF link
                    pdf_link: str | None = None
                    alt_link: str | None = None
                    for link in entry.find_all("link"):
                        raw_href = link.get("href")
                        href_str = str(raw_href) if raw_href else None
                        if link.get("title") == "pdf" or link.get("type") == "application/pdf":
                            pdf_link = href_str
                        elif link.get("rel") == "alternate":
                            alt_link = href_str

                    if not pdf_link and alt_link:
                        # Convert arxiv.org/abs/... to arxiv.org/pdf/...
                        pdf_link = alt_link.replace("/abs/", "/pdf/") + ".pdf"

                    if not pdf_link:
                        continue

                    # Ensure .pdf suffix for clarity
                    if not pdf_link.endswith(".pdf"):
                        pdf_link = pdf_link + ".pdf"

                    item = ResourceItem(
                        title=title,
                        download_url=pdf_link,
                        format="PDF",
                        source=self.name,
                        authors=authors,
                        year=year,
                        details_url=alt_link or pdf_link,
                        description=summary[:280] + "..." if len(summary) > 280 else summary,
                        score=88.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items
