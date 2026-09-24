# Antigravity Workspace Guidelines: BookHunt (Universal Book Scraper)

Welcome to the **Universal Book Scraper (BookHunt)** repository. This file provides context and operational guidelines for Antigravity AI agents working in this codebase.

---

## 🏗️ Project Architecture

```
universal-book-scraper/
├── bookhunt                # Portable executable CLI & GUI launcher
├── build_app.py            # macOS BookHunt.app bundle generator
├── setup.sh                # Automated setup script (creates .venv & installs dependencies)
├── requirements.txt        # Core runtime dependencies
├── requirements-dev.txt    # Testing & development dependencies (pytest)
├── pyproject.toml          # PEP 518/621 package metadata & pytest configuration
├── assets/                 # Icons and pre-compiled assets (AppIcon.icns)
├── downloads/              # Default destination for scraped eBooks/PDFs (.gitkeep)
├── tests/                  # Pytest unit & integration test suite
└── scraper/
    ├── __init__.py         # Package declaration
    ├── __main__.py         # Module entrypoint: python -m scraper
    ├── cli.py              # Click + Rich interactive terminal interface
    ├── gui.py              # CustomTkinter modern dark-mode desktop GUI
    ├── engine.py           # Multi-provider async orchestrator & deduplicator
    ├── dorker.py           # Precision Google / DuckDuckGo dork query generator
    ├── downloader.py       # Streaming async HTTP downloader with resume support
    ├── exporter.py         # Exporters for BibTeX, Markdown, JSON, and CSV
    ├── models.py           # ResourceItem dataclass & deterministic ID generator
    └── providers/          # Source-specific search providers
        ├── base.py         # BaseProvider abstract class & default headers
        ├── arxiv.py        # arXiv API provider
        ├── gutendex.py     # Project Gutenberg provider
        ├── hal_science.py  # HAL Science open repository provider
        ├── internet_archive.py # Internet Archive search provider
        ├── oapen.py        # OAPEN open access books provider
        ├── open_library.py # Open Library curated editions provider
        ├── standard_ebooks.py # Standard Ebooks feed provider
        ├── web_dork.py     # DuckDuckGo HTML dork scraping provider
        └── zenodo.py       # CERN Zenodo research repository provider
```

---

## ⚡ Development & Operations

### 1. Environment & Setup
The project uses Python 3.9+ with an isolated virtual environment at `.venv`:
```bash
./setup.sh
```

### 2. Running Applications
- **Desktop GUI**:
  ```bash
  ./bookhunt gui
  # or: .venv/bin/python -m scraper gui
  ```
- **Terminal CLI Search**:
  ```bash
  ./bookhunt search "distributed systems" --format pdf
  ```
- **Dork Query Generator**:
  ```bash
  ./bookhunt dork "deep learning"
  ```

### 3. Running Tests
All tests are written with `pytest` and reside in `tests/`:
```bash
.venv/bin/pytest
```

### 4. Building the Native macOS Bundle
```bash
.venv/bin/python build_app.py
```
This builds `BookHunt.app` in the repository root with custom retina icons and desktop integration.

---

## 📐 Coding Conventions & Rules

1. **Async HTTP**: Always use `httpx.AsyncClient` with proper timeouts and error handling (`BaseProvider` pattern).
2. **Deterministic Identifiers**: Always use `ResourceItem.id` for deduplication across providers.
3. **GUI Thread Safety**: When writing GUI code in `scraper/gui.py`, all network/search operations must run in background daemon threads, and GUI state updates must be scheduled via `root.after()` or thread-safe callbacks.
4. **Resilient Downloads**: Downloads should stream via chunks in `scraper/downloader.py` and support HTTP `Range` requests for resumption.
5. **No Hardcoded Machine Paths**: Never hardcode user paths (e.g. `/Users/...`); always resolve dynamically relative to `Path(__file__)` or standard system directories (`~/Library/Logs`, etc.).
