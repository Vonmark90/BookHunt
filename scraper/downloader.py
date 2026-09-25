"""Aria2-inspired high-performance segmented async downloader with progress tracking,
file preallocation, stateful resume (.part/.meta), atomic finalization, and resilient link resolution.
"""

import asyncio
from dataclasses import dataclass
import json
import os
import re
import time
import threading
import urllib.parse
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import httpx
from bs4 import BeautifulSoup
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from .models import ResourceItem
from .providers.base import DEFAULT_HEADERS
from .providers.archive_helper import extract_ia_identifier, resolve_ia_direct_url


@dataclass
class DownloadSegment:
    """Represents a discrete byte-range segment for parallel downloading."""
    index: int
    start_byte: int
    end_byte: int
    downloaded_bytes: int = 0

    @property
    def current_pos(self) -> int:
        return self.start_byte + self.downloaded_bytes

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.end_byte - self.current_pos + 1)

    @property
    def is_complete(self) -> bool:
        return self.current_pos > self.end_byte

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "start_byte": self.start_byte,
            "end_byte": self.end_byte,
            "downloaded_bytes": self.downloaded_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DownloadSegment":
        return cls(
            index=data["index"],
            start_byte=data["start_byte"],
            end_byte=data["end_byte"],
            downloaded_bytes=data.get("downloaded_bytes", 0),
        )


