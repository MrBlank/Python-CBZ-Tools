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

def process_cbr(cbr_path: Path, output_dir: Path, show_progress=True, move_processed=False, processed_folder="cbz_processed", move_cbr=False, cbr_folder="cbr_processed"):
    import math
    import shutil
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
                # Move to processed folder if requested
                if move_processed:
                    processed_dir = output_dir / processed_folder
                    processed_dir.mkdir(exist_ok=True)
                    new_path = processed_dir / output_cbz.name
                    shutil.move(str(output_cbz), str(new_path))
                    output_cbz = new_path
                # Move CBR if requested
                if move_cbr:
                    cbr_dir = cbr_path.parent / cbr_folder
                    cbr_dir.mkdir(exist_ok=True)
                    new_cbr_path = cbr_dir / cbr_path.name
                    shutil.move(str(cbr_path), str(new_cbr_path))
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

def worker_process_cbr(cbr_path_str, output_dir_str, move_processed=False, processed_folder="cbz_processed", move_cbr=False, cbr_folder="cbr_processed"):
    from pathlib import Path
    cbr_path = Path(cbr_path_str)
    output_dir = Path(output_dir_str)
    print(f"🔁 Processing {cbr_path.name}")
    process_cbr(cbr_path, output_dir, show_progress=False, move_processed=move_processed, processed_folder=processed_folder, move_cbr=move_cbr, cbr_folder=cbr_folder)

from multiprocessing import Manager

def worker_process_cbr_capture(cbr_path_str, output_dir_str, result_queue, move_processed=False, processed_folder="cbz_processed", move_cbr=False, cbr_folder="cbr_processed"):
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
        process_cbr(cbr_path, output_dir, show_progress=False, move_processed=move_processed, processed_folder=processed_folder, move_cbr=move_cbr, cbr_folder=cbr_folder)
    finally:
        sys.stdout = sys_stdout
    result = buf.getvalue()
    if result.strip():
        result_queue.put((str(cbr_path.name), result.strip()))

def batch_convert_cbrs(cbr_dir: Path, output_dir: Path, max_workers=None, move_processed=False, processed_folder="cbz_processed", move_cbr=False, cbr_folder="cbr_processed"):
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
            futures = {executor.submit(worker_process_cbr_capture, str(cbr_path), str(output_dir), result_queue, move_processed, processed_folder, move_cbr, cbr_folder): cbr_path for cbr_path in batch_iter}
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
    parser.add_argument("-m", "--move-processed", nargs="?", const="cbz_processed", default=None, metavar="FOLDER", help="Move processed CBZ files into the specified folder (default: cbz_processed) after conversion")
    parser.add_argument("-c", "--move-cbr", nargs="?", const="cbr_processed", default=None, metavar="FOLDER", help="Move original CBR files into the specified folder (default: cbr_processed) after conversion")
    args = parser.parse_args()

    input_path = Path(args.input)
    move_processed = args.move_processed is not None
    processed_folder = args.move_processed if args.move_processed else "cbz_processed"
    move_cbr = args.move_cbr is not None
    cbr_folder = args.move_cbr if args.move_cbr else "cbr_processed"
    if input_path.is_file() and input_path.suffix.lower() == ".cbr":
        output_path = input_path.parent
        print(f"🔁 Processing {input_path.name}")
        process_cbr(input_path, output_path, show_progress=True, move_processed=move_processed, processed_folder=processed_folder, move_cbr=move_cbr, cbr_folder=cbr_folder)
    elif input_path.is_dir():
        output_path = input_path
        batch_convert_cbrs(input_path, output_path, move_processed=move_processed, processed_folder=processed_folder, move_cbr=move_cbr, cbr_folder=cbr_folder)
    else:
        print("❌ ERROR: Input must be a .cbr file or a directory containing .cbr files.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Conversion Cancelled!")
