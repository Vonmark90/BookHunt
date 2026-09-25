"""Rich Interactive Command Line Interface for Universal eBook & PDF Scraper."""

from __future__ import annotations

import asyncio
from pathlib import Path
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import ResourceItem
from .engine import UniversalScraper
from .downloader import Downloader
from .exporter import ResultExporter
from .dorker import DorkGenerator

console = Console()


def display_results_table(items: list[ResourceItem], topic: str) -> None:
    """Renders a formatted table of search results in the terminal."""
    table = Table(
        title=f"[bold cyan]Discovered Resources for:[/bold cyan] [yellow]\"{topic}\"[/yellow] ({len(items)} found)",
        border_style="bright_blue",
        show_lines=True,
    )

    table.add_column("#", style="bold yellow", width=4, justify="right")
    table.add_column("Title", style="white", min_width=25, max_width=45)
    table.add_column("Format", style="bold magenta", width=8, justify="center")
    table.add_column("Source", style="cyan", width=22)
    table.add_column("Authors", style="green", max_width=20)
    table.add_column("Year", style="dim", width=6, justify="center")
    table.add_column("Size", style="blue", width=9, justify="right")
    table.add_column("Score", style="bold green", width=6, justify="right")

    for idx, item in enumerate(items, 1):
        year_str = str(item.year) if item.year else "-"
        fmt_badge = f"[bold red]{item.format}[/bold red]" if item.format == "PDF" else f"[bold green]{item.format}[/bold green]"
        table.add_row(
            str(idx),
            item.title,
            fmt_badge,
            item.source,
            item.formatted_authors,
            year_str,
            item.formatted_size,
            f"{int(item.score)}%",
        )

    console.print(table)


async def interactive_selection_loop(items: list[ResourceItem], download_dir: str, connections: int = 4) -> None:
    """Interactive loop allowing the user to inspect or download items."""
    downloader = Downloader(download_dir=download_dir, max_connections=connections)

    while True:
        console.print("\n[bold yellow]Actions:[/bold yellow] Enter item numbers to download (e.g. [bold cyan]1,3,5-7[/bold cyan]), [bold cyan]'info <num>'[/bold cyan] for details, [bold cyan]'all'[/bold cyan] to download all, or [bold cyan]'q'[/bold cyan] to exit:")
        choice = input(" > ").strip()

        if not choice or choice.lower() in ["q", "quit", "exit"]:
            console.print("[dim]Exiting interactive session.[/dim]")
            break

        if choice.lower().startswith("info "):
            parts = choice.split()
            if len(parts) == 2 and parts[1].isdigit():
                idx = int(parts[1]) - 1
                if 0 <= idx < len(items):
                    it = items[idx]
                    panel_text = (
                        f"[bold cyan]Title:[/bold cyan] {it.title}\n"
                        f"[bold cyan]Format:[/bold cyan] {it.format}\n"
                        f"[bold cyan]Source:[/bold cyan] {it.source}\n"
                        f"[bold cyan]Authors:[/bold cyan] {it.formatted_authors}\n"
                        f"[bold cyan]Year:[/bold cyan] {it.year or 'Unknown'}\n"
                        f"[bold cyan]Download URL:[/bold cyan] [link={it.download_url}]{it.download_url}[/link]\n"
                        f"[bold cyan]Details URL:[/bold cyan] {it.details_url or 'N/A'}\n"
                        f"[bold cyan]Estimated Size:[/bold cyan] {it.formatted_size}\n"
                        f"[bold cyan]Relevance Score:[/bold cyan] {it.score:.1f}%\n"
                        f"[bold cyan]Description:[/bold cyan] {it.description or 'No description available.'}"
                    )
                    console.print(Panel(panel_text, title=f"Item #{idx+1} Details", border_style="cyan"))
                else:
                    console.print("[bold red]Invalid item index.[/bold red]")
            continue

        selected_indices: list[int] = []
        if choice.lower() == "all":
            selected_indices = list(range(len(items)))
        else:
            # Parse ranges like 1,3,5-7
            chunks = choice.split(",")
            valid = True
            for ch in chunks:
                ch = ch.strip()
                if "-" in ch:
                    bounds = ch.split("-")
                    if len(bounds) == 2 and bounds[0].isdigit() and bounds[1].isdigit():
                        start, end = int(bounds[0]), int(bounds[1])
                        selected_indices.extend(range(start - 1, end))
                    else:
                        valid = False
                elif ch.isdigit():
                    selected_indices.append(int(ch) - 1)
                else:
                    valid = False

            if not valid:
                console.print("[bold red]Unrecognized input format. Try '1,2,4' or '1-5' or 'all'.[/bold red]")
                continue

        # Filter valid bounds
        chosen_items = [items[i] for i in selected_indices if 0 <= i < len(items)]
        if not chosen_items:
            console.print("[bold red]No valid items selected.[/bold red]")
            continue

        console.print(f"\n[bold green]Preparing download of {len(chosen_items)} items to '{download_dir}'...[/bold green]")
        results = await downloader.download_multiple(chosen_items)

        success_count = sum(1 for _, s, _ in results if s)
        console.print(f"[bold green]Download complete: {success_count}/{len(chosen_items)} succeeded.[/bold green]")


@click.group()
def cli():
    """Universal eBook & PDF Finder and Web Dorking Scraper."""
    pass


