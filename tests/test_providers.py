"""Tests for Provider registrations and interfaces."""

import pytest
from scraper.providers.base import BaseProvider
from scraper.providers.arxiv import ArxivProvider
from scraper.providers.gutendex import GutenbergProvider
from scraper.providers.internet_archive import InternetArchiveProvider
from scraper.providers.open_library import OpenLibraryProvider
from scraper.providers.standard_ebooks import StandardEbooksProvider
from scraper.providers.web_dork import WebDorkProvider
from scraper.providers.zenodo import ZenodoProvider
from scraper.providers.oapen import OapenProvider
from scraper.providers.hal_science import HalScienceProvider
from scraper.providers.doab import DoabProvider
from scraper.providers.openalex import OpenAlexProvider


PROVIDERS = [
    ArxivProvider,
    GutenbergProvider,
    InternetArchiveProvider,
    OpenLibraryProvider,
    StandardEbooksProvider,
    WebDorkProvider,
    ZenodoProvider,
    OapenProvider,
    HalScienceProvider,
    DoabProvider,
    OpenAlexProvider,
]


@pytest.mark.parametrize("provider_cls", PROVIDERS)
def test_provider_subclass_contract(provider_cls):
    assert issubclass(provider_cls, BaseProvider)
    instance = provider_cls()
    assert hasattr(instance, "name")
    assert isinstance(instance.name, str)
    assert len(instance.name) > 0
    assert hasattr(instance, "supported_formats")
    assert isinstance(instance.supported_formats, list)
    assert hasattr(instance, "search")
    assert callable(instance.search)


def test_openalex_abstract_reconstruction():
    provider = OpenAlexProvider()
    inverted = {
        "Deep": [0],
        "learning": [1],
        "is": [2],
        "a": [3],
        "subset": [4],
        "of": [5],
        "machine": [6],
        "learning.": [7],
    }
    reconstructed = provider._reconstruct_abstract(inverted)
    assert reconstructed == "Deep learning is a subset of machine learning."

    assert provider._reconstruct_abstract(None) is None
    assert provider._reconstruct_abstract({}) is None


def test_universal_scraper_has_all_providers():
    from scraper.engine import UniversalScraper
    scraper = UniversalScraper()
    assert "doab" in scraper.providers
    assert "openalex" in scraper.providers
    assert len(scraper.providers) == 11

