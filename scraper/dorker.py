"""Advanced Google / DuckDuckGo Dorking Engine and Query Generator."""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class DorkPattern:
    name: str
    category: str
    query_template: str
    description: str


class DorkGenerator:
    """Generates precision search dorks for locating PDFs, textbooks, preprints, and open directories."""

    TEMPLATES = [
        DorkPattern(
            name="Direct PDF Files",
            category="Filetype",
            query_template='"{topic}" filetype:pdf',
            description="Finds documents and books distributed directly as PDF files.",
        ),
        DorkPattern(
            name="Direct EPUB eBooks",
            category="Filetype",
            query_template='"{topic}" filetype:epub',
            description="Finds digital publications distributed as EPUB eBooks.",
        ),
        DorkPattern(
            name="University Textbooks & Notes",
            category="Academic",
            query_template='site:edu filetype:pdf "{topic}" (textbook OR "lecture notes" OR syllabus)',
            description="Searches accredited educational domains for lecture notes and course textbooks.",
        ),
        DorkPattern(
            name="Open Web Server Directories",
            category="Directories",
            query_template='intitle:"index of" (pdf OR epub) "{topic}"',
            description="Discovers unprotected web server directories containing downloadable documents.",
        ),
        DorkPattern(
            name="eBook Server Directories",
            category="Directories",
            query_template='intitle:"index of" /books/ "{topic}"',
            description="Locates server paths specifically labeled /books/ or /ebooks/.",
        ),
        DorkPattern(
            name="Academic Research & Whitepapers",
            category="Academic",
            query_template='site:org OR site:edu filetype:pdf ("{topic}" survey OR "handbook of" OR monograph)',
            description="Finds published surveys, handbooks, and monographs from institutions.",
        ),
        DorkPattern(
            name="Clean Downloads (Excluded HTML)",
            category="Filetype",
            query_template='"{topic}" (ext:pdf OR ext:epub) -inurl:(html|htm|php|asp)',
            description="Filters out landing pages, returning direct file links.",
        ),
    ]

    @classmethod
    def get_dorks_for_topic(cls, topic: str, file_format: str = "ALL") -> List[Tuple[DorkPattern, str]]:
        """Returns list of (DorkPattern, formatted_query) for a given topic and format."""
        results = []
        fmt = file_format.upper()

        for pattern in cls.TEMPLATES:
            # Filter if format specific
            if fmt == "PDF" and "EPUB" in pattern.name:
                continue
            if fmt == "EPUB" and ("PDF" in pattern.name or "University" in pattern.name):
                continue

            query = pattern.query_template.format(topic=topic)
            results.append((pattern, query))

        return results
