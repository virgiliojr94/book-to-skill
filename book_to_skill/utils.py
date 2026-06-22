from __future__ import annotations

import os
import shutil
import zipfile
import hashlib
import json
import datetime
from pathlib import Path

from book_to_skill.exceptions import ExtractionError

from book_to_skill.config import (
    OUTPUT_DIR,          # noqa: F401
    OUTPUT_TEXT,         # noqa: F401
    OUTPUT_META,         # noqa: F401
    WORDS_PER_TOKEN,
    SUPPORTED_EXTENSIONS,
    TEXT_EXTENSIONS,
    HTML_EXTENSIONS,
    CALIBRE_EBOOK_EXTENSIONS,
    supported_formats_message,
)
from book_to_skill.dependencies import (
    prepare_dependencies,
)
from book_to_skill.parsers.text import read_text_file
from book_to_skill.parsers.html import extract_html_file
from book_to_skill.parsers.docx import extract_docx
from book_to_skill.parsers.rtf import extract_rtf
from book_to_skill.parsers.calibre import extract_with_ebook_convert
from book_to_skill.parsers.pdf import (
    extract_with_docling,
    extract_with_pdftotext,
    extract_with_pypdf,
    extract_with_pdfminer,
    count_pages,
)
from book_to_skill.parsers.epub import (
    extract_with_ebooklib,
    extract_with_zipfile,
    count_epub_chapters,
)


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) / WORDS_PER_TOKEN)

from book_to_skill.chapter_detector import (
    detect_structure,
    _cn_numeral_to_int,  # noqa: F401
    _chapter_number,     # noqa: F401
)

USE_CACHE = True
CACHE_DIR = Path(".book_to_skill_cache")


