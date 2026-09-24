"""Internet Archive (archive.org) provider for books, texts, and documents."""

from typing import List, Optional
import urllib.parse
import httpx

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class InternetArchiveProvider(BaseProvider):
    """Searches the Internet Archive's millions of digitized books, papers, and manuscripts."""

    name = "Internet Archive"
    supported_formats = ["PDF", "EPUB", "DJVU"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        items: List[ResourceItem] = []
        
        # Build Lucene query for Internet Archive
        clean_q = query.replace('"', '\\"')
        lucene_query = f'({clean_q}) AND mediatype:(texts)'
        
        if file_format:
            fmt_upper = file_format.upper()
            if fmt_upper == "PDF":
                lucene_query += ' AND (format:"Text PDF" OR format:"Additional Text PDF" OR format:"PDF")'
            elif fmt_upper == "EPUB":
                lucene_query += ' AND format:"EPUB"'

        params = {
            "q": lucene_query,
            "fl[]": ["identifier", "title", "creator", "year", "format", "description", "item_size"],
            "rows": str(limit),
            "output": "json",
        }

        url = "https://archive.org/advancedsearch.php"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params, headers=DEFAULT_HEADERS)
                if resp.status_code != 200:
                    return items

                data = resp.json()
                docs = data.get("response", {}).get("docs", [])

                for doc in docs:
                    identifier = doc.get("identifier")
                    if not identifier:
                        continue

                    title = doc.get("title", identifier)
                    creator = doc.get("creator", [])
                    if isinstance(creator, str):
                        authors = [creator]
                    elif isinstance(creator, list):
                        authors = [str(c) for c in creator if c]
                    else:
                        authors = []

                    year_val = doc.get("year")
                    year = int(year_val) if year_val and str(year_val).isdigit() else None
                    description = doc.get("description")
                    if isinstance(description, list):
                        description = " ".join(description)

                    formats = doc.get("format", [])
                    if isinstance(formats, str):
                        formats = [formats]

                    # Determine preferred format and construct download link
                    target_fmt = "PDF"
                    dl_ext = "pdf"
                    if file_format and file_format.upper() == "EPUB":
                        target_fmt = "EPUB"
                        dl_ext = "epub"
                    elif "EPUB" in formats and not file_format:
                        # If both are available, default to PDF or EPUB based on user
                        target_fmt = "PDF" if any("PDF" in f for f in formats) else "EPUB"
                        dl_ext = target_fmt.lower()
                    
                    download_url = f"https://archive.org/download/{identifier}/{identifier}.{dl_ext}"
                    details_url = f"https://archive.org/details/{identifier}"

                    size = doc.get("item_size")
                    size_bytes = int(size) if size and str(size).isdigit() else None

                    item = ResourceItem(
                        title=title,
                        download_url=download_url,
                        format=target_fmt,
                        source=self.name,
                        authors=authors,
                        year=year,
                        details_url=details_url,
                        size_bytes=size_bytes,
                        description=str(description)[:300] if description else None,
                        score=85.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items
