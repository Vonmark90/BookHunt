"""Exporters for saving search results into JSON, CSV, Markdown, and BibTeX."""

import csv
import json
import re
from pathlib import Path
from typing import List
from .models import ResourceItem


class ResultExporter:
    """Exports ResourceItem lists to various file formats."""

    @staticmethod
    def to_json(items: List[ResourceItem], output_path: str) -> None:
        data = [item.to_dict() for item in items]
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @staticmethod
    def to_csv(items: List[ResourceItem], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "id", "title", "authors", "year", "format", "source",
            "download_url", "details_url", "formatted_size", "score", "dork_type",
        ]
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in items:
                row = item.to_dict()
                row["authors"] = "; ".join(item.authors)
                writer.writerow({k: row.get(k, "") for k in fieldnames})

    @staticmethod
    def to_markdown(items: List[ResourceItem], output_path: str, topic: str = "") -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Discovered Resources: {topic}\n\n")
            f.write(f"Total items found: {len(items)}\n\n")
            f.write("| # | Title | Format | Source | Authors | Year | Download |\n")
            f.write("|---|-------|--------|--------|---------|------|----------|\n")
            for idx, it in enumerate(items, 1):
                clean_title = it.title.replace("|", "-")
                authors = it.formatted_authors.replace("|", "-")
                year = str(it.year) if it.year else "-"
                f.write(f"| {idx} | {clean_title} | **{it.format}** | {it.source} | {authors} | {year} | [Link]({it.download_url}) |\n")

    @staticmethod
    def to_bibtex(items: List[ResourceItem], output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for item in items:
                # Generate clean cite key
                first_author = re.sub(r"\W+", "", item.authors[0].split()[-1].lower()) if item.authors else "doc"
                year_str = str(item.year) if item.year else "nd"
                cite_key = f"{first_author}{year_str}_{item.id[:6]}"

                clean_title = re.sub(r'["\\]', "", item.title)
                authors_str = " and ".join(item.authors) if item.authors else "Anonymous"

                f.write(f"@misc{{{cite_key},\n")
                f.write(f'  title = "{clean_title}",\n')
                f.write(f'  author = "{authors_str}",\n')
                if item.year:
                    f.write(f"  year = {{{item.year}}},\n")
                f.write(f'  howpublished = "\\url{{{item.download_url}}}",\n')
                f.write(f'  note = "Source: {item.source}"\n')
                f.write("}\n\n")
