#!/usr/bin/env python
import os
import sys
import subprocess
import zipfile
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
import argparse
import threading
import time
import resource
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, Callable
from functools import wraps

def handle_keyboard_interrupt(message: str = "Conversion cancelled!"):
    """Decorator to handle keyboard interrupts with a custom message."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                print(f"\n🛑 {message}")
                sys.exit(1)
        return wrapper
    return decorator

# Increase file descriptor limit
soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
try:
    resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
except ValueError:
    # If we can't set to hard limit, try a reasonable number
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (4096, hard))
    except ValueError:
        pass  # Use whatever we can get

DEFAULT_DPI = 300
DEFAULT_QUALITY = 85
MAX_DPI = 900

VENV_DIR = Path("venv")
VENV_PYTHON = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")

def in_virtualenv():
    return sys.prefix == str(VENV_DIR.resolve())

def setup_virtualenv():
    if not VENV_DIR.exists():
        print("📦 Creating virtual environment...")
        subprocess.run(["python", "-m", "venv", str(VENV_DIR)], check=True)

    try:
        subprocess.run([str(VENV_PYTHON), "-c", "import pdf2image, tqdm, PyPDF2"], check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("📥 Installing dependencies (pdf2image, tqdm, PyPDF2)...")
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "pdf2image", "tqdm", "PyPDF2"], check=True)

def check_dependencies():
    if not shutil.which("pdfinfo"):
        print("❌ Poppler not found. Please install.")
        print("👉 On macOS: brew install poppler")
        sys.exit(1)

def spinner(message, stop_event):
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while not stop_event.is_set():
        print(f"\r{message} {frames[i % len(frames)]}", end="", flush=True)
        time.sleep(0.1)
        i += 1
    print("\r" + " " * (len(message) + 4) + "\r", end="")

@dataclass
class ConversionJob:
    page_num: int
    pdf_path: str
    output_dir: str
    dpi: int
    quality: int
    padding_width: int
    max_retries: int = 3
    retry_delay: float = 2.0

def convert_single_page(job: ConversionJob) -> Optional[str]:
    from pdf2image import convert_from_path
    import gc
    import time

    output_file = Path(job.output_dir) / f"page_{str(job.page_num).zfill(job.padding_width)}.jpg"
    
    # Skip if already exists
    if output_file.exists():
        return "EXISTS"

    # Retry loop
    for attempt in range(job.max_retries):
        try:
            # Convert single page using pdf2image
            images = convert_from_path(
                str(job.pdf_path),
                dpi=job.dpi,
                first_page=job.page_num,
                last_page=job.page_num,
                fmt="jpeg",
                output_folder=str(job.output_dir),
                output_file=f"page_{str(job.page_num).zfill(job.padding_width)}",
                thread_count=1,
                jpegopt={"quality": job.quality, "progressive": True, "optimize": True}
            )

            if len(images) > 0:
                return output_file
            else:
                if output_file.exists():
                    output_file.unlink()
                return None

        except KeyboardInterrupt:
            if output_file.exists():
                output_file.unlink()
            return "CANCELLED"

        except Exception as e:
            if output_file.exists():
                output_file.unlink()
            if attempt < job.max_retries - 1:
                time.sleep(job.retry_delay)
                gc.collect()
                continue
            return None

    return None

@handle_keyboard_interrupt()
def convert_pdf_to_images(pdf_path, output_dir, dpi=DEFAULT_DPI, quality=DEFAULT_QUALITY):
    from tqdm import tqdm
    from tqdm.utils import _term_move_up
    from PyPDF2 import PdfReader

    print("🖼️  Processing pages with pdf2image...")

    # Use spinner while reading PDF
    stop_event = threading.Event()
    spin_thread = threading.Thread(target=spinner, args=("Reading PDF file", stop_event))
    spin_thread.start()

    try:
        # Get total page count
        with open(str(pdf_path), 'rb') as pdf_file:
            pdf = PdfReader(pdf_file)
            total_pages = len(pdf.pages)
    finally:
        stop_event.set()
        spin_thread.join()

    if total_pages == 0:
        print("❌ Invalid or empty PDF file")
        sys.exit(1)

    # Calculate padding width for consistent filename lengths
    padding_width = len(str(total_pages))

    # Set up multiprocessing
    max_workers = min(multiprocessing.cpu_count(), total_pages)
    successful_pages = 0

    print(f"📄 Total pages: {total_pages}")

    pbar = tqdm(total=total_pages, desc="Converting", unit="page")
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Create conversion jobs
            jobs = [
                ConversionJob(
                    page_num=i,
                    pdf_path=str(pdf_path),
                    output_dir=str(output_dir),
                    dpi=dpi,
                    quality=quality,
                    padding_width=padding_width
                )
                for i in range(1, total_pages + 1)
            ]

            # Process pages with progress bar
            futures = [executor.submit(convert_single_page, job) for job in jobs]
            try:
                for future in as_completed(futures):
                    try:
                        result = future.result(timeout=0.1)
                        if result == "CANCELLED":
                            pbar.disable = True
                            print("\n🛑 Conversion cancelled by user.")
                            # Cancel all pending futures
                            for f in futures:
                                f.cancel()
                            executor.shutdown(wait=False, cancel_futures=True)
                            sys.exit(1)
                        if result is None:
                            pbar.disable = True
                            print(f"\n❌ Failed to convert a page after multiple retries")
                            # Cancel all pending futures
                            for f in futures:
                                f.cancel()
                            executor.shutdown(wait=False, cancel_futures=True)
                            sys.exit(1)
                        successful_pages += 1
                        pbar.update(1)
                    except TimeoutError:
                        continue
            except KeyboardInterrupt:
                pbar.disable = True
                print("\n🛑 Conversion cancelled!")
                # Cancel all pending futures
                for f in futures:
                    f.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                sys.exit(1)
    finally:
        if not pbar.disable:
            pbar.close()
    
    if successful_pages != total_pages:
        print(f"\n❌ Only converted {successful_pages}/{total_pages} pages successfully")
        sys.exit(1)
    
    # Clear the progress bar
    print(_term_move_up(), end='\r')
    print(' ' * (pbar.ncols if hasattr(pbar, 'ncols') else 80), end='\r')
    
    return padding_width

@handle_keyboard_interrupt()
def convert_pdf_to_cbz(pdf_path, dpi=DEFAULT_DPI, quality=DEFAULT_QUALITY):
    start_time = time.time()
    cbz_path = pdf_path.with_suffix(".cbz")
    print(f"🔁 Converting: {pdf_path.name} → {cbz_path.name} at {dpi} DPI, quality {quality}")

    with TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        padding_width = convert_pdf_to_images(pdf_path, temp_dir_path, dpi, quality)

        # Sort files by creation time to maintain page order
        image_files = sorted(temp_dir_path.glob("*.jpg"), key=lambda x: x.name)
        if not image_files:
            print("❌ No images were generated. Conversion failed.")
            return

        # Use spinner during CBZ creation
        stop_event = threading.Event()
        spin_thread = threading.Thread(target=spinner, args=("Creating CBZ archive", stop_event))
        spin_thread.start()

        try:
            with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as cbz:
                # Use enumerate to get sequential page numbers
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
    print(f"✅ Created: {cbz_path.name} ({minutes}m {seconds}s)")

@handle_keyboard_interrupt()
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
📋 PDF to CBZ Converter (pdf2image + Virtualenv)

Usage:
  python pdf_to_cbz_pdf2image.py mycomic.pdf
    → Converts a single PDF to CBZ

  python pdf_to_cbz_pdf2image.py .
    → Converts all PDFs in the current folder

Options:
  --dpi [number]      Set image resolution (default: {DEFAULT_DPI}, max: {MAX_DPI})
  --quality [1–100]   Set JPEG quality (default: {DEFAULT_QUALITY})

Requirements:
  - Poppler (install with: brew install poppler)
""")

@handle_keyboard_interrupt()
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

    check_dependencies()

    if not in_virtualenv():
        setup_virtualenv()
        print(f"🔐 Running inside virtual environment: {VENV_DIR.resolve()}")
        try:
            subprocess.run([str(VENV_PYTHON), str(Path(__file__).resolve())] + sys.argv[1:])
            sys.exit(0)
        except KeyboardInterrupt:
            sys.exit(1)

    process_path(target, dpi=args.dpi, quality=args.quality)

if __name__ == "__main__":
    main()