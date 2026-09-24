"""OpenAlex provider for open access academic books, monographs, and book chapters."""

from typing import List, Optional
import httpx

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class OpenAlexProvider(BaseProvider):
    """Searches OpenAlex scholarly knowledge graph for open access books, monographs, and textbooks."""

    name = "OpenAlex Books"
    supported_formats = ["PDF", "EPUB"]

    def _reconstruct_abstract(self, inverted_index: Optional[dict]) -> Optional[str]:
        """Rebuilds readable text from OpenAlex abstract inverted index structure."""
        if not inverted_index or not isinstance(inverted_index, dict):
            return None
        try:
            words = []
            for word, positions in inverted_index.items():
                for pos in positions:
                    words.append((pos, word))
            words.sort(key=lambda x: x[0])
            return " ".join(w[1] for w in words)
        except Exception:
            return None

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        items: List[ResourceItem] = []
        url = "https://api.openalex.org/works"
        params = {
            "search": query,
            "filter": "is_oa:true,type:book|monograph|book-chapter",
            "per_page": min(limit * 2, 40),
            "sort": "relevance_score:desc",
        }

        # Friendly User-Agent with contact header per OpenAlex API etiquette
        headers = dict(DEFAULT_HEADERS)
        headers["User-Agent"] = "BookHunt/1.0 (https://github.com/universal-book-scraper; bookhunt@users.noreply.github.com)"

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code != 200:
                    return items

                data = resp.json()
                results = data.get("results", [])
                if not isinstance(results, list):
                    return items

                for work in results:
                    if len(items) >= limit:
                        break

                    title = work.get("title")
                    if not title or title.strip() == "":
                        continue

                    # Extract authors
                    authors: List[str] = []
                    for authorship in work.get("authorships", []):
                        author_obj = authorship.get("author", {})
                        author_name = author_obj.get("display_name")
                        if author_name:
                            authors.append(author_name)

                    year = work.get("publication_year")

                    # Abstract
                    abstract_raw = self._reconstruct_abstract(work.get("abstract_inverted_index"))
                    desc_snippet = (
                        abstract_raw[:280] + "..."
                        if abstract_raw and len(abstract_raw) > 280
                        else abstract_raw
                    )

                    best_oa = work.get("best_oa_location") or {}
                    oa_info = work.get("open_access") or {}
                    doi = work.get("doi")
                    item_id = work.get("id")

                    # Primary download link preference
                    pdf_url = best_oa.get("pdf_url")
                    oa_url = oa_info.get("oa_url")
                    landing_page = best_oa.get("landing_page_url")

                    download_url = pdf_url or oa_url or landing_page or doi or item_id
                    if not download_url:
                        continue

                    details_url = doi or landing_page or item_id or download_url

                    # Format detection
                    dl_lower = download_url.lower()
                    title_lower = title.lower()
                    detected_format = "PDF"
                    if "epub" in dl_lower or "[epub]" in title_lower:
                        detected_format = "EPUB"

                    if file_format and file_format.upper() != "ALL":
                        if file_format.upper() != detected_format:
                            continue

                    item = ResourceItem(
                        title=title.strip(),
                        download_url=download_url,
                        format=detected_format,
                        source=self.name,
                        authors=authors,
                        year=year,
                        details_url=details_url,
                        description=desc_snippet,
                        score=89.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items[:limit]
