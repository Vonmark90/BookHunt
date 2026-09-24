"""Tests for Downloader resilience and Archive.org link resolution."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scraper.models import ResourceItem
from scraper.downloader import Downloader
from scraper.providers.archive_helper import extract_ia_identifier, resolve_ia_direct_url


def test_extract_ia_identifier():
    assert extract_ia_identifier("https://archive.org/download/my_book_123/my_book_123.pdf") == ("my_book_123", "my_book_123.pdf")
    assert extract_ia_identifier("https://archive.org/details/my_book_123") == ("my_book_123", None)
    assert extract_ia_identifier("https://google.com/search") is None


def test_extract_pdf_from_html():
    dl = Downloader()
    html_with_meta = """
    <html><head><meta name="citation_pdf_url" content="https://example.com/doc.pdf"></head></html>
    """
    assert dl._extract_pdf_from_html(html_with_meta, "https://example.com/page") == "https://example.com/doc.pdf"

    html_with_anchor = """
    <html><body><a href="/files/book.pdf">Download PDF</a></body></html>
    """
    assert dl._extract_pdf_from_html(html_with_anchor, "https://example.com/page") == "https://example.com/files/book.pdf"


@pytest.mark.asyncio
async def test_resolve_ia_direct_url_restricted():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "metadata": {
            "access-restricted-item": "true",
            "collection": ["inlibrary", "lendinglibrary"],
        },
        "files": [],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    url, err = await resolve_ia_direct_url("restricted_book", client=mock_client)
    assert url is None
    assert "Controlled Digital Lending" in err


@pytest.mark.asyncio
async def test_resolve_ia_direct_url_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "metadata": {},
        "files": [
            {"name": "thumb.jpg", "size": "100", "private": "false"},
            {"name": "ActualBook.pdf", "size": "5000000", "private": "false"},
            {"name": "Other.epub", "size": "2000000", "private": "false"},
        ],
    }

    mock_client = AsyncMock()
    mock_client.get.return_value = mock_resp

    url, err = await resolve_ia_direct_url("valid_book", preferred_fmt="pdf", client=mock_client)
    assert err is None
    assert url == "https://archive.org/download/valid_book/ActualBook.pdf"
