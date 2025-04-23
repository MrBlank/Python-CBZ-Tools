# CBZ Conversion Tools

I prefer my comics to be in a CBZ format for editing, compatability, and portability. These are my Python scripts for converting EPUB or PDF files to CBZ (Comic Book ZIP) format. 

Once I have the files converted to CBZ and in my library, I use [Kindle Comic Converter (KCC)][1] to optimize and size the CBZ files before trasferring a copy to various e-readers, like BOOX, Kindle, or Kobo devices.

---

## EPUB 2 CBZ Script

### Features
- Converts EPUB files (single or batch) to CBZ (Comic Book ZIP) format
- Ports EPUB metadata to the CBZ's ComicInfo.xml 
- Preserves reading order of images as in the original EPUB
- Automatically sets up and uses a Python virtual environment for dependencies

### Requirements
- Python 3.7+
- The script automatically creates and manages a virtual environment and installs required Python packages (`beautifulsoup4`, `lxml`).
- No additional system-level dependencies required for basic EPUB to CBZ conversion.

### Usage
Convert a single EPUB file:
```bash
python epub2cbz.py /path/to/book.epub
```

Convert all EPUB files in a folder:
```bash
python epub2cbz.py /path/to/folder_with_epubs
```

Specify an output directory (optional):
```bash
python epub2cbz.py /path/to/book.epub -o /path/to/output_folder
```

### Options
- `-o`, `--output [folder]`: Set output folder for CBZ files (defaults to the EPUB's folder)
- `--help`: Show help message  
- `--ltr`: Set reading direction to LeftToRight (Western style, default)
- `--rtl`: Set reading direction to RightToLeft (manga style)
- `--vertical`: Set reading direction to Vertical
  
__Note:__ If the EPUB file specifies a reading direction, that direction will be used and any direction flags (`--ltr`, `--rtl`, `--vertical`) will be ignored. If the EPUB does not specify a reading direction, `LeftToRight` is used by default, unless you provide a direction flag.

#### ComicInfo.xml Metadata
- The script generates a `ComicInfo.xml` file inside each CBZ, containing metadata such as title, series, author, publisher, language, summary, date, and reading direction for compatibility with most comic readers.

---

## PDF 2 CBZ Scripts

### 1. `pdf2cbz.py` (MuPDF/PyMuPDF Version)
Uses MuPDF (PyMuPDF) for high-quality, fast PDF rendering and conversion. Features:
- Very fast, especially for large PDFs (multiprocessing)
- High-quality rendering (excellent text and image fidelity)
- No external system dependencies (auto-installs Python packages: `pymupdf`, `Pillow`, `tqdm`)
- Best choice for speed, quality, and ease of setup if you have Python 3.8+

### 2. `pdf2cbz_pop.py` (pdf2image Version)
Uses pdf2image (Poppler-based) for conversion. Features:
- Generally faster conversion than ImageMagick for most PDFs
- Lighter on system resources
- Requires Poppler installation

### 3. `pdf2cbz_im.py` (ImageMagick Version)
Uses ImageMagick for PDF to image conversion. Features:
- Advanced image manipulation capabilities
- Better suited for complex or problematic PDFs
- Requires ImageMagick (and Ghostscript) installation

**Summary:**
- Use **MuPDF** for the fastest, highest-quality conversion with minimal setup.
- Use **pdf2image/Poppler** if you already have Poppler and want a lightweight solution.
- Use **ImageMagick** if you need advanced image processing or have problematic/complex PDFs.

### Features
All scripts offer:
- Converts PDF files (single or batch) to CBZ (Comic Book ZIP) format
- Configurable DPI (default: 300, max: 900)
- Adjustable JPEG quality (default: 85, max: 100)
- Automatic virtual environment setup
- Progress indicators with spinners
- Multi-core support for fast processing of files

### Requirements
All scripts automatically set up their own virtual environments and install required Python packages. However, some need certain system-level dependencies to be installed first:

### For MuPDF version (`pdf2cbz.py`)
No system-level dependencies required! All necessary Python packages (`pymupdf`, `Pillow`, `tqdm`) are automatically installed in a virtual environment when you run the script. Just make sure you have Python 3.8 or higher.

### For ImageMagick version (`pdf2cbz_im.py`)
Requires **both ImageMagick and Ghostscript** to be installed on your system:

```bash
# macOS
brew install imagemagick ghostscript

# Ubuntu/Debian
sudo apt-get install imagemagick ghostscript

# Fedora
sudo dnf install ImageMagick ghostscript

# Windows
# Download and install both:
# - ImageMagick: https://imagemagick.org/script/download.php
# - Ghostscript: https://ghostscript.com/download/gsdnld.html
```

### For pdf2image version (`pdf2cbz_pop.py`)
Requires Poppler:
```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils

# Fedora
sudo dnf install poppler-utils

# Windows
# Download binary from http://blog.alivate.com.au/poppler-windows/
# Add the bin/ folder to your PATH
```

### Usage

Both scripts use the same command-line interface:

```bash
# Convert a single PDF
python pdf2cbz.py mycomic.pdf
python pdf2cbz_pop.py mycomic.pdf
python pdf2cbz_im.py mycomic.pdf

# Convert all PDFs in current directory
python pdf2cbz.py .
python pdf2cbz_pop.py .
python pdf2cbz_im.py .

# Set custom DPI and quality
python pdf2cbz.py mycomic.pdf --dpi 600 --quality 90
python pdf2cbz_pop.py mycomic.pdf --dpi 600 --quality 90
python pdf2cbz_im.py mycomic.pdf --dpi 600 --quality 90
```

### Options

- `--dpi [number]`: Set image resolution (default: 300, max: 900)
- `--quality [1-100]`: Set JPEG quality (default: 85)
- `--help`: Show help message

---

## Disclaimer

These scripts are provided "as is" without warranty of any kind. Use at your own risk. The authors are not responsible for any damage or data loss that may occur through the use of this plugin.

This tool is intended for converting legally obtained files that you own. Please respect copyright laws and only convert materials you have the right to access.

[1]:	https://github.com/ciromattia/kcc
