"""Zenodo open repository provider for scientific books, preprints, and research documents."""

import re
from typing import List, Optional
import httpx

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class ZenodoProvider(BaseProvider):
    """Searches Zenodo open-access research repository for publications, books, and preprints."""

    name = "Zenodo"
    supported_formats = ["PDF"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        # Zenodo publications focus on PDF documents
        if file_format and file_format.upper() not in ["PDF", "ALL"]:
            return []

        items: List[ResourceItem] = []
        url = "https://zenodo.org/api/records"
        params = {
            "q": query,
            "type": "publication",
            "file_type": "pdf",
            "size": limit,
            "sort": "bestmatch",
        }

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(url, params=params, headers=DEFAULT_HEADERS)
                if resp.status_code != 200:
                    return items

                hits = resp.json().get("hits", {}).get("hits", [])
                for h in hits:
                    meta = h.get("metadata", {})
                    title = meta.get("title", "Untitled")
                    authors = [
                        c.get("name")
                        for c in meta.get("creators", [])
                        if c.get("name")
                    ]

                    pub_date = str(meta.get("publication_date", ""))
                    year = None
                    if len(pub_date) >= 4 and pub_date[:4].isdigit():
                        year = int(pub_date[:4])

                    raw_desc = meta.get("description", "")
                    clean_desc = re.sub(r"<[^>]+>", "", raw_desc).strip()
                    desc_snippet = (
                        clean_desc[:280] + "..." if len(clean_desc) > 280 else clean_desc
                    )

                    # Extract PDF download link
                    pdf_url = None
                    size_bytes = None
                    files = h.get("files", [])
                    for f in files:
                        key = (f.get("key") or "").lower()
                        mimetype = (f.get("mimetype") or "").lower()
                        if key.endswith(".pdf") or "pdf" in mimetype:
                            pdf_url = f.get("links", {}).get("self")
                            size_bytes = f.get("size")
                            break

                    if not pdf_url:
                        continue

                    details_url = h.get("links", {}).get("html") or pdf_url

                    item = ResourceItem(
                        title=title,
                        download_url=pdf_url,
                        format="PDF",
                        source=self.name,
                        authors=authors,
                        year=year,
                        details_url=details_url,
                        size_bytes=size_bytes,
                        description=desc_snippet if desc_snippet else None,
                        score=86.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items
