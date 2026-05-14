#!/usr/bin/env python3
"""
Extract text from a PDF or EPUB file for book-to-skill processing.

PDF extraction tries methods in order:
  1. pdftotext (poppler-utils) — best quality
  2. PyPDF2 — common Python library
  3. pdfminer.six — thorough fallback

EPUB extraction tries methods in order:
  1. ebooklib + BeautifulSoup4 — best quality
  2. zipfile + html.parser — stdlib fallback (no extra deps)

Outputs:
  <tempdir>/book_skill_work/full_text.txt  — full extracted text
  <tempdir>/book_skill_work/metadata.json  — stats and metadata

Set BOOK_SKILL_WORKDIR to override the output directory.
"""

import html
import html.parser
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

OUTPUT_DIR = Path(
    os.environ.get(
        "BOOK_SKILL_WORKDIR",
        str(Path(tempfile.gettempdir()) / "book_skill_work"),
    )
)
OUTPUT_TEXT = OUTPUT_DIR / "full_text.txt"
OUTPUT_META = OUTPUT_DIR / "metadata.json"

WORDS_PER_TOKEN = 0.75  # approximate


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) / WORDS_PER_TOKEN)


def extract_with_pdftotext(pdf_path: str) -> str | None:
    if not shutil.which("pdftotext"):
        return None
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except Exception:
        pass
    return None


def extract_with_pypdf2(pdf_path: str) -> str | None:
    try:
        import PyPDF2
        text_parts = []
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    text_parts.append(page.extract_text() or "")
                except Exception:
                    text_parts.append("")
        return "\n".join(text_parts)
    except ImportError:
        return None
    except Exception:
        return None


def extract_with_pdfminer(pdf_path: str) -> str | None:
    try:
        from pdfminer.high_level import extract_text
        return extract_text(pdf_path)
    except ImportError:
        return None
    except Exception:
        return None


def extract_with_ebooklib(epub_path: str) -> str | None:
    try:
        import ebooklib
        from ebooklib import epub
        from bs4 import BeautifulSoup

        book = epub.read_epub(epub_path)
        parts = []
        for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
            soup = BeautifulSoup(item.get_content(), "html.parser")
            parts.append(soup.get_text(separator="\n"))
        return "\n\n".join(parts)
    except ImportError:
        return None
    except Exception:
        return None


class _HTMLTextExtractor(html.parser.HTMLParser):
    """Minimal HTML → plain text converter using stdlib only."""

    SKIP_TAGS = {"script", "style", "head"}

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0
        self._current_skip: str | None = None

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip_depth += 1
        if tag in ("p", "br", "h1", "h2", "h3", "h4", "h5", "h6", "li", "div"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if not self._skip_depth:
            self._parts.append(data)

    def get_text(self) -> str:
        return html.unescape("".join(self._parts))


def extract_with_zipfile(epub_path: str) -> str | None:
    """stdlib-only EPUB extractor: unzip → parse HTML files."""
    try:
        with zipfile.ZipFile(epub_path) as zf:
            names = zf.namelist()
            # Read OPF spine to get reading order, fall back to sorted xhtml files
            spine_order: list[str] = []
            opf_files = [n for n in names if n.endswith(".opf")]
            if opf_files:
                opf_text = zf.read(opf_files[0]).decode("utf-8", errors="replace")
                spine_order = re.findall(r'href=["\']([^"\']+\.(?:xhtml|html))["\']', opf_text)

            html_files = spine_order or sorted(
                n for n in names if n.endswith((".html", ".xhtml"))
            )
            if not html_files:
                return None

            parts = []
            for name in html_files:
                try:
                    raw = zf.read(name).decode("utf-8", errors="replace")
                    parser = _HTMLTextExtractor()
                    parser.feed(raw)
                    parts.append(parser.get_text())
                except Exception:
                    continue
            return "\n\n".join(parts) if parts else None
    except Exception:
        return None


def extract_epub(epub_path: str) -> tuple[str, str]:
    """Return (text, method) for an EPUB file."""
    print("Trying ebooklib + BeautifulSoup4...", end=" ", flush=True)
    text = extract_with_ebooklib(epub_path)
    if text and text.strip():
        print("OK")
        return text, "ebooklib"

    print("not available")
    print("Trying stdlib zipfile parser...", end=" ", flush=True)
    text = extract_with_zipfile(epub_path)
    if text and text.strip():
        print("OK")
        return text, "zipfile"

    print("FAILED")
    print(
        "\nERROR: Could not extract text from EPUB.\n"
        "Install ebooklib + beautifulsoup4 for best results:\n"
        "  pip3 install ebooklib beautifulsoup4",
        file=sys.stderr,
    )
    sys.exit(1)


def count_epub_chapters(epub_path: str) -> int:
    """Count spine items (approximate chapter count) without dependencies."""
    try:
        with zipfile.ZipFile(epub_path) as zf:
            opf_files = [n for n in zf.namelist() if n.endswith(".opf")]
            if not opf_files:
                return 0
            opf_text = zf.read(opf_files[0]).decode("utf-8", errors="replace")
            return len(re.findall(r'<itemref\b', opf_text))
    except Exception:
        return 0


def count_pages(pdf_path: str) -> int:
    # Try pdfinfo first
    if shutil.which("pdfinfo"):
        try:
            result = subprocess.run(
                ["pdfinfo", pdf_path], capture_output=True, text=True, timeout=15
            )
            for line in result.stdout.splitlines():
                if line.startswith("Pages:"):
                    return int(line.split(":")[1].strip())
        except Exception:
            pass
    # Fallback: count form-feed chars (pdftotext -layout uses \f between pages)
    try:
        import PyPDF2
        with open(pdf_path, "rb") as f:
            return len(PyPDF2.PdfReader(f).pages)
    except Exception:
        return 0


def detect_structure(text: str) -> dict:
    """Detect chapter count and table of contents presence."""
    import re
    lines = text[:50000].splitlines()

    # Look for chapter headings
    chapter_pattern = re.compile(
        r"^\s*(chapter\s+\d+|CHAPTER\s+\d+|ch\.\s*\d+|\d+\.\s+[A-Z])",
        re.IGNORECASE
    )
    chapters_found = [l.strip() for l in lines if chapter_pattern.match(l)]

    # Look for ToC indicators
    toc_keywords = ["table of contents", "contents", "índice", "sumário"]
    has_toc = any(kw in text[:5000].lower() for kw in toc_keywords)

    return {
        "chapters_detected": len(chapters_found),
        "chapter_headings_sample": chapters_found[:10],
        "has_toc": has_toc,
    }


def extract_with_docling(pdf_path: str) -> str | None:
    """Layout-aware extraction using Docling. Best for technical books with tables and code."""
    try:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import PdfFormatOption

        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True

        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
            }
        )
        result = converter.convert(pdf_path)
        return result.document.export_to_markdown()
    except ImportError:
        return None
    except Exception:
        return None


