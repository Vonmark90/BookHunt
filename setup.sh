#!/usr/bin/env bash
# ==============================================================================
# BookHunt / Universal Book Scraper - Setup Script for macOS & Linux
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================================="
echo "  🚀 Setting up Universal Book Scraper (BookHunt)"
echo "=========================================================="

# 1. Detect Python 3.9+
PYTHON_BIN=""
for candidate in python3 python python3.12 python3.11 python3.10 python3.9; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" 2>/dev/null; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "❌ Error: Python 3.9 or newer is required, but was not found."
    echo "   Please install Python 3 (e.g. 'brew install python' or download from python.org)."
    exit 1
fi

PY_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')")
echo "  • Found Python: $PYTHON_BIN ($PY_VERSION)"

# 2. Virtual Environment Setup
if [ ! -d ".venv" ]; then
    echo "  • Creating virtual environment (.venv)..."
    "$PYTHON_BIN" -m venv .venv
else
    echo "  • Using existing virtual environment (.venv)"
fi

# 3. Install Requirements
echo "  • Upgrading pip..."
.venv/bin/pip install --upgrade pip --quiet

echo "  • Installing project dependencies from requirements.txt..."
.venv/bin/pip install -r requirements.txt --quiet

if [ -f "requirements-dev.txt" ]; then
    echo "  • Installing dev & testing dependencies (pytest)..."
    .venv/bin/pip install -r requirements-dev.txt --quiet
fi

# 4. Make executable scripts runnable
chmod +x bookhunt setup.sh

# 5. Verify Installation
echo "  • Verifying scraper module..."
PYTHONPATH="$SCRIPT_DIR" .venv/bin/python -m scraper --help >/dev/null 2>&1

echo ""
echo "=========================================================="
echo "  🎉 Setup Successful!"
echo "=========================================================="
echo ""
echo "Ready to use BookHunt! Here are common commands:"
echo ""
echo "  • Launch Desktop GUI:    ./bookhunt gui"
echo "  • Interactive Search:    ./bookhunt search \"quantum computing\""
echo "  • Generate Search Dorks: ./bookhunt dork \"distributed systems\""
echo "  • Run Test Suite:        .venv/bin/pytest"
echo "  • Build macOS App:       .venv/bin/python build_app.py"
echo ""
