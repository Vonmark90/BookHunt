"""Helper utilities for resolving Internet Archive and Open Library direct download links."""

import re
import urllib.parse
from typing import Optional, Tuple
import httpx

from .base import DEFAULT_HEADERS

# Matches archive.org download or details paths
IA_PATH_REGEX = re.compile(r"^/(?:download|details)/([^/?#]+)(?:/(.*))?", re.IGNORECASE)


def extract_ia_identifier(url: str) -> Optional[Tuple[str, Optional[str]]]:
    """Extracts the (identifier, subpath_filename) from an archive.org URL if present."""
    try:
        parsed = urllib.parse.urlparse(url)
        if "archive.org" not in parsed.netloc.lower():
            return None
        match = IA_PATH_REGEX.match(parsed.path)
        if match:
            ident = match.group(1)
            filename = match.group(2) if match.group(2) else None
            return ident, filename
    except Exception:
        pass
    return None


async def resolve_ia_direct_url(
    identifier: str,
    preferred_fmt: str = "pdf",
    client: Optional[httpx.AsyncClient] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Resolves the exact, publicly downloadable file URL for an Internet Archive item.

    Returns:
        (direct_download_url, error_reason)
        If success, direct_download_url is a working URL and error_reason is None.
        If restricted or unavailable, direct_download_url is None and error_reason explains why.
    """
    metadata_url = f"https://archive.org/metadata/{identifier}"
    headers = dict(DEFAULT_HEADERS)

    should_close = False
    if client is None:
        client = httpx.AsyncClient(timeout=10.0, follow_redirects=True)
        should_close = True

    try:
        resp = await client.get(metadata_url, headers=headers)
        if resp.status_code != 200:
            return None, f"Item \"{identifier}\" was not found on Internet Archive (HTTP {resp.status_code})"

        data = resp.json()
        meta = data.get("metadata", {})

        # Check for lending library / controlled digital lending restrictions
        if meta.get("access-restricted-item") == "true":
            return None, (
                f"Controlled Digital Lending: \"{identifier}\" is restricted to Internet Archive\"s "
                "1-hour borrowing loan and cannot be downloaded directly without borrowing in a browser."
            )

        collections = meta.get("collection", [])
        if isinstance(collections, str):
            collections = [collections]
        restricted_collections = {"inlibrary", "lendinglibrary", "printdisabled"}
        if any(c.lower() in restricted_collections for c in collections if isinstance(c, str)):
            # If all text files are marked private, it is restricted
            pass

        files = data.get("files", [])
        if not files:
            return None, f"No files available for item \"{identifier}\" on Internet Archive."

        # Find non-private candidates matching preferred format
        fmt_target = preferred_fmt.lower().strip(".")
        candidates = []

        for f in files:
            name = f.get("name", "")
            private = f.get("private")
            if private == "true":
                continue

            name_lower = name.lower()
            size = int(f.get("size", 0) or 0)

            # Skip small derivatives or system files
            if name_lower.endswith(("_thumb.jpg", "_files.xml", "_meta.xml", "_meta.sqlite", "_archive.torrent")):
                continue

            if name_lower.endswith(f".{fmt_target}"):
                candidates.append((name, size))

        # Fallback to alternative document formats if target format not found
        if not candidates:
            for f in files:
                name = f.get("name", "")
                if f.get("private") == "true":
                    continue
                name_lower = name.lower()
                size = int(f.get("size", 0) or 0)
                if name_lower.endswith((".pdf", ".epub", ".djvu")):
                    candidates.append((name, size))

        if not candidates:
            # Check if files exist but are all private (restricted)
            has_private_docs = any(
                f.get("private") == "true" and f.get("name", "").lower().endswith((".pdf", ".epub", ".djvu"))
                for f in files
            )
            if has_private_docs:
                return None, (
                    f"Controlled Digital Lending: \"{identifier}\" files are marked private by Internet Archive "
                    "(1-hour loan only). Direct HTTP download is unauthorized (HTTP 401)."
                )
            return None, f"No downloadable PDF/EPUB found for item \"{identifier}\"."

        # Pick the largest file of that format (main book content rather than small sample/preview)
        candidates.sort(key=lambda x: x[1], reverse=True)
        chosen_filename = candidates[0][0]
        # URL encode filename while preserving safe characters
        encoded_filename = urllib.parse.quote(chosen_filename, safe="/: ")
        direct_url = f"https://archive.org/download/{identifier}/{encoded_filename}"
        return direct_url, None

    except Exception as e:
        return None, f"Failed to resolve Internet Archive item \"{identifier}\": {str(e)}"
    finally:
        if should_close:
            await client.aclose()
