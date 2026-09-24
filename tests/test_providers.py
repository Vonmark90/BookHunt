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
