import os
import sys
import subprocess
import time
import threading
from pathlib import Path
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Manager

# --- VENV & DEPENDENCY MANAGEMENT (auto) ---
VENV_DIR = Path("venv")
VENV_PYTHON = VENV_DIR / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
REQUIRED_PACKAGES = ["rarfile"]

def in_virtualenv():
    return sys.prefix == str(VENV_DIR.resolve())

def setup_virtualenv():
    if not VENV_DIR.exists():
        print("📦 Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    try:
        subprocess.run([str(VENV_PYTHON), "-c", "import rarfile"], check=True, stdout=subprocess.DEVNULL)
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
import rarfile

def spinner(message, stop_event, printed_event=None):
    import sys
    frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
    while not stop_event.is_set():
        print(f"\r{message} {frames[i % len(frames)]}", end="", flush=True)
        if printed_event is not None and printed_event.is_set():
            print("", end="", flush=True)  # flush after result print
            printed_event.clear()
        time.sleep(0.1)
        i += 1
    print("\r" + " " * (len(message) + 4) + "\r", end="")

def process_cbr(cbr_path: Path, output_dir: Path, show_progress=True):
    import math
    output_cbz = output_dir / (cbr_path.stem + ".cbz")
    with tempfile.TemporaryDirectory() as tmpdirname:
        tmpdir = Path(tmpdirname)
        try:
            with rarfile.RarFile(cbr_path) as rf:
                rf.extractall(tmpdir)
                # Collect all image and other files, preserving order
                files = sorted([p for p in tmpdir.rglob("*") if p.is_file()])
                if not files:
                    print(f"❌ ERROR: {cbr_path.name} contains no files!")
                    return
                # Spinner for CBZ creation (only if show_progress is True)
                stop_event = threading.Event()
                start_time = time.time()
                if show_progress:
                    spin_thread = threading.Thread(target=spinner, args=(f"📦 Creating {output_cbz.name}", stop_event))
                    spin_thread.start()
                with zipfile.ZipFile(output_cbz, "w", zipfile.ZIP_DEFLATED) as zf:
                    for file in files:
                        arcname = file.relative_to(tmpdir)
                        zf.write(file, arcname)
                elapsed = time.time() - start_time
                if show_progress:
                    stop_event.set()
                    spin_thread.join()
                # Format time as mm:ss if >= 60s, else as x.y s
                if elapsed >= 60:
                    mins = int(elapsed // 60)
                    secs = int(elapsed % 60)
                    duration = f"{mins}m {secs}s"
                else:
                    duration = f"{elapsed:.1f}s"
                print(f"✅ Created {output_cbz.name} ({len(files)} files, {duration})")
        except rarfile.Error as e:
            print(f"❌ ERROR: Failed to extract {cbr_path.name}: {e}")

def worker_process_cbr(cbr_path_str, output_dir_str):
    from pathlib import Path
    cbr_path = Path(cbr_path_str)
    output_dir = Path(output_dir_str)
    print(f"🔁 Processing {cbr_path.name}")
    process_cbr(cbr_path, output_dir, show_progress=False)

from multiprocessing import Manager

def worker_process_cbr_capture(cbr_path_str, output_dir_str, result_queue):
    from pathlib import Path
    import sys
    import time
    cbr_path = Path(cbr_path_str)
    output_dir = Path(output_dir_str)
    # Patch process_cbr to capture output
    import io
    buf = io.StringIO()
    sys_stdout = sys.stdout
    sys.stdout = buf
    try:
        process_cbr(cbr_path, output_dir, show_progress=False)
    finally:
        sys.stdout = sys_stdout
    result = buf.getvalue()
    if result.strip():
        result_queue.put((str(cbr_path.name), result.strip()))

def batch_convert_cbrs(cbr_dir: Path, output_dir: Path, max_workers=None):
    import queue
    import threading
    import sys
    cbr_dir = Path(cbr_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cbr_files = sorted(cbr_dir.glob("*.cbr"))
    total = len(cbr_files)
    if not cbr_files:
        print("❌ No .cbr files found in the directory.")
        return
    batch_iter = cbr_files
    for cbr_path in batch_iter:
        print(f"🔁 Processing {cbr_path.name}")
    # Spinner and live result printing
    stop_event = threading.Event()
    printed_event = threading.Event()
    manager = Manager()
    result_queue = manager.Queue()
    def live_result_printer():
        finished = 0
        while finished < total:
            try:
                name, lines = result_queue.get(timeout=0.1)
            except Exception:
                if stop_event.is_set():
                    break
                continue
            for line in lines.splitlines():
                if line.startswith("✅ Created"):
                    print(f"\r{' ' * 80}\r", end="")  # clear spinner line
                    print(line)
                    printed_event.set()
            finished += 1
    spin_thread = threading.Thread(target=spinner, args=("📦 Batch converting...", stop_event, printed_event))
    printer_thread = threading.Thread(target=live_result_printer)
    spin_thread.start()
    printer_thread.start()
    try:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(worker_process_cbr_capture, str(cbr_path), str(output_dir), result_queue): cbr_path for cbr_path in batch_iter}
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ ERROR processing {futures[future].name}: {e}")
    finally:
        stop_event.set()
        spin_thread.join()
        printer_thread.join()

def main():
    parser = argparse.ArgumentParser(description="📋 Convert CBR or folder of CBRs to CBZ.")
    parser.add_argument("input", type=str, help="Path to a CBR file or folder of CBRs")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output folder for CBZ files (defaults to CBR's folder)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if input_path.is_file() and input_path.suffix.lower() == ".cbr":
        output_path = Path(args.output) if args.output else input_path.parent
        output_path.mkdir(parents=True, exist_ok=True)
        print(f"🔁 Processing {input_path.name}")
        process_cbr(input_path, output_path, show_progress=True)
    elif input_path.is_dir():
        output_path = Path(args.output) if args.output else input_path
        output_path.mkdir(parents=True, exist_ok=True)
        batch_convert_cbrs(input_path, output_path)
    else:
        print("❌ ERROR: Input must be a .cbr file or a directory containing .cbr files.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Conversion Cancelled!")