def _compute_file_sha256(file_path: Path) -> str:
    """Read a file in 64KB blocks and compute its SHA-256 hash."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def _get_cached_extraction(file_path: Path, extraction_mode: str) -> dict | None:
    """Retrieve cached extraction data if it matches the current file hash and mode."""
    if not USE_CACHE:
        return None
    try:
        if not file_path.exists():
            return None
        sha256 = _compute_file_sha256(file_path)
        cache_file = CACHE_DIR / f"{sha256}.json"
        if cache_file.exists():
            data = json.loads(cache_file.read_text(encoding="utf-8"))
            if data.get("extraction_mode") == extraction_mode and data.get("sha256") == sha256:
                return data.get("extraction_result")
    except Exception:
        pass  # Graceful degradation on cache read/parse errors
    return None


def _save_to_cache(file_path: Path, extraction_mode: str, data: dict) -> None:
    """Persist extraction result to cache directory."""
    if not USE_CACHE:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        sha256 = _compute_file_sha256(file_path)
        cache_file = CACHE_DIR / f"{sha256}.json"
        
        cache_data = {
            "sha256": sha256,
            "extraction_mode": extraction_mode,
            "cached_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "extraction_result": data,
        }
        cache_file.write_text(json.dumps(cache_data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # Graceful degradation on cache write errors



def _sniff_format_and_extension(input_path: Path) -> tuple[str, str]:
    """Detect extension and format based on path suffix and magic bytes fallback."""
    input_str = str(input_path)
    ext = input_path.suffix.lower()
    document_format = ext.lstrip(".")
    
    if ext not in SUPPORTED_EXTENSIONS:
        with open(input_str, "rb") as f:
            header = f.read(8)
        if header[:4] == b"%PDF":
            ext = ".pdf"
            document_format = "pdf"
        elif header[:2] == b"PK":
            try:
                with zipfile.ZipFile(input_str) as zf:
                    names = set(zf.namelist())
                    if "mimetype" in names and zf.read("mimetype").startswith(b"application/epub"):
                        ext = ".epub"
                        document_format = "epub"
                    elif "word/document.xml" in names:
                        ext = ".docx"
                        document_format = "docx"
                    else:
                        raise ExtractionError(
                            f"Unsupported ZIP-based format '{input_path.name}'. Supported: {supported_formats_message()}"
                        )
            except (zipfile.BadZipFile, KeyError, OSError):
                raise ExtractionError(
                    f"Unsupported ZIP-based format '{input_path.name}'. Supported: {supported_formats_message()}"
                )
        else:
            raise ExtractionError(
                f"Unsupported format '{ext or '<none>'}'. Supported: {supported_formats_message()}"
            )
            
    return ext, document_format


def _extract_epub(input_str: str) -> tuple[str, str, int]:
    """Extract text from EPUB using ebooklib or zipfile fallback."""
    print(f"Extracting EPUB: {input_str}")
    text = extract_with_ebooklib(input_str)
    if text and text.strip():
        method = "ebooklib"
    else:
        print("ebooklib not available")
        print("Trying stdlib zipfile parser...", end=" ", flush=True)
        text = extract_with_zipfile(input_str)
        if text and text.strip():
            print("OK")
            method = "zipfile"
        else:
            print("FAILED")
            raise ExtractionError(
                "Could not extract text from EPUB.\n"
                "Install ebooklib + beautifulsoup4 for best results:\n"
                "  pip3 install ebooklib beautifulsoup4"
            )
    pages = count_epub_chapters(input_str)
    return text, method, pages


def _extract_pdf(input_str: str, extraction_mode: str) -> tuple[str, str, int]:
    """Extract text from PDF using docling, pdftotext, pypdf or pdfminer cascade."""
    print(f"Extracting PDF: {input_str}")
    text = ""
    method = ""
    
    if extraction_mode == "technical":
        print("Mode: technical — using Docling (layout-aware)...", end=" ", flush=True)
        text = extract_with_docling(input_str)
        if text:
            method = "docling"
            print("OK")
        else:
            print("not available, falling back to pdftotext")
            extraction_mode = "text"
            
    if extraction_mode == "text" or not text:
        print("Mode: text — using pdftotext...")
        print("Trying pdftotext...", end=" ", flush=True)
        text = extract_with_pdftotext(input_str)
        
        if text:
            method = "pdftotext"
            print("OK")
        else:
            print("not available")
            print("Trying pypdf...", end=" ", flush=True)
            text = extract_with_pypdf(input_str)
            if text:
                method = "pypdf"
                print("OK")
            else:
                print("not available")
                print("Trying pdfminer.six...", end=" ", flush=True)
                text = extract_with_pdfminer(input_str)
                if text:
                    method = "pdfminer"
                    print("OK")
                else:
                    print("FAILED")
                    raise ExtractionError(
                        "Could not extract text from PDF.\n"
                        "Install one of: poppler-utils (pdftotext), pypdf, or pdfminer.six\n"
                        "  sudo apt install poppler-utils\n"
                        "  pip3 install pypdf\n"
                        "  pip3 install pdfminer.six"
                    )
                    
    pages = count_pages(input_str)
    return text, method, pages


def extract_single_file(input_path: Path, extraction_mode: str, install_mode: str) -> dict:
    """Extract text and metadata from a single file path."""
    input_str = str(input_path)
    
    if not input_path.exists():
        raise ExtractionError(f"File not found: {input_str}")
        
    cached_res = _get_cached_extraction(input_path, extraction_mode)
    if cached_res is not None:
        print(f"Using cached extraction for {input_path.name}")
        return cached_res
        
    ext, document_format = _sniff_format_and_extension(input_path)
    prepare_dependencies(ext, extraction_mode, install_mode)
    
    if ext in CALIBRE_EBOOK_EXTENSIONS and not shutil.which("ebook-convert"):
        raise ExtractionError(
            "MOBI/AZW/AZW3 extraction requires Calibre's ebook-convert command. "
            "Install Calibre and ensure ebook-convert is on PATH, then rerun this command."
        )
        
    text = ""
    method = ""
    pages = 0
    pages_label = "sections"
    
    if ext == ".epub":
        text, method, pages = _extract_epub(input_str)
        pages_label = "spine_items"
    elif ext == ".pdf":
        text, method, pages = _extract_pdf(input_str, extraction_mode)
        pages_label = "pages"
    elif ext in TEXT_EXTENSIONS:
        print(f"Extracting text document: {input_str}")
        text = read_text_file(input_str)
        if text is None or not text.strip():
            raise ExtractionError(f"Could not read text document: {input_path.name}")
        method = "plain-text"
        pages = 0
        pages_label = "sections"
    elif ext in HTML_EXTENSIONS:
        print(f"Extracting HTML: {input_str}")
        text = extract_html_file(input_str)
        if text is None or not text.strip():
            raise ExtractionError(f"Could not extract text from HTML: {input_path.name}")
        method = "html-parser"
        pages = 0
        pages_label = "sections"
    elif ext == ".docx":
        print(f"Extracting DOCX: {input_str}")
        text, method = extract_docx(input_str)
        pages = 0
        pages_label = "sections"
    elif ext == ".rtf":
        print(f"Extracting RTF: {input_str}")
        text, method = extract_rtf(input_str)
        pages = 0
        pages_label = "sections"
    elif ext in CALIBRE_EBOOK_EXTENSIONS:
        print(f"Extracting ebook with Calibre: {input_str}")
        text = extract_with_ebook_convert(input_str)
        if text is None or not text.strip():
            raise ExtractionError(
                f"Could not extract text from {ext}. Install Calibre and ensure ebook-convert is on PATH."
            )
        method = "ebook-convert"
        pages = 0
        pages_label = "sections"
        
    tokens = estimate_tokens(text)
    structure = detect_structure(text)
    file_size_mb = os.path.getsize(input_str) / (1024 * 1024)
    
    result = {
        "source_file": str(input_path.resolve()),
        "filename": input_path.name,
        "format": document_format,
        "extraction_method": method,
        "file_size_mb": round(file_size_mb, 2),
        pages_label: pages,
        "pages_label": pages_label,
        "pages": pages,
        "chars": len(text),
        "words": len(text.split()),
        "estimated_tokens": tokens,
        "text": text,
        **structure,
    }
    
    _save_to_cache(input_path, extraction_mode, result)
    
    return result


def parse_arguments(argv: list[str]) -> tuple[list[str], str, str]:
    import importlib
    cli = importlib.import_module("book_to_skill.cli")
    return cli.parse_arguments(argv)


def resolve_input_files(paths: list[str]) -> list[Path]:
    import importlib
    cli = importlib.import_module("book_to_skill.cli")
    return cli.resolve_input_files(paths)


def main():
    import importlib
    cli = importlib.import_module("book_to_skill.cli")
    cli.main()
