#!/usr/bin/env python3
"""Native macOS Application Bundle and Installer Builder for BookHunt.

Produces:
1. BookHunt.app (standalone sandboxed macOS application bundle)
2. dist/BookHunt-1.0.0.dmg (drag-and-drop installer disk image)
3. dist/BookHunt-1.0.0.pkg (Apple App Store / Transporter compliant installer)
"""

import os
import sys
import shutil
import plistlib
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw


def create_app_icon(output_icns: Path) -> bool:
    """Generate a high-resolution retina macOS icon (.icns)."""
    size = 1024
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer rounded squircle
    margin = 48
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=210,
        fill=(18, 22, 28, 255),
        outline=(52, 63, 75, 255),
        width=12,
    )

    # Accent gradient glow inside
    draw.rounded_rectangle(
        [margin + 16, margin + 16, size - margin - 16, size - margin - 16],
        radius=195,
        fill=(24, 30, 39, 255),
    )

    # Book covers & pages
    book_x0, book_y0 = 240, 310
    book_w, book_h = 544, 400

    draw.rounded_rectangle(
        [book_x0, book_y0, book_x0 + book_w, book_y0 + book_h],
        radius=28,
        fill=(226, 232, 240, 255),
        outline=(148, 163, 184, 255),
        width=8,
    )
    draw.line(
        [book_x0 + book_w // 2, book_y0, book_x0 + book_w // 2, book_y0 + book_h],
        fill=(100, 116, 139, 255),
        width=10,
    )

    # Text lines on book
    for y_off in range(60, 320, 48):
        draw.line([book_x0 + 40, book_y0 + y_off, book_x0 + 220, book_y0 + y_off], fill=(148, 163, 184, 255), width=8)
        draw.line([book_x0 + 310, book_y0 + y_off, book_x0 + 490, book_y0 + y_off], fill=(148, 163, 184, 255), width=8)

    # Magnifying glass
    lens_center = (600, 600)
    lens_r = 170
    lens_box = [
        lens_center[0] - lens_r,
        lens_center[1] - lens_r,
        lens_center[0] + lens_r,
        lens_center[1] + lens_r,
    ]
    draw.ellipse(lens_box, fill=(31, 106, 165, 190), outline=(97, 175, 239, 255), width=16)

    handle_start = (lens_center[0] + 90, lens_center[1] + 90)
    handle_end = (lens_center[0] + 200, lens_center[1] + 200)
    draw.line([handle_start, handle_end], fill=(97, 175, 239, 255), width=28)

    iconset_dir = output_icns.parent / "AppIcon.iconset"
    iconset_dir.mkdir(parents=True, exist_ok=True)

    sizes = [16, 32, 64, 128, 256, 512]
    for s in sizes:
        resized = img.resize((s, s), Image.Resampling.LANCZOS)
        resized.save(iconset_dir / f"icon_{s}x{s}.png")
        if s <= 512:
            s2x = s * 2
            resized2x = img.resize((s2x, s2x), Image.Resampling.LANCZOS)
            resized2x.save(iconset_dir / f"icon_{s}x{s}@2x.png")

    if shutil.which("iconutil"):
        subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(output_icns)], check=True)
        for f in iconset_dir.glob("*.png"):
            f.unlink()
        iconset_dir.rmdir()
        return True
    return False


def build_app_bundle():
    project_dir = Path(__file__).resolve().parent
    app_dir = project_dir / "BookHunt.app"
    dist_dir = project_dir / "dist"
    build_dir = project_dir / "build"
    assets_dir = project_dir / "assets"

    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ensure high-resolution AppIcon.icns
    cached_icon = assets_dir / "AppIcon.icns"
    if not cached_icon.is_file():
        print("🎨 Generating retina macOS AppIcon...")
        create_app_icon(cached_icon)

    # 2. Generate Apple App Store Sandbox Entitlements
    entitlements_path = project_dir / "entitlements.plist"
    entitlements_content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>com.apple.security.app-sandbox</key>
    <true/>
    <key>com.apple.security.network.client</key>
    <true/>
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
    <key>com.apple.security.files.downloads.read-write</key>
    <true/>
    <key>com.apple.security.inherit</key>
    <true/>
