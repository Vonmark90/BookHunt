"""Generates the macOS BookHunt.app application bundle with custom icon."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def create_app_icon(output_icns: Path):
    """Draws a modern macOS style squircle book & search icon and compiles to .icns."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("Pillow not installed. Skipping dynamic icon drawing.")
        return False

    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Background Rounded Squircle with gradient
    margin = 80
    r = 200
    box = [margin, margin, size - margin, size - margin]

    # Fill base squircle
    draw.rounded_rectangle(box, radius=r, fill=(24, 28, 38, 255), outline=(56, 139, 253, 200), width=12)

    # Decorative subtle accent glow / ribbon
    accent_box = [margin + 20, margin + 20, size - margin - 20, size - margin - 20]
    draw.rounded_rectangle(accent_box, radius=r - 10, outline=(97, 175, 239, 60), width=6)

    # 2. Draw Book Silhouette (Center)
    center_x = size // 2
    book_top = 280
    book_bottom = 680
    spine_x = center_x
    page_w = 260

    # Left Page
    left_poly = [
        (spine_x - 10, book_bottom - 40),
        (spine_x - page_w, book_bottom),
        (spine_x - page_w, book_top + 40),
        (spine_x - 10, book_top),
    ]
    draw.polygon(left_poly, fill=(235, 240, 248, 255))

    # Right Page
    right_poly = [
        (spine_x + 10, book_bottom - 40),
        (spine_x + page_w, book_bottom),
        (spine_x + page_w, book_top + 40),
        (spine_x + 10, book_top),
    ]
    draw.polygon(right_poly, fill=(215, 225, 238, 255))

    # Page line details (Left)
    for y_off in [60, 110, 160, 210]:
        draw.line(
            [(spine_x - 40, book_top + y_off), (spine_x - page_w + 50, book_top + y_off + 8)],
            fill=(170, 185, 205, 255),
            width=8,
        )

    # Page line details (Right)
    for y_off in [60, 110, 160, 210]:
        draw.line(
            [(spine_x + 40, book_top + y_off), (spine_x + page_w - 50, book_top + y_off + 8)],
            fill=(160, 175, 195, 255),
            width=8,
        )

    # Book Spine
    draw.line([(spine_x, book_top - 5), (spine_x, book_bottom - 35)], fill=(31, 106, 165, 255), width=18)

    # 3. Draw Magnifying Glass / Search Symbol over Book
    lens_center = (center_x + 100, book_bottom - 60)
    lens_r = 130
    lens_box = [
        lens_center[0] - lens_r,
        lens_center[1] - lens_r,
        lens_center[0] + lens_r,
        lens_center[1] + lens_r,
    ]
    # Lens Glass
    draw.ellipse(lens_box, fill=(31, 106, 165, 190), outline=(97, 175, 239, 255), width=16)

    # Lens Handle
    handle_start = (lens_center[0] + 90, lens_center[1] + 90)
    handle_end = (lens_center[0] + 200, lens_center[1] + 200)
    draw.line([handle_start, handle_end], fill=(97, 175, 239, 255), width=28)

    # Save to iconset
    iconset_dir = output_icns.parent / "AppIcon.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    sizes = [16, 32, 64, 128, 256, 512, 1024]
    for s in sizes:
        resized = img.resize((s, s), Image.Resampling.LANCZOS)
        if s <= 512:
            resized.save(iconset_dir / f"icon_{s}x{s}.png")
            s2x = s * 2
            if s2x <= 1024:
                resized2x = img.resize((s2x, s2x), Image.Resampling.LANCZOS)
                resized2x.save(iconset_dir / f"icon_{s}x{s}@2x.png")

    # Run macOS iconutil
    if shutil.which("iconutil"):
        subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_icns)], check=True)
        # Clean up iconset directory
        for f in iconset_dir.glob("*.png"):
            f.unlink()
        iconset_dir.rmdir()
        return True
    return False


def build_app_bundle():
    project_dir = Path(__file__).resolve().parent
    app_dir = project_dir / "BookHunt.app"
    contents_dir = app_dir / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    macos_dir.mkdir(parents=True, exist_ok=True)
    resources_dir.mkdir(parents=True, exist_ok=True)

    # 1. Create Info.plist
    info_plist_path = contents_dir / "Info.plist"
    info_plist_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>BookHunt</string>
    <key>CFBundleExecutable</key>
    <string>BookHunt</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.marksadler.bookhunt</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>BookHunt</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Copyright © 2026 Mark Sadler</string>
</dict>
</plist>
"""
    with open(info_plist_path, "w", encoding="utf-8") as f:
        f.write(info_plist_content)

    # 2. Create Portable Executable Launcher
    launcher_path = macos_dir / "BookHunt"
    launcher_script = """#!/bin/bash
# Portable macOS App Launcher for BookHunt

# Resolve bundle and project directories
BUNDLE_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PARENT_DIR="$(cd "$BUNDLE_DIR/.." && pwd)"

if [ -f "$PARENT_DIR/.venv/bin/python" ]; then
    PROJECT_DIR="$PARENT_DIR"
elif [ -n "$VIRTUAL_ENV" ] && [ -f "$VIRTUAL_ENV/bin/python" ]; then
    PROJECT_DIR="$(cd "$VIRTUAL_ENV/.." && pwd)"
elif [ -f "$HOME/universal-book-scraper/.venv/bin/python" ]; then
    PROJECT_DIR="$HOME/universal-book-scraper"
else
    PROJECT_DIR="$PARENT_DIR"
fi

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
export PYTHONPATH="$PROJECT_DIR"

cd "$PROJECT_DIR" || exit 1
mkdir -p "$HOME/Library/Logs"

if [ -f "$PROJECT_DIR/.venv/bin/python" ]; then
    exec "$PROJECT_DIR/.venv/bin/python" -m scraper gui > "$HOME/Library/Logs/BookHunt.log" 2>&1
elif command -v python3 >/dev/null 2>&1; then
    exec python3 -m scraper gui > "$HOME/Library/Logs/BookHunt.log" 2>&1
else
    osascript -e 'display alert "BookHunt Error" message "Python environment not found. Run ./setup.sh in the repository folder."'
fi
"""
    with open(launcher_path, "w", encoding="utf-8") as f:
        f.write(launcher_script)

    os.chmod(launcher_path, 0o755)

    # 3. Handle AppIcon.icns
    icns_path = resources_dir / "AppIcon.icns"
    cached_icon = project_dir / "assets" / "AppIcon.icns"

    if cached_icon.is_file():
        shutil.copyfile(cached_icon, icns_path)
        print(f"Copied icon from assets to {icns_path}")
    else:
        print("Generating custom macOS AppIcon...")
        create_app_icon(icns_path)

    print(f"✅ Successfully built macOS application bundle at: {app_dir}")


if __name__ == "__main__":
    build_app_bundle()
