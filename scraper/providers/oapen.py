"""OAPEN Library provider for open access peer-reviewed academic books and textbooks."""

import re
from typing import List, Optional
import httpx

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class OapenProvider(BaseProvider):
    """Searches OAPEN Library for open-access monographs, edited volumes, and academic books."""

    name = "OAPEN Library"
    supported_formats = ["PDF"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        # OAPEN library documents are PDFs
        if file_format and file_format.upper() not in ["PDF", "ALL"]:
            return []

        items: List[ResourceItem] = []
        url = "https://library.oapen.org/rest/search"
        params = {
            "query": query,
            "expand": "metadata,bitstreams",
            "limit": limit,
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
                    title = item_data.get("name", "Untitled")
                    authors = []
                    year = None
                    description = None

                    # Extract Dublin Core metadata fields
                    for meta in item_data.get("metadata", []):
                        k = meta.get("key")
                        v = meta.get("value")
                        if not v:
                            continue

                        if k == "dc.contributor.author":
                            authors.append(v)
                        elif k == "dc.date.issued" and not year:
                            m = re.match(r"^(\d{4})", v)
                            if m:
                                year = int(m.group(1))
                        elif k in ["dc.description.abstract", "dc.description"] and not description:
                            description = v

                    # Locate direct PDF bitstream
                    pdf_url = None
                    size_bytes = None
                    for b in item_data.get("bitstreams", []):
                        mime = (b.get("mimeType") or "").lower()
                        name = (b.get("name") or "").lower()
                        if mime == "application/pdf" or name.endswith(".pdf"):
                            rel_link = b.get("retrieveLink")
                            if rel_link:
                                pdf_url = f"https://library.oapen.org{rel_link}"
                                size_bytes = b.get("sizeBytes")
                                break

                    if not pdf_url:
                        continue

                    handle = item_data.get("handle")
                    details_url = f"https://library.oapen.org/handle/{handle}" if handle else pdf_url

                    desc_snippet = (
                        description[:280] + "..."
                        if description and len(description) > 280
                        else description
                    )

                    item = ResourceItem(
                        title=title,
                        download_url=pdf_url,
                        format="PDF",
                        source=self.name,
                        authors=authors,
                        year=year,
                        details_url=details_url,
                        size_bytes=size_bytes,
                        description=desc_snippet,
                        score=89.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items