class Downloader:
    """Aria2-inspired multi-connection streaming downloader with segmented chunks,
    sparse file preallocation, stateful resume, and resilient link extraction.
    """

    def __init__(
        self,
        download_dir: str = "./downloads",
        max_connections: int = 4,
        min_split_size: int = 2 * 1024 * 1024,  # 2MB minimum segment size
        enable_segmented: bool = True,
        chunk_size: int = 65536,
    ):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.max_connections = max(1, min(16, max_connections))
        self.min_split_size = max(1024, min_split_size)
        self.enable_segmented = enable_segmented
        self.chunk_size = chunk_size

    def sanitize_filename(self, title: str, extension: str) -> str:
        """Generates a clean, safe local filename."""
        clean = re.sub(r"""[\\/*?:"<>|]""", "", title)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            clean = "downloaded_document"

        # Cap length to avoid OS filename limits
        clean = clean[:120]

        ext = extension.lstrip(".").lower()
        if not ext:
            ext = "pdf"

        return f"{clean}.{ext}"

    def _extract_pdf_from_html(self, html_text: str, base_url: str) -> Optional[str]:
        """Attempts to extract direct PDF / document links from an HTML landing page."""
        try:
            soup = BeautifulSoup(html_text, "html.parser")

            # 1. Scholarly citation meta tag (Google Scholar / HighWire standard)
            meta = soup.find("meta", {"name": re.compile(r"citation_pdf_url", re.IGNORECASE)})
            if meta and meta.get("content"):
                return urllib.parse.urljoin(base_url, meta["content"])

            # 2. Alternate link tag
            alt = soup.find("link", {"type": "application/pdf"})
            if alt and alt.get("href"):
                return urllib.parse.urljoin(base_url, alt["href"])

            # 3. Direct PDF/EPUB anchors
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                href_lower = href.lower()
                text_lower = a.get_text(strip=True).lower()

                # Check for explicit pdf/epub extensions or download text
                if (href_lower.endswith(".pdf") or href_lower.endswith(".epub")) and not href_lower.startswith("#"):
                    return urllib.parse.urljoin(base_url, href)
                if ("download" in text_lower or "full text" in text_lower) and "pdf" in text_lower:
                    if not href_lower.startswith("#") and not href_lower.startswith("javascript:"):
                        return urllib.parse.urljoin(base_url, href)

        except Exception:
            pass
        return None

    def _preallocate_file(self, fd: int, total_bytes: int):
        """Preallocates file space on disk to eliminate fragmentation and filesystem stalls."""
        try:
            if hasattr(os, "posix_fallocate"):
                os.posix_fallocate(fd, 0, total_bytes)
            else:
                os.ftruncate(fd, total_bytes)
        except Exception:
            try:
                os.ftruncate(fd, total_bytes)
            except Exception:
                pass

    def _write_chunk_at(self, fd: int, chunk: bytes, offset: int, lock: asyncio.Lock):
        """Writes data at an exact byte offset using lock-free pwrite where supported."""
        if hasattr(os, "pwrite"):
            os.pwrite(fd, chunk, offset)
        else:
            with lock:
                os.lseek(fd, offset, os.SEEK_SET)
                os.write(fd, chunk)

    def _load_meta(self, meta_path: Path, target_url: str, total_bytes: int) -> Optional[List[DownloadSegment]]:
        """Loads and verifies segmented download state from .meta file."""
        if not meta_path.exists():
            return None
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            if data.get("url") == target_url and data.get("total_bytes") == total_bytes:
                segments = [DownloadSegment.from_dict(d) for d in data.get("segments", [])]
                if segments:
                    return segments
        except Exception:
            pass
        return None

    def _save_meta(self, meta_path: Path, target_url: str, total_bytes: int, segments: List[DownloadSegment]):
        """Persists segment download progress to disk."""
        try:
            data = {
                "url": target_url,
                "total_bytes": total_bytes,
                "timestamp": time.time(),
                "segments": [seg.to_dict() for seg in segments],
            }
            meta_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    async def _probe_server(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict,
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[httpx.Response]]:
        """Probes the remote endpoint for Accept-Ranges support, Content-Length, and redirects."""
        try:
            resp = await client.head(url, headers=headers)

            if resp.status_code in [403, 405, 501]:
                probe_headers = dict(headers)
                probe_headers["Range"] = "bytes=0-0"
                resp = await client.get(url, headers=probe_headers)

            if resp.status_code not in [200, 206]:
                return False, None, None, resp

            content_type = resp.headers.get("content-type", "").lower()
            accept_ranges = "bytes" in resp.headers.get("accept-ranges", "").lower() or resp.status_code == 206

            total_size: Optional[int] = None
            if resp.status_code == 206 and "content-range" in resp.headers:
                match = re.search(r"/(\d+)$", resp.headers["content-range"])
                if match:
                    total_size = int(match.group(1))
            elif "content-length" in resp.headers and resp.headers["content-length"].isdigit():
                total_size = int(resp.headers["content-length"])

            return accept_ranges, total_size, content_type, resp
        except Exception:
            return False, None, None, None

    async def download_item(
        self,
        item: ResourceItem,
        custom_filename: Optional[str] = None,
        progress: Optional[Progress] = None,
        progress_callback: Optional[Callable[[int, Optional[int], float], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
        """Downloads a single ResourceItem using multi-connection segmented downloading
        with automatic fallback to single-stream streaming, stateful resumption, and atomic finalization.
        """
        target_url = item.download_url
        ext = item.format.lower() if item.format else "pdf"

        # 1. Archive.org special identifier resolution
        ia_info = extract_ia_identifier(target_url)
        if ia_info:
            identifier, _ = ia_info
            resolved_url, ia_err = await resolve_ia_direct_url(identifier, preferred_fmt=ext)
            if ia_err:
                return False, ia_err
            if resolved_url:
                target_url = resolved_url

        filename = custom_filename or self.sanitize_filename(item.title, ext)
        dest_path = self.download_dir / filename
        part_path = self.download_dir / f"{filename}.part"
        meta_path = self.download_dir / f"{filename}.part.meta"

        # Check if already completed
        if dest_path.exists():
            existing_size = dest_path.stat().st_size
            if item.size_bytes and existing_size == item.size_bytes and existing_size > 0:
                if progress_callback:
                    progress_callback(existing_size, existing_size, 0.0)
                return True, f"Already downloaded: {dest_path.name}"
            elif not item.size_bytes and existing_size > 0:
                if progress_callback:
                    progress_callback(existing_size, existing_size, 0.0)
                return True, f"Already downloaded: {dest_path.name}"

        headers = dict(DEFAULT_HEADERS)
        parsed_url = urllib.parse.urlparse(target_url)
        if parsed_url.scheme and parsed_url.netloc:
            headers["Referer"] = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                if cancel_event and cancel_event.is_set():
                    return False, "Download cancelled."

                # Probe server capabilities
                supports_range, total_bytes, content_type, probe_resp = await self._probe_server(client, target_url, headers)

                # Check if server returned HTML landing page
                if content_type and "text/html" in content_type and not target_url.lower().endswith(".html"):
                    get_resp = await client.get(target_url, headers=headers)
                    if get_resp.status_code in [200, 206]:
                        html_text = get_resp.text
                        extracted = self._extract_pdf_from_html(html_text, str(get_resp.url))
                        if extracted and extracted != target_url:
                            target_url = extracted
                            headers["Referer"] = str(get_resp.url)
                            supports_range, total_bytes, content_type, _ = await self._probe_server(client, target_url, headers)
                        else:
                            return False, "Server returned an HTML landing page instead of a document file (login/paywall required)."
                    else:
                        return False, f"HTTP Error {get_resp.status_code}: {get_resp.reason_phrase}"

                # Decide download strategy: Segmented vs Single-Stream
                can_segment = (
                    self.enable_segmented
                    and supports_range
                    and total_bytes is not None
                    and total_bytes >= self.min_split_size
                    and self.max_connections > 1
                )

                if can_segment and total_bytes is not None:
                    return await self._download_segmented(
                        client=client,
                        target_url=target_url,
                        headers=headers,
                        dest_path=dest_path,
                        part_path=part_path,
                        meta_path=meta_path,
                        total_bytes=total_bytes,
                        filename=filename,
                        progress=progress,
                        progress_callback=progress_callback,
                        cancel_event=cancel_event,
                    )
                else:
                    return await self._download_single_stream(
                        client=client,
                        target_url=target_url,
                        headers=headers,
                        dest_path=dest_path,
                        part_path=part_path,
                        meta_path=meta_path,
                        filename=filename,
                        total_bytes=total_bytes,
                        progress=progress,
                        progress_callback=progress_callback,
                        cancel_event=cancel_event,
                    )

        except Exception as e:
            return False, f"Download failed: {str(e)}"

    async def _download_segmented(
        self,
        client: httpx.AsyncClient,
        target_url: str,
        headers: dict,
        dest_path: Path,
        part_path: Path,
        meta_path: Path,
        total_bytes: int,
        filename: str,
        progress: Optional[Progress] = None,
        progress_callback: Optional[Callable[[int, Optional[int], float], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
        """Aria2-style multi-connection segmented download with preallocated sparse file."""
        num_segments = min(self.max_connections, max(1, total_bytes // self.min_split_size))

        # Check for resumable segments
        segments = self._load_meta(meta_path, target_url, total_bytes)
        if not segments or len(segments) != num_segments:
            segments = []
            seg_size = total_bytes // num_segments
            for i in range(num_segments):
                start = i * seg_size
                end = (i + 1) * seg_size - 1 if i < num_segments - 1 else total_bytes - 1
                segments.append(DownloadSegment(index=i, start_byte=start, end_byte=end))

        # Preallocate or open sparse .part file
        fd = os.open(str(part_path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            current_file_size = os.fstat(fd).st_size
            if current_file_size != total_bytes:
                self._preallocate_file(fd, total_bytes)

            file_lock = asyncio.Lock()
            completed_bytes = sum(seg.downloaded_bytes for seg in segments)
            initial_completed = completed_bytes
            t_start = time.time()
            last_cb_time = 0.0

            task_id = None
            if progress:
                task_id = progress.add_task(
                    f"[cyan]{filename[:26]} ({num_segments}x)[/cyan]",
                    total=total_bytes,
                    completed=completed_bytes,
                )

            if progress_callback:
                progress_callback(completed_bytes, total_bytes, 0.0)

            async def _worker(seg: DownloadSegment):
                nonlocal completed_bytes, last_cb_time

                if seg.is_complete:
                    return True

                retries = 3
                while retries > 0:
                    if cancel_event and cancel_event.is_set():
                        return False

                    req_headers = dict(headers)
                    req_headers["Range"] = f"bytes={seg.current_pos}-{seg.end_byte}"

                    try:
                        async with client.stream("GET", target_url, headers=req_headers) as resp:
                            if resp.status_code not in [200, 206]:
                                retries -= 1
                                await asyncio.sleep(0.5)
                                continue

                            async for chunk in resp.aiter_bytes(chunk_size=self.chunk_size):
                                if cancel_event and cancel_event.is_set():
                                    return False

                                write_offset = seg.current_pos
                                self._write_chunk_at(fd, chunk, write_offset, file_lock)

                                seg.downloaded_bytes += len(chunk)
                                completed_bytes += len(chunk)

                                if progress and task_id is not None:
                                    progress.update(task_id, advance=len(chunk))

                                now = time.time()
                                if progress_callback and (now - last_cb_time >= 0.05 or completed_bytes >= total_bytes):
                                    elapsed = max(0.05, now - t_start)
                                    speed = (completed_bytes - initial_completed) / elapsed
                                    progress_callback(completed_bytes, total_bytes, speed)
                                    last_cb_time = now

                            return True
                    except Exception:
                        retries -= 1
                        await asyncio.sleep(0.5)

                return False

            # Run segmented download tasks concurrently
            tasks = [_worker(seg) for seg in segments]
            results = await asyncio.gather(*tasks)

            # Persist state
            self._save_meta(meta_path, target_url, total_bytes, segments)

            if cancel_event and cancel_event.is_set():
                return False, "Download cancelled by user."

            if not all(results) or completed_bytes < total_bytes:
                return False, "Segmented download failed for one or more segments. Partial progress saved for resume."

            # Flush file to disk
            os.fsync(fd)

        finally:
            os.close(fd)

        # Atomic finalization
        if progress and task_id is not None:
            progress.remove_task(task_id)

        if meta_path.exists():
            try:
                meta_path.unlink()
            except Exception:
                pass

        # Atomic rename .part -> dest_path
        part_path.replace(dest_path)

        if progress_callback:
            elapsed = max(0.01, time.time() - t_start)
            speed = (completed_bytes - initial_completed) / elapsed
            progress_callback(completed_bytes, total_bytes, speed)

        return True, str(dest_path)

    async def _download_single_stream(
        self,
        client: httpx.AsyncClient,
        target_url: str,
        headers: dict,
        dest_path: Path,
        part_path: Path,
        meta_path: Path,
        filename: str,
        total_bytes: Optional[int],
        progress: Optional[Progress] = None,
        progress_callback: Optional[Callable[[int, Optional[int], float], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> Tuple[bool, str]:
        """Resilient single-connection streaming into .part with atomic completion."""
        existing_size = 0
        if part_path.exists():
            existing_size = part_path.stat().st_size
            if existing_size > 0:
                headers["Range"] = f"bytes={existing_size}-"

        resp = await client.send(
            client.build_request("GET", target_url, headers=headers),
            stream=True,
        )

        # Retry without Range if 416 or 403
        if resp.status_code in [401, 403, 416] and "Range" in headers:
            await resp.aclose()
            headers.pop("Range", None)
            existing_size = 0
            resp = await client.send(
                client.build_request("GET", target_url, headers=headers),
                stream=True,
            )

        if resp.status_code not in [200, 206]:
            status = resp.status_code
            phrase = resp.reason_phrase
            await resp.aclose()
            if status == 401:
                return False, "HTTP 401: Unauthorized. The hosting site requires an account, active subscription, or loan."
            elif status == 403:
                return False, "HTTP 403: Forbidden. Direct file access is blocked by the host server."
            elif status == 404:
                return False, "HTTP 404: File not found on the host server."
            return False, f"HTTP Error {status}: {phrase}"

        # Verify Content-Type for landing pages
        content_type = resp.headers.get("content-type", "").lower()
        if "text/html" in content_type and not target_url.lower().endswith(".html"):
            html_bytes = await resp.aread()
            html_text = html_bytes.decode("utf-8", errors="replace")
            await resp.aclose()

            extracted_pdf = self._extract_pdf_from_html(html_text, str(resp.url))
            if extracted_pdf and extracted_pdf != target_url:
                target_url = extracted_pdf
                headers["Referer"] = str(resp.url)
                headers.pop("Range", None)
                existing_size = 0

                resp = await client.send(
                    client.build_request("GET", target_url, headers=headers),
                    stream=True,
                )
                if resp.status_code not in [200, 206]:
                    await resp.aclose()
                    return False, f"Extracted file link failed with HTTP {resp.status_code}"
                content_type = resp.headers.get("content-type", "").lower()
                if "text/html" in content_type:
                    await resp.aclose()
                    return False, "Host returned an HTML landing page instead of a document file."
            else:
                return False, "Server returned an HTML landing page instead of a document file (login/paywall required)."

        content_len = resp.headers.get("content-length")
        if content_len and content_len.isdigit():
            total_bytes = int(content_len) + existing_size

        task_id = None
        if progress:
            task_id = progress.add_task(
                f"[cyan]{filename[:30]}...",
                total=total_bytes,
                completed=existing_size,
            )

        mode = "ab" if resp.status_code == 206 and existing_size > 0 else "wb"
        completed_bytes = existing_size
        t_start = time.time()
        last_cb_time = 0.0

        if progress_callback:
            progress_callback(completed_bytes, total_bytes, 0.0)

        with open(part_path, mode) as f:
            async for chunk in resp.aiter_bytes(chunk_size=self.chunk_size):
                if cancel_event and cancel_event.is_set():
                    await resp.aclose()
                    return False, "Download cancelled by user."

                f.write(chunk)
                completed_bytes += len(chunk)

                if progress and task_id is not None:
                    progress.update(task_id, advance=len(chunk))

                now = time.time()
                if progress_callback and (now - last_cb_time >= 0.05 or (total_bytes and completed_bytes >= total_bytes)):
                    elapsed = max(0.05, now - t_start)
                    speed = (completed_bytes - existing_size) / elapsed
                    progress_callback(completed_bytes, total_bytes, speed)
                    last_cb_time = now

        await resp.aclose()

        if progress and task_id is not None:
            progress.remove_task(task_id)

        # Atomic rename .part -> dest_path
        part_path.replace(dest_path)
        if meta_path.exists():
            try:
                meta_path.unlink()
            except Exception:
                pass

        if progress_callback:
            elapsed = max(0.01, time.time() - t_start)
            speed = (completed_bytes - existing_size) / elapsed
            progress_callback(completed_bytes, total_bytes or completed_bytes, speed)

        return True, str(dest_path)

    async def download_multiple(
        self,
        items: List[ResourceItem],
        item_progress_callback: Optional[Callable[[int, int, ResourceItem, int, Optional[int], float], None]] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> List[Tuple[ResourceItem, bool, str]]:
        """Downloads a collection of items sequentially with an active Rich progress bar or GUI callbacks."""
        results = []

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            total_items = len(items)
            for idx, item in enumerate(items, 1):
                if cancel_event and cancel_event.is_set():
                    results.append((item, False, "Batch download cancelled."))
                    break

                def _cb(done_b: int, tot_b: Optional[int], spd: float, i=idx, it=item):
                    if item_progress_callback:
                        item_progress_callback(i, total_items, it, done_b, tot_b, spd)

                success, msg = await self.download_item(
                    item,
                    progress=progress,
                    progress_callback=_cb if item_progress_callback else None,
                    cancel_event=cancel_event,
                )
                results.append((item, success, msg))

        return results
