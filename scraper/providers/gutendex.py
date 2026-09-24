"""Project Gutenberg search provider via the Gutendex public API."""

from typing import List, Optional
import httpx

from .base import BaseProvider, DEFAULT_HEADERS
from ..models import ResourceItem


class GutenbergProvider(BaseProvider):
    """Searches Project Gutenberg's catalog of classic literature and public-domain eBooks."""

    name = "Project Gutenberg"
    supported_formats = ["EPUB", "PDF", "HTML"]

    async def search(
        self,
        query: str,
        limit: int = 15,
        file_format: Optional[str] = None,
    ) -> List[ResourceItem]:
        items: List[ResourceItem] = []
        url = "https://gutendex.com/books/"
        params = {"search": query}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url, params=params, headers=DEFAULT_HEADERS)
                if resp.status_code != 200:
                    return items

                data = resp.json()
                books = data.get("results", [])

                for b in books[:limit]:
                    title = b.get("title", "Untitled")
                    authors = [a.get("name", "") for a in b.get("authors", []) if a.get("name")]
                    formats = b.get("formats", {})

                    # Extract best download link according to preference
                    download_url = None
                    detected_format = "EPUB"

                    if file_format and file_format.upper() == "PDF":
                        # Gutenberg rarely has native PDFs, but check if any pdf/octet is present
                        download_url = formats.get("application/pdf")
                        detected_format = "PDF"
                        if not download_url:
                            # Skip if user strictly asked for PDF and none exists
                            continue
                    else:
                        # Prefer EPUB 3 or EPUB zip
                        for mime in [
                            "application/epub+zip",
                            "application/x-mobipocket-ebook",
                            "text/html",
                            "text/plain; charset=utf-8",
                        ]:
                            if mime in formats:
                                download_url = formats[mime]
                                if "epub" in mime:
                                    detected_format = "EPUB"
                                elif "mobi" in mime:
                                    detected_format = "MOBI"
                                else:
                                    detected_format = "HTML"
                                break

                    if not download_url:
                        continue

                    # Gutenberg details page
                    book_id = b.get("id")
                    details_url = f"https://www.gutenberg.org/ebooks/{book_id}" if book_id else None

                    # Subjects as description
                    subjects = b.get("subjects", [])
                    desc = "; ".join(subjects[:3]) if subjects else None

                    item = ResourceItem(
                        title=title,
                        download_url=download_url,
                        format=detected_format,
                        source=self.name,
                        authors=authors,
                        year=None,
                        details_url=details_url,
                        description=desc,
                        score=90.0,
                    )
                    items.append(item)

            except Exception:
                pass

        return items
