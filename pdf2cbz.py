#!/usr/bin/env python3
import os
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import threading
import time
from typing import Optional
import subprocess
import shutil
from functools import wraps

DEFAULT_DPI = 300
DEFAULT_QUALITY = 85
MAX_DPI = 900

VENV_DIR = Path("venv")
VENV_PYTHON = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")

# --- Virtualenv helpers ---
def in_virtualenv():
    return sys.prefix == str(VENV_DIR.resolve())

def setup_virtualenv():
    if not VENV_DIR.exists():
        print("📦 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    try:
        subprocess.run([str(VENV_PYTHON), "-c", "import fitz, tqdm, PIL"], check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("📥 Installing dependencies (pymupdf, tqdm, Pillow)...")
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "pymupdf", "tqdm", "Pillow"], check=True)


def save_page_as_jpeg_worker(args):
    pdf_path, page_num, output_file, dpi, quality = args
    import fitz  # PyMuPDF
    from PIL import Image
    import io
    doc = fitz.open(str(pdf_path))
    page = doc.load_page(page_num - 1)  # 0-based
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    img = Image.open(io.BytesIO(png_bytes))
    img = img.convert("RGB")
    img.save(output_file, "JPEG", quality=quality, optimize=True, progressive=True)
    return output_file


def convert_pdf_to_images(pdf_path, output_dir, dpi=DEFAULT_DPI, quality=DEFAULT_QUALITY):
    import fitz  # PyMuPDF
    from tqdm import tqdm
    from concurrent.futures import ProcessPoolExecutor, as_completed
    doc = fitz.open(str(pdf_path))
    num_pages = len(doc)
    padding_width = len(str(num_pages))
    jobs = []
    for i in range(1, num_pages + 1):
        output_file = output_dir / f"page_{str(i).zfill(padding_width)}.jpg"
        jobs.append((pdf_path, i, str(output_file), dpi, quality))
    image_paths = [None] * num_pages
    label = " page" if num_pages == 1 else " pages"
    unit_label = label
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(save_page_as_jpeg_worker, job): idx for idx, job in enumerate(jobs)}
        for f in tqdm(
            as_completed(futures),
            total=num_pages,
            desc=f"🖼️  Rendering {pdf_path.name}",
            unit=unit_label
        ):
            idx = futures[f]
            try:
                image_paths[idx] = f.result()
            except Exception as e:
                print(f"❌ Error rendering page {idx+1}: {e}")
    return image_paths, padding_width


def convert_pdf_to_cbz(pdf_path, dpi=DEFAULT_DPI, quality=DEFAULT_QUALITY):
    start_time = time.time()
    cbz_path = pdf_path.with_suffix(".cbz")
    print(f"🔁 Converting: {pdf_path.name} → {cbz_path.name} at {dpi} DPI, quality {quality}")

    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        image_files, padding_width = convert_pdf_to_images(pdf_path, temp_dir_path, dpi, quality)
        num_pages = len(image_files)
        label = "page" if num_pages == 1 else "pages"

        if not image_files:
            print("❌ No images were generated. Conversion failed.")
            return

        # Spinner for CBZ creation
        stop_event = threading.Event()
        spin_thread = threading.Thread(target=spinner, args=("Creating CBZ archive", stop_event))
        spin_thread.start()
        try:
            with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as cbz:
                for page_num, img in enumerate(image_files, start=1):
                    new_name = f"{page_num:0{padding_width}d}.jpg"
                    cbz.write(img, arcname=new_name)
        finally:
            stop_event.set()
            spin_thread.join()

    end_time = time.time()
    duration = end_time - start_time
    minutes = int(duration // 60)
    seconds = int(duration % 60)
    print(f"✅ Created: {cbz_path.name} ({num_pages} {label} in {minutes}m {seconds}s)")


def spinner(message, stop_event):
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while not stop_event.is_set():
        print(f"\r{message} {frames[i % len(frames)]}", end="", flush=True)
        time.sleep(0.1)
        i += 1
    print("\r" + " " * (len(message) + 4) + "\r", end="")


def process_path(target_path, dpi=DEFAULT_DPI, quality=DEFAULT_QUALITY):
    if target_path.is_file() and target_path.suffix.lower() == ".pdf":
        convert_pdf_to_cbz(target_path, dpi, quality)
    elif target_path.is_dir():
        pdfs = list(target_path.glob("*.pdf"))
        if not pdfs:
            print("📂 No PDF files found in folder.")
            return
        print(f"🔁 Found {len(pdfs)} PDFs. Starting batch conversion...")
        for i, pdf in enumerate(sorted(pdfs), 1):
            print(f"\n[{i}/{len(pdfs)}]")
            convert_pdf_to_cbz(pdf, dpi, quality)
    else:
        print("❌ Please provide a valid PDF file or folder.")


def print_help():
    print(f"""
📋 PDF to CBZ Converter (MuPDF)

Usage:
  python pdf2cbz.py mycomic.pdf
    → Converts a single PDF to CBZ

  python pdf2cbz.py .
    → Converts all PDFs in the current folder

Options:
  --dpi [number]      Set image resolution (default: {DEFAULT_DPI}, max: {MAX_DPI})
  --quality [1–100]   Set JPEG quality (default: {DEFAULT_QUALITY})

Requirements:
  - Python 3 (recommended 3.8+)
  - MuPDF (PyMuPDF), Pillow, tqdm (auto-installed if not present)
""")


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print_help()
        sys.exit(0)

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("path", type=str, help="PDF file or folder")
    parser.add_argument("--dpi", type=int, default=DEFAULT_DPI, help=f"DPI resolution (max: {MAX_DPI})")
    parser.add_argument("--quality", type=int, default=DEFAULT_QUALITY, help=f"JPEG quality (1–100, default: {DEFAULT_QUALITY})")
    args = parser.parse_args()

    if args.dpi > MAX_DPI:
        print(f"❌ Maximum allowed DPI is {MAX_DPI}.")
        sys.exit(1)
    if args.quality < 1 or args.quality > 100:
        print("❌ JPEG quality must be between 1 and 100.")
        sys.exit(1)

    target = Path(args.path).expanduser().resolve()

    if not target.exists():
        print(f"❌ Path does not exist: {target}")
        sys.exit(1)

    # Virtualenv logic
    if not in_virtualenv():
        setup_virtualenv()
        print(f"🔐 Running inside virtual environment: {VENV_DIR.resolve()}")
        try:
            subprocess.run([str(VENV_PYTHON), str(Path(__file__).resolve())] + sys.argv[1:])
            sys.exit(0)
        except KeyboardInterrupt:
            sys.exit(1)

    import fitz  # PyMuPDF
    from tqdm import tqdm

    process_path(target, dpi=args.dpi, quality=args.quality)

if __name__ == "__main__":
    main()