</dict>
</plist>
"""
    with open(entitlements_path, "w", encoding="utf-8") as f:
        f.write(entitlements_content)

    # 3. Build Standalone App Bundle with PyInstaller
    pyinstaller_dist = build_dir / "pyi_dist"
    pyinstaller_work = build_dir / "pyi_work"
    if pyinstaller_dist.exists():
        shutil.rmtree(pyinstaller_dist)
    if pyinstaller_work.exists():
        shutil.rmtree(pyinstaller_work)

    print("📦 Compiling standalone BookHunt.app with embedded runtime...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--windowed",
        "--name", "BookHunt",
        "--icon", str(cached_icon),
        "--osx-bundle-identifier", "com.marksadler.bookhunt",
        "--collect-all", "customtkinter",
        "--collect-all", "scraper",
        "--clean",
        "--noconfirm",
        "--distpath", str(pyinstaller_dist),
        "--workpath", str(pyinstaller_work),
        str(project_dir / "scraper" / "__main__.py"),
    ]
    subprocess.run(cmd, check=True)

    # Replace root BookHunt.app with newly built standalone bundle
    compiled_app = pyinstaller_dist / "BookHunt.app"
    if app_dir.exists():
        shutil.rmtree(app_dir)
    shutil.copytree(compiled_app, app_dir, symlinks=True)

    contents_dir = app_dir / "Contents"
    resources_dir = contents_dir / "Resources"

    # Copy AppIcon to Resources
    shutil.copyfile(cached_icon, resources_dir / "AppIcon.icns")

    # 4. Enhance Info.plist with App Store Metadata
    info_plist_path = contents_dir / "Info.plist"
    with open(info_plist_path, "rb") as f:
        plist_data = plistlib.load(f)

    plist_data.update({
        "CFBundleDisplayName": "BookHunt",
        "CFBundleName": "BookHunt",
        "CFBundleIdentifier": "com.marksadler.bookhunt",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "1.0.0",
        "LSApplicationCategoryType": "public.app-category.reference-tools",
        "LSMinimumSystemVersion": "10.15",
        "NSHighResolutionCapable": True,
        "NSSupportsAutomaticGraphicsSwitching": True,
        "NSHumanReadableCopyright": "Copyright © 2026 Mark Sadler. All rights reserved.",
        "ITSAppUsesNonExemptEncryption": False,
        "NSDownloadsFolderUsageDescription": "BookHunt needs access to your Downloads folder to save downloaded books and documents.",
        "NSDocumentsFolderUsageDescription": "BookHunt needs access to save search results and citation bibliographies.",
        "NSDesktopFolderUsageDescription": "BookHunt needs access if you choose to export books or citations to your Desktop.",
    })

    with open(info_plist_path, "wb") as f:
        plistlib.dump(plist_data, f)

    # 5. Create PkgInfo
    pkginfo_path = contents_dir / "PkgInfo"
    with open(pkginfo_path, "wb") as f:
        f.write(b"APPL????")

    # 6. Ensure clean bundle root (codesign strict requirement)
    for item in app_dir.iterdir():
        if item.name != "Contents":
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()

    # 7. Apply Code Signing with Sandbox Entitlements
    if shutil.which("codesign"):
        print("🔐 Signing bundle with macOS App Sandbox entitlements...")
        subprocess.run(
            ["codesign", "--force", "--deep", "-s", "-", "--entitlements", str(entitlements_path), str(app_dir)],
            check=True,
        )
        verify_res = subprocess.run(
            ["codesign", "--verify", "--deep", "--strict", "--verbose=1", str(app_dir)],
            capture_output=True,
            text=True,
        )
        print(f"   Signature validation: {verify_res.stderr.strip() or OK}")

    # 8. Create Distributable DMG Disk Image
    dmg_path = dist_dir / "BookHunt-1.0.0.dmg"
    staging_dir = build_dir / "dmg_staging"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)

    shutil.copytree(app_dir, staging_dir / "BookHunt.app", symlinks=True)
    os.symlink("/Applications", staging_dir / "Applications")

    if dmg_path.exists():
        dmg_path.unlink()

    if shutil.which("hdiutil"):
        print(f"💿 Creating distribution disk image: {dmg_path.name}...")
        subprocess.run(
            ["hdiutil", "create", "-volname", "BookHunt", "-srcfolder", str(staging_dir), "-ov", "-format", "UDZO", str(dmg_path)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        shutil.rmtree(staging_dir)

    # 9. Create App Store Installer Package (.pkg)
    pkg_path = dist_dir / "BookHunt-1.0.0.pkg"
    if pkg_path.exists():
        pkg_path.unlink()

    if shutil.which("productbuild"):
        print(f"📦 Generating App Store package: {pkg_path.name}...")
        subprocess.run(
            ["productbuild", "--component", str(app_dir), "/Applications", str(pkg_path)],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    # Clean intermediate build directories
    if pyinstaller_dist.exists():
        shutil.rmtree(pyinstaller_dist)
    if pyinstaller_work.exists():
        shutil.rmtree(pyinstaller_work)

    print("")
    print("==========================================================")
    print("  🎉 BookHunt Standalone & App Store Build Complete!")
    print("==========================================================")
    print(f"  • Standalone App Bundle: {app_dir}")
    if dmg_path.exists():
        dmg_size_mb = dmg_path.stat().st_size / (1024 * 1024)
        print(f"  • Distributable DMG:     {dmg_path} ({dmg_size_mb:.2f} MB)")
    if pkg_path.exists():
        pkg_size_mb = pkg_path.stat().st_size / (1024 * 1024)
        print(f"  • App Store PKG:         {pkg_path} ({pkg_size_mb:.2f} MB)")
    print(f"  • Entitlements:          {entitlements_path}")
    print("==========================================================")


if __name__ == "__main__":
    build_app_bundle()
