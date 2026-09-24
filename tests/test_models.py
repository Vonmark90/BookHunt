"""Tests for ResourceItem data model."""

import pytest
from scraper.models import ResourceItem


def test_resource_item_initialization():
    item = ResourceItem(
        title="Automate the Boring Stuff with Python",
        download_url="https://example.com/automate.pdf",
        format="PDF",
        source="Test Source",
        authors=["Al Sweigart"],
        year=2020,
        size_bytes=10485760,  # 10 MB
    )
    assert item.title == "Automate the Boring Stuff with Python"
    assert item.format == "PDF"
    assert item.year == 2020
    assert len(item.id) == 12


def test_resource_item_deterministic_id():
    item1 = ResourceItem(
        title="Clean Code",
        download_url="https://example.com/cleancode.pdf",
        format="PDF",
        source="Test",
    )
    item2 = ResourceItem(
        title="Clean Code",
        download_url="https://example.com/cleancode.pdf",
        format="PDF",
        source="Test",
    )
    assert item1.id == item2.id


def test_formatted_authors():
    item_none = ResourceItem("T", "u", "PDF", "S", authors=[])
    assert item_none.formatted_authors == "Unknown"

    item_one = ResourceItem("T", "u", "PDF", "S", authors=["Dennis Ritchie"])
    assert item_one.formatted_authors == "Dennis Ritchie"

    item_two = ResourceItem("T", "u", "PDF", "S", authors=["Brian Kernighan", "Dennis Ritchie"])
    assert item_two.formatted_authors == "Brian Kernighan, Dennis Ritchie"

    item_three = ResourceItem("T", "u", "PDF", "S", authors=["A", "B", "C"])
    assert item_three.formatted_authors == "A et al."


def test_formatted_size():
    item_unknown = ResourceItem("T", "u", "PDF", "S", size_bytes=None)
    assert item_unknown.formatted_size == "Unknown"

    item_zero = ResourceItem("T", "u", "PDF", "S", size_bytes=0)
    assert item_zero.formatted_size == "Unknown"

    item_bytes = ResourceItem("T", "u", "PDF", "S", size_bytes=500)
    assert item_bytes.formatted_size == "500.0 B"

    item_kb = ResourceItem("T", "u", "PDF", "S", size_bytes=2048)
    assert item_kb.formatted_size == "2.0 KB"

    item_mb = ResourceItem("T", "u", "PDF", "S", size_bytes=10485760)
    assert item_mb.formatted_size == "10.0 MB"

    item_gb = ResourceItem("T", "u", "PDF", "S", size_bytes=2147483648)
    assert item_gb.formatted_size == "2.0 GB"


def test_to_dict():
    item = ResourceItem(
        title="Structure and Interpretation of Computer Programs",
        download_url="https://mit.edu/sicp.pdf",
        format="PDF",
        source="MIT",
        authors=["Harold Abelson", "Gerald Jay Sussman"],
        year=1996,
        size_bytes=5242880,
        score=0.954,
    )
    d = item.to_dict()
    assert d["title"] == "Structure and Interpretation of Computer Programs"
    assert d["year"] == 1996
    assert d["score"] == 0.95
    assert d["formatted_size"] == "5.0 MB"
    assert "id" in d
