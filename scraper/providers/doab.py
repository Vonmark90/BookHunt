"""DOAB (Directory of Open Access Books) provider for peer-reviewed academic books."""

import re
from typing import List, Optional
import httpx

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class DoabProvider(BaseProvider):
    """Searches the Directory of Open Access Books (DOAB) repository for peer-reviewed books and monographs."""

    name = "DOAB"
    supported_formats = ["PDF", "EPUB"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        items: List[ResourceItem] = []
        url = "https://directory.doabooks.org/rest/search"
        # Fetch up to 2x limit to account for non-book entities or items without direct files
        params = {
            "query": query,
            "expand": "metadata",
            "limit": min(limit * 2, 40),
        }

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(url, params=params, headers=DEFAULT_HEADERS)
                if resp.status_code != 200:
                    return items

                records = resp.json()
                if not isinstance(records, list):
                    return items

                for item_data in records:
                    if len(items) >= limit:
                        break

                    title = item_data.get("name")
                    if not title or title.strip() == "":
                        continue

                    # Filter out communities or collections
                    if item_data.get("type") and item_data.get("type") != "item":
                        continue

                    authors: List[str] = []
                    year: Optional[int] = None
                    description: Optional[str] = None
                    direct_download_url: Optional[str] = None
                    doi: Optional[str] = None
                    handle = item_data.get("handle")

                    # Parse metadata fields
                    for meta in item_data.get("metadata", []):
                        k = meta.get("key", "")
                        v = meta.get("value")
                        if not v:
                            continue

                        if k == "dc.contributor.author":
                            authors.append(v)
                        elif k == "dc.date.issued" and not year:
                            m = re.search(r"\b(19\d\d|20\d\d)\b", v)
                            if m:
                                year = int(m.group(1))
                        elif k in ["dc.description.abstract", "dc.description"] and not description:
                            description = v
                        elif k == "oapen.identifier.doi" and not doi:
                            doi = v.strip()
                        elif "downloadurl" in k.lower() or "exampleurl" in k.lower():
                            v_clean = v.strip()
                            if v_clean.startswith("http") and not v_clean.lower().endswith(
                                (".jpg", ".jpeg", ".png", ".xml", ".tsv", ".ris", ".marc")
                            ):
                                direct_download_url = v_clean

                    handle_url = f"https://directory.doabooks.org/handle/{handle}" if handle else None
                    details_url = handle_url or (f"https://doi.org/{doi}" if doi else None)

                    # Determine download URL
                    download_url = direct_download_url
                    if not download_url:
                        if doi:
                            download_url = f"https://doi.org/{doi}"
                        elif handle_url:
                            download_url = handle_url
                        else:
                            continue

                    # Detect format
                    detected_format = "PDF"
                    dl_lower = download_url.lower()
                    title_lower = title.lower()
                    if "epub" in dl_lower or "[epub]" in title_lower:
                        detected_format = "EPUB"

                    if file_format and file_format.upper() != "ALL":
                        if file_format.upper() != detected_format:
                            continue

                    desc_snippet = (
                        description[:280] + "..."
                        if description and len(description) > 280
                        else description
                    )

                    item = ResourceItem(
                        title=title.strip(),
                        download_url=download_url,
                        format=detected_format,
                        source=self.name,
                        authors=authors,
                        year=year,
                        details_url=details_url or download_url,
                        description=desc_snippet,
                        score=88.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items[:limit]