def main():
    if len(sys.argv) < 2:
        print("Usage: extract.py <path-to-pdf-or-epub> [--mode technical|text]", file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]

    # Parse --mode flag
    extraction_mode = "text"
    if "--mode" in sys.argv:
        idx = sys.argv.index("--mode")
        if idx + 1 < len(sys.argv):
            extraction_mode = sys.argv[idx + 1].lower()
    if extraction_mode not in ("technical", "text"):
        extraction_mode = "text"

    if not os.path.exists(input_path):
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    ext = Path(input_path).suffix.lower()
    is_epub = ext == ".epub"
    is_pdf = ext == ".pdf"

    if not is_epub and not is_pdf:
        # Sniff magic bytes as fallback
        with open(input_path, "rb") as f:
            header = f.read(8)
        if header[:4] == b"%PDF":
            is_pdf = True
        elif header[:2] == b"PK":  # ZIP magic → likely EPUB
            is_epub = True
        else:
            print(
                f"ERROR: Unsupported format '{ext}'. Supported: .pdf, .epub",
                file=sys.stderr,
            )
            sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if is_epub:
        print(f"Extracting EPUB: {input_path}")
        text, method = extract_epub(input_path)
        pages = count_epub_chapters(input_path)
        pages_label = "spine_items"
    else:
        print(f"Extracting PDF: {input_path}")
        if extraction_mode == "technical":
            print("Mode: technical — using Docling (layout-aware)...", end=" ", flush=True)
            text = extract_with_docling(input_path)
            if text:
                method = "docling"
                print("OK")
            else:
                print("not available, falling back to pdftotext")
                extraction_mode = "text"

        if extraction_mode == "text":
            print("Mode: text — using pdftotext...")
            print("Trying pdftotext...", end=" ", flush=True)
            text = extract_with_pdftotext(input_path)

            if text:
                method = "pdftotext"
                print("OK")
            else:
                print("not available")
                print("Trying PyPDF2...", end=" ", flush=True)
                text = extract_with_pypdf2(input_path)
                if text:
                    method = "PyPDF2"
                    print("OK")
                else:
                    print("not available")
                    print("Trying pdfminer.six...", end=" ", flush=True)
                    text = extract_with_pdfminer(input_path)
                    if text:
                        method = "pdfminer"
                        print("OK")
                    else:
                        print("FAILED")
                        print(
                            "\nERROR: Could not extract text from PDF.\n"
                            "Install one of: poppler-utils (pdftotext), PyPDF2, or pdfminer.six\n"
                            "  sudo apt install poppler-utils\n"
                            "  pip3 install PyPDF2\n"
                            "  pip3 install pdfminer.six",
                            file=sys.stderr,
                        )
                        sys.exit(1)

        pages = count_pages(input_path)
        pages_label = "pages"

    # Write full text
    OUTPUT_TEXT.write_text(text, encoding="utf-8")

    tokens = estimate_tokens(text)
    structure = detect_structure(text)
    file_size_mb = os.path.getsize(input_path) / (1024 * 1024)

    metadata = {
        "source_file": str(Path(input_path).resolve()),
        "filename": Path(input_path).name,
        "format": "epub" if is_epub else "pdf",
        "extraction_method": method,
        "extraction_mode": extraction_mode,
        "file_size_mb": round(file_size_mb, 2),
        pages_label: pages,
        "chars": len(text),
        "words": len(text.split()),
        "estimated_tokens": tokens,
        "estimated_tokens_human": f"~{tokens // 1000}K",
        "output_text": str(OUTPUT_TEXT),
        **structure,
    }

    OUTPUT_META.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    page_line = f"   {'Spine items' if is_epub else 'Pages'}: {pages}"
    print(f"\n📖 Extraction complete:")
    print(f"   Format  : {'EPUB' if is_epub else 'PDF'}")
    print(f"   Method  : {method}")
    print(page_line)
    print(f"   Words   : {len(text.split()):,}")
    print(f"   Tokens  : ~{tokens // 1000}K")
    print(f"   Chapters: {structure['chapters_detected']} detected")
    print(f"   ToC     : {'yes' if structure['has_toc'] else 'not detected'}")
    print(f"\n   Text → {OUTPUT_TEXT}")
    print(f"   Meta → {OUTPUT_META}")


if __name__ == "__main__":
    main()
