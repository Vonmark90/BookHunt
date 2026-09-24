"""Dorking provider: searches the open web using Google/DuckDuckGo dorking patterns to find PDFs and eBooks."""

import re
import urllib.parse
from typing import List, Optional
import httpx
from bs4 import BeautifulSoup

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class WebDorkProvider(BaseProvider):
    """Searches open web engines using dork operators (filetype:pdf, ext:epub, intitle:index of, etc.)."""

    name = "Web Dorking (DDG)"
    supported_formats = ["PDF", "EPUB"]

    # Multiple dorking templates to surface hidden documents, books, and open directories
    DORK_TEMPLATES = [
        # Standard filetype targeting
        ("{query} (filetype:pdf OR filetype:epub)", "filetype:pdf/epub"),
        # Academic & university repositories
        ("site:edu filetype:pdf \"{query}\"", "site:edu (academic)"),
        # Open web directory indexes
        ("intitle:\"index of\" (pdf|epub) \"{query}\"", "index-of (open dir)"),
        # Books and textbooks
        ("\"{query}\" (textbook OR book) filetype:pdf", "book-target"),
    ]

    async def search(
        self,
        query: str,
        limit: int = 20,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        results: List[ResourceItem] = []
        seen_urls = set()

        # Format filter customization
        fmt_target = file_format.lower() if file_format else "pdf"

        # Select queries based on requested format
        dorks_to_run = []
        if file_format and file_format.upper() == "EPUB":
            dorks_to_run.append((f"{query} filetype:epub", "filetype:epub"))
            dorks_to_run.append((f"intitle:\"index of\" epub \"{query}\"", "index-of (epub)"))
        elif file_format and file_format.upper() == "PDF":
            dorks_to_run.append((f"{query} filetype:pdf", "filetype:pdf"))
            dorks_to_run.append((f"site:edu filetype:pdf \"{query}\"", "site:edu (academic)"))
            dorks_to_run.append((f"intitle:\"index of\" pdf \"{query}\"", "index-of (pdf)"))
        else:
            dorks_to_run.extend(self.DORK_TEMPLATES[:3])

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for dork_pattern, dork_type in dorks_to_run:
                if len(results) >= limit:
                    break
                dork_query = dork_pattern.format(query=query)
                try:
                    items = await self._search_duckduckgo_html(client, dork_query, dork_type, limit - len(results))
                    for item in items:
                        if item.download_url not in seen_urls:
                            seen_urls.add(item.download_url)
                            results.append(item)
                except Exception as e:
                    # Continue gracefully if a query encounters a temporary block
                    continue

        return results[:limit]

    async def _search_duckduckgo_html(
        self,
        client: httpx.AsyncClient,
        search_query: str,
        dork_type: str,
        limit: int,
    ) -> List[ResourceItem]:
        items: List[ResourceItem] = []
        url = "https://html.duckduckgo.com/html/"
        data = {"q": search_query, "b": ""}

        headers = dict(DEFAULT_HEADERS)
        headers["Referer"] = "https://html.duckduckgo.com/"

        resp = await client.post(url, data=data, headers=headers)
        if resp.status_code != 200:
            return items

        soup = BeautifulSoup(resp.text, "html.parser")
        result_elements = soup.find_all("div", class_=re.compile(r"result|web-result"))

        for elem in result_elements:
            if len(items) >= limit:
                break

            title_elem = elem.find("a", class_=re.compile(r"result__snippet|result__a|result__title"))
            snippet_elem = elem.find("a", class_="result__snippet") or elem.find(class_=re.compile(r"result__snippet"))

            if not title_elem:
                continue

            raw_href = title_elem.get("href", "")
            title = title_elem.get_text(strip=True)
            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

            # Unquote DuckDuckGo redirect link
            actual_url = self._extract_target_url(raw_href)
            if not actual_url or actual_url.startswith("https://duckduckgo.com"):
                continue

            # Detect format
            detected_format = self._detect_format(actual_url, title, snippet)
            if not detected_format:
                continue

            # Clean title
            clean_title = re.sub(r"^(?:\[?(?:PDF|EPUB)\]?\s*)+", "", title, flags=re.IGNORECASE)
            clean_title = re.sub(r"\[PDF\]|\[EPUB\]|\.pdf$|\.epub$", "", clean_title, flags=re.IGNORECASE).strip()

            item = ResourceItem(
                title=clean_title or title,
                download_url=actual_url,
                format=detected_format,
                source=f"Web Dork ({dork_type})",
                description=snippet,
                dork_type=dork_type,
                details_url=actual_url,
                score=80.0 if "index-of" in dork_type else 70.0,
            )
            items.append(item)

        return items

    def _extract_target_url(self, href: str) -> Optional[str]:
        """Extracts the actual destination URL from a search engine redirect parameter."""
        if not href:
            return None
        if "uddg=" in href:
            match = re.search(r"uddg=([^&]+)", href)
            if match:
                return urllib.parse.unquote(match.group(1))
        if href.startswith("/l/?kh=-1&uddg="):
            parts = href.split("uddg=")
            if len(parts) > 1:
                return urllib.parse.unquote(parts[1].split("&")[0])
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return None

    def _detect_format(self, url: str, title: str, snippet: str) -> Optional[str]:
        lower_url = url.lower()
        lower_title = title.lower()
        lower_snippet = snippet.lower()

        if lower_url.endswith(".pdf") or ".pdf?" in lower_url or "[pdf]" in lower_title or "filetype: pdf" in lower_snippet:
            return "PDF"
        if lower_url.endswith(".epub") or ".epub?" in lower_url or "[epub]" in lower_title:
            return "EPUB"
        if lower_url.endswith(".mobi") or ".mobi?" in lower_url:
            return "MOBI"
        if lower_url.endswith(".djvu"):
            return "DJVU"
        
        # If open directory, allow if it mentions pdf or epub
        if "index of" in lower_title and ("pdf" in lower_snippet or "epub" in lower_snippet):
            return "PDF"

        return None
