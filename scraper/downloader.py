"""High-performance streaming downloader with progress tracking and file sanitization."""

import os
import re
from pathlib import Path
from typing import List, Optional, Tuple
import httpx
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


class Downloader:
    """Handles single and batch downloading of eBooks and PDFs."""

    def __init__(self, download_dir: str = "./downloads"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    def sanitize_filename(self, title: str, extension: str) -> str:
        """Generates a clean, safe local filename."""
        clean = re.sub(r'[\\/*?:"<>|]', "", title)
        clean = re.sub(r"\s+", " ", clean).strip()
        if not clean:
            clean = "downloaded_document"

        # Cap length to avoid OS filename limits
        clean = clean[:120]

        ext = extension.lstrip(".").lower()
        if not ext:
            ext = "pdf"

        return f"{clean}.{ext}"

    async def download_item(
        self,
        item: ResourceItem,
        custom_filename: Optional[str] = None,
        progress: Optional[Progress] = None,
    ) -> Tuple[bool, str]:
        """Downloads a single ResourceItem to the target directory.

        Returns:
            (success: bool, local_path_or_error_message: str)
        """
        ext = item.format.lower() if item.format else "pdf"
        filename = custom_filename or self.sanitize_filename(item.title, ext)
        dest_path = self.download_dir / filename

        headers = dict(DEFAULT_HEADERS)
        existing_size = 0

        # Check for existing partial file for resume
        if dest_path.exists():
            existing_size = dest_path.stat().st_size
            if item.size_bytes and existing_size == item.size_bytes:
                return True, f"Already downloaded: {dest_path.name}"
            # Attempt resume if existing
            headers["Range"] = f"bytes={existing_size}-"

        try:
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                async with client.stream("GET", item.download_url, headers=headers) as resp:
                    if resp.status_code not in [200, 206]:
                        # If range request failed (416, etc.), restart from beginning
                        if resp.status_code == 416:
                            headers.pop("Range", None)
                            existing_size = 0
                        else:
                            return False, f"HTTP Error {resp.status_code}: {resp.reason_phrase}"

                    # Verify Content-Type
                    content_type = resp.headers.get("content-type", "").lower()
                    if "text/html" in content_type and not item.download_url.lower().endswith(".html"):
                        return False, "Server returned HTML instead of a document file (link may require login/captcha)."

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
