"""High-performance streaming downloader with progress tracking, file sanitization, and resilient link resolution."""

import os
import re
import urllib.parse
from pathlib import Path
from typing import List, Optional, Tuple
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


class Downloader:
    """Handles resilient single and batch downloading of eBooks and PDFs."""

    def __init__(self, download_dir: str = "./downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

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

    async def download_item(
        self,
        item: ResourceItem,
        custom_filename: Optional[str] = None,
        progress: Optional[Progress] = None,
    ) -> Tuple[bool, str]:
        """Downloads a single ResourceItem to the target directory with smart resolution for Archive.org and landing pages.

        Returns:
            (success: bool, local_path_or_error_message: str)
        """
        target_url = item.download_url
        ext = item.format.lower() if item.format else "pdf"

        # 1. Special resolution for Internet Archive links (handles 401 lending restrictions & exact filenames)
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

        headers = dict(DEFAULT_HEADERS)
        parsed_url = urllib.parse.urlparse(target_url)
        if parsed_url.scheme and parsed_url.netloc:
            headers["Referer"] = f"{parsed_url.scheme}://{parsed_url.netloc}/"

        existing_size = 0
        if dest_path.exists():
            existing_size = dest_path.stat().st_size
            if item.size_bytes and existing_size == item.size_bytes and existing_size > 0:
                return True, f"Already downloaded: {dest_path.name}"
            # Only send Range if file is partially downloaded and non-zero
            if existing_size > 0:
                headers["Range"] = f"bytes={existing_size}-"

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.send(
                    client.build_request("GET", target_url, headers=headers),
                    stream=True,
                )

                # If server returns 416 (Range Not Satisfiable) or 401/403 with Range header, retry from byte 0
                if (resp.status_code in [401, 403, 416]) and "Range" in headers:
                    await resp.aclose()
                    headers.pop("Range", None)
                    existing_size = 0
                    resp = await client.send(
                        client.build_request("GET", target_url, headers=headers),
                        stream=True,
                    )

                # Check status
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

                # Verify Content-Type
                content_type = resp.headers.get("content-type", "").lower()
                if "text/html" in content_type and not target_url.lower().endswith(".html"):
                    # Attempt to extract direct PDF link from landing page
                    html_bytes = await resp.aread()
                    html_text = html_bytes.decode("utf-8", errors="replace")
                    await resp.aclose()

                    extracted_pdf = self._extract_pdf_from_html(html_text, str(resp.url))
                    if extracted_pdf and extracted_pdf != target_url:
                        # Retry download with the extracted PDF URL
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

                total_size = resp.headers.get("content-length")
                total_bytes = (int(total_size) + existing_size) if total_size and total_size.isdigit() else None

                task_id = None
                if progress:
                    task_id = progress.add_task(
                        f"[cyan]{filename[:30]}...",
                        total=total_bytes,
                        completed=existing_size,
                    )

                mode = "ab" if resp.status_code == 206 and existing_size > 0 else "wb"
                with open(dest_path, mode) as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        if progress and task_id is not None:
                            progress.update(task_id, advance=len(chunk))

                await resp.aclose()

                if progress and task_id is not None:
                    progress.remove_task(task_id)

                return True, str(dest_path)

        except Exception as e:
            return False, f"Download failed: {str(e)}"

    async def download_multiple(
        self,
        items: List[ResourceItem],
    ) -> List[Tuple[ResourceItem, bool, str]]:
        """Downloads a collection of items sequentially with an active Rich progress bar."""
        results = []

        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            for item in items:
                success, msg = await self.download_item(item, progress=progress)
                results.append((item, success, msg))

        return results
