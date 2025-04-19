import os
import sys
import subprocess
import shutil
from pathlib import Path

# --- VENV & DEPENDENCY MANAGEMENT (auto) ---
VENV_DIR = Path("venv")
VENV_PYTHON = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
REQUIRED_PACKAGES = ["beautifulsoup4", "lxml"]

def in_virtualenv():
    return sys.prefix == str(VENV_DIR.resolve())

def setup_virtualenv():
    if not VENV_DIR.exists():
        print("📦 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    try:
        subprocess.run([str(VENV_PYTHON), "-c", "import bs4, lxml"], check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print(f"📥 Installing dependencies: {', '.join(REQUIRED_PACKAGES)}...")
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install"] + REQUIRED_PACKAGES, check=True)

def ensure_env():
    if not in_virtualenv():
        setup_virtualenv()
        print(f"🔐 Running inside virtual environment: {VENV_DIR.resolve()}")
        try:
            subprocess.run([str(VENV_PYTHON), str(Path(__file__).resolve())] + sys.argv[1:])
            sys.exit(0)
        except KeyboardInterrupt:
            sys.exit(1)

ensure_env()

import zipfile
import tempfile
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from typing import List, Optional
import argparse

def get_opf_path(container_path: Path) -> Optional[str]:
    try:
        tree = ET.parse(container_path)
        rootfile = tree.find(".//{*}rootfile")
        return rootfile.attrib["full-path"] if rootfile is not None else None
    except Exception:
        return None

def parse_opf(opf_path: Path):
    tree = ET.parse(opf_path)
    root = tree.getroot()

    manifest = {}
    spine = []
    cover_id = None
    cover_href = None

    for item in root.findall(".//{*}item"):
        item_id = item.attrib["id"]
        href = item.attrib["href"]
        manifest[item_id] = href

    for itemref in root.findall(".//{*}spine/{*}itemref"):
        spine.append(itemref.attrib["idref"])

    for meta in root.findall(".//{*}meta"):
        if meta.attrib.get("name") == "cover":
            cover_id = meta.attrib.get("content")
        if meta.attrib.get("property") == "cover-image":
            cover_href = meta.text

    if cover_id and cover_id in manifest:
        cover_href = manifest[cover_id]

    return manifest, spine, cover_href

def resolve_image_paths(spine_files: List[Path], base_dir: Path) -> List[Path]:
    found_images = []
    seen = set()

    for spine_path in spine_files:
        if not spine_path.exists():
            continue
        with open(spine_path, "rb") as f:
            soup = BeautifulSoup(f, features="xml")
            img_tags = soup.find_all("img")
            for img in img_tags:
                src = img.get("src")
                if not src:
                    continue
                img_path = (spine_path.parent / src).resolve()
                if img_path not in seen and img_path.exists():
                    found_images.append(img_path)
                    seen.add(img_path)
    return found_images


def build_cbz(images: List[Path], output_cbz: Path):
    with zipfile.ZipFile(output_cbz, "w") as cbz:
        digits = len(str(len(images)))
        for i, img_path in enumerate(images, 1):
            ext = img_path.suffix
            name = f"{i:0{digits}d}{ext}"
            cbz.write(img_path, arcname=name)

def process_epub(epub_path: Path, output_dir: Path):
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)

        mimetype_path = tmpdir / "mimetype"
        if not mimetype_path.exists() or mimetype_path.read_text().strip() != "application/epub+zip":
            print(f"❌ ERROR: {epub_path.name} is not a valid EPUB (bad mimetype)")
            return

        container_path = tmpdir / "META-INF" / "container.xml"
        if not container_path.exists():
            print(f"❌ ERROR: {epub_path.name} missing META-INF/container.xml")
            return

        opf_rel_path = get_opf_path(container_path)
        if not opf_rel_path:
            print(f"❌ ERROR: {epub_path.name} container.xml doesn't point to a valid OPF")
            return

        opf_path = tmpdir / opf_rel_path
        if not opf_path.exists():
            print(f"❌ ERROR: {epub_path.name} OPF file not found at {opf_rel_path}")
            return

        manifest, spine, cover_href = parse_opf(opf_path)
        spine_files = [opf_path.parent / manifest[item] for item in spine if item in manifest]
        images = resolve_image_paths(spine_files, tmpdir)

        output_cbz = output_dir / (epub_path.stem + ".cbz")
        build_cbz(images, output_cbz)
        print(f"✅ Created {output_cbz.name} ({len(images)} images)")

def batch_convert_epubs(epub_dir: Path, output_dir: Path):
    epub_dir = Path(epub_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    epub_files = sorted(epub_dir.glob("*.epub"))
    total = len(epub_files)
    for idx, epub_path in enumerate(epub_files, 1):
        print(f"🔁 Processing [{idx}/{total}] {epub_path.name}")
        process_epub(epub_path, output_dir)

def main():
    parser = argparse.ArgumentParser(description="📋 Convert EPUB or folder of EPUBs to CBZ.")
    parser.add_argument("input", type=str, help="Path to an EPUB file or folder of EPUBs")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output folder for CBZ files (defaults to EPUB's folder)")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = None

    if input_path.is_file() and input_path.suffix.lower() == ".epub":
        # Default output to EPUB's parent if not specified
        output_path = Path(args.output) if args.output else input_path.parent
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"🔁 Processing {input_path.name}")
        process_epub(input_path, output_path)
    elif input_path.is_dir():
        # Default output to EPUBs' directory if not specified
        output_path = Path(args.output) if args.output else input_path
        output_path.mkdir(parents=True, exist_ok=True)
        batch_convert_epubs(input_path, output_path)
    else:
        print("❌ ERROR: Input must be a .epub file or a directory containing .epub files.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Conversion Cancelled!")
