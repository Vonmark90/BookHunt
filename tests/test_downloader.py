"""Tests for Downloader resilience, Archive.org link resolution, and Aria2-style segmented downloads."""

import asyncio
import tempfile
import threading
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import httpx
import pytest

from scraper.models import ResourceItem
from scraper.downloader import Downloader, DownloadSegment
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


def test_segment_math():
    dl = Downloader(min_split_size=1024, max_connections=4)
    total_bytes = 4096
    num_segments = min(dl.max_connections, max(1, total_bytes // dl.min_split_size))
    assert num_segments == 4

    seg_size = total_bytes // num_segments
    segments = []
    for i in range(num_segments):
        start = i * seg_size
        end = (i + 1) * seg_size - 1 if i < num_segments - 1 else total_bytes - 1
        segments.append(DownloadSegment(index=i, start_byte=start, end_byte=end))

    assert segments[0].start_byte == 0 and segments[0].end_byte == 1023
    assert segments[3].start_byte == 3072 and segments[3].end_byte == 4095
    assert segments[0].remaining_bytes == 1024
    assert not segments[0].is_complete


@pytest.mark.asyncio
async def test_segmented_download_flow(monkeypatch):
    file_content = b"SEC1_" * 200 + b"SEC2_" * 200 + b"SEC3_" * 200 + b"SEC4_" * 200
    total_len = len(file_content)

    def custom_handler(request: httpx.Request):
        range_hdr = request.headers.get("range")
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={"Content-Length": str(total_len), "Accept-Ranges": "bytes", "Content-Type": "application/pdf"},
            )
        elif request.method == "GET":
            if range_hdr and range_hdr.startswith("bytes="):
                parts = range_hdr[6:].split("-")
                start = int(parts[0])
                end = int(parts[1]) if parts[1] else total_len - 1
                body = file_content[start:end + 1]
                return httpx.Response(
                    206,
                    headers={
                        "Content-Length": str(len(body)),
                        "Content-Range": f"bytes {start}-{end}/{total_len}",
                        "Content-Type": "application/pdf",
                    },
                    content=body,
                )
            return httpx.Response(200, headers={"Content-Length": str(total_len), "Content-Type": "application/pdf"}, content=file_content)
        return httpx.Response(404)

    transport = httpx.MockTransport(custom_handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr("scraper.downloader.httpx.AsyncClient", lambda *a, **kw: real_async_client(transport=transport, *a, **kw))

    with tempfile.TemporaryDirectory() as tmpdir:
        dl = Downloader(download_dir=tmpdir, max_connections=4, min_split_size=500)
        item = ResourceItem(
            title="Segmented Book",
            download_url="https://example.com/segmented.pdf",
            format="pdf",
            source="test",
        )

        progress_records = []
        def _cb(done, tot, speed):
            progress_records.append((done, tot))

        success, path = await dl.download_item(item, progress_callback=_cb)
        assert success is True
        dest = Path(path)
        assert dest.exists()
        assert dest.stat().st_size == total_len
        assert dest.read_bytes() == file_content
        # Ensure temporary staging files were cleanly cleaned up
        assert not Path(f"{path}.part").exists()
        assert not Path(f"{path}.part.meta").exists()
        assert len(progress_records) > 0


@pytest.mark.asyncio
async def test_segmented_download_cancellation_and_resumption(monkeypatch):
    file_content = b"DATA_PART_1" * 300 + b"DATA_PART_2" * 300
    total_len = len(file_content)

    def custom_handler(request: httpx.Request):
        range_hdr = request.headers.get("range")
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={"Content-Length": str(total_len), "Accept-Ranges": "bytes", "Content-Type": "application/pdf"},
            )
        elif request.method == "GET":
            if range_hdr and range_hdr.startswith("bytes="):
                parts = range_hdr[6:].split("-")
                start = int(parts[0])
                end = int(parts[1]) if parts[1] else total_len - 1
                body = file_content[start:end + 1]
                return httpx.Response(
                    206,
                    headers={
                        "Content-Length": str(len(body)),
                        "Content-Range": f"bytes {start}-{end}/{total_len}",
                        "Content-Type": "application/pdf",
                    },
                    content=body,
                )
        return httpx.Response(404)

    transport = httpx.MockTransport(custom_handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr("scraper.downloader.httpx.AsyncClient", lambda *a, **kw: real_async_client(transport=transport, *a, **kw))

    with tempfile.TemporaryDirectory() as tmpdir:
        dl = Downloader(download_dir=tmpdir, max_connections=2, min_split_size=500)
        item = ResourceItem(
            title="Resumable Book",
            download_url="https://example.com/resumable.pdf",
            format="pdf",
            source="test",
        )

        # 1. Immediate cancellation
        cancel_evt = threading.Event()
        cancel_evt.set()
        success, msg = await dl.download_item(item, cancel_event=cancel_evt)
        assert success is False
        assert "cancelled" in msg.lower()

        # 2. Resuming with cleared event
        cancel_evt.clear()
        success, path = await dl.download_item(item, cancel_event=cancel_evt)
        assert success is True
        dest = Path(path)
        assert dest.exists()
        assert dest.read_bytes() == file_content


@pytest.mark.asyncio
async def test_fallback_when_server_does_not_support_ranges(monkeypatch):
    file_content = b"STREAMING_ONLY_CONTENT" * 100

    def custom_handler(request: httpx.Request):
        if request.method == "HEAD":
            return httpx.Response(
                200,
                headers={"Content-Length": str(len(file_content)), "Accept-Ranges": "none", "Content-Type": "application/pdf"},
            )
        elif request.method == "GET":
            return httpx.Response(
                200,
                headers={"Content-Length": str(len(file_content)), "Content-Type": "application/pdf"},
                content=file_content,
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(custom_handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr("scraper.downloader.httpx.AsyncClient", lambda *a, **kw: real_async_client(transport=transport, *a, **kw))

    with tempfile.TemporaryDirectory() as tmpdir:
        dl = Downloader(download_dir=tmpdir, max_connections=4, min_split_size=500)
        item = ResourceItem(
            title="Fallback Book",
            download_url="https://example.com/stream.pdf",
            format="pdf",
            source="test",
        )

        success, path = await dl.download_item(item)
        assert success is True
        dest = Path(path)
        assert dest.exists()
        assert dest.read_bytes() == file_content
