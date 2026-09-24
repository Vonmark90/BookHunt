"""HAL Science open archive provider for scientific publications, research books, and theses."""

from typing import List, Optional
import httpx

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class HalScienceProvider(BaseProvider):
    """Searches HAL Science open repository for scientific papers, theses, and research documents."""

    name = "HAL Science"
    supported_formats = ["PDF"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        # HAL provides full-text PDF documents
        if file_format and file_format.upper() not in ["PDF", "ALL"]:
            return []

        items: List[ResourceItem] = []
        url = "https://api.archives-ouvertes.fr/search/"
        params = {
            "q": query,
            "fq": "submitType_s:file",
            "wt": "json",
            "rows": limit,
            "fl": "docid,title_s,authFullName_s,producedDateY_i,files_s,uri_s,abstract_s",
        }

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = await client.get(url, params=params, headers=DEFAULT_HEADERS)
                if resp.status_code != 200:
                    return items

                docs = resp.json().get("response", {}).get("docs", [])
                for d in docs:
                    # Title
                    raw_titles = d.get("title_s", ["Untitled"])
                    title = raw_titles[0] if isinstance(raw_titles, list) else str(raw_titles)

                    # Authors
                    raw_authors = d.get("authFullName_s", [])
                    if isinstance(raw_authors, str):
                        authors = [raw_authors]
                    else:
                        authors = [str(a) for a in raw_authors]

                    # Year
                    year = d.get("producedDateY_i")
                    if year and not isinstance(year, int):
                        try:
                            year = int(year)
                        except ValueError:
                            year = None

                    # Download PDF URL
                    files = d.get("files_s", [])
                    pdf_url = files[0] if files else None
                    if not pdf_url:
                        continue

                    # Details URL
                    details_url = d.get("uri_s") or pdf_url

                    # Abstract
                    abstract_val = d.get("abstract_s", "")
                    if isinstance(abstract_val, list):
                        abstract_val = abstract_val[0] if abstract_val else ""
                    abstract_str = str(abstract_val).strip()
                    desc_snippet = (
                        abstract_str[:280] + "..." if len(abstract_str) > 280 else abstract_str
                    )

                    item = ResourceItem(
                        title=title,
                        download_url=pdf_url,
                        format="PDF",
                        source=self.name,
                        authors=authors,
                        year=year,
                        details_url=details_url,
                        description=desc_snippet if desc_snippet else None,
                        score=87.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items