@cli.command()
@click.argument("topic", required=True)
@click.option("--format", "-f", "file_format", type=click.Choice(["pdf", "epub", "all"], case_sensitive=False), default="all", help="Target document format")
@click.option("--limit", "-l", default=10, help="Results limit per source provider")
@click.option("--sources", "-s", default="all", help="Comma-separated sources: dork,archive,gutenberg,arxiv,openlib,standard,oapen,hal,zenodo,doab,openalex, or 'all'")
@click.option("--validate", "-v", is_flag=True, default=False, help="Perform HEAD requests to verify active links and file sizes")
@click.option("--download", "-d", is_flag=True, default=False, help="Download all discovered resources immediately")
@click.option("--interactive/--no-interactive", "-i", default=True, help="Enter interactive download selection mode")
@click.option("--output", "-o", default=None, help="Export results to file (.json, .csv, .md, .bib)")
@click.option("--connections", "-c", default=4, type=int, help="Max parallel download connections/segments per file (Aria2-style acceleration, 1-16)")
@click.option("--out-dir", default="./downloads", help="Directory where downloaded files are saved")
def search(
    topic: str,
    file_format: str,
    limit: int,
    sources: str,
    validate: bool,
    download: bool,
    interactive: bool,
    connections: int,
    output: str | None,
    out_dir: str,
):
    """Search for eBooks, PDFs, and documents across digital archives and web dorks."""
    console.print(f"\n[bold cyan]Initiating search for topic:[/bold cyan] [bold yellow]\"{topic}\"[/bold yellow]")
    
    # Map sources
    source_map = {
        "dork": "web_dork",
        "archive": "internet_archive",
        "gutenberg": "gutenberg",
        "arxiv": "arxiv",
        "openlib": "open_library",
        "open_library": "open_library",
        "standard": "standard_ebooks",
        "standard_ebooks": "standard_ebooks",
        "oapen": "oapen",
        "hal": "hal_science",
        "hal_science": "hal_science",
        "zenodo": "zenodo",
        "doab": "doab",
        "openalex": "openalex",
    }
    
    enabled_sources = None
    if sources.lower() != "all":
        enabled_sources = [source_map.get(s.strip().lower(), s.strip()) for s in sources.split(",")]


    fmt_filter = None if file_format.lower() == "all" else file_format.upper()

    scraper = UniversalScraper()

    with console.status("[bold green]Querying providers and executing web dorks...", spinner="dots"):
        items = asyncio.run(
            scraper.search(
                query=topic,
                limit_per_source=limit,
                file_format=fmt_filter,
                enabled_sources=enabled_sources,
                validate_links=validate,
            )
        )

    if not items:
        console.print("[bold red]No matching resources found.[/bold red] Try broader keywords or check dorking queries.")
        return

    display_results_table(items, topic)

    # Export if requested
    if output:
        out_path = Path(output)
        suffix = out_path.suffix.lower()
        if suffix == ".json":
            ResultExporter.to_json(items, output)
        elif suffix == ".csv":
            ResultExporter.to_csv(items, output)
        elif suffix in [".md", ".markdown"]:
            ResultExporter.to_markdown(items, output, topic=topic)
        elif suffix == ".bib":
            ResultExporter.to_bibtex(items, output)
        else:
            # Default to JSON
            ResultExporter.to_json(items, output)
        console.print(f"[bold green]Saved results to:[/bold green] {output}")

    # Immediate download mode
    if download:
        downloader = Downloader(download_dir=out_dir)
        console.print(f"\n[bold green]Downloading all {len(items)} resources to '{out_dir}'...[/bold green]")
        results = asyncio.run(downloader.download_multiple(items))
        succeeded = sum(1 for _, s, _ in results if s)
        console.print(f"[bold green]Finished downloading: {succeeded}/{len(items)} files saved.[/bold green]")
        return

    # Interactive mode
    if interactive:
        asyncio.run(interactive_selection_loop(items, download_dir=out_dir, connections=connections))


@cli.command()
@click.argument("topic", required=True)
@click.option("--format", "-f", "file_format", default="ALL", help="Format filter: PDF, EPUB, or ALL")
def dork(topic: str, file_format: str):
    """Generate specialized Google & DuckDuckGo search dorks for a topic."""
    dorks = DorkGenerator.get_dorks_for_topic(topic=topic, file_format=file_format)

    table = Table(
        title=f"[bold cyan]Generated Search Dorks for:[/bold cyan] [yellow]\"{topic}\"[/yellow]",
        border_style="magenta",
        show_lines=True,
    )
    table.add_column("Category", style="cyan", width=14)
    table.add_column("Strategy / Name", style="bold white", width=26)
    table.add_column("Dork Query Pattern (Paste into Google/DuckDuckGo)", style="bold yellow")

    for pattern, query in dorks:
        table.add_row(pattern.category, pattern.name, query)

    console.print(table)
    console.print("\n[bold green]Tip:[/bold green] You can copy and paste any of these directly into Google, DuckDuckGo, or Bing to find direct PDF/eBook index downloads.")


@cli.command()
def gui():
    """Launch the BookHunt Native Desktop Graphical User Interface."""
    from .gui import launch_gui
    launch_gui()


def main():
    cli()


if __name__ == "__main__":
    main()

