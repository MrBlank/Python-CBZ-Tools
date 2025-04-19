# CBZ Conversion Tools

Python scripts for converting EPUB or PDF files to CBZ (Comic Book ZIP) format.

---

## EPUB 2 CBZ Script

### Features
- Converts EPUB files (single or batch) to CBZ (Comic Book ZIP) format
- Ports EPUB meta to the CBZ's ComicInfo.xml 
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
- `--ltr`: Set reading direction to LeftToRight (Western style, default)
- `--rtl`: Set reading direction to RightToLeft (manga style)
- `--vertical`: Set reading direction to Vertical
- `--help`: Show help message

If multiple direction flags (`--ltr`, `--rtl`, `--vertical`) are used, the last one specified takes precedence. By default, the reading direction is `LeftToRight` unless another is set.

#### ComicInfo.xml Metadata
- The script generates a `ComicInfo.xml` file inside each CBZ, containing metadata such as title, series, author, publisher, language, summary, date, and reading direction for compatibility with most comic readers.

---

## PDF 2 CBZ Scripts

### 1. `pdf2cbz_im.py` (ImageMagick Version)
Uses ImageMagick for PDF to image conversion. Features:
- Advanced image manipulation capabilities
- Better suited for complex PDFs
- Requires ImageMagick installation

### 2. `pdf2cbz_pop.py` (pdf2image Version)
Uses pdf2image (poppler-based) for conversion. Features:
- Generally faster conversion
- Lighter on system resources
- Requires Poppler installation

### Features
Both scripts offer:
- Converts PDF files (single or batch) to CBZ (Comic Book ZIP) format
- Configurable DPI (default: 300, max: 900)
- Adjustable JPEG quality (default: 85, max: 100)
- Automatic virtual environment setup
- Progress indicators with spinners
- Multi-core support for fast processing of files

### Requirements
Both scripts automatically set up their own virtual environments and install required Python packages. However, they need certain system-level dependencies to be installed first:

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
python pdf2cbz_im.py mycomic.pdf
python pdf2cbz_pop.py mycomic.pdf

# Convert all PDFs in current directory
python pdf2cbz_im.py .
python pdf2cbz_pop.py .

# Set custom DPI and quality
python pdf2cbz_im.py mycomic.pdf --dpi 600 --quality 90
python pdf2cbz_pop.py mycomic.pdf --dpi 600 --quality 90
```

### Options

- `--dpi [number]`: Set image resolution (default: 300, max: 900)
- `--quality [1-100]`: Set JPEG quality (default: 85)
- `--help`: Show help message

---

## Notes

For optimizing CBZ files for e-readers, [check out KCC][1].

## Disclaimer

These scripts are provided "as is" without warranty of any kind. Use at your own risk. The authors are not responsible for any damage or data loss that may occur through the use of this plugin.

This tool is intended for converting legally obtained files that you own. Please respect copyright laws and only convert materials you have the right to access.

[1]:	https://github.com/ciromattia/kcc