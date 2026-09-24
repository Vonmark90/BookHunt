"""Native Desktop GUI for Universal eBook & PDF Scraper using CustomTkinter."""

from __future__ import annotations

import asyncio
import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

import customtkinter as ctk

from .models import ResourceItem
from .engine import UniversalScraper
from .downloader import Downloader
from .exporter import ResultExporter
from .dorker import DorkGenerator

# Configure CustomTkinter theme
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


class BookHuntGUI(ctk.CTk):
    """Main desktop application window."""

    scraper: UniversalScraper
    results: list[ResourceItem]
    selected_item: ResourceItem | None
    is_searching: bool
    is_downloading: bool
    download_dir: str

    tabview: ctk.CTkTabview = None  # type: ignore
    tab_search: ctk.CTkFrame = None  # type: ignore
    tab_dork: ctk.CTkFrame = None  # type: ignore
    tab_settings: ctk.CTkFrame = None  # type: ignore

    # Search & Download UI elements
    search_entry: ctk.CTkEntry = None  # type: ignore
    btn_search: ctk.CTkButton = None  # type: ignore
    fmt_var: ctk.StringVar = None  # type: ignore
    fmt_menu: ctk.CTkOptionMenu = None  # type: ignore
    limit_var: ctk.StringVar = None  # type: ignore
    limit_menu: ctk.CTkOptionMenu = None  # type: ignore

    src_dork: ctk.CTkCheckBox = None  # type: ignore
    src_archive: ctk.CTkCheckBox = None  # type: ignore
    src_arxiv: ctk.CTkCheckBox = None  # type: ignore
    src_gutenberg: ctk.CTkCheckBox = None  # type: ignore
    src_openlib: ctk.CTkCheckBox = None  # type: ignore
    src_standard: ctk.CTkCheckBox = None  # type: ignore
    src_oapen: ctk.CTkCheckBox = None  # type: ignore
    src_doab: ctk.CTkCheckBox = None  # type: ignore
    src_openalex: ctk.CTkCheckBox = None  # type: ignore
    src_hal: ctk.CTkCheckBox = None  # type: ignore
    src_zenodo: ctk.CTkCheckBox = None  # type: ignore

    site_entry: ctk.CTkEntry = None  # type: ignore
    exclude_entry: ctk.CTkEntry = None  # type: ignore

    tree: ttk.Treeview = None  # type: ignore
    context_menu: tk.Menu = None  # type: ignore

    detail_title: ctk.CTkLabel = None  # type: ignore
    detail_meta: ctk.CTkLabel = None  # type: ignore
    detail_desc: ctk.CTkTextbox = None  # type: ignore

    btn_download_one: ctk.CTkButton = None  # type: ignore
    btn_open_browser: ctk.CTkButton = None  # type: ignore
    btn_copy_link: ctk.CTkButton = None  # type: ignore
    btn_open_folder: ctk.CTkButton = None  # type: ignore
    btn_copy_citation: ctk.CTkButton = None  # type: ignore

    lbl_status: ctk.CTkLabel = None  # type: ignore
    progress_bar: ctk.CTkProgressBar = None  # type: ignore
    lbl_progress_pct: ctk.CTkLabel = None  # type: ignore
    btn_export: ctk.CTkOptionMenu = None  # type: ignore
    dl_hud: ctk.CTkFrame = None  # type: ignore
    hud_lbl_title: ctk.CTkLabel = None  # type: ignore
    hud_btn_cancel: ctk.CTkButton = None  # type: ignore
    hud_progress_bar: ctk.CTkProgressBar = None  # type: ignore
    hud_lbl_size: ctk.CTkLabel = None  # type: ignore
    hud_lbl_speed: ctk.CTkLabel = None  # type: ignore
    download_cancel_event: threading.Event = None  # type: ignore
    btn_download_all: ctk.CTkButton = None  # type: ignore

    # Dorking Studio UI elements
    dork_entry: ctk.CTkEntry = None  # type: ignore
    dork_scroll: ctk.CTkScrollableFrame = None  # type: ignore
    lbl_dork_empty: ctk.CTkLabel = None  # type: ignore

    # Settings UI elements
    lbl_dl_path: ctk.CTkEntry = None  # type: ignore
    theme_menu: ctk.CTkOptionMenu = None  # type: ignore

    def __init__(self):
        super().__init__()

        self.title("BookHunt - Universal eBook & PDF Scraper")
        self.geometry("1120x740")
        self.minsize(920, 620)

        # Application state
        self.scraper = UniversalScraper()
        self.results = []
        self.selected_item = None
        self.is_searching = False
        self.is_downloading = False
        self.download_dir = str(Path.home() / "Downloads" / "BookHunt")
        os.makedirs(self.download_dir, exist_ok=True)

        self._build_ui()

    def _build_ui(self):
        # Main Tabview
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=12)

        self.tab_search = self.tabview.add("🔍 Search & Download")
        self.tab_dork = self.tabview.add("🎯 Dorking Studio")
        self.tab_settings = self.tabview.add("⚙️ Settings")

        self._build_search_tab()
        self._build_dork_tab()
        self._build_settings_tab()

    # -------------------------------------------------------------
    # TAB 1: Search & Download
    # -------------------------------------------------------------
    def _build_search_tab(self):
        parent = self.tab_search

        # 1. Search Bar Frame
        search_frame = ctk.CTkFrame(parent, corner_radius=8)
        search_frame.pack(fill="x", padx=8, pady=(4, 8))

        self.search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="Enter topic, book title, author, or research field (e.g., 'quantum algorithms', 'calculus')...",
            height=38,
            font=("Helvetica", 14),
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=10)
        self.search_entry.bind("<Return>", lambda e: self.start_search())

        self.btn_search = ctk.CTkButton(
            search_frame,
            text="Search Everywhere",
            width=140,
            height=38,
            font=("Helvetica", 13, "bold"),
            command=self.start_search,
        )
        self.btn_search.pack(side="left", padx=(0, 12), pady=10)

        # 2. Filters Bar
        # 2. Filters & Controls
        filter_container = ctk.CTkFrame(parent, fg_color="transparent")
        filter_container.pack(fill="x", padx=8, pady=(0, 6))

        # Top Control Row: Format, Limit, and Quick Source Toggles
        control_row = ctk.CTkFrame(filter_container, fg_color="transparent")
        control_row.pack(fill="x", pady=(0, 4))

        ctk.CTkLabel(control_row, text="Format:", font=("Helvetica", 12, "bold")).pack(side="left", padx=(4, 4))
        self.fmt_var = ctk.StringVar(value="PDF")
        self.fmt_menu = ctk.CTkOptionMenu(
            control_row,
            values=["All", "PDF", "EPUB"],
            variable=self.fmt_var,
            width=85,
            height=26,
        )
        self.fmt_menu.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(control_row, text="Limit/Source:", font=("Helvetica", 12)).pack(side="left", padx=(0, 4))
        self.limit_var = ctk.StringVar(value="10")
        self.limit_menu = ctk.CTkOptionMenu(
            control_row,
            values=["5", "10", "15", "25"],
            variable=self.limit_var,
            width=70,
            height=26,
        )
        self.limit_menu.pack(side="left", padx=(0, 20))

        # Quick select buttons on right
        btn_clear_src = ctk.CTkButton(
            control_row,
            text="Clear Sources",
            width=90,
            height=24,
            font=("Helvetica", 11),
            fg_color="#3a3f4b",
            hover_color="#4b5263",
            command=self._clear_all_sources,
        )
        btn_clear_src.pack(side="right", padx=(4, 4))

        btn_all_src = ctk.CTkButton(
            control_row,
            text="Select All",
            width=80,
            height=24,
            font=("Helvetica", 11),
            fg_color="#3a3f4b",
            hover_color="#4b5263",
            command=self._select_all_sources,
        )
        btn_all_src.pack(side="right", padx=4)

        # Sources Row with all 11 providers
        sources_row = ctk.CTkFrame(filter_container, fg_color="transparent")
        sources_row.pack(fill="x", pady=(2, 0))

        ctk.CTkLabel(sources_row, text="Sources:", font=("Helvetica", 12, "bold")).pack(side="left", padx=(4, 6))

        self.src_dork = ctk.CTkCheckBox(sources_row, text="Google + DDG", width=100)
        self.src_dork.select()
        self.src_dork.pack(side="left", padx=2)

        self.src_archive = ctk.CTkCheckBox(sources_row, text="Archive", width=68)
        self.src_archive.select()
        self.src_archive.pack(side="left", padx=2)

        self.src_arxiv = ctk.CTkCheckBox(sources_row, text="arXiv", width=58)
        self.src_arxiv.select()
        self.src_arxiv.pack(side="left", padx=2)

        self.src_gutenberg = ctk.CTkCheckBox(sources_row, text="Gutenberg", width=80)
        self.src_gutenberg.select()
        self.src_gutenberg.pack(side="left", padx=2)

        self.src_openlib = ctk.CTkCheckBox(sources_row, text="OpenLib", width=72)
        self.src_openlib.select()
        self.src_openlib.pack(side="left", padx=2)

        self.src_standard = ctk.CTkCheckBox(sources_row, text="Std Ebooks", width=85)
        self.src_standard.select()
        self.src_standard.pack(side="left", padx=2)

        self.src_oapen = ctk.CTkCheckBox(sources_row, text="OAPEN", width=65)
        self.src_oapen.select()
        self.src_oapen.pack(side="left", padx=2)

        self.src_doab = ctk.CTkCheckBox(sources_row, text="DOAB", width=60)
        self.src_doab.select()
        self.src_doab.pack(side="left", padx=2)

        self.src_openalex = ctk.CTkCheckBox(sources_row, text="OpenAlex", width=75)
        self.src_openalex.select()
        self.src_openalex.pack(side="left", padx=2)

        self.src_hal = ctk.CTkCheckBox(sources_row, text="HAL", width=52)
        self.src_hal.select()
        self.src_hal.pack(side="left", padx=2)

        self.src_zenodo = ctk.CTkCheckBox(sources_row, text="Zenodo", width=68)
        self.src_zenodo.select()
        self.src_zenodo.pack(side="left", padx=2)

        # Optional web-only refinements. Catalog providers continue to receive
        # the unmodified topic, while the web search uses these operators.
        refine_frame = ctk.CTkFrame(parent, fg_color="transparent")
        refine_frame.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(refine_frame, text="Web search refinements:", font=("Helvetica", 12, "bold")).pack(side="left", padx=(0, 8))
        self.site_entry = ctk.CTkEntry(refine_frame, placeholder_text="Limit to site (e.g. edu, nasa.gov)", width=245, height=30)
        self.site_entry.pack(side="left", padx=(0, 8))
        self.exclude_entry = ctk.CTkEntry(refine_frame, placeholder_text="Exclude terms (comma separated)", width=270, height=30)
        self.exclude_entry.pack(side="left")

        # 3. Main Workspace: Table + Details Panel
        work_paned = ctk.CTkFrame(parent, fg_color="transparent")
        work_paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Table Container (Left 65%)
        table_frame = ctk.CTkFrame(work_paned)
        table_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Configure style for dark-theme ttk Treeview
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#23272d",
            foreground="#f0f0f0",
            fieldbackground="#23272d",
            rowheight=28,
            font=("Helvetica", 11),
        )
        style.configure(
            "Treeview.Heading",
            background="#1e2227",
            foreground="#61afef",
            font=("Helvetica", 11, "bold"),
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#1f6aa5")], foreground=[("selected", "#ffffff")])

        cols = ("idx", "title", "format", "source", "authors", "year", "score")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")

        headings = {
            "idx": "#",
            "title": "Title ↕",
            "format": "Format ↕",
            "source": "Source ↕",
            "authors": "Authors ↕",
            "year": "Year ↕",
            "score": "Score ↕",
        }
        for col_name, label in headings.items():
            self.tree.heading(col_name, text=label, command=lambda c=col_name: self._sort_column(c))

        self.tree.column("idx", width=40, anchor="center")
        self.tree.column("title", width=290, anchor="w")
        self.tree.column("format", width=65, anchor="center")
        self.tree.column("source", width=130, anchor="w")
        self.tree.column("authors", width=140, anchor="w")
        self.tree.column("year", width=55, anchor="center")
        self.tree.column("score", width=55, anchor="center")

        tree_scroll_y = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set)
        tree_scroll_y.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", lambda e: self.open_in_browser())

        # Right-click context menu
        self.context_menu = tk.Menu(
            self,
            tearoff=0,
            background="#23272d",
            foreground="#f0f0f0",
            activebackground="#1f6aa5",
            activeforeground="#ffffff",
            relief="flat",
            bd=1,
        )
        self.context_menu.add_command(label="📥 Download Selected", command=self.download_selected)
        self.context_menu.add_command(label="🌐 Open in Browser", command=self.open_in_browser)
        self.context_menu.add_command(label="📋 Copy Download URL", command=self.copy_download_link)
        self.context_menu.add_command(label="📂 Open in Folder / Finder", command=self.open_containing_folder)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="📄 Copy Citation", command=self.copy_citation)

        self.tree.bind("<Button-2>", self._show_context_menu)
        self.tree.bind("<Button-3>", self._show_context_menu)

        # Details Panel (Right 35%)
        detail_frame = ctk.CTkFrame(work_paned, width=320, corner_radius=8)
        detail_frame.pack(side="right", fill="both", padx=(0, 0))
        detail_frame.pack_propagate(False)

        ctk.CTkLabel(detail_frame, text="Resource Inspector", font=("Helvetica", 14, "bold")).pack(
            anchor="w", padx=12, pady=(12, 6)
        )

        self.detail_title = ctk.CTkLabel(
            detail_frame, text="Select an item to view details", wraplength=295, font=("Helvetica", 13, "bold"), justify="left"
        )
        self.detail_title.pack(anchor="w", padx=12, pady=4)

        self.detail_meta = ctk.CTkLabel(
            detail_frame, text="", wraplength=295, justify="left", text_color="#abb2bf", font=("Helvetica", 11)
        )
        self.detail_meta.pack(anchor="w", padx=12, pady=4)

        # Live Graphical Download Progress Card (shown during active downloads)
        self.dl_hud = ctk.CTkFrame(
            detail_frame, corner_radius=8, fg_color="#1e2227", border_width=1, border_color="#3a3f4b"
        )
        hud_header = ctk.CTkFrame(self.dl_hud, fg_color="transparent")
        hud_header.pack(fill="x", padx=10, pady=(8, 2))

        self.hud_lbl_title = ctk.CTkLabel(
            hud_header, text="⬇️ Downloading...", font=("Helvetica", 12, "bold"), text_color="#61afef", anchor="w"
        )
        self.hud_lbl_title.pack(side="left", fill="x", expand=True)

        self.hud_btn_cancel = ctk.CTkButton(
            hud_header,
            text="✕ Cancel",
            width=65,
            height=22,
            font=("Helvetica", 10, "bold"),
            fg_color="#e06c75",
            hover_color="#be5046",
            command=self.cancel_current_download,
        )
        self.hud_btn_cancel.pack(side="right")

        self.hud_progress_bar = ctk.CTkProgressBar(
            self.dl_hud, height=12, corner_radius=6, progress_color="#61afef", fg_color="#2c313a"
        )
        self.hud_progress_bar.set(0)
        self.hud_progress_bar.pack(fill="x", padx=10, pady=(4, 2))

        hud_stats = ctk.CTkFrame(self.dl_hud, fg_color="transparent")
        hud_stats.pack(fill="x", padx=10, pady=(2, 8))

        self.hud_lbl_size = ctk.CTkLabel(
            hud_stats, text="0 B / ...", font=("Helvetica", 10), text_color="#abb2bf", anchor="w"
        )
        self.hud_lbl_size.pack(side="left")

        self.hud_lbl_speed = ctk.CTkLabel(
            hud_stats, text="0 KB/s", font=("Helvetica", 10), text_color="#98c379", anchor="e"
        )
        self.hud_lbl_speed.pack(side="right")

        self.detail_desc = ctk.CTkTextbox(detail_frame, height=120, font=("Helvetica", 11))
        self.detail_desc.pack(fill="x", padx=12, pady=6)
        self.detail_desc.insert("1.0", "Description / Snippet will appear here.")
        self.detail_desc.configure(state="disabled")

        # Action Buttons in Inspector
        btn_box = ctk.CTkFrame(detail_frame, fg_color="transparent")
        btn_box.pack(fill="x", padx=12, pady=6)

        self.btn_download_one = ctk.CTkButton(
            btn_box, text="📥 Download Selected", command=self.download_selected, state="disabled"
        )
        self.btn_download_one.pack(fill="x", pady=2)

        self.btn_open_browser = ctk.CTkButton(
            btn_box,
            text="🌐 Open Link in Browser",
            fg_color="#3a3f4b",
            hover_color="#4b5263",
            command=self.open_in_browser,
            state="disabled",
        )
        self.btn_open_browser.pack(fill="x", pady=2)

        self.btn_copy_link = ctk.CTkButton(
            btn_box,
            text="📋 Copy Download URL",
            fg_color="#3a3f4b",
            hover_color="#4b5263",
            command=self.copy_download_link,
            state="disabled",
        )
        self.btn_copy_link.pack(fill="x", pady=2)

        self.btn_open_folder = ctk.CTkButton(
            btn_box,
            text="📂 Open in Folder / Finder",
            fg_color="#3a3f4b",
            hover_color="#4b5263",
            command=self.open_containing_folder,
            state="disabled",
        )
        self.btn_open_folder.pack(fill="x", pady=2)

        self.btn_copy_citation = ctk.CTkButton(
            btn_box,
            text="📄 Copy Citation",
            fg_color="#3a3f4b",
            hover_color="#4b5263",
            command=self.copy_citation,
            state="disabled",
        )
        self.btn_copy_citation.pack(fill="x", pady=2)

        # 4. Bottom Status & Batch Download Bar
        bottom_bar = ctk.CTkFrame(parent, height=48, corner_radius=8)
        bottom_bar.pack(fill="x", padx=8, pady=(0, 4))

        self.lbl_status = ctk.CTkLabel(
            bottom_bar, text="Ready. Enter a search query or explore Dorking Studio.", font=("Helvetica", 12)
        )
        self.lbl_status.pack(side="left", padx=12, pady=8)

        self.progress_bar = ctk.CTkProgressBar(bottom_bar, width=190, height=14, corner_radius=7, progress_color="#61afef")
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", padx=(12, 6), pady=8)

        self.lbl_progress_pct = ctk.CTkLabel(
            bottom_bar, text="", font=("Helvetica", 11, "bold"), text_color="#61afef", width=42, anchor="w"
        )
        self.lbl_progress_pct.pack(side="left", padx=(0, 8), pady=8)

        # Batch Download & Export buttons
        self.btn_export = ctk.CTkOptionMenu(
            bottom_bar,
            values=["Export...", "JSON", "CSV", "Markdown", "BibTeX"],
            command=self.export_results,
            width=110,
        )
        self.btn_export.pack(side="right", padx=(4, 12), pady=8)

        self.btn_download_all = ctk.CTkButton(
            bottom_bar,
            text="📥 Download All",
            width=120,
            fg_color="#2da44e",
            hover_color="#2c974b",
            command=self.download_all,
            state="disabled",
        )
        self.btn_download_all.pack(side="right", padx=4, pady=8)

    # -------------------------------------------------------------
    # TAB 2: Dorking Studio
    # -------------------------------------------------------------
    def _build_dork_tab(self):
        parent = self.tab_dork

        header_frame = ctk.CTkFrame(parent, corner_radius=8)
        header_frame.pack(fill="x", padx=8, pady=8)

        self.dork_entry = ctk.CTkEntry(
            header_frame,
            placeholder_text="Enter topic to generate precision search dorks (e.g., 'machine learning', 'linear algebra')...",
            height=38,
            font=("Helvetica", 13),
        )
        self.dork_entry.pack(side="left", fill="x", expand=True, padx=(12, 8), pady=10)
        self.dork_entry.bind("<Return>", lambda e: self.generate_dorks())

        btn_gen_dorks = ctk.CTkButton(
            header_frame,
            text="Generate Dorks",
            width=140,
            height=38,
            font=("Helvetica", 13, "bold"),
            command=self.generate_dorks,
        )
        btn_gen_dorks.pack(side="left", padx=(0, 12), pady=10)

        # Dork Cards Container
        self.dork_scroll = ctk.CTkScrollableFrame(parent, label_text="Precision Google & DuckDuckGo Search Patterns")
        self.dork_scroll.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # Initial message
        self.lbl_dork_empty = ctk.CTkLabel(
            self.dork_scroll,
            text="Enter a topic above and click 'Generate Dorks' to produce ready-to-run queries for university lecture notes, direct PDF/eBook indices, and open server directories.",
            wraplength=700,
            font=("Helvetica", 13),
            text_color="#abb2bf",
        )
        self.lbl_dork_empty.pack(pady=40)

    # -------------------------------------------------------------
    # TAB 3: Settings
    # -------------------------------------------------------------
    def _build_settings_tab(self):
        parent = self.tab_settings

        card = ctk.CTkFrame(parent, corner_radius=8)
        card.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(card, text="General Configuration", font=("Helvetica", 16, "bold")).pack(
            anchor="w", padx=16, pady=(16, 8)
        )

        # Download Directory
        dl_row = ctk.CTkFrame(card, fg_color="transparent")
        dl_row.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(dl_row, text="Downloads Folder:", font=("Helvetica", 13, "bold"), width=140, anchor="w").pack(
            side="left"
        )
        self.lbl_dl_path = ctk.CTkEntry(dl_row, height=32)
        self.lbl_dl_path.insert(0, self.download_dir)
        self.lbl_dl_path.configure(state="readonly")
        self.lbl_dl_path.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(dl_row, text="Browse...", width=100, command=self.change_download_dir)
        btn_browse.pack(side="left")

        # Appearance Mode
        theme_row = ctk.CTkFrame(card, fg_color="transparent")
        theme_row.pack(fill="x", padx=16, pady=8)
        ctk.CTkLabel(theme_row, text="Theme Mode:", font=("Helvetica", 13, "bold"), width=140, anchor="w").pack(
            side="left"
        )
        self.theme_menu = ctk.CTkOptionMenu(
            theme_row, values=["Dark", "Light", "System"], command=ctk.set_appearance_mode, width=140
        )
        self.theme_menu.pack(side="left")

    # -------------------------------------------------------------
    # Search Logic
    # -------------------------------------------------------------
    def start_search(self):
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showwarning("Search Topic Required", "Please enter a topic or keywords to search.")
            return

        if self.is_searching:
            return

        # Determine enabled sources
        enabled_sources: list[str] = []
        if self.src_dork.get():
            enabled_sources.append("web_dork")
        if self.src_archive.get():
            enabled_sources.append("internet_archive")
        if self.src_arxiv.get():
            enabled_sources.append("arxiv")
        if self.src_gutenberg.get():
            enabled_sources.append("gutenberg")
        if self.src_openlib.get():
            enabled_sources.append("open_library")
        if self.src_standard.get():
            enabled_sources.append("standard_ebooks")
        if self.src_oapen.get():
            enabled_sources.append("oapen")
        if self.src_doab.get():
            enabled_sources.append("doab")
        if self.src_openalex.get():
            enabled_sources.append("openalex")
        if self.src_hal.get():
            enabled_sources.append("hal_science")
        if self.src_zenodo.get():
            enabled_sources.append("zenodo")

        if not enabled_sources:
            messagebox.showwarning("No Sources Selected", "Please select at least one search provider.")
            return

        fmt = None if self.fmt_var.get() == "All" else self.fmt_var.get()
        limit = int(self.limit_var.get())

        web_query = query
        site = self.site_entry.get().strip().removeprefix("https://").removeprefix("http://").strip(" /")
        if site:
            web_query += f" site:{site}"
        exclusions = [term.strip() for term in self.exclude_entry.get().split(",") if term.strip()]
        for term in exclusions:
            web_query += f' -"{term}"' if " " in term else f" -{term}"

        self.is_searching = True
        self.btn_search.configure(state="disabled", text="Searching...")
        self.lbl_status.configure(text=f"Searching for '{query}' across {len(enabled_sources)} providers...")
        self.progress_bar.set(0)
        self.progress_bar.start()

        # Clear existing rows
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.results = []
        self._reset_inspector()

        # Run search asynchronously in a background worker thread
        def _worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                items = loop.run_until_complete(
                    self.scraper.search(
                        query=query,
                        limit_per_source=limit,
                        file_format=fmt,
                        enabled_sources=enabled_sources,
                        validate_links=True,
                        web_query=web_query,
                    )
                )
                self.after(0, self._on_search_complete, items, None)
            except Exception as e:
                self.after(0, self._on_search_complete, [], str(e))
            finally:
                loop.close()

        threading.Thread(target=_worker, daemon=True).start()

    def _select_all_sources(self):
        for cb in [
            self.src_dork,
            self.src_archive,
            self.src_arxiv,
            self.src_gutenberg,
            self.src_openlib,
            self.src_standard,
            self.src_oapen,
            self.src_doab,
            self.src_openalex,
            self.src_hal,
            self.src_zenodo,
        ]:
            cb.select()

    def _clear_all_sources(self):
        for cb in [
            self.src_dork,
            self.src_archive,
            self.src_arxiv,
            self.src_gutenberg,
            self.src_openlib,
            self.src_standard,
            self.src_oapen,
            self.src_doab,
            self.src_openalex,
            self.src_hal,
            self.src_zenodo,
        ]:
            cb.deselect()

    def _populate_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for idx, item in enumerate(self.results, 1):
            year_str = str(item.year) if item.year else "-"
            authors_str = item.formatted_authors
            self.tree.insert(
                "",
                "end",
                iid=str(idx - 1),
                values=(
                    idx,
                    item.title,
                    item.format,
                    item.source,
                    authors_str,
                    year_str,
                    f"{int(item.score)}%",
                ),
            )

    def _sort_column(self, col: str):
        if not self.results:
            return

        attr_key = f"_sort_asc_{col}"
        current_asc = getattr(self, attr_key, True)
        setattr(self, attr_key, not current_asc)

        if col == "idx":
            self.results.sort(key=lambda x: x.score, reverse=current_asc)
        elif col == "title":
            self.results.sort(key=lambda x: x.title.lower(), reverse=not current_asc)
        elif col == "format":
            self.results.sort(key=lambda x: x.format.lower(), reverse=not current_asc)
        elif col == "source":
            self.results.sort(key=lambda x: x.source.lower(), reverse=not current_asc)
        elif col == "authors":
            self.results.sort(key=lambda x: x.formatted_authors.lower(), reverse=not current_asc)
        elif col == "year":
            self.results.sort(key=lambda x: (x.year is not None, x.year or 0), reverse=not current_asc)
        elif col == "score":
            self.results.sort(key=lambda x: x.score, reverse=not current_asc)

        self._populate_table()
        self._reset_inspector()

    def _show_context_menu(self, event: tk.Event) -> None:
        item_id = self.tree.identify_row(event.y)
        if item_id:
            self.tree.selection_set(item_id)
            self._on_tree_select(None)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def copy_citation(self):
        if not self.selected_item:
            return
        it = self.selected_item
        year_str = f" ({it.year})" if it.year else ""
        authors_str = f"{it.formatted_authors}. " if it.authors else ""
        citation = f"{authors_str}{it.title}{year_str}. Available at: {it.details_url or it.download_url}"
        self.clipboard_clear()
        self.clipboard_append(citation)
        self.lbl_status.configure(text="Citation copied to clipboard!")

    def open_containing_folder(self):
        if not self.selected_item:
            return
        downloader = Downloader(download_dir=self.download_dir)
        ext = self.selected_item.format.lower() if self.selected_item.format else "pdf"
        target_name = downloader.sanitize_filename(self.selected_item.title, ext)
        target_path = Path(self.download_dir) / target_name

        if target_path.exists():
            if sys.platform == "darwin":
                import subprocess
                subprocess.run(["open", "-R", str(target_path)])
            elif sys.platform == "win32":
                import subprocess
                subprocess.run(["explorer", f"/select,{str(target_path)}"])
            else:
                webbrowser.open(str(self.download_dir))
            self.lbl_status.configure(text=f"Revealed in folder: {target_name}")
        else:
            webbrowser.open(str(Path(self.download_dir).as_uri()))
            self.lbl_status.configure(text=f"Opened download folder: {self.download_dir}")

    def _on_search_complete(self, items: list[ResourceItem], error: str | None = None) -> None:
        self.is_searching = False
        self.btn_search.configure(state="normal", text="Search Everywhere")
        self.progress_bar.stop()
        self.progress_bar.set(0)

        if error:
            self.lbl_status.configure(text=f"Search failed: {error}")
            messagebox.showerror("Search Error", f"An error occurred during search:\n{error}")
            return

        self.results = items
        self.lbl_status.configure(text=f"Found {len(items)} resources matching query.")

        if not items:
            self.btn_download_all.configure(state="disabled")
            return

        self.btn_download_all.configure(state="normal")
        self._populate_table()

    def _on_tree_select(self, event: tk.Event | None = None) -> None:
        selected = self.tree.selection()
        if not selected:
            self._reset_inspector()
            return

        idx = int(selected[0])
        if 0 <= idx < len(self.results):
            item = self.results[idx]
            self.selected_item = item

            self.detail_title.configure(text=item.title)
            meta_str = (
                f"Format: {item.format} | Source: {item.source}\n"
                f"Authors: {item.formatted_authors}\n"
                f"Year: {item.year or 'Unknown'} | Size: {item.formatted_size}\n"
                f"Relevance: {item.score:.1f}%"
            )
            if item.dork_type:
                meta_str += f"\nDork Type: {item.dork_type}"

            self.detail_meta.configure(text=meta_str)

            self.detail_desc.configure(state="normal")
            self.detail_desc.delete("1.0", "end")
            self.detail_desc.insert("1.0", item.description or "No description provided by source.")
            self.detail_desc.configure(state="disabled")

            self.btn_download_one.configure(state="normal")
            self.btn_open_browser.configure(state="normal")
            self.btn_copy_link.configure(state="normal")
            self.btn_open_folder.configure(state="normal")
            self.btn_copy_citation.configure(state="normal")

    def _reset_inspector(self):
        self.selected_item = None
        self.detail_title.configure(text="Select an item to view details")
        self.detail_meta.configure(text="")
        self.detail_desc.configure(state="normal")
        self.detail_desc.delete("1.0", "end")
        self.detail_desc.insert("1.0", "Description / Snippet will appear here.")
        self.detail_desc.configure(state="disabled")

        self.btn_download_one.configure(state="disabled")
        self.btn_open_browser.configure(state="disabled")
        self.btn_copy_link.configure(state="disabled")
        self.btn_open_folder.configure(state="disabled")
        self.btn_copy_citation.configure(state="disabled")

    # -------------------------------------------------------------
    # Download Actions & Graphical Progress
    # -------------------------------------------------------------
    @staticmethod
    def _format_bytes(n: float | int) -> str:
        if not n or n <= 0:
            return "0 B"
        for unit in ["B", "KB", "MB", "GB"]:
            if abs(n) < 1024.0:
                return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
            n /= 1024.0
        return f"{n:.1f} TB"

    def cancel_current_download(self):
        if self.download_cancel_event and not self.download_cancel_event.is_set():
            self.download_cancel_event.set()
            self.lbl_status.configure(text="Cancelling download...")
            self.hud_lbl_size.configure(text="Cancelling...")

    def _update_download_progress(self, completed: int, total: int | None, speed: float, title: str):
        if not self.is_downloading:
            return

        speed_str = f"⚡ {self._format_bytes(speed)}/s"

        if total and total > 0:
            pct = min(1.0, max(0.0, completed / total))
            pct_int = int(pct * 100)
            size_str = f"{self._format_bytes(completed)} / {self._format_bytes(total)}"
            eta_secs = int((total - completed) / speed) if speed > 1024 else None
            eta_str = f" • ETA: {eta_secs}s" if eta_secs is not None and eta_secs < 3600 else ""

            self.hud_progress_bar.set(pct)
            self.progress_bar.set(pct)
            self.lbl_progress_pct.configure(text=f"{pct_int}%")
            self.hud_lbl_size.configure(text=f"{pct_int}% ({size_str})")
            self.hud_lbl_speed.configure(text=f"{speed_str}{eta_str}")
            self.lbl_status.configure(
                text=f"Downloading '{title[:26]}...' • {pct_int}% ({size_str}) • {self._format_bytes(speed)}/s"
            )
        else:
            size_str = f"{self._format_bytes(completed)} downloaded"
            self.hud_lbl_size.configure(text=size_str)
            self.hud_lbl_speed.configure(text=speed_str)
            self.lbl_progress_pct.configure(text="")
            self.lbl_status.configure(
                text=f"Downloading '{title[:28]}...' • {size_str} • {self._format_bytes(speed)}/s"
            )

    def download_selected(self):
        if not self.selected_item or self.is_downloading:
            return

        item = self.selected_item
        self.is_downloading = True
        self.download_cancel_event = threading.Event()

        # Show graphical download HUD in inspector
        self.dl_hud.pack(fill="x", padx=12, pady=(4, 6), before=self.detail_desc)
        self.hud_lbl_title.configure(text=f"⬇️ Downloading [{item.format}]...")
        self.hud_progress_bar.set(0)
        self.hud_lbl_size.configure(text="Connecting to server...")
        self.hud_lbl_speed.configure(text="0 KB/s")
        self.hud_btn_cancel.configure(state="normal", text="✕ Cancel")

        self.btn_download_one.configure(state="disabled", text="Downloading...")
        self.btn_download_all.configure(state="disabled")
        self.lbl_status.configure(text=f"Connecting to host for '{item.title[:30]}...'")
        self.progress_bar.set(0)
        self.lbl_progress_pct.configure(text="0%")

        def _progress_cb(done: int, total: int | None, speed: float):
            self.after(0, self._update_download_progress, done, total, speed, item.title)

        def _worker():
            downloader = Downloader(download_dir=self.download_dir)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                success, path_or_err = loop.run_until_complete(
                    downloader.download_item(
                        item,
                        progress_callback=_progress_cb,
                        cancel_event=self.download_cancel_event,
                    )
                )
                self.after(0, self._on_download_one_complete, success, path_or_err)
            finally:
                loop.close()

        threading.Thread(target=_worker, daemon=True).start()

    def _on_download_one_complete(self, success: bool, msg: str):
        self.is_downloading = False
        self.btn_download_one.configure(state="normal", text="📥 Download Selected")
        if self.results:
            self.btn_download_all.configure(state="normal")
        self.dl_hud.pack_forget()
        self.progress_bar.set(0)
        self.lbl_progress_pct.configure(text="")

        if success:
            self.lbl_status.configure(text=f"Saved to: {Path(msg).name}")
            messagebox.showinfo("Download Complete", f"File saved successfully:\n{msg}")
        elif "cancelled" in msg.lower():
            self.lbl_status.configure(text="Download cancelled by user.")
        else:
            self.lbl_status.configure(text=f"Download failed: {msg}")
            messagebox.showerror("Download Failed", f"Could not download file:\n{msg}")

    def _update_batch_progress(self, idx: int, total_items: int, item: ResourceItem, done: int, total: int | None, speed: float):
        if not self.is_downloading:
            return

        item_pct = (done / total) if total and total > 0 else 0.0
        overall_pct = min(1.0, max(0.0, ((idx - 1) + item_pct) / total_items))
        overall_pct_int = int(overall_pct * 100)

        self.hud_lbl_title.configure(text=f"⬇️ Batch [{idx}/{total_items}] [{item.format}]")
        self.hud_progress_bar.set(item_pct)
        self.progress_bar.set(overall_pct)
        self.lbl_progress_pct.configure(text=f"{overall_pct_int}%")

        size_str = f"{self._format_bytes(done)} / {self._format_bytes(total)}" if total else f"{self._format_bytes(done)}"
        self.hud_lbl_size.configure(text=f"Item {idx}/{total_items}: {size_str}")
        self.hud_lbl_speed.configure(text=f"⚡ {self._format_bytes(speed)}/s")
        self.lbl_status.configure(
            text=f"[{idx}/{total_items}] Downloading '{item.title[:24]}...' • Overall: {overall_pct_int}% • {self._format_bytes(speed)}/s"
        )

    def download_all(self):
        if not self.results or self.is_downloading:
            return

        confirm = messagebox.askyesno(
            "Batch Download", f"Download all {len(self.results)} resources to:\n{self.download_dir}?"
        )
        if not confirm:
            return

        self.is_downloading = True
        self.download_cancel_event = threading.Event()
        self.btn_download_all.configure(state="disabled", text="Downloading All...")
        self.btn_download_one.configure(state="disabled")

        # Show graphical HUD
        self.dl_hud.pack(fill="x", padx=12, pady=(4, 6), before=self.detail_desc)
        self.hud_lbl_title.configure(text=f"⬇️ Batch Download (0/{len(self.results)})...")
        self.hud_progress_bar.set(0)
        self.hud_lbl_size.configure(text="Starting batch...")
        self.hud_lbl_speed.configure(text="0 KB/s")
        self.hud_btn_cancel.configure(state="normal", text="✕ Cancel")

        self.progress_bar.set(0)
        self.lbl_progress_pct.configure(text="0%")

        def _item_cb(idx: int, total_items: int, item: ResourceItem, done: int, total: int | None, speed: float):
            self.after(0, self._update_batch_progress, idx, total_items, item, done, total, speed)

        def _worker():
            downloader = Downloader(download_dir=self.download_dir)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                res = loop.run_until_complete(
                    downloader.download_multiple(
                        self.results,
                        item_progress_callback=_item_cb,
                        cancel_event=self.download_cancel_event,
                    )
                )
                success_count = sum(1 for _, s, _ in res if s)
                self.after(0, self._on_download_all_complete, success_count, len(self.results))
            finally:
                loop.close()

        threading.Thread(target=_worker, daemon=True).start()

    def _on_download_all_complete(self, succeeded: int, total: int):
        self.is_downloading = False
        self.btn_download_all.configure(state="normal", text="📥 Download All")
        if self.selected_item:
            self.btn_download_one.configure(state="normal")
        self.dl_hud.pack_forget()
        self.progress_bar.set(0)
        self.lbl_progress_pct.configure(text="")

        self.lbl_status.configure(text=f"Batch download finished: {succeeded}/{total} succeeded.")
        messagebox.showinfo(
            "Batch Download Complete", f"Finished downloading files:\n{succeeded} of {total} saved successfully."
        )

    # -------------------------------------------------------------
    # External Links & Helpers
    # -------------------------------------------------------------
    def open_in_browser(self):
        if not self.selected_item:
            return
        target = self.selected_item.details_url or self.selected_item.download_url
        webbrowser.open(target)

    def copy_download_link(self):
        if not self.selected_item:
            return
        self.clipboard_clear()
        self.clipboard_append(self.selected_item.download_url)
        self.lbl_status.configure(text="Download URL copied to clipboard.")

    def change_download_dir(self):
        selected = filedialog.askdirectory(initialdir=self.download_dir, title="Select Downloads Folder")
        if selected:
            self.download_dir = selected
            self.lbl_dl_path.configure(state="normal")
            self.lbl_dl_path.delete(0, "end")
            self.lbl_dl_path.insert(0, selected)
            self.lbl_dl_path.configure(state="readonly")

    def export_results(self, format_choice: str):
        if format_choice == "Export..." or not self.results:
            return

        fmt = format_choice.lower()
        ext_map = {"json": ".json", "csv": ".csv", "markdown": ".md", "bibtex": ".bib"}
        ext = ext_map.get(fmt, ".json")

        file_path = filedialog.asksaveasfilename(
            defaultextension=ext,
            filetypes=[(f"{format_choice} Files", f"*{ext}")],
            initialfile=f"bookhunt_results{ext}",
            title="Export Search Results",
        )
        if not file_path:
            self.btn_export.set("Export...")
            return

        try:
            if fmt == "json":
                ResultExporter.to_json(self.results, file_path)
            elif fmt == "csv":
                ResultExporter.to_csv(self.results, file_path)
            elif fmt == "markdown":
                ResultExporter.to_markdown(self.results, file_path, topic=self.search_entry.get())
            elif fmt == "bibtex":
                ResultExporter.to_bibtex(self.results, file_path)

            messagebox.showinfo("Export Successful", f"Results exported to:\n{file_path}")
            self.lbl_status.configure(text=f"Exported {len(self.results)} items to {Path(file_path).name}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not export file:\n{str(e)}")
        finally:
            self.btn_export.set("Export...")

    # -------------------------------------------------------------
    # Dorking Studio Logic
    # -------------------------------------------------------------
    def generate_dorks(self):
        topic = self.dork_entry.get().strip()
        if not topic:
            messagebox.showwarning("Topic Required", "Please enter a topic to generate search dorks.")
            return

        # Clear existing dork cards
        for widget in self.dork_scroll.winfo_children():
            widget.destroy()

        dorks = DorkGenerator.get_dorks_for_topic(topic=topic)

        for pattern, query in dorks:
            card = ctk.CTkFrame(self.dork_scroll, corner_radius=6)
            card.pack(fill="x", padx=6, pady=6)

            top_row = ctk.CTkFrame(card, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 2))

            ctk.CTkLabel(top_row, text=pattern.name, font=("Helvetica", 13, "bold"), text_color="#61afef").pack(
                side="left"
            )
            badge = ctk.CTkLabel(
                top_row,
                text=pattern.category,
                font=("Helvetica", 10, "bold"),
                fg_color="#3a3f4b",
                corner_radius=4,
                width=65,
                height=20,
            )
            badge.pack(side="left", padx=8)

            desc = ctk.CTkLabel(card, text=pattern.description, font=("Helvetica", 11), text_color="#abb2bf", anchor="w")
            desc.pack(fill="x", padx=10, pady=(0, 4))

            # Query display box
            q_box = ctk.CTkEntry(card, font=("Courier", 11), height=30)
            q_box.insert(0, query)
            q_box.configure(state="readonly")
            q_box.pack(fill="x", padx=10, pady=4)

            # Actions row
            actions = ctk.CTkFrame(card, fg_color="transparent")
            actions.pack(fill="x", padx=10, pady=(4, 8))

            ctk.CTkButton(
                actions,
                text="📋 Copy Query",
                width=110,
                height=26,
                fg_color="#3a3f4b",
                hover_color="#4b5263",
                command=lambda q=query: self._copy_text(q),
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                actions,
                text="🌐 Open in Google",
                width=120,
                height=26,
                fg_color="#3a3f4b",
                hover_color="#4b5263",
                command=lambda q=query: webbrowser.open(f"https://www.google.com/search?q={q}"),
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                actions,
                text="🦆 Open in DuckDuckGo",
                width=140,
                height=26,
                fg_color="#3a3f4b",
                hover_color="#4b5263",
                command=lambda q=query: webbrowser.open(f"https://duckduckgo.com/?q={q}"),
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                actions,
                text="⚡ Search in App",
                width=120,
                height=26,
                fg_color="#1f6aa5",
                command=lambda t=topic: self._search_topic_from_dork(t),
            ).pack(side="right")

    def _copy_text(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.lbl_status.configure(text="Query copied to clipboard!")

    def _search_topic_from_dork(self, topic: str):
        self.tabview.set("🔍 Search & Download")
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, topic)
        self.start_search()


def launch_gui():
    """Entry point for running the GUI."""
    app = BookHuntGUI()
    app.mainloop()


if __name__ == "__main__":
    launch_gui()
