"""Provider registry."""

from .base import BaseProvider
from .internet_archive import InternetArchiveProvider
from .gutendex import GutenbergProvider
from .arxiv import ArxivProvider
from .open_library import OpenLibraryProvider
from .web_dork import WebDorkProvider
from .standard_ebooks import StandardEbooksProvider
from .oapen import OapenProvider
from .hal_science import HalScienceProvider
from .zenodo import ZenodoProvider
from .doab import DoabProvider
from .openalex import OpenAlexProvider

__all__ = [
    "BaseProvider",
    "InternetArchiveProvider",
    "GutenbergProvider",
    "ArxivProvider",
    "OpenLibraryProvider",
    "WebDorkProvider",
    "StandardEbooksProvider",
    "OapenProvider",
    "HalScienceProvider",
    "ZenodoProvider",
    "DoabProvider",
    "OpenAlexProvider",
]

