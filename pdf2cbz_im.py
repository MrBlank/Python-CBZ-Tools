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
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Optional, Callable
from functools import wraps
import resource

def handle_keyboard_interrupt(message: str = "Conversion cancelled!"):
    """Decorator to handle keyboard interrupts with a custom message."""
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except KeyboardInterrupt:
                # Clear the current line to avoid progress bar artifacts
                print("\r", end="")
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
        subprocess.run([str(VENV_PYTHON), "-c", "import tqdm"], check=True, stdout=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        print("📥 Installing tqdm into virtualenv...")
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "tqdm"], check=True)

def check_dependencies():
    if not shutil.which("magick"):
        print("❌ ImageMagick not found. Please install.")
        print("👉 On macOS: brew install imagemagick")
        sys.exit(1)
    if not shutil.which("gs"):
        print("❌ Ghostscript (gs) not found. Please install.")
        print("👉 On macOS: brew install ghostscript")
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

def get_pdf_page_count(pdf_path):
    # Use ImageMagick to get page count
    result = subprocess.run(
        ["magick", "identify", str(pdf_path)],
        capture_output=True,
        text=True
    )
    # Count the number of lines in the output (each line is one page)
    return len(result.stdout.strip().split('\n'))

def convert_single_page(job: ConversionJob):
    output_file = Path(job.output_dir) / f"page_{str(job.page_num).zfill(job.padding_width)}.jpg"
    temp_pdf = None
    
    # Skip if already exists
    if output_file.exists():
        return "EXISTS"

    # Retry loop
    for attempt in range(job.max_retries):
        try:
            # Convert PDF to JPEG using ImageMagick
            subprocess.run(
                [
                    "magick",
                    "-density", str(job.dpi),
                    "-quality", str(job.quality),
                    "-colorspace", "RGB",
                    f"{job.pdf_path}[{job.page_num - 1}]",  # 0-based page index
                    str(output_file)
                ],
                check=True,
                capture_output=True,
                text=True
            )

            if output_file.exists():
                return output_file
            else:
                return None

        except KeyboardInterrupt:
            if output_file.exists():
                output_file.unlink()
            return "CANCELLED"

        except subprocess.CalledProcessError as e:

            if output_file.exists():
                output_file.unlink()
            if attempt < job.max_retries - 1:
                time.sleep(job.retry_delay)
                gc.collect()
                continue
            return None

        except Exception as e:
            if output_file.exists():
                output_file.unlink()
            if temp_pdf:
                try:
                    Path(temp_pdf.name).unlink()
                except FileNotFoundError:
                    pass
            if attempt < job.max_retries - 1:
                time.sleep(job.retry_delay)
                gc.collect()
                continue
            return None

    return None

@handle_keyboard_interrupt()
def convert_pdf_to_images(pdf_path, output_dir, dpi=DEFAULT_DPI, quality=DEFAULT_QUALITY):
    from tqdm import tqdm
    print("🖼️  Processing pages with ImageMagick...")

    # Use spinner while reading PDF
    stop_event = threading.Event()
    spin_thread = threading.Thread(target=spinner, args=("Reading PDF file", stop_event))
    spin_thread.start()

    try:
        total_pages = get_pdf_page_count(pdf_path)
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
            completed = 0
            with tqdm(total=total_pages, desc="Converting", unit="page", leave=False) as pbar:
                try:
                    for future in as_completed(futures):
                        try:
                            result = future.result(timeout=0.1)
                            if result == "CANCELLED":
                                print("\n🛑 Conversion cancelled!")
                                # Cancel all pending futures
                                for f in futures:
                                    f.cancel()
                                executor.shutdown(wait=False, cancel_futures=True)
                                sys.exit(1)
                            if result is None:
                                print(f"\n❌ Failed to convert a page after multiple retries")
                                # Cancel all pending futures
                                for f in futures:
                                    f.cancel()
                                executor.shutdown(wait=False, cancel_futures=True)
                                sys.exit(1)
                            successful_pages += 1
                            completed += 1
                            pbar.update(1)
                        except TimeoutError:
                            continue
                except KeyboardInterrupt:
                    print("\n🛑 Conversion cancelled!")
                    # Cancel all pending futures
                    for f in futures:
                        f.cancel()
                    executor.shutdown(wait=False, cancel_futures=True)
                    sys.exit(1)
    except Exception as e:
        sys.exit(1)
    finally:
        pass
    
    if successful_pages != total_pages:
        print(f"\n❌ Only converted {successful_pages}/{total_pages} pages successfully")
        sys.exit(1)
    
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

@handle_keyboard_interrupt("Batch conversion cancelled by user.")
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
📋 PDF to CBZ Converter (ImageMagick + Virtualenv)

Usage:
  python pdf_to_cbz_magick.py mycomic.pdf
    → Converts a single PDF to CBZ

  python pdf_to_cbz_magick.py .
    → Converts all PDFs in the current folder

Options:
  --dpi [number]      Set image resolution (default: {DEFAULT_DPI}, max: {MAX_DPI})
  --quality [1–100]   Set JPEG quality (default: {DEFAULT_QUALITY})

Requirements:
  - ImageMagick (install with: brew install imagemagick)
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
