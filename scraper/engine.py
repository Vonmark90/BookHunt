"""Universal Scraper Engine: Orchestrates multi-provider searches, deduplication, and ranking."""

import asyncio
import re
from typing import Dict, List, Optional, Set
import httpx

from .models import ResourceItem
from .providers.base import BaseProvider, DEFAULT_HEADERS
from .providers.internet_archive import InternetArchiveProvider
from .providers.gutendex import GutenbergProvider
from .providers.arxiv import ArxivProvider
from .providers.open_library import OpenLibraryProvider
from .providers.web_dork import WebDorkProvider
from .providers.standard_ebooks import StandardEbooksProvider
from .providers.oapen import OapenProvider
from .providers.hal_science import HalScienceProvider
from .providers.zenodo import ZenodoProvider


class UniversalScraper:
    """Central engine that searches multiple digital libraries, academic archives, and web dorks."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout
        self.providers: Dict[str, BaseProvider] = {
            "internet_archive": InternetArchiveProvider(timeout=timeout),
            "gutenberg": GutenbergProvider(timeout=timeout),
            "arxiv": ArxivProvider(timeout=timeout),
            "open_library": OpenLibraryProvider(timeout=timeout),
            "web_dork": WebDorkProvider(timeout=timeout),
            "standard_ebooks": StandardEbooksProvider(timeout=timeout),
            "oapen": OapenProvider(timeout=timeout),
            "hal_science": HalScienceProvider(timeout=timeout),
            "zenodo": ZenodoProvider(timeout=timeout),
        }


    async def search(
        self,
        query: str,
        limit_per_source: int = 15,
        file_format: Optional[str] = None,
        enabled_sources: Optional[List[str]] = None,
        validate_links: bool = False,
    ) -> List[ResourceItem]:
        """Execute parallel searches across all designated providers.

        Args:
            query: Topic or keywords to search.
            limit_per_source: Max items requested from each provider.
            file_format: 'PDF', 'EPUB', or None for all.
            enabled_sources: List of provider keys to query (or None for all).
            validate_links: Whether to perform HEAD requests to check link liveness and file size.

        Returns:
            Ranked, deduplicated list of ResourceItem objects.
        """
        active_providers = []
        for key, provider in self.providers.items():
            if enabled_sources is None or key in enabled_sources:
                active_providers.append(provider)

        # Launch all provider searches concurrently
        tasks = [
            provider.search(query=query, limit=limit_per_source, file_format=file_format)
            for provider in active_providers
        ]
        results_nested = await asyncio.gather(*tasks, return_exceptions=True)

        all_items: List[ResourceItem] = []
        for res in results_nested:
            if isinstance(res, list):
                all_items.extend(res)

        # Deduplicate
        unique_items = self._deduplicate(all_items)

        # Calculate relevance scores
        for item in unique_items:
            item.score = self._compute_score(item, query)

        # Sort by relevance score descending
        unique_items.sort(key=lambda x: x.score, reverse=True)

        # Optionally validate links via HEAD requests
        if validate_links:
            await self._validate_urls(unique_items)

        return unique_items

    def _normalize_title(self, title: str) -> str:
        """Strips noise, punctuation, and file extensions for deduplication matching."""
        t = title.lower()
        t = re.sub(r"\[.*?\]|\(.*?\)", "", t)
        t = re.sub(r"\.pdf|\.epub|\.djvu", "", t)
        t = re.sub(r"[^\w\s]", "", t)
        return " ".join(t.split())

    def _deduplicate(self, items: List[ResourceItem]) -> List[ResourceItem]:
        seen_urls: Set[str] = set()
        seen_titles: Dict[str, ResourceItem] = {}
        unique: List[ResourceItem] = []

        for item in items:
            clean_url = item.download_url.split("?")[0].rstrip("/")
            if clean_url in seen_urls:
                continue
            seen_urls.add(clean_url)

            norm_title = self._normalize_title(item.title)
            if len(norm_title) > 6 and norm_title in seen_titles:
                existing = seen_titles[norm_title]
                # If existing doesn't have authors or size, enrich it
                if not existing.authors and item.authors:
                    existing.authors = item.authors
                if not existing.size_bytes and item.size_bytes:
                    existing.size_bytes = item.size_bytes
                continue

            if len(norm_title) > 6:
                seen_titles[norm_title] = item

            unique.append(item)

        return unique

    def _compute_score(self, item: ResourceItem, query: str) -> float:
        """Computes a relevance score based on keyword match, metadata richness, and provider trust."""
        score = 50.0
        query_terms = [t.lower() for t in query.split() if len(t) > 2]
        title_lower = item.title.lower()

        # Title keyword match
        matched_terms = sum(1 for term in query_terms if term in title_lower)
        if query_terms:
            score += (matched_terms / len(query_terms)) * 30.0

        # Exact query match
        if query.lower() in title_lower:
            score += 15.0

        # Metadata richness
        if item.authors:
            score += 5.0
        if item.year:
            score += 5.0
        if item.size_bytes:
            score += 5.0

        # Format bonus
        if item.format in ["PDF", "EPUB"]:
            score += 5.0

        # Direct file link bonus
        if item.download_url.lower().endswith((".pdf", ".epub")):
            score += 5.0

        return min(score, 100.0)

    async def _validate_urls(self, items: List[ResourceItem], concurrency: int = 8) -> None:
        """Verifies URLs concurrently and populates file size if available."""
        sem = asyncio.Semaphore(concurrency)

        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=DEFAULT_HEADERS) as client:
            async def _check(item: ResourceItem):
                async with sem:
                    try:
                        resp = await client.head(item.download_url)
                        if resp.status_code in [200, 206]:
                            item.validated = True
                            cl = resp.headers.get("content-length")
                            if cl and cl.isdigit():
                                item.size_bytes = int(cl)
                            ct = resp.headers.get("content-type")
                            if ct:
                                item.content_type = ct
                    except Exception:
                        pass

            tasks = [_check(it) for it in items[:30]]  # Validate top 30
            await asyncio.gather(*tasks, return_exceptions=True)
