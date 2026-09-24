"""Tests for DorkGenerator module."""

import pytest
from scraper.dorker import DorkGenerator


def test_get_dorks_for_topic_all():
    dorks = DorkGenerator.get_dorks_for_topic("machine learning", "ALL")
    assert len(dorks) == len(DorkGenerator.TEMPLATES)
    # Check that topic was properly substituted
    for pattern, query in dorks:
        assert "machine learning" in query


def test_get_dorks_for_topic_pdf_filter():
    dorks = DorkGenerator.get_dorks_for_topic("deep learning", "PDF")
    # EPUB specific should be excluded
    for pattern, query in dorks:
        assert "EPUB" not in pattern.name.upper()


def test_get_dorks_for_topic_epub_filter():
    dorks = DorkGenerator.get_dorks_for_topic("shakespeare", "EPUB")
    # PDF specific and University Textbooks should be excluded
    for pattern, query in dorks:
        assert "Direct PDF" not in pattern.name
        assert "University" not in pattern.name


def test_dork_pattern_structure():
    assert len(DorkGenerator.TEMPLATES) > 0
    for pat in DorkGenerator.TEMPLATES:
        assert pat.name
        assert pat.category
        assert "{topic}" in pat.query_template
        assert pat.description
