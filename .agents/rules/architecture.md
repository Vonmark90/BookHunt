---
description: Universal Book Scraper (BookHunt) architectural rules and provider patterns
always_on: true
---

# BookHunt Architecture & Guidelines

## Adding New Search Providers
When creating a new provider in `scraper/providers/`:
1. Subclass `BaseProvider` from `scraper.providers.base`.
2. Define `name: str` and `supported_formats: List[str]`.
3. Implement `async def search(self, query: str, limit: int = 15, file_format: Optional[str] = None) -> List[ResourceItem]`.
4. Always handle network exceptions gracefully, returning an empty list on timeout or network error instead of crashing the aggregate search.
5. Export the new class in `scraper/providers/__init__.py`.
6. Register the provider instance in `scraper/engine.py` in `UniversalScraper.DEFAULT_PROVIDERS`.
7. Add a unit test verifying the provider contract in `tests/test_providers.py`.

## Downloader Rules
- Always verify remote status before writing to disk.
- Detect HTML redirect/captcha error responses masquerading as PDF or EPUB.
- Sanitize filenames to prevent path traversal or invalid filesystem characters.
