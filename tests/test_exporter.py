"""Tests for ResultExporter module."""

import json
import csv
import pytest
from pathlib import Path
from scraper.models import ResourceItem
from scraper.exporter import ResultExporter


@pytest.fixture
def sample_items():
    return [
        ResourceItem(
            title="The Art of Computer Programming",
            download_url="https://example.com/taocp.pdf",
            format="PDF",
            source="Internet Archive",
            authors=["Donald Knuth"],
            year=1968,
            size_bytes=15728640,
            score=0.98,
        ),
        ResourceItem(
            title="Introduction to Algorithms",
            download_url="https://example.com/clrs.pdf",
            format="PDF",
            source="arXiv",
            authors=["Thomas Cormen", "Charles Leiserson", "Ronald Rivest", "Clifford Stein"],
            year=1990,
            size_bytes=20971520,
            score=0.95,
        ),
    ]


def test_export_to_json(tmp_path, sample_items):
    out = tmp_path / "results.json"
    ResultExporter.to_json(sample_items, str(out))

    assert out.exists()
    with open(out, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data) == 2
    assert data[0]["title"] == "The Art of Computer Programming"
    assert data[1]["year"] == 1990


def test_export_to_csv(tmp_path, sample_items):
    out = tmp_path / "results.csv"
    ResultExporter.to_csv(sample_items, str(out))

    assert out.exists()
    with open(out, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    assert len(reader) == 2
    assert reader[0]["source"] == "Internet Archive"
    assert reader[0]["format"] == "PDF"


def test_export_to_markdown(tmp_path, sample_items):
    out = tmp_path / "results.md"
    ResultExporter.to_markdown(sample_items, str(out), topic="Algorithms")

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "# Discovered Resources: Algorithms" in content
    assert "The Art of Computer Programming" in content
    assert "Donald Knuth" in content


def test_export_to_bibtex(tmp_path, sample_items):
    out = tmp_path / "results.bib"
    ResultExporter.to_bibtex(sample_items, str(out))

    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "@misc{" in content
    assert "Donald Knuth" in content
    assert "1968" in content
    assert "https://example.com/taocp.pdf" in content
