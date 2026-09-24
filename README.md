# Universal eBook & PDF Scraper (BookHunt)

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux-lightgrey.svg)](https://apple.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Antigravity IDE Ready](https://img.shields.io/badge/Antigravity%20IDE-Ready-purple.svg)](https://antigravity.google)

A high-performance universal document and eBook search aggregator, dorking engine, and downloader. BookHunt queries major digital libraries, academic archives, open web repositories, and search engine dorks concurrently to surface all available online PDFs and eBooks on any topic.

---

## 🌟 Key Features

- 🔍 **Multi-Source Concurrent Aggregation**:
  - **Internet Archive (`archive.org`)**: Scanned books, manuscripts, historical documents, and texts.
  - **OpenAlex Books**: Open access books, monographs, and textbooks with direct PDF full-text links.
  - **DOAB (Directory of Open Access Books)**: Over 85,000 peer-reviewed academic open access books.
  - **arXiv**: Academic books, preprints, research papers, and technical surveys.
  - **Project Gutenberg (`gutendex`)**: Over 70,000 public-domain literary classics.
  - **Open Library**: Curated editions with direct lending and archive access links.
  - **HAL Science**: Open-access European academic repository and doctoral dissertations.
  - **OAPEN**: Peer-reviewed academic open access books and monographs.
  - **Zenodo (CERN)**: Research publications, datasets, and technical reports.
  - **Standard Ebooks**: Beautifully formatted free editions with OPDS feed integration.
  - **Web Dorking Engine (DuckDuckGo / Open Web)**: Automated dorks to discover unindexed PDFs, university lecture textbooks, and open server directories.
- 🎯 **Advanced Dorking Engine**:
  - Automatically runs targeted dorks (`filetype:pdf`, `ext:epub`, `site:edu`, `intitle:"index of"`).
  - Standalone `dork` command to generate ready-to-paste Google/DuckDuckGo queries.
- ⚡ **Interactive Terminal UI**:
  - Formatted Rich tables with title, format, authors, year, file size, and relevance scores.
  - Interactive download picker (`1,3,5-8` or `all`), details inspection (`info <num>`), and link preview.
- 🖥️ **Modern Desktop GUI (CustomTkinter)**:
  - Dark/Light/System theme with responsive search table, inspection panel, and multi-threaded background downloader.
  - **Interactive Table**: Click-to-sort on any column (Title, Format, Source, Authors, Year, Score).
  - **Right-Click Context Menu**: Quick download, open in browser, copy URL, reveal in Finder, and copy citation.
  - **One-Click Actions**: Select All / Clear Sources, Reveal downloaded files in Finder/File Manager, and Copy formatted citation.
  - **Dorking Studio**: Interactive studio with one-click copy and direct browser searching.
- 📥 **Resilient Streaming Downloader**:
  - Streaming chunk downloads to avoid memory bloat on large files.
  - Automatic resume for interrupted downloads via HTTP `Range` headers.
  - Filename sanitization and format verification (detects login/captcha HTML redirects).
- 📊 **Multi-Format Bibliography Exporters**:
  - Export search results directly to **BibTeX** (`.bib`), **Markdown** (`.md`), **JSON**, or **CSV**.

---

## 🚀 Quick Start (New Machine Setup)

### 1-Step Setup
On a new Mac laptop, run the automated setup script:

```bash
chmod +x setup.sh bookhunt
./setup.sh
```

This automatically:
1. Detects Python 3.9+
2. Creates an isolated virtual environment (`.venv`)
3. Installs all required dependencies and test frameworks
4. Verifies the CLI entrypoint

---

## 💻 Working with Antigravity IDE

This repository is pre-configured for seamless development in **Antigravity IDE**:

1. **Open the Project**:
   ```bash
   agy .
   # or open this directory in Antigravity IDE
   ```
2. **Built-in Run & Debug Configurations** (<kbd>F5</kbd>):
   - `BookHunt GUI (Desktop Application)`: Launches the native CustomTkinter GUI.
   - `BookHunt CLI: Search Quantum Computing`: Runs an interactive sample CLI search.
   - `BookHunt CLI: Dork Generator`: Generates targeted search dorks.
   - `Pytest: Run All Tests`: Runs the unit test suite inside the editor.
3. **Agent Rules & Context**:
   - `AGENTS.md` and `.agents/rules/architecture.md` are automatically discovered by Antigravity IDE to guide the AI assistant with architecture, coding conventions, and provider patterns.

---

## 📖 Usage Guide

### Launch Desktop Application
```bash
./bookhunt gui
```

### Interactive CLI Search
```bash
./bookhunt search "quantum computing"
```

### Format Filtering (PDF or EPUB only)
```bash
# Only find PDFs
./bookhunt search "reinforcement learning" --format pdf

# Only find EPUB eBooks
./bookhunt search "marcus aurelius meditations" --format epub
```

### Generate Search Dorks for any Topic
```bash
./bookhunt dork "deep learning"
```

### Direct Batch Download
```bash
./bookhunt search "distributed systems" --limit 5 --download --out-dir ./downloads
```

### Export to Bibliography / Data File
```bash
# Export to BibTeX
./bookhunt search "neural networks" --output bibliography.bib --no-interactive

# Export to Markdown table
./bookhunt search "cryptography" --output books.md --no-interactive

# Export to JSON
./bookhunt search "compilers" --output results.json --no-interactive
```

### Filter Specific Providers
```bash
# Query only arXiv and Internet Archive
./bookhunt search "generative models" --sources arxiv,archive
```
Available source aliases: `arxiv`, `archive`, `gutenberg`, `openlib`, `hal`, `oapen`, `zenodo`, `standardebooks`, `doab`, `openalex`, `dork`, or `all`.

---

## 🧪 Running Tests

Run the test suite using `pytest`:

```bash
.venv/bin/pytest
```

---

## 🍏 Building Native macOS App (`BookHunt.app`)

To generate a standalone macOS application bundle with custom retina app icon:

```bash
.venv/bin/python build_app.py
```

This creates `BookHunt.app` directly in the project root, launchable via Finder or Spotlight.

---

## 📁 Repository Structure

```text
universal-book-scraper/
├── .agents/
│   └── rules/
│       └── architecture.md # Antigravity IDE progressive rules
├── .github/
│   └── workflows/
│       └── ci.yml          # GitHub Actions CI workflow
├── .vscode/
│   ├── launch.json         # Debug & run configurations
│   ├── settings.json       # Workspace python & test settings
│   └── tasks.json          # Build and test tasks
├── assets/
│   └── AppIcon.icns        # High-resolution retina macOS icon
├── downloads/
│   └── .gitkeep            # Scraped books destination folder
├── scraper/
│   ├── __init__.py
│   ├── __main__.py         # python -m scraper entrypoint
│   ├── cli.py              # Click + Rich interactive terminal interface
│   ├── dorker.py           # Dork generator and search query patterns
│   ├── downloader.py       # Streaming async downloader with progress bars
│   ├── engine.py           # Multi-provider async orchestrator & deduplicator
│   ├── exporter.py         # JSON, CSV, Markdown, and BibTeX exporters
│   ├── gui.py              # CustomTkinter Native Desktop Application
│   ├── models.py           # ResourceItem dataclass & deterministic hashing
│   └── providers/          # 9 modular search & archive providers
│       ├── __init__.py
│       ├── arxiv.py
│       ├── base.py
│       ├── gutendex.py
│       ├── hal_science.py
│       ├── internet_archive.py
│       ├── oapen.py
│       ├── open_library.py
│       ├── standard_ebooks.py
│       ├── web_dork.py
│       └── zenodo.py
├── tests/
│   ├── __init__.py
│   ├── test_dorker.py      # Dork query generation tests
│   ├── test_exporter.py    # JSON/CSV/Markdown/BibTeX export tests
│   ├── test_models.py      # Data model & serialization tests
│   └── test_providers.py   # Provider contract compliance tests
├── .gitattributes          # Line ending and binary file definitions
├── .gitignore              # Python, macOS, and IDE ignores
├── AGENTS.md               # Antigravity IDE agent instructions
├── bookhunt                # Portable launcher script
├── build_app.py            # macOS App bundler
├── LICENSE                 # MIT License
├── pyproject.toml          # PEP 518/621 packaging metadata
├── README.md               # Documentation
├── requirements-dev.txt    # Testing dependencies
├── requirements.txt        # Runtime dependencies
└── setup.sh                # Automated setup bootstrap script
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
