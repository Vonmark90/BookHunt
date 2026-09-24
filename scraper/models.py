"""Data models for universal ebook and document scraper."""

from dataclasses import dataclass, field
from typing import List, Optional
import hashlib


@dataclass
class ResourceItem:
    """Represents a discovered eBook, PDF, or document."""
    title: str
    download_url: str
    format: str  # "PDF", "EPUB", "MOBI", "DJVU", "HTML"
    source: str  # e.g., "Internet Archive", "arXiv", "Gutenberg", "Google Dork", "OpenLibrary"
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    details_url: Optional[str] = None
    size_bytes: Optional[int] = None
    description: Optional[str] = None
    dork_type: Optional[str] = None  # e.g., "filetype:pdf", "index-of", "site:edu"
    score: float = 0.0
    validated: bool = False
    content_type: Optional[str] = None

    @property
    def id(self) -> str:
        """Unique deterministic identifier based on source and URL."""
        raw = f"{self.source}:{self.download_url}:{self.title}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]

    @property
    def formatted_authors(self) -> str:
        if not self.authors:
            return "Unknown"
        if len(self.authors) <= 2:
            return ", ".join(self.authors)
        return f"{self.authors[0]} et al."

    @property
    def formatted_size(self) -> str:
        if not self.size_bytes or self.size_bytes <= 0:
            return "Unknown"
        size = float(self.size_bytes)
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "authors": self.authors,
            "year": self.year,
            "format": self.format,
            "source": self.source,
            "download_url": self.download_url,
            "details_url": self.details_url,
            "size_bytes": self.size_bytes,
            "formatted_size": self.formatted_size,
            "description": self.description,
            "dork_type": self.dork_type,
            "score": round(self.score, 2),
            "validated": self.validated,
        }
