"""Dorking provider: searches the open web using Google/DuckDuckGo dorking patterns to find PDFs and eBooks."""

from __future__ import annotations

import re
import urllib.parse
import httpx
from bs4 import BeautifulSoup

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class WebDorkProvider(BaseProvider):
    """Searches open web engines using dork operators (filetype:pdf, ext:epub, intitle:index of, etc.)."""

    name: str = "Web Search (Google + DDG)"
    supported_formats: list[str] = ["PDF", "EPUB"]

    # Multiple dorking templates to surface hidden documents, books, and open directories
    DORK_TEMPLATES: list[tuple[str, str]] = [
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
        file_format: str | None = None,
    ) -> list[ResourceItem]:
        results: list[ResourceItem] = []
        seen_urls: set[str] = set()

        # Select queries based on requested format
        dorks_to_run: list[tuple[str, str]] = []
        if file_format and file_format.upper() == "EPUB":
            dorks_to_run.append((f"{query} filetype:epub", "filetype:epub"))
            dorks_to_run.append((f"intitle:\"index of\" epub \"{query}\"", "index-of (epub)"))
        elif file_format and file_format.upper() == "PDF":
            dorks_to_run.append((f"{query} filetype:pdf", "filetype:pdf"))
            dorks_to_run.append((f"site:edu filetype:pdf \"{query}\"", "site:edu (academic)"))
            dorks_to_run.append((f"intitle:\"index of\" pdf \"{query}\"", "index-of (pdf)"))
        else:
            dorks_to_run.extend(self.DORK_TEMPLATES[:3])

        # Reserve room for both engines so one engine cannot crowd the other out.
        per_engine_limit = max(1, (limit + 1) // 2)
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            for engine, search_method in (
                ("Google", self._search_google_html),
                ("DuckDuckGo", self._search_duckduckgo_html),
            ):
                engine_count = 0
                for dork_pattern, dork_type in dorks_to_run:
                    if engine_count >= per_engine_limit:
                        break
                    dork_query = dork_pattern.format(query=query)
                    try:
                        items = await search_method(
                            client, dork_query, f"{engine}: {dork_type}",
                            per_engine_limit - engine_count,
                        )
                        for item in items:
                            if file_format and item.format != file_format.upper():
                                continue
                            if item.download_url in seen_urls:
                                continue
                            seen_urls.add(item.download_url)
                            results.append(item)
                            engine_count += 1
                    except Exception:
                        # Search engines may block or change their result markup.
                        continue

        return results[:limit]

    async def _search_duckduckgo_html(
        self,
        client: httpx.AsyncClient,
        search_query: str,
        dork_type: str,
        limit: int,
    ) -> list[ResourceItem]:
        items: list[ResourceItem] = []
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

            raw_href = str(title_elem.get("href", "") or "")
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
                source=f"Web Search ({dork_type.split(':', 1)[0]})",
                description=snippet,
                dork_type=dork_type,
                details_url=actual_url,
                score=80.0 if "index-of" in dork_type else 70.0,
            )
            items.append(item)

        return items

    async def _search_google_html(
        self,
        client: httpx.AsyncClient,
        search_query: str,
        dork_type: str,
        limit: int,
    ) -> list[ResourceItem]:
        """Search Google's public results page for links to document files."""
        response = await client.get(
            "https://www.google.com/search",
            params={"q": search_query, "num": min(max(limit * 2, 10), 100)},
            headers=DEFAULT_HEADERS,
        )
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        items: list[ResourceItem] = []
        seen: set[str] = set()
        for heading in soup.select("a:has(h3)"):
            if len(items) >= limit:
                break
            target = self._extract_target_url(str(heading.get("href", "")))
            if not target:
                continue
            if "google." in urllib.parse.urlparse(target).netloc.lower():
                continue

            title = heading.get_text(" ", strip=True)
            card = heading.find_parent("div", class_=re.compile(r"\bMjjYud\b"))
            snippet_node = card.select_one(".VwiC3b, .aCOpRe") if card else None
            snippet = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            detected_format = self._detect_format(target, title, snippet)
            if not detected_format or target in seen:
                continue

            seen.add(target)
            items.append(ResourceItem(
                title=title or target,
                download_url=target,
                format=detected_format,
                source="Web Search (Google)",
                description=snippet,
                dork_type=dork_type,
                details_url=target,
                score=70.0,
            ))
        return items

    def _extract_target_url(self, href: str) -> str | None:
        """Extracts the actual destination URL from a search engine redirect parameter."""
        if not href:
            return None
        parsed = urllib.parse.urlparse(href)
        params = urllib.parse.parse_qs(parsed.query)
        redirect = params.get("uddg")
        if not redirect and parsed.path == "/url" and "google." in parsed.netloc.lower():
            redirect = params.get("q")
        if redirect:
            target = redirect[0]
            # DDG sometimes double-encodes its redirect target.
            for _ in range(2):
                decoded = urllib.parse.unquote(target)
                if decoded == target:
                    break
                target = decoded
            return target if target.startswith(("http://", "https://")) else None
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return None

    def _detect_format(self, url: str, title: str, snippet: str) -> str | None:
        lower_url = url.lower()
        lower_title = title.lower()
        lower_snippet = snippet.lower()
        path = urllib.parse.urlparse(url).path.lower()

        if path.endswith(".pdf") or "[pdf]" in lower_title or "filetype: pdf" in lower_snippet:
            return "PDF"
        if path.endswith(".epub") or "[epub]" in lower_title:
            return "EPUB"
        if lower_url.endswith(".mobi") or ".mobi?" in lower_url:
            return "MOBI"
        if lower_url.endswith(".djvu"):
            return "DJVU"
        
        # If open directory, allow if it mentions pdf or epub
        if "index of" in lower_title and ("pdf" in lower_snippet or "epub" in lower_snippet):
            return "PDF"

        return None
