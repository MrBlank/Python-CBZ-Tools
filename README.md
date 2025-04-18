# PDF to CBZ Conversion Tools

Two Python scripts for converting PDF files to CBZ (Comic Book ZIP) format, with different conversion engines for flexibility and performance.

## Scripts

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

## Features
Both scripts offer:
- Configurable DPI (default: 300, max: 900)
- Adjustable JPEG quality (default: 85, max: 100)
- Automatic virtual environment setup
- Progress indicators with spinners
- Batch processing of multiple PDFs in a single folder
- Multi-core support for fast processing of files

## Requirements

Both scripts automatically set up their own virtual environments and install required Python packages. However, they need certain system-level dependencies to be installed first:

### For ImageMagick version (`pdf2cbz_im.py`)
Requires **both ImageMagick and Ghostscript** to be installed on your system:

#### Install ImageMagick and Ghostscript:
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
Requires Poppler to be installed on your system:
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

## Usage

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

## Options
- `--dpi [number]`: Set image resolution (default: 300, max: 900)
- `--quality [1-100]`: Set JPEG quality (default: 85)
- `--help`: Show help message

## Notes

For optimizing CBZ files for e-readers, [check out KCC](https://github.com/ciromattia/kcc).

## Disclaimer

This script is provided "as is" without warranty of any kind. Use at your own risk. The authors are not responsible for any damage or data loss that may occur through the use of this plugin.

This tool is intended for converting legally obtained files that you own. Please respect copyright laws and only convert materials you have the right to access.